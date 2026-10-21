"""init_db 의 계획(plan)이 옳은지 본다.

여기서 지키려는 성질은 두 가지다.

1. **--dry-run 은 서버에 붙지 않는다.** 무엇이 실행될지 먼저 보고 결정할 수
   있어야 한다. build_plan 이 순수 함수라서 대부분의 검사는 DB 없이 돈다.
2. **탭을 추가해도 권한이 따라간다.** 탭 하나가 테이블 하나이고(tab_config.json)
   탭을 추가하면 init_db 를 다시 돌린다(README). ALTER DEFAULT PRIVILEGES 가
   없으면 새로 생긴 탭만 조용히 권한 오류가 난다.
"""

import os
import re

import pytest

from genviewer.config.config import tab_config
from genviewer.scripts.init_db import build_plan, main
from genviewer.service import schema

APP = "molgen_app"


def _labels(steps):
    return [s.label for s in steps]


def _first(steps, needle):
    for i, s in enumerate(steps):
        if needle in s.label:
            return i
    raise AssertionError(f"{needle!r} 가 계획에 없다: {_labels(steps)}")


# --------------------------------------------------------------------------
# DB 불필요.
# --------------------------------------------------------------------------


def test_plan_without_flags_is_ddl_only():
    """기존 호출부가 그대로 돌아야 한다 (README 의 두 예시)."""
    steps = build_plan("", "", "")
    assert steps, "계획이 비었다"
    assert all(s.conn == "db" for s in steps), "서버 단계가 끼어들었다"
    assert not any("GRANT" in s.label or "SET ROLE" in s.label for s in steps)


def test_app_role_adds_grants_after_the_ddl():
    """ON ALL TABLES 는 실행 시점에 있는 테이블만 본다 - DDL 뒤여야 한다."""
    steps = build_plan("", "", "", APP)
    last_ddl = max(i for i, s in enumerate(steps) if "CREATE TABLE" in s.label)
    assert _first(steps, "GRANT USAGE") > last_ddl
    assert _first(steps, "ALTER DEFAULT PRIVILEGES") > last_ddl


def test_add_column_steps_sit_between_their_create_table_and_the_grants():
    """빠진 컬럼 더하기는 그 테이블이 생긴 뒤, 권한 주기 전에 돈다.

    --dry-run 라벨만 보고 어느 테이블의 단계인지 알 수 있어야 한다. DO 블록의
    첫 줄(DO $$)이 라벨이 되면 14개가 다 똑같이 찍힌다.
    """
    steps = build_plan("", "", "", APP)
    grant = _first(steps, "GRANT")
    labels = []
    for info in tab_config.values():
        table = info["table"]
        create = _first(steps, f'CREATE TABLE IF NOT EXISTS "{table}"')
        adds = [
            i
            for i, s in enumerate(steps)
            if not isinstance(s.sql, str)
            and f'ALTER TABLE "{table}" ADD COLUMN' in s.sql.as_string()
        ]
        assert len(adds) == 1, f"{table} 의 컬럼 더하기 단계가 {len(adds)}개다"
        (add,) = adds
        assert create < add < grant, f"{table}: {_labels(steps)}"
        assert table in steps[add].label
        labels.append(steps[add].label)
    assert len(set(labels)) == len(labels), labels


def _sql_text(step) -> str:
    return step.sql if isinstance(step.sql, str) else step.sql.as_string()


def test_process_and_change_log_moves_have_their_own_labels():
    """phase 19 의 옮기기 두 단계가 --dry-run 에서 서로·다른 단계와 구별된다.

    process 옮기기는 process 가 생긴 바로 뒤(device 앞), change_log 컬럼 더하기는
    change_log 가 생긴 뒤 그 인덱스 앞이다.
    """
    steps = build_plan("", "", "")
    labels = _labels(steps)
    process_alter = re.compile(r'ALTER TABLE "?process"? ADD COLUMN')
    log_alter = re.compile(r'ALTER TABLE "?change_log"? ADD COLUMN')
    moves = [i for i, s in enumerate(steps) if process_alter.search(_sql_text(s))]
    adds = [i for i, s in enumerate(steps) if log_alter.search(_sql_text(s))]
    assert len(moves) == 1, labels
    assert len(adds) == 1, labels
    (move,), (add,) = moves, adds

    assert labels.count(labels[move]) == 1, labels
    assert labels.count(labels[add]) == 1, labels
    assert "process" in labels[move] and "release" in labels[move]
    assert "change_log" in labels[add]
    assert (
        _first(steps, "CREATE TABLE IF NOT EXISTS process")
        < move
        < _first(steps, "CREATE TABLE IF NOT EXISTS device")
    )
    assert (
        _first(steps, "CREATE TABLE IF NOT EXISTS change_log")
        < add
        < _first(steps, "idx_change_log")
    )


