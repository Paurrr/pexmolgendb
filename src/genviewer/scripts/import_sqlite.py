#!/usr/bin/env python
"""기존 .sqlite 파일을 PostgreSQL 로 옮긴다.

지금까지는 .sqlite 파일을 주고받는 게 공유 방식이었으므로, 여러 사람의 파일을
한 서버로 모으는 상황을 전제한다.

  # 무엇이 들어갈지만 본다
  uv run python -m genviewer.scripts.import_sqlite --sqlite mine.sqlite \
      --dsn "$GENDB_PG_DSN" --dry-run

  # 여러 사람 파일을 각자 이름으로 구분해서 넣는다 (초기 대량 이관에 권장)
  uv run python -m genviewer.scripts.import_sqlite --sqlite mine.sqlite --dsn "$GENDB_PG_DSN" \
      --on-conflict rename

원본 파일은 읽기 전용으로 열며 절대 수정하지 않는다.
"""

# 서버(RHEL 7)의 파이썬은 3.9 다. 이 도구는 GUI 를 import 하지 않으므로 거기서
# 돌릴 수 있는데, X | None (3.10+) 이 평가되는 자리에 있으면 import 조차 안 된다.
# 이 한 줄이 애노테이션을 문자열로 만들어 평가 자체를 없앤다. 런타임 동작은 같다.
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from genviewer.scripts import survive_console_encoding
from genviewer.service import schema
from genviewer.utils.user import current_user


