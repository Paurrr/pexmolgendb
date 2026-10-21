"""변경 이력 - 누가 언제 어떤 데이터를 바꿨는지.

쓰는 쪽(write)과 읽는 쪽(AuditRepository)이 한 파일에 있고, 한 줄 문장을 만드는
자리도 여기다. 명령줄과 창이 같은 글을 써야 하기 때문이다.

Qt 를 import 하지 않는다. cli.py 의 log 서브커맨드가 이 모듈만 쓴다.

**write() 가 Database 가 아니라 호출자의 커서를 받는 것이 이 파일의 요점이다.**
저장과 이력이 같은 트랜잭션이라야 "저장은 됐는데 이력이 없다" 나 그 반대가
생기지 않는다. 저장이 StaleWriteError 로 롤백되면 이력도 함께 사라진다.

무엇을 남길지의 기준은 "사람이 한 일" 이다. 값이 실제로 달라지지 않은 저장은
한 줄도 남기지 않는다 - save_all 은 화면의 device 를 전부 보내므로, 여기서
걸러내지 않으면 누가 Save 를 누를 때마다 수십 줄이 쌓여 아무도 안 보게 된다.
"""

import json
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from psycopg import sql
from psycopg.types.json import Jsonb

from genviewer.config.config import tab_config
from genviewer.service.pool import Database
from genviewer.service.schema import child_tables

# action 값. 문자열을 여기저기 손으로 적지 않는다.
INSERT = "insert"
UPDATE = "update"
DELETE = "delete"
TAB = "tab"
IMPORT = "import"
PROCESS_ADD = "process_add"
PROCESS_DELETE = "process_delete"

# device 행에서 사람이 고칠 수 있는 컬럼. id/version/updated_* 는 뺀다.
DEVICE_COLUMNS = ("name", "celltype", "description", "order")

# 자식 테이블 이름 -> 탭 이름. 사람은 inst_terms 가 아니라 InstTerm 을 안다.
_TAB_LABEL = {info["table"]: name for name, info in tab_config.items()}

_source = ""


def set_source(name: str) -> None:
    """이 프로세스가 남기는 이력의 출처. cli.main() 과 run_gui() 가 부른다."""
    global _source
    _source = name


def source() -> str:
    return _source


@dataclass(frozen=True)
class Entry:
    """이력 한 줄. summary 는 목록용 문장, detail 은 펼쳐 볼 원본이다."""

    action: str
    process_name: str = ""
    device_name: str = ""
    device_id: int | None = None
    table_name: str = ""
    summary: str = ""
    detail: dict = field(default_factory=dict)
    # process 의 버전. 빈 문자열은 "버전 없음" 이다. 위치 인자로 만드는 곳이 깨지지 않게 맨 뒤다.
    process_release: str = ""


# 행마다 VALUES 를 늘리는 문장 하나에 담는 행 수. libpq 는 한 문장의 바인드
# 파라미터를 65,535개까지만 보낸다(넘으면 "number of parameters must be between
# 0 and 65535" 로 저장 전체가 실패한다). 행 하나에 이력은 10개, device UPDATE 는
# 6개라 1,000행이면 많아야 10,000개로 넉넉하다. 나눈 문장은 모두 호출자의 커서로
# 차례로 돈다 - 같은 트랜잭션이라 하나라도 실패하면 전부 롤백된다.
BATCH_ROWS = 1_000


