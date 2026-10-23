"""DB 접속 설정.

fmserver/config.py 와 같은 형태 - frozen dataclass + 환경변수, 접속 정보가 없으면
즉시 실패.

서버와 다른 점이 둘이다:

- dsn_override. 이 앱은 GUI 의 Connect 다이얼로그에서도 DSN 을 받으므로,
  환경변수보다 우선하는 값을 넣을 수 있어야 한다.
- 설정 파일. 여러 사람이 각자 데스크톱에서 실행하므로 서버 주소를 매번 손으로
  치게 둘 수 없다. service/env_file.py 가 개인 파일과 설치 디렉터리를 본다.

**DSN 이 빈 문자열이어도 된다.** PGHOST/PGPORT/... 만 있으면 libpq 가 알아서
만든다. 그래서 여기서 문자열을 조립하지 않는다.
"""

import os
from dataclasses import dataclass

from genviewer.service import env_file
from genviewer.utils.user import current_user

DSN_ENV = "GENDB_PG_DSN"
CONFIG_ENV = "GENDB_CONFIG"


@dataclass(frozen=True)
class DbConfig:
    # 빈 문자열이면 libpq 가 PG* 환경변수에서 만든다.
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


def resolve_dsn(dsn_override: str = "") -> str:
    """접속 정보를 확정한다. 설정 파일을 읽어 환경변수에 넣는 부수효과가 있다.

    돌려주는 빈 문자열은 "정보가 없다" 가 아니라 "libpq 가 PG* 환경변수에서
    만든다" 는 뜻이다. 정말 아무것도 없으면 여기서 예외가 난다.
    """
    dsn = (dsn_override or os.environ.get(DSN_ENV, "")).strip()
    if dsn:
        return dsn

    # 환경변수가 없으면 설정 파일을 본다. 개인 파일이 설치 디렉터리의 공통 값을
    # 덮어쓴다 (env_file.candidates 참고).
    _, searched = env_file.load(os.environ.get(CONFIG_ENV, "").strip())

    dsn = os.environ.get(DSN_ENV, "").strip()
    if dsn or env_file.libpq_env_present():
        return dsn

    # 찾아본 자리를 다 보여준다. "설정이 없다" 만으로는 어디에 두라는 것인지 알 수
    # 없고, 그게 다음 질문이 된다.
    places = "\n".join(f"  {p}" for p in searched)
    raise RuntimeError(
        f"No connection settings. Use --dsn, the {DSN_ENV} environment variable, "
        f"the Connect dialog, or put {env_file.SITE_NAME} in one of the places below"
        f" ({CONFIG_ENV} can also point to the file directly):\n"
        f"{places}"
    )


def load_config(dsn_override: str = "") -> DbConfig:
    # 접속 정보를 먼저 확정한다. 제일 흔한 실패라 그 에러가 먼저 보여야 한다.
    dsn = resolve_dsn(dsn_override)

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
