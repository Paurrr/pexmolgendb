"""History 다시 읽기가 도는 동안의 필터 변경·DB 변경 (phase 12 step 2, K23a·K41).

다시 읽기(`Task`)가 돌고 있으면 `reload()` 는 아무것도 하지 않고 돌아갔다. 그래서 그사이 바꾼
필터는 버려지고(자동 갱신이 꺼져 있으면 다시 누를 때까지), 재접속의 `set_db(새)` 도 새 DB로
읽지 않은 채 옛 DB로 돌던 작업의 결과·실패를 보였다. 이제 그 요청은 보류로 남았다가 도는 작업이
끝난 뒤 한 번 읽히고, 그사이 도착한 옛 결과·실패는 버린다.

`store.hold_next("recent")` 로 다시 읽기를 붙잡아 "도는 중" 을 만든다.
"""

import threading

import pytest
import shiboken6
from gui_support.fakes import FakeDatabase

from genviewer.service.errors import DbUnavailableError
from genviewer.service.repo import audit

COUNT_FAILED = "이력을 읽지 못했다"
NOT_CONNECTED = "데이터베이스에 붙어 있지 않다."
NO_LINES = "조건에 맞는 이력이 없다."


def recent_calls(store) -> int:
    return len(store.calls_of("recent"))


def add_two_lines(store) -> None:
    store.add_audit("kim", audit.process_add("sf9x"))
    store.add_audit("lee", audit.process_add("sf8x"))


def start_held_reload(ctrl, store):
    """recent 에서 붙잡힌 다시 읽기를 띄운다. (도는 Task, 놓아 줄 Event) 를 준다."""
    release = store.hold_next("recent")
    ctrl.reload()
    task = ctrl._task
    assert task is not None and task.isRunning()
    return task, release


def press_enter(field, text: str) -> None:
    field.setText(text)
    field.returnPressed.emit()


@pytest.mark.parametrize("auto", [True, False], ids=["auto", "manual"])
def test_a_filter_changed_while_reloading_is_read_when_it_finishes(
    qtbot, history_ctrl, store, auto
):
    ctrl, ui = history_ctrl, history_ctrl.ui
    ui.auto_cb.setChecked(auto)
    add_two_lines(store)
    before = recent_calls(store)
    _, release = start_held_reload(ctrl, store)

    press_enter(ui.who_field, "kim")
    release.set()

    qtbot.waitUntil(
        lambda: any(c["actor"] == "kim" for c in store.calls_of("recent")), timeout=3000
    )
    qtbot.waitUntil(lambda: ctrl._task is None and recent_calls(store) == before + 2)
    assert [r["summary"] for r in ctrl.model.get_data()] == ["process 추가  sf9x"]
    assert ui.count_label.text() == "1줄"
    # 보류는 타이머와 무관하다. 자동 갱신 상태를 바꾸지 않는다.
    assert ctrl._timer.isActive() is auto


def test_a_failure_of_a_reload_the_filter_outdated_is_dropped(qtbot, history_ctrl, store):
    ctrl, ui = history_ctrl, history_ctrl.ui
    before = recent_calls(store)
    first, release = start_held_reload(ctrl, store)
    store.fail_next("recent", DbUnavailableError("pool closed"))

    press_enter(ui.who_field, "kim")
    second_release = store.hold_next("recent")
    release.set()

    # 다음 작업이 떴다 = 앞 작업의 실패와 정리가 끝났다
    qtbot.waitUntil(lambda: ctrl._task is not None and ctrl._task is not first)
    assert not ui.count_label.text().startswith(COUNT_FAILED)
    assert ctrl._failures == 0

    second_release.set()
    qtbot.waitUntil(lambda: ctrl._task is None and recent_calls(store) == before + 2)
    assert store.calls_of("recent")[-1]["actor"] == "kim"
    assert ui.count_label.text() == NO_LINES


@pytest.mark.parametrize("old_fails", [True, False], ids=["old-fails", "old-ok"])
@pytest.mark.parametrize("auto", [True, False], ids=["auto", "manual"])
def test_set_db_while_reloading_reads_again_from_the_new_db(
    qtbot, history_ctrl, store, auto, old_fails
):
    ctrl, ui = history_ctrl, history_ctrl.ui
    ui.auto_cb.setChecked(auto)
    before = recent_calls(store)
    _, release = start_held_reload(ctrl, store)
    if old_fails:
        # 재접속이 옛 풀을 닫아 그 위에서 돌던 작업이 실패한 것의 흉내
        store.fail_next("recent", DbUnavailableError("pool closed"))

    ctrl.set_db(FakeDatabase(store, "db2"))
    release.set()

    qtbot.waitUntil(lambda: ctrl._task is None and recent_calls(store) == before + 2)
    assert ctrl.repo.db.cfg.dsn == "db2"
    assert not ui.count_label.text().startswith(COUNT_FAILED)
    assert ctrl._failures == 0
    assert ctrl._timer.isActive() is auto


