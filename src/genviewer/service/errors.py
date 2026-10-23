"""DB 계층이 컨트롤러에 올려보내는 예외와, 예외를 사람 말로 바꾸는 곳.

psycopg 예외를 그대로 UI 까지 올리지 않는다. 사용자가 실제로 뭔가 할 수 있는
두 가지 상황 — 남이 먼저 고쳤다, 서버에 못 붙었다 — 은 전용 예외로 구분한다.

나머지는 어차피 psycopg 예외 그대로 올라온다. 그것을 트레이스백으로 보여주는
대신 user_message() 가 한 줄짜리 영어 문장으로 바꾼다(ADR-020).
"""

from dataclasses import dataclass
from datetime import datetime

from genviewer.utils.logs import scrub


@dataclass(frozen=True)
class Conflict:
    """다른 사용자가 먼저 바꾼 device 하나."""

    device_id: int
    device_name: str
    reason: str  # "stale" | "deleted"
    updated_by: str = ""
    updated_at: datetime | None = None

    def describe(self) -> str:
        who = self.updated_by or "another user"
        when = self.updated_at.strftime("%Y-%m-%d %H:%M") if self.updated_at else ""
        verb = {"stale": "modified", "deleted": "deleted"}.get(self.reason, "changed")
        tail = f" ({when})" if when else ""
        return f"{self.device_name or self.device_id}: {verb} by {who}{tail}"


class StaleWriteError(Exception):
    """저장하려는 행을 다른 사용자가 먼저 바꿨다."""

    def __init__(self, conflicts: list[Conflict]):
        self.conflicts = conflicts
        super().__init__("; ".join(c.describe() for c in conflicts))


class DbUnavailableError(Exception):
    """서버에 못 붙거나 연결이 끊겼다. 재시도할 만한 상황."""


# SQLSTATE -> 사용자가 읽고 뭘 할지 알 수 있는 문장.
#
# 57014(statement_timeout)와 55P03(lock_timeout)은 예외 상황이 아니다.
# service/pool.py 가 두 타임아웃을 **일부러** 걸어 두었으므로, 사람이 몰려서 쓰면
# 정상적으로 나오는 결과다. 지금까지 이 둘은 아무 데서도 다뤄지지 않아 그대로
# 트레이스백이 됐다.
_BY_SQLSTATE = {
    "22001": "A value is longer than the column allows.",
    "23502": "A required value is empty.",
    "23503": "Cannot delete it because other data refers to it.",
    "23505": "The same value already exists.",
    "28000": "Cannot connect as this user.",
    "28P01": "The user name or password is wrong.",
    "3D000": "The database does not exist. Check the connection settings.",
    "40001": "The same data was changed at the same time. Save again.",
    "40P01": "Two saves blocked each other. Save again.",
    "42501": "You do not have permission for this. Ask the administrator.",
    "42P01": "Tables are missing. Run genviewer-init-db first.",
    "53300": "The server has too many connections. Try again later.",
    "55P03": "Another user is saving. Try again later.",
    "57014": "The server canceled the operation because it took too long. Try again later.",
    "57P01": "The server closed the connection. Connect again.",
}

_UNAVAILABLE = "Cannot connect to the database. Check the server and the connection settings."


def _detail(exc: BaseException) -> str:
    """서버가 준 설명. 비밀번호가 섞여 있을 수 있으므로 반드시 가린다."""
    diag = getattr(exc, "diag", None)
    parts: list[str] = []
    if diag is not None:
        for attr in ("message_primary", "message_detail", "message_hint"):
            value = getattr(diag, attr, None)
            if value:
                parts.append(str(value).strip())
    if not parts:
        text = str(exc).strip()
        if text:
            # psycopg 예외는 여러 줄이다. 첫 줄이면 충분하고, 나머지는 로그에 있다.
            parts.append(text.splitlines()[0])
    return scrub(" ".join(parts)).strip()


def user_message(exc: BaseException) -> str:
    """예외를 사용자에게 보여줄 문장으로 바꾼다. 절대 빈 문자열을 내지 않는다."""
    if isinstance(exc, StaleWriteError):
        return str(exc)

    headline = _BY_SQLSTATE.get(getattr(exc, "sqlstate", None) or "")
    if headline is None and isinstance(exc, DbUnavailableError):
        headline = _UNAVAILABLE

    detail = _detail(exc)
    if headline and detail:
        return f"{headline}\n\n{detail}"
    return headline or detail or exc.__class__.__name__
