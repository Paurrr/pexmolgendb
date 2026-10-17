"""Database.connection() 의 예외 변환.

DB 가 필요 없다. 못 붙는 경우는 닫힌 포트로, 붙은 뒤의 경우는 가짜 풀로 만든다.

커넥션을 얻지 못한 것만 DbUnavailableError("접속할 수 없다")가 되어야 한다.
with 본문이나 commit 에서 난 예외까지 바꾸면 user_message 의 SQLSTATE 별 안내
(57P01, 57014, 55P03 …)와 StaleWriteError 처리가 사라진다.
"""

from contextlib import contextmanager

import psycopg
import pytest

from genviewer.service.config import DbConfig
from genviewer.service.errors import DbUnavailableError, StaleWriteError, user_message
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