def test_default_privileges_are_granted():
    """이게 빠지면 다음에 추가하는 탭마다 손으로 GRANT 해야 한다."""
    sqls = " ".join(
        s.sql for s in build_plan("", "", "", APP) if isinstance(s.sql, str)
    )
    assert "ALTER DEFAULT PRIVILEGES IN SCHEMA public" in sqls
    assert f'ON TABLES TO "{APP}"' in sqls


def test_owner_is_set_before_the_ddl():
    """SET ROLE 이 없으면 --owner 는 객체 소유권에 아무 효과가 없다.

    run_plan 은 관리자 DSN 에서 dbname 만 바꿔 붙기 때문에, 그대로 두면
    테이블 주인이 접속 계정이 되고 기본 권한도 엉뚱한 role 에 붙는다.
    """
    steps = build_plan("", "", "molgen_owner", APP)
    assert _first(steps, "SET ROLE") < _first(steps, "CREATE TABLE")


def test_default_privileges_do_not_name_a_role():
    """SET ROLE 로 이미 owner 로 돌고 있으므로 FOR ROLE 을 쓰면 안 된다.

    FOR ROLE 을 쓰면 '그 role 이 만드는 객체'에 붙는데, 정작 테이블을 만드는
    것은 지금 세션이다. 둘이 어긋나면 기본 권한이 아무 데도 적용되지 않는다.
    """
    (step,) = [
        s for s in build_plan("", "", "molgen_owner", APP)
        if "ALTER DEFAULT PRIVILEGES" in s.label
    ]
    assert "FOR ROLE" not in step.sql


def test_connect_is_granted_only_when_the_database_name_is_known():
    """--dry-run 은 --dsn 없이도 돌아야 해서 DSN 을 파싱할 수 없다.

    기존 DB 에 얹는 경로에서는 어차피 no-op 이다 - PostgreSQL 15 가 회수한
    것은 public '스키마' 의 CREATE 이지 데이터베이스 CONNECT 가 아니다.
    """
    assert not any(
        "GRANT CONNECT" in s.label for s in build_plan("", "", "", APP)
    )
    assert any(
        "GRANT CONNECT" in s.label
        for s in build_plan("", "molgen", "", APP)
    )


def test_no_password_ever_reaches_the_plan():
    """--dry-run 이 계획을 통째로 출력하므로 비밀번호가 들어가면 새어 나간다."""
    steps = build_plan("molgen_owner", "molgen", "molgen_owner", APP)
    for s in steps:
        text = s.sql if isinstance(s.sql, str) else s.sql.as_string()
        assert "PASSWORD %s" in text or "PASSWORD" not in text


def test_dry_run_never_connects(monkeypatch, capsys):
    import psycopg

    def boom(*a, **kw):
        raise AssertionError("--dry-run 이 서버에 붙었다")

    monkeypatch.setattr(psycopg, "connect", boom)
    monkeypatch.setattr("sys.argv", ["init_db", "--dry-run", "--app-role", APP])
    assert main() == 0
    assert "GRANT USAGE" in capsys.readouterr().out


def test_grant_targets_cover_every_table():
    """만든 테이블과 권한 준 테이블이 어긋나면 안 된다.

    GRANT 를 ON ALL TABLES IN SCHEMA public 으로 쓰는 이유가 이것이다 -
    탭이 늘어도 목록을 따로 관리하지 않는다. 그 전제를 고정해 둔다.
    """
    sqls = " ".join(
        s.sql for s in build_plan("", "", "", APP) if isinstance(s.sql, str)
    )
    assert "ON ALL TABLES IN SCHEMA public" in sqls
    # 테이블 이름을 하나씩 나열하지 않는다는 것을 확인 (나열하면 탭 추가 때 샌다).
    for table in schema.child_tables():
        assert f'"{table}" TO' not in sqls


