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


def validate(src: sqlite3.Connection) -> list[str]:
    """원본에 필요한 테이블과 컬럼이 다 있는지 본다. 문제를 문자열로 돌려준다."""
    problems: list[str] = []
    have = {
        r[0]
        for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for table, columns in schema.child_tables().items():
        if table not in have:
            problems.append(f"테이블 없음: {table}")
            continue
        cols = {r[1] for r in src.execute(f"PRAGMA table_info({table})")}
        missing = set(columns) - cols
        if missing:
            problems.append(f"{table} 에 컬럼 없음: {sorted(missing)}")
    for table in ("process", "device"):
        if table not in have:
            problems.append(f"테이블 없음: {table}")
    return problems


def duplicate_devices(src: sqlite3.Connection) -> list[tuple]:
    """PostgreSQL 의 UNIQUE (process_id, name) 를 위반할 행."""
    return [
        tuple(r)
        for r in src.execute(
            "SELECT process_id, name, count(*) FROM device "
            "GROUP BY 1, 2 HAVING count(*) > 1"
        )
    ]


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

    dups = duplicate_devices(src)
    if dups:
        for process_id, name, n in dups:
            print(f"  ! device 중복: process_id={process_id} name={name!r} x{n}")
        raise SystemExit(
            "PostgreSQL 은 (process_id, name) 이 유일해야 한다. 원본을 먼저 정리할 것."
        )

    child = schema.child_tables()
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

                for dev in devices:
                    # id 는 새로 발급받는다. 명시적으로 넣으면 identity 시퀀스가
                    # 전진하지 않아 다음 INSERT 가 중복 키로 실패한다.
                    new_id = cur.execute(
                        "INSERT INTO device "
                        '  (process_id, name, celltype, description, "order", updated_by) '
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (process_id, name) DO UPDATE "
                        "   SET celltype = EXCLUDED.celltype, "
                        "       description = EXCLUDED.description, "
                        '       "order" = EXCLUDED."order" '
                        "RETURNING id",
                        (
                            pid,
                            dev["name"],
                            dev["celltype"],
                            dev["description"] or "",
                            dev["order"] or 0,
                            actor,
                        ),
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