@pytest.mark.parametrize("old_fails", [True, False], ids=["old-fails", "old-ok"])
def test_set_db_none_while_reloading_stays_disconnected(qtbot, history_ctrl, store, old_fails):
    ctrl, ui = history_ctrl, history_ctrl.ui
    add_two_lines(store)
    before = recent_calls(store)
    _, release = start_held_reload(ctrl, store)
    if old_fails:
        store.fail_next("recent", DbUnavailableError("pool closed"))

    ctrl.set_db(None)
    release.set()

    qtbot.waitUntil(lambda: ctrl._task is None and recent_calls(store) == before + 1)
    assert ui.count_label.text() == NOT_CONNECTED
    assert ctrl.model.rowCount() == 0
    assert ctrl._failures == 0


def test_three_filter_changes_while_reloading_read_once_with_the_last(
    qtbot, history_ctrl, store
):
    ctrl, ui = history_ctrl, history_ctrl.ui
    before = recent_calls(store)
    _, release = start_held_reload(ctrl, store)

    press_enter(ui.who_field, "kim")
    ui.process_cb.setCurrentIndex(ui.process_cb.findText("sf2p"))
    press_enter(ui.find_field, "nfet")
    release.set()

    qtbot.waitUntil(
        lambda: ctrl._task is None and not ctrl._pending and recent_calls(store) >= before + 2
    )
    calls = store.calls_of("recent")
    assert len(calls) == before + 2
    assert (calls[-1]["actor"], calls[-1]["process"], calls[-1]["contains"]) == (
        "kim",
        "sf2p",
        "nfet",
    )


def test_an_auto_reload_tick_while_reloading_keeps_the_running_result(
    qtbot, history_ctrl, store
):
    """자동 갱신 틱은 도는 작업을 낡게 만들지 않는다(지금처럼 건너뛴다).

    도는 작업이 이미 지금 필터로 읽고 있다. 틱마다 보류로 만들면 10초보다 오래 걸리는 서버에서는
    결과가 매번 버려져 화면이 영영 바뀌지 않는다.
    """
    ctrl, ui = history_ctrl, history_ctrl.ui
    add_two_lines(store)
    before = recent_calls(store)
    _, release = start_held_reload(ctrl, store)

    ctrl._tick()
    release.set()

    qtbot.waitUntil(lambda: ctrl._task is None and recent_calls(store) >= before + 1)
    assert recent_calls(store) == before + 1
    assert ui.count_label.text() == "2줄"


def test_shutdown_while_reloading_waits_and_does_not_read_again(qtbot, history_ctrl, store):
    ctrl, ui = history_ctrl, history_ctrl.ui
    before = recent_calls(store)
    first, release = start_held_reload(ctrl, store)
    press_enter(ui.who_field, "kim")

    # shutdown 은 GUI 스레드에서 기다린다. 놓아 주는 것은 다른 스레드다.
    timer = threading.Timer(0.2, release.set)
    timer.start()
    ctrl.shutdown()
    timer.join()
    assert first.isFinished()

    # 기다린 작업의 finished 는 큐로 나중에 온다. 그것까지 처리된(그 작업이 지워진) 뒤에 본다.
    qtbot.waitUntil(lambda: not shiboken6.isValid(first))
    qtbot.waitUntil(lambda: ctrl._task is None)
    assert recent_calls(store) == before + 1


def test_the_held_reload_starts_only_after_the_first_task_is_cleaned_up(
    qtbot, history_ctrl, store
):
    """보류된 다시 읽기는 앞 작업의 finished 를 처리하면서 띄운다.

    그래서 앞 작업의 정리가 돌고 있는 다음 작업을 지울 수 없다. 앞 작업의 결과 시그널에서 띄우면
    큐에 남은 그 finished 가 도는 다음 작업을 지워 크래시가 난다.
    """
    ctrl, ui = history_ctrl, history_ctrl.ui
    before = recent_calls(store)
    first, release = start_held_reload(ctrl, store)
    press_enter(ui.who_field, "kim")
    second_release = store.hold_next("recent")
    release.set()

    qtbot.waitUntil(lambda: ctrl._task is not None and ctrl._task is not first)
    second = ctrl._task
    assert not shiboken6.isValid(first) or first.isFinished()

    qtbot.waitUntil(lambda: not shiboken6.isValid(first))
    assert shiboken6.isValid(second) and second.isRunning()
    assert ctrl._task is second

    second_release.set()
    qtbot.waitUntil(lambda: ctrl._task is None and recent_calls(store) == before + 2)


def test_a_task_finishing_after_shutdown_leaves_a_newer_task_running(
    qtbot, history_ctrl, store
):
    """shutdown 이 기다린 작업의 done·finished 는 큐에 남아 나중에 온다.

    그사이 새 작업이 떴으면 그 finished 는 끝난 자기 작업만 지우고, 그 결과는 화면에 쓰지 않는다.
    """
    ctrl, ui = history_ctrl, history_ctrl.ui
    add_two_lines(store)
    first, release = start_held_reload(ctrl, store)
    timer = threading.Timer(0.2, release.set)
    timer.start()
    ctrl.shutdown()
    timer.join()

    second, second_release = start_held_reload(ctrl, store)
    qtbot.waitUntil(lambda: not shiboken6.isValid(first))
    assert shiboken6.isValid(second) and second.isRunning()
    assert ctrl._task is second
    assert ui.count_label.text() == NO_LINES  # 앞 작업의 결과(2줄)를 쓰지 않았다

    second_release.set()
    qtbot.waitUntil(lambda: ctrl._task is None)
    assert ui.count_label.text() == "2줄"
