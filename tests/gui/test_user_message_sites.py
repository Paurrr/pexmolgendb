"""화면으로 가는 예외 문자열이 user_message() 를 거친다 (phase 11 step 0).

K34: process 를 고를 때 get_or_create_id 가 실패하면 알림 본문이 psycopg 원문이었다. 55P03 이면
SQLSTATE 안내 대신 원문이 나왔고, 예외에 conninfo 가 들어 있으면 비밀번호가 화면에 찍혔다.
K35: 변경 감지 폴링이 연속 3번 실패해 멈출 때 로그 패널에 예외 원문을 썼다. 로그 패널은 파일
로그의 scrub 포매터를 지나지 않는다(ADR-013).
"""

import psycopg
import pytest
from gui_support.helpers import select_process

from genviewer.controllers.device_tab import POLL_FAILURE_LIMIT
from genviewer.service.errors import user_message

PASSWORD = "s3cret"
LOOKUP_TITLE = "Process Lookup Failed"
POLL_STOPPED = "변경 감지 폴링을 중단했다: "


def lookup_texts(dialogs) -> list[str]:
    return [text for kind, title, text in dialogs.shown if (kind, title) == ("error", LOOKUP_TITLE)]


def select_failing_process(ctrl, store, qtbot, exc: BaseException) -> None:
    """sf4u 를 고르되 get_or_create_id 가 exc 로 실패하게 한다."""
    n = len(store.calls_of("get_or_create_id"))
    store.fail_next("get_or_create_id", exc)

    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("get_or_create_id")) == n + 1)


def fail_polls(ctrl, store, qtbot, exc_factory, times: int) -> None:
    """폴링을 times 번 돌린다. 매번 etag 가 exc_factory() 로 실패하고 결과 슬롯까지 끝난다."""
    n = len(store.calls_of("etag"))
    for k in range(1, times + 1):
        store.fail_next("etag", exc_factory())

        ctrl._poll_remote_changes()

        qtbot.waitUntil(
            lambda k=k: len(store.calls_of("etag")) == n + k and ctrl._poll_task is None
        )


def stop_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith(POLL_STOPPED)]


def password_error() -> psycopg.OperationalError:
    return psycopg.OperationalError(f"connection failed: host=h password={PASSWORD}")


def test_a_lock_timeout_on_process_lookup_shows_the_sqlstate_message(
    device_tab_ctrl, store, dialogs, qtbot
):
    exc = psycopg.errors.LockNotAvailable("canceling statement due to lock timeout")
    assert exc.sqlstate == "55P03"

    select_failing_process(device_tab_ctrl, store, qtbot, exc)

    assert ("error", LOOKUP_TITLE, user_message(exc)) in dialogs.shown


def test_a_process_lookup_failure_does_not_show_the_password(
    device_tab_ctrl, store, dialogs, qtbot
):
    select_failing_process(device_tab_ctrl, store, qtbot, password_error())

    (text,) = lookup_texts(dialogs)
    assert PASSWORD not in text


def test_the_poll_stop_log_hides_the_password(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    lines: list[str] = []
    ctrl.logRequested.connect(lines.append)

    fail_polls(ctrl, store, qtbot, password_error, POLL_FAILURE_LIMIT)

    (line,) = stop_lines(lines)
    assert PASSWORD not in line
    assert "\n" not in line
    assert not ctrl._poll_timer.isActive()


def test_the_poll_stop_log_is_the_user_message_on_one_line(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    lines: list[str] = []
    ctrl.logRequested.connect(lines.append)
    exc = psycopg.errors.QueryCanceled("canceling statement due to statement timeout")
    assert exc.sqlstate == "57014"
    # 제목 줄, 빈 줄, 상세 줄. 로그 패널은 줄 단위라 한 줄로 붙어야 한다.
    assert "\n" in user_message(exc)

    fail_polls(ctrl, store, qtbot, lambda: exc, POLL_FAILURE_LIMIT)

    (line,) = stop_lines(lines)
    assert line == POLL_STOPPED + " ".join(user_message(exc).split())
    assert not ctrl._poll_timer.isActive()


@pytest.mark.parametrize("failed", range(1, POLL_FAILURE_LIMIT))
def test_polling_keeps_going_before_the_failure_limit(device_tab_ctrl, store, qtbot, failed):
    ctrl = device_tab_ctrl
    lines: list[str] = []
    ctrl.logRequested.connect(lines.append)

    fail_polls(ctrl, store, qtbot, password_error, failed)

    assert stop_lines(lines) == []
    assert ctrl._poll_timer.isActive()
