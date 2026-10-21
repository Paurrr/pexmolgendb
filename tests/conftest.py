"""PostgreSQL 테스트 픽스처.

GENDB_TEST_PG_DSN 이 없으면 DB 가 필요한 테스트는 통째로 skip 한다. 서버가
없는 사람의 `uv run pytest` 를 막지 않기 위해서다.

  GENDB_TEST_PG_DSN="postgresql://user@127.0.0.1:55433/postgres" uv run pytest

세션마다 gendb_test_<pid> 데이터베이스를 만들고 끝나면 지운다.
"""

import os

import pytest

TEST_DSN_ENV = "GENDB_TEST_PG_DSN"


def _admin_dsn() -> str:
    return os.environ.get(TEST_DSN_ENV, "").strip()


requires_pg = pytest.mark.skipif(
    not _admin_dsn(), reason=f"{TEST_DSN_ENV} 가 설정되지 않았다"
)


@pytest.fixture(scope="session")
def pg_dsn():
    """테스트 전용 데이터베이스를 만들고 DSN 을 준다. 세션 끝에 지운다."""
    admin = _admin_dsn()
    if not admin:
        pytest.skip(f"{TEST_DSN_ENV} 가 설정되지 않았다")

    import psycopg

    dbname = f"gendb_test_{os.getpid()}"
    with psycopg.connect(admin, autocommit=True) as con:
        con.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        con.execute(f'CREATE DATABASE "{dbname}"')

    info = psycopg.conninfo.conninfo_to_dict(admin)
    info["dbname"] = dbname
    dsn = psycopg.conninfo.make_conninfo(**info)

    try:
        yield dsn
    finally:
        with psycopg.connect(admin, autocommit=True) as con:
            con.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (dbname,),
            )
            con.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@pytest.fixture
def scratch_dsn(pg_dsn):
    """빈 데이터베이스 하나를 만들고 DSN 을 준다. 테스트가 끝나면 지운다.

    스키마를 옛 모양으로 손으로 만들어 보는 테스트가 쓴다. 세션 DB 에서 하면
    DDL 이 그 모양을 되돌리지 못했을 때 뒤의 DB 테스트가 줄줄이 깨진다.
    """
    import psycopg

    info = psycopg.conninfo.conninfo_to_dict(pg_dsn)
    dbname = f"{info['dbname']}_scratch"
    with psycopg.connect(pg_dsn, autocommit=True) as con:
        con.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        con.execute(f'CREATE DATABASE "{dbname}"')
    info["dbname"] = dbname

    try:
        yield psycopg.conninfo.make_conninfo(**info)
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as con:
            con.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (dbname,),
            )
            con.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@pytest.fixture
def db(pg_dsn):
    """스키마가 적용된 빈 Database. 테스트마다 모든 행을 지운다."""
    from genviewer.service.config import load_config
    from genviewer.service.pool import Database
    from genviewer.service.schema import child_tables, postgres_all_ddl

    database = Database(load_config(pg_dsn))
    database.open()

    with database.connection() as conn:
        for stmt in postgres_all_ddl():
            conn.execute(stmt)

    with database.connection() as conn:
        # process 를 지우면 device 와 자식 행까지 cascade 된다.
        conn.execute("TRUNCATE process RESTART IDENTITY CASCADE")
        # change_log 는 일부러 FK 가 없어서 위 CASCADE 가 닿지 않는다.
        # 여기서 안 비우면 앞 테스트의 이력이 다음 테스트로 새어 나간다.
        conn.execute("TRUNCATE change_log RESTART IDENTITY")
        for table in child_tables():
            conn.execute(f'ALTER SEQUENCE IF EXISTS "{table}_id_seq" RESTART')

    yield database
    database.close()


@pytest.fixture
def two_processes(db):
    """process 2개, 각각 device 1개, 자식 행은 순서가 의미를 갖도록 여러 개.

    반환: fetch_export_data 가 받는 형태의 device_info 리스트.
    """
    from genviewer.service.repo.device import DeviceRepository
    from genviewer.service.repo.parameter import ParameterRepository
    from genviewer.service.repo.process import ProcessRepository

    pr, dr, par = ProcessRepository(db), DeviceRepository(db), ParameterRepository(db)
    columns = ["reserved_key", "cds_inst_term_name"]
    info = []
    for pname, dname, celltype in [
        ("sf2p", "nfet_b", "NFET"),
        ("sf4u", "pfet_b", "PFET"),
    ]:
        pid = pr.get_or_create_id(pname)
        dev = dr.upsert_device(
            pid, {"name": dname, "celltype": celltype, "description": "", "order": 0}
        )
        # 알파벳 순이 아닌 순서로 넣어 정렬이 아니라 삽입 순서가 유지되는지 본다.
        par.replace_all_for_device(
            "inst_terms",
            columns,
            dev["id"],
            [
                {"reserved_key": k, "cds_inst_term_name": v}
                for k, v in [("DRN", "d"), ("GATE", "g"), ("SRC", "s"), ("BULK", "b")]
            ],
        )
        info.append({**dev, "process_id": pid, "process_name": pname})
    return info