def write(cur, actor: str, entries: list[Entry]) -> None:
    """호출자의 커서로 쓴다. 반드시 저장과 같은 트랜잭션이어야 한다.

    BATCH_ROWS 줄씩 나눠 순서대로 쓴다. 나중 항목의 id 가 크다.
    """
    if not entries:
        return
    row = sql.SQL("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
    for start in range(0, len(entries), BATCH_ROWS):
        batch = entries[start : start + BATCH_ROWS]
        stmt = sql.SQL(
            "INSERT INTO change_log "
            "  (actor, source, action, process_name, device_name, device_id, "
            "   table_name, summary, detail, process_release) "
            "VALUES {rows}"
        ).format(rows=sql.SQL(", ").join([row] * len(batch)))

        params: list = []
        for e in batch:
            params += [
                actor,
                _source,
                e.action,
                e.process_name,
                e.device_name,
                e.device_id,
                e.table_name,
                e.summary,
                Jsonb(e.detail),
                e.process_release,
            ]
        cur.execute(stmt, params)


# 사라질 자식 행을 통째로 보관할 때의 상한. process 하나에 device 가 아주 많으면
# detail 한 줄이 수십 MB 가 된다. 그때는 device 행만 남기고 자식은 포기한다.
CHILD_ROW_CAP = 20_000


def capture_children(
    cur, device_ids: list[int], max_rows: int = 0
) -> tuple[dict, bool]:
    """지워질 device 의 자식 행을 미리 읽어 둔다. 지운 뒤에는 못 읽는다.

    반환: ({device_id: {테이블: [행, ...]}}, 너무 많아서 포기했는가).
    max_rows 가 0 이면 제한 없이 전부 담는다.
    """
    out: dict[int, dict] = {i: {} for i in device_ids}
    if not device_ids:
        return out, False

    if max_rows:
        # 먼저 세어 본다. 담아 놓고 버리면 그 사이 메모리를 다 쓴다.
        total = 0
        for table in child_tables():
            stmt = sql.SQL(
                "SELECT count(*) AS n FROM {tbl} WHERE device_id = ANY(%s)"
            ).format(tbl=sql.Identifier(table))
            total += cur.execute(stmt, (device_ids,)).fetchone()["n"]
            if total > max_rows:
                return {}, True

    for table, columns in child_tables().items():
        stmt = sql.SQL(
            "SELECT device_id, {cols} FROM {tbl} "
            "WHERE device_id = ANY(%s) ORDER BY id"
        ).format(
            cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
            tbl=sql.Identifier(table),
        )
        for record in cur.execute(stmt, (device_ids,)).fetchall():
            row = dict(record)
            out[row.pop("device_id")].setdefault(table, []).append(row)
    return out, False


# ---------------------------------------------------------------------------
# Entry 를 만드는 곳. 한국어 문장이 여기 한 군데에만 있다.
# ---------------------------------------------------------------------------


def _norm(value):
    """None 을 빈 문자열로. DB 는 NOT NULL DEFAULT 빈문자열이고 payload 는 None 이다."""
    return "" if value is None else value


def _short(value, limit: int = 40) -> str:
    text = str(_norm(value))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _row(device: dict) -> dict:
    return {c: _norm(device.get(c)) for c in DEVICE_COLUMNS}


def device_insert(process_name: str, device: dict, *, process_release: str = "") -> Entry:
    name = str(_norm(device.get("name")))
    celltype = _norm(device.get("celltype"))
    return Entry(
        action=INSERT,
        process_name=process_name,
        device_name=name,
        device_id=device.get("id"),
        summary=f"device 추가  {name} ({celltype})",
        detail={"after": _row(device)},
        process_release=process_release,
    )


def device_update(
    process_name: str, before: dict, after: dict, *, process_release: str = ""
) -> Entry | None:
    """값이 실제로 달라진 컬럼만 담는다. 하나도 없으면 None - 로그를 안 쓴다."""
    changed = {}
    for col in DEVICE_COLUMNS:
        old, new = _norm(before.get(col)), _norm(after.get(col))
        if old != new:
            changed[col] = (old, new)
    if not changed:
        return None

    parts = [
        f"{c} {_quoted(o)} -> {_quoted(n)}" for c, (o, n) in changed.items()
    ]
    return Entry(
        action=UPDATE,
        process_name=process_name,
        device_name=str(_norm(after.get("name") or before.get("name"))),
        device_id=before.get("id"),
        summary="device 수정  " + ", ".join(parts),
        detail={
            "before": {c: o for c, (o, _) in changed.items()},
            "after": {c: n for c, (_, n) in changed.items()},
        },
        process_release=process_release,
    )


def _quoted(value) -> str:
    return chr(34) + _short(value) + chr(34)


def device_delete(
    process_name: str, before: dict, children: dict, *, process_release: str = ""
) -> Entry:
    """children: {자식 테이블: [행, ...]}. 지워진 내용을 통째로 보관한다."""
    total = sum(len(rows) for rows in children.values())
    name = str(_norm(before.get("name")))
    celltype = _norm(before.get("celltype"))
    tail = f", 자식 행 {total}개" if total else ""
    return Entry(
        action=DELETE,
        process_name=process_name,
        device_name=name,
        device_id=before.get("id"),
        summary=f"device 삭제  {name} ({celltype}){tail}",
        detail={"before": _row(before), "children": children},
        process_release=process_release,
    )


def tab_change(
    process_name: str,
    device_name: str,
    device_id: int,
    table: str,
    before: list[dict],
    after: list[dict],
    *,
    process_release: str = "",
) -> Entry | None:
    """탭 하나의 변화. 내용이 같으면 None 이다.

    탭 저장은 DELETE 전체 + INSERT 전체라서 DB 쪽에서 보면 늘 "다 바뀌었다" 다.
    사람이 보기에 무엇이 달라졌는지는 여기서만 알 수 있다.
    """
    if before == after:
        return None

    label = _TAB_LABEL.get(table, table)
    if len(before) == len(after):
        n = sum(1 for b, a in zip(before, after, strict=True) if b != a)
        summary = f"탭 {label}  {len(after)}행 중 {n}행 바뀜"
    else:
        summary = f"탭 {label}  {len(before)}행 -> {len(after)}행"

    return Entry(
        action=TAB,
        process_name=process_name,
        device_name=device_name,
        device_id=device_id,
        table_name=table,
        summary=summary,
        detail={"table": table, "before": before, "after": after},
        process_release=process_release,
    )


def csv_import(path: str, created: int, per_process: dict[str, int]) -> Entry:
    breakdown = ", ".join(f"{p} {n}" for p, n in sorted(per_process.items()))
    tail = f" ({breakdown})" if breakdown else ""
    only = next(iter(per_process)) if len(per_process) == 1 else ""
    return Entry(
        action=IMPORT,
        process_name=only,
        summary=f"CSV 불러오기  {Path(path).name}  device {created}개{tail}",
        detail={"file": str(path), "devices": created, "processes": per_process},
    )


def process_add(name: str, *, process_release: str = "") -> Entry:
    return Entry(
        action=PROCESS_ADD,
        process_name=name,
        summary=f"process 추가  {process_label(name, process_release)}",
        process_release=process_release,
    )


def process_delete(
    name: str, devices: list[dict], truncated: bool, *, process_release: str = ""
) -> Entry:
    """devices 의 각 항목은 자기 자식 행을 children 키에 달고 있다."""
    tail = "  (내용이 너무 많아 자식 행은 보관하지 않았다)" if truncated else ""
    label = process_label(name, process_release)
    return Entry(
        action=PROCESS_DELETE,
        process_name=name,
        summary=f"process 삭제  {label}  device {len(devices)}개가 함께 사라짐{tail}",
        detail={"devices": devices, "truncated": truncated},
        process_release=process_release,
    )


# ---------------------------------------------------------------------------
# 보여주기. 명령줄과 창이 같은 글자를 쓴다.
# ---------------------------------------------------------------------------


def process_label(name: str, release: str) -> str:
    """사람이 읽는 process 이름. 버전이 비면 이름만, 있으면 "이름 버전" 이다."""
    return f"{name} {release}" if release else name


def where_of(row: dict) -> str:
    """process 와 device 를 한 칸에. 둘 다 없으면 붙임표 하나."""
    name = row.get("process_name")
    place = process_label(name, row.get("process_release", "")) if name else "-"
    device = row.get("device_name")
    return f"{place}/{device}" if device else place


def _pad(text: str, width: int) -> str:
    """터미널에서 보이는 너비로 맞춘다.

    f-string 의 :<12 를 쓰면 안 된다. 한글과 한자는 터미널에서 두 칸을 먹는데
    len() 은 한 칸으로 세기 때문에, 이름에 한글이 섞이면 칸이 통째로 어긋난다.
    """
    seen = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(0, width - seen)


def format_line(row: dict) -> str:
    when = row["at"].strftime("%Y-%m-%d %H:%M:%S")
    who = _pad(row["actor"] or "(모름)", 12)
    return f"{when}  {who}  {_pad(where_of(row), 28)}  {row['summary']}"


def format_detail(row: dict, indent: str = "      ") -> list[str]:
    """detail 을 사람이 읽게 편다. 비어 있으면 빈 목록."""
    detail = row.get("detail") or {}
    if not detail:
        return []
    text = json.dumps(detail, ensure_ascii=False, indent=2, default=str)
    return [indent + line for line in text.splitlines()]


# ---------------------------------------------------------------------------
# 읽기
# ---------------------------------------------------------------------------

_COLUMNS = (
    "id, at, actor, source, action, process_name, device_name, device_id, "
    "table_name, summary, detail, process_release"
)


def _aware(when: datetime) -> datetime:
    """naive 시각은 클라이언트 로컬 시각으로 보고 tz 를 붙인다. aware 면 그대로.

    psycopg 는 naive datetime 을 timestamp(without time zone) 로 보내고, 서버는
    그것을 at(timestamptz) 와 비교하려고 세션 TimeZone 으로 읽는다. 호출자
    (cli._parse_when, history_tab._since)는 로컬 시각을 넘기므로, 서버 세션이
    UTC 이고 클라이언트가 KST 면 9시간 어긋난다.
    """
    return when.astimezone() if when.tzinfo is None else when


class AuditRepository:
    def __init__(self, db: Database):
        self.db = db

    def recent(
        self,
        *,
        limit: int = 50,
        since: datetime | None = None,
        until: datetime | None = None,
        actor: str = "",
        process: str = "",
        device: str = "",
        contains: str = "",
        after_id: int | None = None,
        release: str | None = None,
    ) -> list[dict]:
        """조건에 맞는 마지막 limit 줄을 오래된 것부터 돌려준다.

        안쪽에서 id 역순으로 자르고 바깥에서 다시 뒤집는다. 그냥 ORDER BY id
        LIMIT 로 하면 "가장 오래된 50줄" 이 나온다 - 보고 싶은 것은 최근이다.

        다른 필터는 빈 문자열이 "거르지 않음" 이지만 release 는 None 이 그것이다.
        빈 문자열은 "버전 없는 것만" 을 고른다.
        """
        where: list[str] = []
        params: list = []
        if after_id is not None:
            where.append("id > %s")
            params.append(after_id)
        if since is not None:
            where.append("at >= %s")
            params.append(_aware(since))
        if until is not None:
            where.append("at < %s")
            params.append(_aware(until))
        if actor:
            where.append("actor = %s")
            params.append(actor)
        if process:
            where.append("process_name = %s")
            params.append(process)
        if device:
            where.append("device_name = %s")
            params.append(device)
        if release is not None:
            where.append("process_release = %s")
            params.append(release)
        if contains:
            # detail 까지 뒤진다. 값 하나로 "그게 언제 바뀌었지" 를 찾을 수 있다.
            where.append("(summary ILIKE %s OR detail::text ILIKE %s)")
            params += [f"%{contains}%", f"%{contains}%"]

        clause = (" WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        query = (
            f"SELECT * FROM (SELECT {_COLUMNS} FROM change_log{clause} "
            "ORDER BY id DESC LIMIT %s) t ORDER BY id"
        )
        with self.db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def latest_id(self) -> int:
        """--follow 의 출발점. 빈 테이블이면 0."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT coalesce(max(id), 0) AS n FROM change_log"
            ).fetchone()
        return row["n"]

    def count_before(self, before: datetime) -> int:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM change_log WHERE at < %s",
                (_aware(before),),
            ).fetchone()
        return row["n"]

    def purge(self, before: datetime) -> int:
        """before 이전 줄을 지운다. 지운 수를 돌려준다."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM change_log WHERE at < %s", (_aware(before),))
            return cur.rowcount
