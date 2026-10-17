"""Database.connection() 의 예외 변환.

DB 가 필요 없다. 못 붙는 경우는 닫힌 포트로, 붙은 뒤의 경우는 가짜 풀로 만든다.

커넥션을 얻지 못한 것만 DbUnavailableError("접속할 수 없다")가 되어야 한다.
with 본문이나 commit 에서 난 예외까지 바꾸면 user_message 의 SQLSTATE 별 안내
(57P01, 57014, 55P03 …)와 StaleWriteError 처리가 사라진다.
"""

from contextlib import contextmanager

import psycopg
import pytest
from psycopg.conninfo import make_conninfo
from psycopg_pool import PoolTimeout

from genviewer.service.config import DbConfig
from genviewer.service.errors import (
    _UNAVAILABLE,
    DbUnavailableError,
    StaleWriteError,
    user_message,
)
from genviewer.service.pool import Database

CLOSED_PORT_DSN = "host=127.0.0.1 port=1 dbname=x user=x"


@pytest.fixture
def closed_port_db():
    db = Database(
        DbConfig(dsn=CLOSED_PORT_DSN, connect_timeout=1, pool_min=1, pool_max=1)
    )
    try:
        yield db
    finally:
        # 닫지 않으면 풀 워커 스레드가 인터프리터 종료를 붙잡는다.
        db.close()


class _FakePool:
    """서버 없이 커넥션 하나를 내주는 풀. commit 실패를 흉내 낼 수 있다."""

    closed = False

    def __init__(self, fail_on_exit: bool = False):
        self.conn = object()
        self.fail_on_exit = fail_on_exit

    @contextmanager
    def connection(self, timeout=None):
        yield self.conn
        if self.fail_on_exit:
            raise psycopg.OperationalError("commit 실패")


@pytest.fixture
def fake_db():
    db = Database(DbConfig(dsn=CLOSED_PORT_DSN))
    db._pool = _FakePool()
    return db


def test_closed_port_raises_db_unavailable(closed_port_db):
    with pytest.raises(DbUnavailableError) as info:
        with closed_port_db.connection():
            pass

    assert isinstance(info.value.__cause__, psycopg.OperationalError)
    assert "접속할 수 없다" in user_message(info.value)


def test_operational_error_in_body_keeps_its_type(fake_db):
    with pytest.raises(psycopg.OperationalError) as info:
        with fake_db.connection():
            raise psycopg.OperationalError("boom")

    assert str(info.value) == "boom"


def test_stale_write_in_body_keeps_its_type(fake_db):
    with pytest.raises(StaleWriteError):
        with fake_db.connection():
            raise StaleWriteError([])


def test_commit_failure_keeps_its_type(fake_db):
    fake_db._pool = _FakePool(fail_on_exit=True)
    with pytest.raises(psycopg.OperationalError) as info:
        with fake_db.connection():
            pass

    assert str(info.value) == "commit 실패"


def test_connection_yields_the_pool_connection(fake_db):
    with fake_db.connection() as conn:
        assert conn is fake_db._pool.conn


def test_ping_returns_false_on_closed_port(closed_port_db):
    assert closed_port_db.ping() is False


# --- 풀이 커넥션을 못 줄 때 실제 원인 (K3) ---------------------------------
#
# psycopg 3.3 은 접속 실패 예외에 SQLSTATE 를 싣지 않고, PoolTimeout 에는
# 원인이 없다. 그래서 한 번 직접 붙어 본 오류의 첫 줄(가림)을 설명으로 쓴다.

POOL_TIMEOUT_TEXT = "couldn't get a connection"


class _TimeoutPool:
    """커넥션을 내주지 못하는 풀. 풀 크기 초과처럼 서버는 멀쩡한 경우."""

    closed = False

    def connection(self, timeout=None):
        raise PoolTimeout(f"{POOL_TIMEOUT_TEXT} after {timeout:.2f} sec")


class _FakeConn:
    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


def _patch_connect(monkeypatch, result):
    """직접 접속(psycopg.Connection.connect)을 바꾼다. 부른 인자를 돌려준다.

    result 가 예외면 낸다. 풀도 같은 함수로 붙으므로 풀도 같이 실패한다.
    """
    calls = []

    def fake(cls, conninfo="", **kwargs):
        calls.append((conninfo, kwargs))
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(fake))
    return calls


def _unavailable(db) -> DbUnavailableError:
    with pytest.raises(DbUnavailableError) as info:
        with db.connection():
            pass
    assert isinstance(info.value.__cause__, psycopg.OperationalError)
    return info.value


def _unavailable_message(db) -> str:
    return user_message(_unavailable(db))


def test_closed_port_shows_the_real_cause(closed_port_db):
    msg = _unavailable_message(closed_port_db)

    assert POOL_TIMEOUT_TEXT not in msg
    # Windows 는 닫힌 루프백 포트에서도 거절 대신 시간 초과(psycopg 문구)가 나고,
    # 리눅스는 libpq 의 "connection to server at "127.0.0.1", port 1 failed" 다.
    assert "connection timeout expired" in msg or "port 1" in msg


def test_real_cause_hides_the_password(monkeypatch, closed_port_db):
    calls = _patch_connect(
        monkeypatch,
        psycopg.OperationalError(
            'connection failed: FATAL:  password authentication failed for user "x"'
            " password=topsecret\nsecond line"
        ),
    )

    err = _unavailable(closed_port_db)
    msg = user_message(err)

    assert msg.startswith(_UNAVAILABLE)
    assert "password authentication failed" in msg
    assert "topsecret" not in msg
    # 예외 문자열 자체도 가린다. 로그·호출자가 str(exc) 를 쓸 수 있다.
    assert "topsecret" not in str(err)
    assert "second line" not in str(err)
    assert POOL_TIMEOUT_TEXT not in msg
    assert calls, "직접 접속을 하지 않았다"


def test_direct_connect_that_succeeds_keeps_the_pool_message(monkeypatch):
    cfg = DbConfig(dsn=CLOSED_PORT_DSN, connect_timeout=3, app_user="tester")
    db = Database(cfg)
    db._pool = _TimeoutPool()
    conn = _FakeConn()
    calls = _patch_connect(monkeypatch, conn)

    msg = _unavailable_message(db)

    assert msg.startswith(_UNAVAILABLE)
    assert f"{POOL_TIMEOUT_TEXT} after 3.00 sec" in msg
    assert conn.close_calls == 1
    # 한 번만, 풀과 같은 conninfo·접속 인자로 붙는다.
    assert len(calls) == 1
    conninfo, kwargs = calls[0]
    assert conninfo == CLOSED_PORT_DSN
    assert kwargs["connect_timeout"] == 3
    assert kwargs["application_name"] == "genviewer:tester"
    assert "lock_timeout" in kwargs["options"]


def test_direct_connect_only_on_failure(monkeypatch, fake_db):
    calls = _patch_connect(monkeypatch, AssertionError("직접 접속을 했다"))

    with fake_db.connection():
        pass

    assert calls == []


def test_missing_database_shows_the_server_message(pg_dsn):
    # pg_dsn 이 DSN 없으면 skip 한다.
    dsn = make_conninfo(pg_dsn, dbname="gendb_no_such_database")
    db = Database(DbConfig(dsn=dsn, connect_timeout=2, pool_min=1, pool_max=1))
    try:
        msg = _unavailable_message(db)
    finally:
        db.close()

    assert POOL_TIMEOUT_TEXT not in msg
    assert "gendb_no_such_database" in msg
