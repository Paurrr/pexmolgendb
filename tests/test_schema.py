"""생성된 스키마가 tab_config.json 과 일치하는지 검증.

탭을 추가할 때 DDL 을 같이 안 고쳐서 생기는 어긋남을 막는다.
"""

import re

from genviewer.config.config import tab_config
from genviewer.service import schema

_CREATE_TABLE = re.compile(r'CREATE TABLE IF NOT EXISTS\s+"?(\w+)"?\s*\(')
_COLUMN = re.compile(r'\s*"?(\w+)"?\s')


def _pg_tables() -> dict[str, list[str]]:
    """PostgreSQL DDL 이 만드는 테이블명 -> [컬럼명, ...] (DDL 에 적힌 순서)

    접속 없이 렌더링한 문자열에서 뽑는다. 자식 테이블은 이름이 따옴표로
    감싸여 나오고(sql.Identifier), process/device/change_log 는 손으로 쓴
    DDL 이라 따옴표가 없다. 둘 다 읽는다.
    """
    tables = {}
    for stmt in _pg_statements():
        m = _CREATE_TABLE.search(stmt)
        if m is None:
            continue
        body = stmt[m.end() : stmt.rindex(")")]
        tables[m.group(1)] = [
            _COLUMN.match(line).group(1) for line in body.splitlines() if line.strip()
        ]
    return tables


def test_child_tables_match_tab_config():
    """자식 테이블 집합과 각 테이블의 payload 컬럼이 tab_config.json 과 같아야 한다."""
    got = _pg_tables()
    expected = {info["table"]: list(info["columns"]) for info in tab_config.values()}

    assert set(got) == set(expected) | {
        schema.PROCESS_TABLE,
        schema.DEVICE_TABLE,
        schema.CHANGE_LOG_TABLE,
    }

    for table, columns in expected.items():
        payload = [c for c in got[table] if c not in ("id", "device_id")]
        assert payload == columns, f"{table} 의 컬럼이 tab_config 와 다르다"


# --------------------------------------------------------------------------
# device 이름 중복 허용
# --------------------------------------------------------------------------


def _pg_statements() -> list[str]:
    return [s.as_string() for s in schema.postgres_all_ddl()]


def test_device_ddl_has_no_unique_constraint():
    """이름 중복을 허용한다.

    UNIQUE (process_id, name) 이 다시 들어오면 CSV 임포트가 같은 이름의 행들을
    device 하나로 합치고(자식 행이 한 탭에 섞인다), 사람이 같은 이름으로
    device 를 추가하면 저장이 UniqueViolation 으로 죽는다.
    """
    device_ddl = next(
        s for s in _pg_statements() if "CREATE TABLE IF NOT EXISTS device" in s
    )
    assert "UNIQUE" not in device_ddl.upper()


def _unique_constraints(db) -> list[str]:
    with db.connection() as conn:
        return [
            r["conname"]
            for r in conn.execute(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'device'::regclass AND contype = 'u' "
                "ORDER BY conname"
            ).fetchall()
        ]


def test_ddl_drops_an_old_unique_constraint_whatever_its_name(db):
    """이미 만들어진 DB 에서도 옛 제약이 떨어진다.

    CREATE TABLE IF NOT EXISTS 는 있는 테이블을 손대지 않으므로, 운영 중인 DB 는
    genviewer-init-db 를 다시 돌려 이 DDL 을 태워야 제약이 없어진다.

    제약 이름을 일부러 기본값(device_process_id_name_key)이 아닌 것으로 만든다.
    이름을 적어 넣지 않고 카탈로그에서 찾는다는 것이 이 테스트의 요점이다.
    """
    with db.connection() as conn:
        conn.execute(
            "ALTER TABLE device ADD CONSTRAINT 손으로_만든_이름 "
            "UNIQUE (process_id, name)"
        )
    assert _unique_constraints(db) == ["손으로_만든_이름"]

    with db.connection() as conn:
        for stmt in schema.postgres_all_ddl():
            conn.execute(stmt)

    assert _unique_constraints(db) == []
