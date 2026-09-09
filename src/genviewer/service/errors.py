"""DB 계층이 컨트롤러에 올려보내는 예외.

psycopg 예외를 그대로 UI 까지 올리지 않는다. 사용자가 실제로 뭔가 할 수 있는
두 가지 상황 — 남이 먼저 고쳤다, 서버에 못 붙었다 — 만 구분해서 전달한다.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Conflict:
    """다른 사용자가 먼저 바꾼 device 하나."""

    device_id: int
    device_name: str
    reason: str  # "stale" | "deleted" | "duplicate"
    updated_by: str = ""
    updated_at: datetime | None = None

    def describe(self) -> str:
        who = self.updated_by or "다른 사용자"
        when = self.updated_at.strftime("%Y-%m-%d %H:%M") if self.updated_at else ""
        verb = {
            "stale": "수정",
            "deleted": "삭제",
            "duplicate": "같은 이름으로 생성",
        }.get(self.reason, "변경")
        tail = f" ({when})" if when else ""
        return f"{self.device_name or self.device_id}: {who} 님이 {verb}{tail}"


class StaleWriteError(Exception):
    """저장하려는 행을 다른 사용자가 먼저 바꿨다."""

    def __init__(self, conflicts: list[Conflict]):
        self.conflicts = conflicts
        super().__init__("; ".join(c.describe() for c in conflicts))


class DbUnavailableError(Exception):
    """서버에 못 붙거나 연결이 끊겼다. 재시도할 만한 상황."""
