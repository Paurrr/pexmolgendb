"""생성된 스키마가 (a) tab_config.json 과 (b) 기존 DB 와 일치하는지 검증.

(a)는 탭을 추가할 때 DDL 을 같이 안 고쳐서 생기는 어긋남을 막고,
(b)는 손으로 쓰던 DDL 을 생성으로 바꾸면서 스키마가 바뀌지 않았음을 보장한다.
"""

import re
import sqlite3
from pathlib import Path

import pytest

from genviewer.config.config import tab_config
from genviewer.service import schema

LEGACY_DB = Path(__file__).resolve().parent.parent / "db" / "init.sqlite"


def _schema_of(conn) -> dict[str, list[tuple]]:
    """테이블명 -> [(컬럼명, 타입, notnull, default, pk), ...]"""
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {
        t: [(r[1], r[2], r[3], r[4], r[5]) for r in conn.execute(f"PRAGMA table_info({t})")]
        for t in tables
    }


def _indexes_of(conn) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
    }


@pytest.fixture
def generated():
    c = sqlite3.connect(":memory:")
    for stmt in schema.sqlite_all_ddl():
        c.execute(stmt)
    yield c
    c.close()


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


def test_generated_schema_matches_legacy_database(generated):
    """기존 db/init.sqlite 에 있는 것은 생성본에서 하나도 달라지면 안 된다.

    손으로 쓰던 _SCHEMA 를 생성으로 대체하면서 스키마가 바뀌지 않았다는 증거다.
    완전 일치가 아니라 포함 관계인 이유: init.sqlite 는 그때 배포됐던 것의
    스냅샷이라 탭이 추가되면 생성본에만 새 테이블이 생긴다. 그 파일에 새 탭을
    끼워 넣으면 "그때 배포된 것" 이라는 증거로서의 값어치가 사라진다.
    """
    legacy = sqlite3.connect(f"file:{LEGACY_DB.as_posix()}?mode=ro", uri=True)
    try:
        legacy_schema = _schema_of(legacy)
        got = _schema_of(generated)

        assert set(legacy_schema) <= set(got), "기존 테이블이 사라졌다"
        for table, columns in legacy_schema.items():
            assert got[table] == columns, f"{table} 의 컬럼이 달라졌다"
        assert _indexes_of(legacy) <= _indexes_of(generated), "기존 인덱스가 사라졌다"
    finally:
        legacy.close()


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
