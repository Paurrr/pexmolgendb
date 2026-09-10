"""DB 접속 설정.

fmserver/config.py 와 같은 형태 — frozen dataclass + 환경변수, DSN 없으면 즉시 실패.
dotenv 는 쓰지 않는다(fmserver 규칙). run.cmd / run.csh 가 환경변수를 세팅한다.

서버와 다른 점은 dsn_override 다. 이 앱은 GUI 의 Connect 다이얼로그에서도
DSN 을 받으므로, 환경변수보다 우선하는 값을 넣을 수 있어야 한다.
"""

import os
from dataclasses import dataclass

from genviewer.utils.user import current_user

DSN_ENV = "GENDB_PG_DSN"


@dataclass(frozen=True)
class DbConfig:
    dsn: str
    # 데스크톱 앱이라 서버처럼 클 필요가 없다. 저장 한 번이 커넥션 하나.
    pool_min: int = 1
    pool_max: int = 4
    # 죽은 호스트에 붙을 때 이벤트 루프가 OS 타임아웃(윈도우 ~20초)만큼
    # 멈추지 않도록 짧게 끊는다.
    connect_timeout: int = 5
    # 다른 사용자의 FOR UPDATE 뒤에서 대기하다 GUI 가 굳는 것을 막는다.
    lock_timeout_ms: int = 5000
    statement_timeout_ms: int = 15000
    app_user: str = ""


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from e


def load_config(dsn_override: str = "") -> DbConfig:
    dsn = (dsn_override or os.environ.get(DSN_ENV, "")).strip()
    if not dsn:
        raise RuntimeError(
            f"{DSN_ENV} is required (또는 --dsn / Connect 다이얼로그로 지정)"
        )

    pool_min = _int_env("GENDB_PG_POOL_MIN", 1)
    pool_max = _int_env("GENDB_PG_POOL_MAX", 4)
    if pool_min < 0 or pool_max < 1 or pool_min > pool_max:
        raise RuntimeError(
            f"invalid pool size: GENDB_PG_POOL_MIN={pool_min} "
            f"GENDB_PG_POOL_MAX={pool_max}"
        )

    return DbConfig(
        dsn=dsn,
        pool_min=pool_min,
        pool_max=pool_max,
        connect_timeout=_int_env("GENDB_PG_CONNECT_TIMEOUT", 5),
        lock_timeout_ms=_int_env("GENDB_PG_LOCK_TIMEOUT_MS", 5000),
        statement_timeout_ms=_int_env("GENDB_PG_STATEMENT_TIMEOUT_MS", 15000),
        app_user=current_user(),
    )
