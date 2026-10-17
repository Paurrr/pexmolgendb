"""커넥션 풀.

fmserver/writer_repo.py 의 풀 설정을 따른다.

- open=False: 모듈 import 시점에 서버로 붙지 않는다. 서버 없이도 import 되어야
  --dry-run 도구와 pytest 수집이 돌아간다.
- check=check_connection: DB 재시작 등으로 죽은 커넥션을 꺼내 쓰기 전에 거른다.
- row_factory=dict_row: 컬럼을 인덱스가 아니라 이름으로 읽는다. device 행이
  version 을 갖게 되면서 튜플 언패킹은 유지보수가 어려워진다.

fmserver 에 없는 것은 options 다. 여기는 GUI 스레드에서 DB 를 호출하므로
lock_timeout / statement_timeout 이 없으면 다른 사용자의 FOR UPDATE 뒤에서
창이 굳는다.
"""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from genviewer.service.config import DbConfig
from genviewer.service.errors import DbUnavailableError
from genviewer.utils.logs import scrub


class Database:
    def __init__(self, cfg: DbConfig):
        self.cfg = cfg
        options = (
            f"-c lock_timeout={cfg.lock_timeout_ms} "
            f"-c statement_timeout={cfg.statement_timeout_ms}"
        )
        # 풀 실패의 원인을 알아보려고 직접 붙을 때도 같은 인자를 쓴다.
        self._connect_kwargs = {
            "row_factory": dict_row,
            "application_name": f"genviewer:{cfg.app_user}",
            "connect_timeout": cfg.connect_timeout,
            "options": options,
        }
        pool_kwargs = {
            "min_size": cfg.pool_min,
            "max_size": cfg.pool_max,
            "open": False,
            "kwargs": self._connect_kwargs,
        }
        # 구버전 psycopg_pool 호환 (fmserver 와 동일한 방어).
        check = getattr(ConnectionPool, "check_connection", None)
        if check is not None:
            pool_kwargs["check"] = check
        self._pool = ConnectionPool(cfg.dsn, **pool_kwargs)

    @property
    def user(self) -> str:
        return self.cfg.app_user

    def open(self) -> None:
        if self._pool.closed:
            self._pool.open()

    def close(self) -> None:
        if not self._pool.closed:
            self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        """트랜잭션 하나. 정상 종료하면 commit, 예외면 rollback.

        커넥션을 얻지 못한 것(PoolTimeout 등)만 DbUnavailableError 로 바꾼다.
        풀의 connection() 은 컨텍스트 매니저를 만들기만 하고 획득은 __enter__ 에서
        하므로, 그 호출을 감싸야 한다. with 본문과 commit/rollback 에서 난 예외는
        그대로 올린다. 바꾸면 user_message 의 SQLSTATE 별 안내가 사라진다.
        """
        if self._pool.closed:
            self._pool.open()
        with ExitStack() as stack:
            try:
                conn = stack.enter_context(
                    self._pool.connection(timeout=self.cfg.connect_timeout)
                )
            except psycopg.OperationalError as e:
                raise DbUnavailableError(self._failure_cause() or str(e)) from e
            yield conn

    def _failure_cause(self) -> str:
        """풀이 커넥션을 못 줬을 때 한 번 직접 붙어 실제 원인을 알아낸다.

        PoolTimeout 에는 원인이 없고("couldn't get a connection after 5.00 sec"),
        psycopg 3.3 은 접속 실패에 SQLSTATE 를 싣지 않는다. 그래서 직접 접속이 낸
        오류의 첫 줄(서버·libpq 원문)을 가려서 돌려준다. 직접 접속이 되면 서버는
        멀쩡하고 풀이 찬 것이므로 닫고 "" 를 돌려준다. 대기는 최대 connect_timeout
        한 번 늘어난다.
        """
        try:
            conn = psycopg.Connection.connect(self.cfg.dsn, **self._connect_kwargs)
        except psycopg.Error as e:
            lines = str(e).strip().splitlines()
            return scrub(lines[0]).strip() if lines else ""
        conn.close()
        return ""

    def ping(self) -> bool:
        """Connect 다이얼로그의 '연결 테스트'."""
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except (psycopg.Error, DbUnavailableError):
            return False

