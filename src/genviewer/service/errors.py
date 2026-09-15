"""DB 계층이 컨트롤러에 올려보내는 예외와, 예외를 사람 말로 바꾸는 곳.

psycopg 예외를 그대로 UI 까지 올리지 않는다. 사용자가 실제로 뭔가 할 수 있는
두 가지 상황 — 남이 먼저 고쳤다, 서버에 못 붙었다 — 은 전용 예외로 구분한다.

나머지는 어차피 psycopg 예외 그대로 올라온다. 그것을 트레이스백으로 보여주는
대신 user_message() 가 한 줄짜리 한국어로 바꾼다.
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
        who = self.updated_by or "다른 사용자"
        when = self.updated_at.strftime("%Y-%m-%d %H:%M") if self.updated_at else ""
        verb = {"stale": "수정", "deleted": "삭제"}.get(self.reason, "변경")
        tail = f" ({when})" if when else ""
        return f"{self.device_name or self.device_id}: {who} 님이 {verb}{tail}"


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
    "22001": "값이 컬럼에 담을 수 있는 길이보다 길다.",
    "23502": "비어 있으면 안 되는 값이 비어 있다.",
    "23503": "다른 자료가 참조하고 있어 지울 수 없다.",
    "23505": "같은 값이 이미 있다.",
    "28000": "이 사용자로는 접속할 수 없다.",
    "28P01": "사용자 이름이나 비밀번호가 맞지 않는다.",
    "3D000": "데이터베이스가 없다. 접속 설정을 확인할 것.",
    "40001": "같은 자료를 동시에 고쳤다. 다시 저장할 것.",
    "40P01": "저장이 서로 맞물렸다. 다시 저장할 것.",
    "42501": "이 작업을 할 권한이 없다. 관리자에게 문의할 것.",
    "42P01": "테이블이 없다. genviewer-init-db 를 먼저 실행할 것.",
    "53300": "서버 접속 수가 한도에 찼다. 잠시 후 다시 시도할 것.",
    "55P03": "다른 사용자가 저장하는 중이다. 잠시 후 다시 시도할 것.",
    "57014": "처리가 너무 오래 걸려 서버가 취소했다. 잠시 후 다시 시도할 것.",
    "57P01": "서버가 연결을 끊었다. 다시 접속할 것.",
}

_UNAVAILABLE = "데이터베이스에 접속할 수 없다. 서버 상태와 접속 설정을 확인할 것."


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
