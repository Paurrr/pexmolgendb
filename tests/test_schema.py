"""생성된 스키마가 tab_config.json 과 일치하는지 검증.

탭을 추가할 때 DDL 을 같이 안 고쳐서 생기는 어긋남을 막는다.
"""

import re

from psycopg import sql

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


# --------------------------------------------------------------------------
# 기존 탭 테이블에 빠진 컬럼 더하기
# --------------------------------------------------------------------------
#
# CREATE TABLE IF NOT EXISTS 는 이미 있는 테이블을 손대지 않는다. tab_config.json
# 에서 기존 탭에 컬럼을 더하면 운영 DB 에는 그 컬럼이 생기지 않아 저장·불러오기가
# 42703 으로 죽었다. init_db 재실행이 빠진 컬럼을 더해야 한다.

_ALTER_TABLE = re.compile(r'ALTER TABLE "(\w+)"')


def test_ddl_adds_every_payload_column_after_its_create_table():
    """탭 테이블마다 모든 payload 컬럼을 pg_child_ddl 과 같은 타입으로 더한다.

    기대값은 tab_config 에서 바로 만든다. child_tables() 끼리 비교하면 그 함수가
    컬럼을 빠뜨려도 양쪽이 같이 틀려서 통과한다.
    """
    stmts = _pg_statements()
    creates = {
        m.group(1): i for i, s in enumerate(stmts) if (m := _CREATE_TABLE.search(s))
    }
    for info in tab_config.values():
        table = info["table"]
        adds = [i for i, s in enumerate(stmts) if table in _ALTER_TABLE.findall(s)]
        assert len(adds) == 1, f"{table} 의 컬럼 더하기 문장이 {len(adds)}개다"
        (add,) = adds
        assert add > creates[table], f"{table} 의 컬럼 더하기가 CREATE TABLE 보다 앞이다"
        assert set(_ALTER_TABLE.findall(stmts[add])) == {table}
        for column in info["columns"]:
            assert (
                f"ADD COLUMN IF NOT EXISTS \"{column}\" TEXT NOT NULL DEFAULT ''"
                in stmts[add]
            ), f"{table}.{column} 을 더하지 않는다"


# 마지막 컬럼을 고른다. 되살린 컬럼은 물리적으로 맨 뒤에 붙으므로 그래야 되살린
# 뒤의 순서가 새 DB 의 DDL 과 같다.
_TAB = tab_config["InstTerm"]
_TABLE = _TAB["table"]
_LAST_COLUMN = _TAB["columns"][-1]


def _columns(conn, table) -> list[dict]:
    return conn.execute(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = %s "
        "ORDER BY ordinal_position",
        (table,),
    ).fetchall()


def _run_all_ddl(conn) -> None:
    for stmt in schema.postgres_all_ddl():
        conn.execute(stmt)


def test_ddl_restores_a_missing_column_on_an_existing_table(db):
    """tab_config 에 컬럼을 더하고 init_db 를 다시 돌린 운영 DB 가 이렇다.

    수정 전에는 fixture 도 이 컬럼을 되살리지 못하므로, finally 에서 직접
    되돌려 둔다. 안 그러면 세션의 다른 테스트가 42703 으로 깨진다.
    """
    with db.connection() as conn:
        pid = conn.execute(
            "INSERT INTO process (name) VALUES ('sf2p') RETURNING id"
        ).fetchone()["id"]
        did = conn.execute(
            "INSERT INTO device (process_id, name, celltype) "
            "VALUES (%s, 'nfet_a', 'NFET') RETURNING id",
            (pid,),
        ).fetchone()["id"]
        conn.execute(
            sql.SQL("INSERT INTO {} (device_id) VALUES (%s)").format(
                sql.Identifier(_TABLE)
            ),
            (did,),
        )
        conn.execute(
            sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(
                sql.Identifier(_TABLE), sql.Identifier(_LAST_COLUMN)
            )
        )
    try:
        with db.connection() as conn:
            _run_all_ddl(conn)

        with db.connection() as conn:
            cols = _columns(conn, _TABLE)
            values = conn.execute(
                sql.SQL("SELECT {} AS v FROM {}").format(
                    sql.Identifier(_LAST_COLUMN), sql.Identifier(_TABLE)
                )
            ).fetchall()
        assert [c["column_name"] for c in cols] == ["id", "device_id", *_TAB["columns"]]
        (restored,) = [c for c in cols if c["column_name"] == _LAST_COLUMN]
        assert (
            restored["data_type"],
            restored["is_nullable"],
            restored["column_default"],
        ) == ("text", "NO", "''::text")
        assert [r["v"] for r in values] == [""]
    finally:
        with db.connection() as conn:
            conn.execute(
                sql.SQL(
                    "ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} TEXT NOT NULL DEFAULT ''"
                ).format(sql.Identifier(_TABLE), sql.Identifier(_LAST_COLUMN))
            )


def test_ddl_twice_leaves_the_same_columns(db):
    """init_db 는 여러 번 돌려도 된다. 두 번째 실행이 컬럼을 바꾸면 안 된다."""
    tables = list(schema.child_tables())
    with db.connection() as conn:
        _run_all_ddl(conn)
    with db.connection() as conn:
        first = {t: _columns(conn, t) for t in tables}
    with db.connection() as conn:
        _run_all_ddl(conn)
    with db.connection() as conn:
        second = {t: _columns(conn, t) for t in tables}
    assert second == first


def test_ddl_takes_no_table_lock_when_no_column_is_missing(db, pg_dsn):
    """사람이 쓰는 중에 init_db 를 다시 돌려도 아무도 멈추지 않는다(README).

    ALTER TABLE … ADD COLUMN IF NOT EXISTS 는 컬럼이 이미 있어도 ACCESS EXCLUSIVE
    를 먼저 잡는다. 그러면 읽는 트랜잭션 하나 뒤에서 init_db 가 기다리고, 그동안
    그 탭을 읽는 모든 사람이 init_db 뒤에 줄을 선다. 컬럼이 다 있으면 ALTER 를
    실행하지 않아야 한다.
    """
    import psycopg

    reader = psycopg.connect(pg_dsn)
    try:
        # 트랜잭션을 열어 둔 채로 AccessShareLock 을 쥐고 있는다.
        reader.execute(
            sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(_TABLE))
        )
        with db.connection() as conn:
            conn.execute("SET LOCAL lock_timeout = '500ms'")
            _run_all_ddl(conn)
    finally:
        reader.rollback()
        reader.close()