def open_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def tables_in(src: sqlite3.Connection) -> set[str]:
    return {
        r[0]
        for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def validate(src: sqlite3.Connection) -> list[str]:
    """원본에 필요한 테이블과 컬럼이 다 있는지 본다. 문제를 문자열로 돌려준다.

    자식 테이블이 통째로 없는 것은 문제가 아니다. 탭이 추가된 뒤에 만들어진
    테이블은 그보다 오래된 .sqlite 파일에 있을 수 없다 — 그 탭에 옮길 행이
    없다는 뜻일 뿐이다. process/device 가 없으면 그건 genviewer 파일이 아니다.
    """
    problems: list[str] = []
    have = tables_in(src)
    for table, columns in schema.child_tables().items():
        if table not in have:
            continue
        cols = {r[1] for r in src.execute(f"PRAGMA table_info({table})")}
        missing = set(columns) - cols
        if missing:
            problems.append(f"{table} 에 컬럼 없음: {sorted(missing)}")
    for table in ("process", "device"):
        if table not in have:
            problems.append(f"테이블 없음: {table}")
    return problems


def resolve_name(cur, name: str, policy: str, suffix: str) -> str | None:
    """충돌 정책을 적용해 실제로 쓸 process 이름을 정한다. None 이면 건너뛴다."""
    exists = cur.execute(
        "SELECT 1 FROM process WHERE name = %s", (name,)
    ).fetchone()
    if not exists:
        return name
    if policy == "fail":
        raise SystemExit(
            f"process '{name}' 이(가) 이미 있다. "
            "--on-conflict rename|merge|skip 중에서 고를 것."
        )
    if policy == "skip":
        return None
    if policy == "rename":
        return f"{name}{suffix}"
    return name  # merge


def import_file(
    src_path: Path, dsn: str, policy: str, suffix: str, dry_run: bool
) -> int:
    import psycopg
    from psycopg.rows import dict_row

    src = open_readonly(src_path)

    problems = validate(src)
    if problems:
        for p in problems:
            print(f"  ! {p}")
        raise SystemExit("원본 스키마가 맞지 않는다. 중단.")

    # 원본의 device 이름 중복은 더 이상 문제가 아니다. 예전에는 PostgreSQL 에
    # UNIQUE (process_id, name) 이 있어서 여기서 미리 막고 원본을 고치게 했는데,
    # 그 제약을 없앴으므로 중복은 중복인 채로 옮겨진다.

    # 원본에 없는 자식 테이블은 건너뛴다 (validate 의 주석 참고). 어느 탭이
    # 비어서 넘어가는지는 말해준다 — 조용히 사라지면 이관 누락과 구분되지 않는다.
    present = tables_in(src)
    child = {t: c for t, c in schema.child_tables().items() if t in present}
    for table in schema.child_tables():
        if table not in present:
            print(f"  - {table}: 원본에 없음 (옮길 행 없음)")
    actor = f"import:{src_path.stem}"
    totals: dict[str, int] = {t: 0 for t in ["process", "device", *child]}

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        for prow in src.execute("SELECT id, name FROM process ORDER BY id"):
            with conn.cursor() as cur:
                target = resolve_name(cur, prow["name"], policy, suffix)
                if target is None:
                    print(f"  skip process {prow['name']!r} (이미 있음)")
                    continue

                devices = src.execute(
                    'SELECT id, name, celltype, description, "order" FROM device '
                    "WHERE process_id = ? ORDER BY id",
                    (prow["id"],),
                ).fetchall()

                if dry_run:
                    print(
                        f"  process {prow['name']!r} -> {target!r}: "
                        f"device {len(devices)}개"
                    )
                    continue

                pid = cur.execute(
                    "INSERT INTO process (name) VALUES (%s) "
                    "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
                    "RETURNING id",
                    (target,),
                ).fetchone()["id"]
                totals["process"] += 1

                # 이미 들어가 있는 device 를 이름별로 모아둔다 (--on-conflict merge
                # 로 같은 process 에 다시 들어올 때만 비어 있지 않다).
                #
                # 이름이 유일하지 않으므로 ON CONFLICT 를 쓸 수 없다 — 대상이 될
                # 유일 인덱스가 없어서 42P10 으로 죽는다. 대신 같은 이름끼리 id
                # 순으로 짝짓는다. 원본의 중복 두 개는 기존 중복 두 개에 하나씩
                # 대응하므로, 다시 돌려도 늘어나지 않는다.
                existing: dict[str, list[int]] = {}
                for r in cur.execute(
                    "SELECT id, name FROM device WHERE process_id = %s ORDER BY id",
                    (pid,),
                ).fetchall():
                    existing.setdefault(r["name"], []).append(r["id"])
                seen: dict[str, int] = {}

                for dev in devices:
                    slot = seen.get(dev["name"], 0)
                    seen[dev["name"]] = slot + 1
                    matched = existing.get(dev["name"], [])
                    values = (
                        dev["celltype"],
                        dev["description"] or "",
                        dev["order"] or 0,
                    )
                    if slot < len(matched):
                        new_id = matched[slot]
                        cur.execute(
                            "UPDATE device SET celltype = %s, description = %s, "
                            '"order" = %s WHERE id = %s',
                            (*values, new_id),
                        )
                    else:
                        # id 는 새로 발급받는다. 명시적으로 넣으면 identity 시퀀스가
                        # 전진하지 않아 다음 INSERT 가 중복 키로 실패한다.
                        new_id = cur.execute(
                            "INSERT INTO device "
                            '  (process_id, name, celltype, description, "order", updated_by) '
                            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                            (pid, dev["name"], *values, actor),
                        ).fetchone()["id"]
                    totals["device"] += 1

                    for table, columns in child.items():
                        rows = src.execute(
                            f"SELECT {', '.join(columns)} FROM {table} "
                            "WHERE device_id = ? ORDER BY id",
                            (dev["id"],),
                        ).fetchall()
                        # merge 정책에서 같은 device 를 다시 만나면 자식 행은
                        # 통째로 교체한다 (누적되지 않게).
                        cur.execute(
                            f'DELETE FROM "{table}" WHERE device_id = %s', (new_id,)
                        )
                        if not rows:
                            continue
                        placeholders = ", ".join(["%s"] * (len(columns) + 1))
                        quoted = ", ".join(f'"{c}"' for c in columns)
                        cur.executemany(
                            f'INSERT INTO "{table}" (device_id, {quoted}) '
                            f"VALUES ({placeholders})",
                            [
                                (new_id, *[r[c] if r[c] is not None else "" for c in columns])
                                for r in rows
                            ],
                        )
                        totals[table] += len(rows)
            # process 단위로 커밋한다. 중간에 실패해도 절반만 남지 않는다.
            conn.commit()

    src.close()

    print()
    print("옮긴 행 수:")
    for table, n in totals.items():
        if n:
            print(f"  {table:34} {n}")
    return 0


def main() -> int:
    survive_console_encoding()
    ap = argparse.ArgumentParser(description="sqlite -> PostgreSQL 이관")
    ap.add_argument("--sqlite", required=True, help="원본 .sqlite 파일")
    ap.add_argument("--dsn", default=os.environ.get("GENDB_PG_DSN", ""))
    ap.add_argument(
        "--on-conflict",
        choices=["fail", "rename", "merge", "skip"],
        default="fail",
        help="같은 이름의 process 가 이미 있을 때 (기본: fail)",
    )
    ap.add_argument(
        "--rename-suffix",
        default="",
        help="rename 정책에서 붙일 접미사 (기본: @<사용자>)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dsn:
        ap.error("--dsn 또는 GENDB_PG_DSN 이 필요하다")

    src_path = Path(args.sqlite)
    if not src_path.is_file():
        ap.error(f"파일이 없다: {src_path}")

    suffix = args.rename_suffix or f"@{current_user()}"
    print(f"원본: {src_path}  정책: {args.on_conflict}")
    if args.dry_run:
        print("(dry-run - 아무것도 쓰지 않는다)")
    return import_file(src_path, args.dsn, args.on_conflict, suffix, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
