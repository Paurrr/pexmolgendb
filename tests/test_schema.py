"""생성된 스키마가 (a) tab_config.json 과 (b) 기존 DB 와 일치하는지 검증.

(a)는 탭을 추가할 때 DDL 을 같이 안 고쳐서 생기는 어긋남을 막고,
(b)는 손으로 쓰던 DDL 을 생성으로 바꾸면서 스키마가 바뀌지 않았음을 보장한다.
"""

import sqlite3
from pathlib import Path

import pytest

from config.config import tab_config
from service import schema

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


def test_child_tables_match_tab_config(generated):
    """자식 테이블 집합과 각 테이블의 payload 컬럼이 tab_config.json 과 같아야 한다."""
    got = _schema_of(generated)
    expected = {info["table"]: list(info["columns"]) for info in tab_config.values()}

    assert set(got) == set(expected) | {schema.PROCESS_TABLE, schema.DEVICE_TABLE}

    for table, columns in expected.items():
        payload = [c[0] for c in got[table] if c[0] not in ("id", "device_id")]
        assert payload == columns, f"{table} 의 컬럼이 tab_config 와 다르다"


def test_generated_schema_matches_legacy_database(generated):
    """생성된 스키마가 기존 db/init.sqlite 와 동일해야 한다.

    손으로 쓰던 _SCHEMA 를 생성으로 대체하면서 스키마가 바뀌지 않았다는 증거.
    """
    legacy = sqlite3.connect(f"file:{LEGACY_DB.as_posix()}?mode=ro", uri=True)
    try:
        assert _schema_of(generated) == _schema_of(legacy)
        assert _indexes_of(generated) == _indexes_of(legacy)
    finally:
        legacy.close()