# --------------------------------------------------------------------------
# DB 필요. 추가로 CREATE ROLE 권한이 있어야 한다.
# --------------------------------------------------------------------------


@pytest.fixture
def app_role(db):
    """권한 확인용 NOLOGIN role.

    NOLOGIN 이라 비밀번호도 pg_hba 항목도 필요 없다. has_table_privilege 로
    카탈로그에 직접 물어보므로 두 번째 접속도 필요 없다.
    """
    name = f"gendb_test_app_{os.getpid()}"
    with db.connection() as conn:
        try:
            conn.execute(f'CREATE ROLE "{name}" NOLOGIN')
        except Exception as e:  # 권한 부족 - superuser 도 CREATEROLE 도 아니다
            pytest.skip(f"CREATE ROLE 을 못 한다: {e}")
    try:
        yield name
    finally:
        with db.connection() as conn:
            # DROP OWNED BY 가 기본권한 항목과 GRANT 를 지운다. 이게 없으면
            # DROP ROLE 이 "some objects depend on it" 로 실패한다.
            conn.execute(f'DROP OWNED BY "{name}"')
            conn.execute(f'DROP ROLE "{name}"')


def _apply_grants(db, role):
    from genviewer.scripts.init_db import _grant_steps

    with db.connection() as conn:
        for step in _grant_steps(role, ""):
            conn.execute(step.sql)


def test_app_role_can_use_the_tables_but_not_drop_them(db, app_role):
    _apply_grants(db, app_role)
    with db.connection() as conn:
        got = conn.execute(
            "SELECT "
            "  has_table_privilege(%s, 'device', 'SELECT') AS sel, "
            "  has_table_privilege(%s, 'device', 'INSERT') AS ins, "
            "  has_table_privilege(%s, 'device', 'UPDATE') AS upd, "
            "  has_table_privilege(%s, 'device', 'DELETE') AS del, "
            "  has_table_privilege(%s, 'device', 'TRUNCATE') AS trunc",
            (app_role,) * 5,
        ).fetchone()
    assert (got["sel"], got["ins"], got["upd"], got["del"]) == (True, True, True, True)
    assert got["trunc"] is False, "앱 role 이 테이블을 비울 수 있으면 안 된다"


def test_identity_columns_need_no_sequence_grant(db, app_role):
    """GENERATED AS IDENTITY 는 serial 과 달리 시퀀스 USAGE 가 필요 없다.

    필요했다면 위 테스트의 INSERT 권한만으로는 실제 삽입이 실패한다.
    """
    _apply_grants(db, app_role)
    with db.connection() as conn:
        conn.execute(f'SET ROLE "{app_role}"')
        row = conn.execute(
            "INSERT INTO process (name) VALUES ('grant_probe') RETURNING id"
        ).fetchone()
        assert row["id"] > 0
        conn.execute("RESET ROLE")


def test_a_table_added_later_is_covered_without_a_new_grant(db, app_role):
    """탭을 추가하는 워크플로우 그대로다.

    init_db 를 다시 돌리면 새 테이블이 생기는데, ALTER DEFAULT PRIVILEGES 가
    없으면 그 테이블만 권한이 없어서 새 탭에서만 오류가 난다.
    """
    _apply_grants(db, app_role)
    with db.connection() as conn:
        conn.execute(
            "CREATE TABLE gendb_test_newtab ("
            "  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,"
            "  value TEXT NOT NULL DEFAULT ''"
            ")"
        )
    try:
        with db.connection() as conn:
            ok = conn.execute(
                "SELECT has_table_privilege(%s, 'gendb_test_newtab', 'INSERT') AS ins",
                (app_role,),
            ).fetchone()["ins"]
        assert ok, "나중에 만든 테이블에 권한이 안 따라갔다"
    finally:
        with db.connection() as conn:
            conn.execute("DROP TABLE IF EXISTS gendb_test_newtab")
