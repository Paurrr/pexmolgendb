"""History 화면의 실패 문구가 user_message() 를 거친다 (phase 12 step 1).

이력 읽기가 실패하면 개수 칸과, 연속 실패로 자동 갱신을 멈출 때의 로그 패널에 예외 원문을
썼다. 예외에 conninfo 가 들어 있으면 비밀번호가 화면에 찍혔고, 55P03·57014 같은 SQLSTATE
안내도 나오지 않았다(K35 와 같은 종류). 로그 패널은 scrub 포매터를 지나지 않는다(ADR-013).
"""

import psycopg
import pytest

from genviewer.controllers.history_tab import POLL_FAILURE_LIMIT
from genviewer.service.errors import _BY_SQLSTATE, user_message
from genviewer.service.repo import audit

PASSWORD = "s3cret"
COUNT_FAILED = "Could not read history: "
AUTO_STOPPED = "Stopped history auto refresh: "


def reload_and_wait(qtbot, ctrl, store) -> None:
    """reload() 하고 recent 호출과 결과 슬롯까지 끝나기를 기다린다."""
    n = len(store.calls_of("recent"))
    ctrl.reload()
    qtbot.waitUntil(lambda: ctrl._task is None and len(store.calls_of("recent")) == n + 1)


def fail_reloads(qtbot, ctrl, store, exc_factory, times: int) -> None:
    """reload 를 times 번 돌린다. 매번 recent 가 exc_factory() 로 실패한다."""
    for _ in range(times):
        store.fail_next("recent", exc_factory())
        reload_and_wait(qtbot, ctrl, store)


def stop_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith(AUTO_STOPPED)]


def password_error() -> psycopg.OperationalError:
    return psycopg.OperationalError(f"connection failed: host=h password={PASSWORD}")


def count_text(ctrl) -> str:
    return ctrl.ui.count_label.text()


def test_a_failed_reload_does_not_show_the_password_in_the_count(qtbot, history_ctrl, store):
    fail_reloads(qtbot, history_ctrl, store, password_error, 1)

    text = count_text(history_ctrl)
    assert text.startswith(COUNT_FAILED)
    assert PASSWORD not in text
    assert "\n" not in text


def test_a_lock_timeout_shows_the_sqlstate_message_in_the_count(qtbot, history_ctrl, store):
    exc = psycopg.errors.LockNotAvailable("canceling statement due to lock timeout")
    assert exc.sqlstate == "55P03"
    # 제목 줄, 빈 줄, 상세 줄. 개수 칸은 한 줄짜리 라벨이다.
    assert "\n" in user_message(exc)

    fail_reloads(qtbot, history_ctrl, store, lambda: exc, 1)

    text = count_text(history_ctrl)
    assert _BY_SQLSTATE["55P03"] in text
    assert text == COUNT_FAILED + " ".join(user_message(exc).split())


def test_the_auto_stop_log_hides_the_password(qtbot, history_ctrl, store):
    lines: list[str] = []
    history_ctrl.logRequested.connect(lines.append)
    assert history_ctrl._timer.isActive()

    fail_reloads(qtbot, history_ctrl, store, password_error, POLL_FAILURE_LIMIT)

    (line,) = stop_lines(lines)
    assert PASSWORD not in line
    assert "\n" not in line
    assert not history_ctrl._timer.isActive()


def test_the_auto_stop_log_is_the_user_message_on_one_line(qtbot, history_ctrl, store):
    lines: list[str] = []
    history_ctrl.logRequested.connect(lines.append)
    exc = psycopg.errors.QueryCanceled("canceling statement due to statement timeout")
    assert exc.sqlstate == "57014"
    assert "\n" in user_message(exc)

    fail_reloads(qtbot, history_ctrl, store, lambda: exc, POLL_FAILURE_LIMIT)

    (line,) = stop_lines(lines)
    assert line == AUTO_STOPPED + " ".join(user_message(exc).split())
    assert not history_ctrl._timer.isActive()


@pytest.mark.parametrize("failed", range(1, POLL_FAILURE_LIMIT))
def test_auto_reload_keeps_going_before_the_failure_limit(qtbot, history_ctrl, store, failed):
    lines: list[str] = []
    history_ctrl.logRequested.connect(lines.append)

    fail_reloads(qtbot, history_ctrl, store, password_error, failed)

    assert stop_lines(lines) == []
    assert history_ctrl._timer.isActive()


def test_a_reload_after_a_failure_shows_the_line_count_again(qtbot, history_ctrl, store):
    fail_reloads(qtbot, history_ctrl, store, password_error, 1)
    assert count_text(history_ctrl).startswith(COUNT_FAILED)

    reload_and_wait(qtbot, history_ctrl, store)
    assert count_text(history_ctrl) == "No history matches."

    store.add_audit("kim", audit.process_add("sf9x"))
    reload_and_wait(qtbot, history_ctrl, store)
    assert count_text(history_ctrl) == "1 row(s)"
