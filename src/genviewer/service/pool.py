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

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from genviewer.service.config import DbConfig
from genviewer.service.errors import DbUnavailableError


class Database:
    def __init__(self, cfg: DbConfig):
        self.cfg = cfg
        options = (
            f"-c lock_timeout={cfg.lock_timeout_ms} "
            f"-c statement_timeout={cfg.statement_timeout_ms}"
        )
        pool_kwargs = {
            "min_size": cfg.pool_min,
            "max_size": cfg.pool_max,
            "open": False,
            "kwargs": {
                "row_factory": dict_row,
                "application_name": f"genviewer:{cfg.app_user}",
                "connect_timeout": cfg.connect_timeout,
                "options": options,
            },
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

    def connection(self):
        """트랜잭션 하나. 정상 종료하면 commit, 예외면 rollback."""
        if self._pool.closed:
            self._pool.open()
        try:
            return self._pool.connection(timeout=self.cfg.connect_timeout)
        except psycopg.OperationalError as e:
            raise DbUnavailableError(str(e)) from e

    def ping(self) -> bool:
        """Connect 다이얼로그의 '연결 테스트'."""
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except (psycopg.Error, DbUnavailableError):
            return False

