"""접속 설정과 서버 상태를 진단한다. Qt 없이 돈다.

cli.py 의 `status` 와 `--check-config` 가 쓴다. 판단과 문장 만들기를 여기서 하고
cli 는 찍기만 한다 - 그래야 창 없이 테스트할 수 있다.

**비밀번호는 절대 값으로 내지 않는다.** 화면 캡처와 로그로 샌다. 그래서 보여줄
키를 화이트리스트로 정해 두고, 그 목록에 password 가 낄 자리를 만들지 않는다.
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from genviewer.service import env_file
from genviewer.service.config import CONFIG_ENV, DSN_ENV
from genviewer.service.errors import user_message
from genviewer.service.pool import Database
from genviewer.service.schema import DEVICE_TABLE, PROCESS_TABLE, child_tables
from genviewer.utils import logs
from genviewer.utils.logs import scrub

# 설정 진단이 값을 그대로 보여줄 키들.
SHOWN = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGSERVICE", "PGSSLMODE")

# "어디에 붙으려 하는가" 요약에 낼 키. 화이트리스트다.
_TARGET = (("host", "PGHOST"), ("port", "PGPORT"), ("dbname", "PGDATABASE"), ("user", "PGUSER"))

_MASKED = "(설정됨, 비밀번호가 들어 있어 감춤)"


@dataclass(frozen=True)
class ConfigInfo:
    """어느 설정 파일이 읽혔고 무엇이 적용됐는지."""

    used: Path | None
    searched: list[Path]
    dsn: str
    # 보여줄 (키, 값). 값은 이미 감춰진 표시용이다.
    values: list[tuple[str, str]] = field(default_factory=list)
    # 설정돼 있는 비밀 키의 이름. 값은 담지 않는다.
    secrets: list[str] = field(default_factory=list)
    log_path: Path = Path()
    has_connection_info: bool = False


def inspect_config(explicit: str = "") -> ConfigInfo:
    """설정 파일을 읽고 무엇이 적용됐는지 모은다.

    설정 파일이 깨졌거나 권한이 헐거우면 env_file 이 RuntimeError 를 낸다.
    그대로 올려보낸다 - 부르는 쪽이 그것만 따로 안내해야 한다.
    """
    used, searched = env_file.load(explicit or os.environ.get(CONFIG_ENV, "").strip())

    dsn = os.environ.get(DSN_ENV, "").strip()
    values: list[tuple[str, str]] = []
    if dsn:
        # DSN 안에 비밀번호가 들어 있을 수 있다. keyword 형식이면 통째로 감추고,
        # postgresql://user:secret@host 형식은 scrub 이 가운데만 가린다.
        # 예전에는 앞의 검사만 있었는데 URL 형식에는 password 라는 낱말이
        # 없어서 비밀번호가 그대로 찍혔다.
        values.append((DSN_ENV, _MASKED if "password" in dsn.lower() else scrub(dsn)))
    for key in SHOWN:
        value = os.environ.get(key, "").strip()
        if value:
            values.append((key, value))

    return ConfigInfo(
        used=used,
        searched=searched,
        dsn=dsn,
        values=values,
        secrets=[k for k in sorted(env_file.SECRET_KEYS) if os.environ.get(k)],
        log_path=logs.log_path(),
        has_connection_info=bool(dsn) or env_file.libpq_env_present(),
    )


def config_lines(info: ConfigInfo) -> list[str]:
    """`--check-config` 가 찍는 그대로의 줄들."""
    out = [f"설정 파일: {info.used if info.used else '(없음)'}", "찾아본 곳:"]
    for path in info.searched:
        mark = "<-- 이것" if info.used == path else ""
        out.append(f"  {path} {mark}".rstrip())

    out.append("적용된 값:")
    out += [f"  {key}={value}" for key, value in info.values]
    out += [f"  {key}=(설정됨)" for key in info.secrets]
    if not info.values:
        out.append("  (없음)")

    out.append(f"로그 파일: {info.log_path}  ({logs.LOG_ENV} 로 바꿀 수 있다)")
    return out


def target_summary(dsn: str) -> str:
    """어디에 붙으려 하는지 한 줄로. 비밀번호는 낄 수 없다 (화이트리스트).

    dsn 이 빈 문자열인 것은 정상이다 - libpq 가 PG* 환경변수로 만든다. 그때는
    같은 환경변수에서 읽어 보여준다.
    """
    try:
        parsed = psycopg.conninfo.conninfo_to_dict(dsn) if dsn else {}
    except psycopg.Error:
        # 접속할 때 어차피 제대로 된 에러가 난다. 여기서 죽지는 않는다.
        parsed = {}

    parts = []
    for key, env in _TARGET:
        value = str(parsed.get(key) or os.environ.get(env, "")).strip()
        if value:
            parts.append(f"{key}={value}")
    return " ".join(parts) if parts else "(libpq 기본값)"


def expected_tables() -> list[str]:
    """스키마가 갖추고 있어야 할 테이블. 탭을 추가하면 자동으로 늘어난다."""
    return [PROCESS_TABLE, DEVICE_TABLE, *child_tables()]


@dataclass(frozen=True)
class ServerInfo:
    reachable: bool
    elapsed: float
    # 못 붙었을 때의 이유. user_message 를 거쳤으므로 비밀번호가 없다.
    message: str = ""
    version: str = ""
    database: str = ""
    user: str = ""
    missing_tables: list[str] = field(default_factory=list)
    processes: int = 0
    devices: int = 0

    @property
    def schema_ready(self) -> bool:
        return self.reachable and not self.missing_tables


def probe(db: Database) -> ServerInfo:
    """붙어 보고 스키마와 행 수를 확인한다.

    **예외를 내지 않는다.** 상태를 물어보는 함수가 상태를 물어보다 죽으면
    안 된다 - 못 붙은 것도 답이다.
    """
    started = time.monotonic()
    try:
        with db.connection() as conn:
            row = conn.execute(
                "SELECT current_database() AS db, current_user AS usr, version() AS ver"
            ).fetchone()

            # 이름 목록을 넘겨 비교하지 않는다. relname 은 name 타입이라
            # text[] 와 그냥 비교하면 연산자가 없다고 죽는다. 다 받아서 판다.
            here = {
                r["name"]
                for r in conn.execute(
                    "SELECT c.relname AS name FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = current_schema() AND c.relkind IN ('r', 'p')"
                )
            }
            missing = [t for t in expected_tables() if t not in here]

            processes = devices = 0
            if PROCESS_TABLE not in missing and DEVICE_TABLE not in missing:
                counts = conn.execute(
                    "SELECT (SELECT count(*) FROM process) AS p, "
                    "       (SELECT count(*) FROM device) AS d"
                ).fetchone()
                processes, devices = counts["p"], counts["d"]
    except Exception as exc:  # 서버가 없다 / 인증이 틀렸다 / 권한이 없다
        return ServerInfo(False, time.monotonic() - started, message=user_message(exc))

    return ServerInfo(
        reachable=True,
        elapsed=time.monotonic() - started,
        # version() 은 컴파일러까지 한 줄로 늘어놓는다. 앞 두 낱말이면 된다.
        version=" ".join(str(row["ver"]).split()[:2]),
        database=row["db"],
        user=row["usr"],
        missing_tables=missing,
        processes=processes,
        devices=devices,
    )
