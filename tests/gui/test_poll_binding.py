"""변경 감지 폴링의 결과를 그 폴링을 시작한 process·DB 에 묶는다 (phase 12 step 3, K23b).

폴링(`Task`)은 시작할 때 repo 와 process_id 를 잡지만, 결과는 도착한 순간의 기준점
(`remembered_etag()`)과 비교했다. 그래서 폴링 중에 process 를 바꾸면 앞 process 의 etag 가 새
process 의 기준점과 비교돼 엉뚱한 배너가 떴다. 재접속(`_release_db` 가 도는 폴링을 기다린다)
뒤에는 이미 큐에 있던 옛 DB 의 결과·실패가 새 DB 의 배너와 실패 횟수를 바꿨고, 그 finished 는
그 순간의 `_poll_task`(새로 띄운, 돌고 있는 폴링일 수 있다)를 지웠다.

이제 결과·실패는 그 작업이 지금 작업이고 시작할 때의 (process_id, repo) 가 그대로일 때만 쓰고,
정리는 끝난 그 작업만 지운다.
"""

import threading

import pytest
import shiboken6
from gui_support.fakes import HOLD_TIMEOUT
from gui_support.helpers import select_process
from PySide6.QtCore import QCoreApplication

from genviewer.controllers.device_tab import POLL_FAILURE_LIMIT

POLL_STOPPED = "Stopped change polling: "


def etag_calls(store, process_id: int) -> int:
    return sum(1 for call in store.calls_of("etag") if call["process_id"] == process_id)


def drain_queued_signals() -> None:
    """GUI 스레드의 큐에 와 있는 시그널을 지금 전달한다.

    `_release_db` 가 도는 폴링을 `wait()` 하고 돌아왔을 때 그 작업의 done/failed·finished 는 이미
    큐에 있다(워커가 emit 할 때 넣는다). 그 작업은 `_poll_task = None` 으로 놓여 바뀌는 상태가 없어
    기다릴 조건이 없다. 큐를 비운 뒤 단언해야 "도착했는데 쓰지 않았다" 가 된다.
    """
    QCoreApplication.sendPostedEvents()


def release_when_releasing_db(monkeypatch, tab, event: threading.Event) -> None:
    """`_release_db` 가 시작될 때 event 를 set 한다.

    붙잡힌 폴링이 `run_blocking`(새 DB 열기) 중에 끝나면 결과가 그 이벤트 루프에서 옛 기준점과
    비교되어 재접속 뒤의 도착이 재현되지 않는다. `_release_db` 의 `wait()` 가 놓아 준 작업의
    시그널은 접속이 끝난 뒤에 처리된다.
    """
    release_db = tab._release_db

    def releasing() -> None:
        event.set()
        release_db()

    monkeypatch.setattr(tab, "_release_db", releasing)


def kim_saves_after_the_read(monkeypatch, store, repo) -> None:
    """repo.etag 가 값을 읽은 뒤 kim 이 nfet_a 를 저장한다. 읽은 값(kim 의 저장 전)을 준다."""
    nfet_a = store.find_device("nfet_a")["id"]
    etag = repo.etag

    def read_then_kim_saves(process_id: int) -> dict:
        value = etag(process_id)
        store.touch_device(nfet_a, actor="kim")
        return value

    monkeypatch.setattr(repo, "etag", read_then_kim_saves)


def hold_poll_etag(monkeypatch, repo) -> threading.Event:
    """폴링(워커 스레드)이 부르는 repo.etag 만 돌려준 Event 가 set 될 때까지 붙잡는다.

    `store.hold_next` 는 이름으로 다음 호출을 잡는다. 폴링의 워커가 그 호출에 닿기 전에 GUI 스레드가
    process 를 바꾸면 기준점을 잡는 `remember_etag` 의 etag 가 대신 잡힌다.
    """
    release = threading.Event()
    etag = repo.etag

    def held_on_the_worker(process_id: int) -> dict:
        if threading.current_thread() is not threading.main_thread():
            assert release.wait(HOLD_TIMEOUT), "폴링의 etag 가 풀리지 않았다"
        return etag(process_id)

    monkeypatch.setattr(repo, "etag", held_on_the_worker)
    return release


def reconnect(main_window) -> None:
    main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")


# ----------------------------------------------------------------------
# process 전환 뒤 도착
# ----------------------------------------------------------------------


def test_a_poll_result_arriving_after_a_process_change_is_dropped(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    sf2p = ctrl.device_table.current_process_id
    n = etag_calls(store, sf2p)

    ctrl._poll_remote_changes()
    # 워커가 sf2p 의 etag 를 다 읽게 둔다. 결과 시그널은 큐에서 기다린다.
    assert ctrl._poll_task.wait(5000)
    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: etag_calls(store, sf2p) == n + 1 and ctrl._poll_task is None)
    assert ctrl.device_table.current_process == "sf4u"
    # sf2p 의 etag(device 2개)를 sf4u 의 기준점(1개)과 비교하지 않는다.
    assert ctrl.ui.refresh_banner.isHidden()


def test_a_poll_failure_arriving_after_a_process_change_is_not_counted(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    sf2p = ctrl.device_table.current_process_id
    n = etag_calls(store, sf2p)
    store.fail_next("etag", RuntimeError("x"))

    ctrl._poll_remote_changes()
    # 기다리지 않으면 실패가 sf4u 로 바꿀 때의 remember_etag 에 걸릴 수 있다.
    assert ctrl._poll_task.wait(5000)
    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: etag_calls(store, sf2p) == n + 1 and ctrl._poll_task is None)
    assert ctrl._poll_failures == 0
    assert ctrl._poll_timer.isActive()


def test_a_poll_result_after_switching_back_to_its_process_is_used(
    device_tab_ctrl, store, qtbot, monkeypatch
):
    """sf2p → sf4u → sf2p 로 돌아온 뒤 도착한 sf2p 의 결과는 지금처럼 판단한다(같은 키)."""
    ctrl = device_tab_ctrl
    sf2p = ctrl.device_table.current_process_id
    nfet_a = store.find_device("nfet_a")["id"]
    banner = ctrl.ui.refresh_banner
    release = hold_poll_etag(monkeypatch, ctrl.device_table.repo)
    n = etag_calls(store, sf2p)
    try:
        ctrl._poll_remote_changes()
        select_process(ctrl, "sf4u")
        select_process(ctrl, "sf2p")
        # 돌아와서 기준점을 잡은 뒤 kim 이 저장하고, 폴링이 그것을 읽는다.
        store.touch_device(nfet_a, actor="kim")
    finally:
        release.set()

    qtbot.waitUntil(lambda: etag_calls(store, sf2p) == n + 2 and ctrl._poll_task is None)
    assert not banner.isHidden()
    assert "kim" in banner.label.text()


# ----------------------------------------------------------------------
# 재접속 뒤 도착 (옛 DB 의 결과·실패가 이미 큐에 있다)
# ----------------------------------------------------------------------


def test_a_poll_result_queued_before_a_reconnect_is_dropped(
    main_window, store, qtbot, monkeypatch
):
    tab = main_window.device_tab
    sf2p = tab.device_table.current_process_id
    old_repo = tab.device_table.repo
    n = etag_calls(store, sf2p)
    released = store.hold_next("etag")
    kim_saves_after_the_read(monkeypatch, store, old_repo)
    release_when_releasing_db(monkeypatch, tab, released)

    tab._poll_remote_changes()
    reconnect(main_window)

    # 폴링(옛 DB, kim 의 저장 전)과 새 DB 의 기준점(kim 의 저장 뒤)을 이미 읽었다.
    assert tab.device_table.repo is not old_repo
    assert etag_calls(store, sf2p) == n + 2
    assert tab._poll_task is None
    drain_queued_signals()
    qtbot.waitUntil(lambda: tab._poll_task is None)
    assert tab.ui.refresh_banner.isHidden()


def test_a_poll_failure_queued_before_a_reconnect_is_not_counted(
    main_window, store, qtbot, monkeypatch
):
    tab = main_window.device_tab
    released = store.hold_next("etag")
    store.fail_next("etag", RuntimeError("x"))
    release_when_releasing_db(monkeypatch, tab, released)

    tab._poll_remote_changes()
    reconnect(main_window)

    assert released.is_set()
    assert tab._poll_task is None
    drain_queued_signals()
    assert tab._poll_failures == 0
    assert tab._poll_timer.isActive()


# ----------------------------------------------------------------------
# 닫은 뒤 도착 (close_db, 창 닫기의 shutdown)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("outcome", ["result", "failure"])
@pytest.mark.parametrize("closing", ["close_db", "shutdown"])
def test_a_poll_arriving_after_closing_is_dropped(main_window, store, closing, outcome):
    tab = main_window.device_tab
    if outcome == "result":
        # 폴링이 읽을 etag 가 기준점과 다르다.
        store.touch_device(store.find_device("nfet_a")["id"], actor="kim")
    else:
        store.fail_next("etag", RuntimeError("x"))

    tab._poll_remote_changes()
    # 둘 다 _release_db 로 도는 폴링을 기다린다. 그사이 이벤트를 돌리지 않아 시그널은 큐에 있다.
    if closing == "close_db":
        tab.close_db()
    else:
        main_window.shutdown()

    assert tab.connected is False and tab.db is None
    drain_queued_signals()
    assert tab.ui.refresh_banner.isHidden()
    assert tab._poll_failures == 0


# ----------------------------------------------------------------------
# 정리
# ----------------------------------------------------------------------


def test_a_finished_poll_cleans_up_only_itself(main_window, store, qtbot, monkeypatch):
    """재접속이 기다린 폴링의 finished 가 나중에 와도 그사이 새로 띄운 폴링을 지우지 않는다.

    옛 작업을 테스트가 잡고 있어야 그 finished 의 sender 가 살아 있다(놓으면 Qt 가 None 을 준다).
    옛 작업의 결과(kim 의 저장 전)도 새 작업의 키로 판단하지 않는다.
    """
    tab = main_window.device_tab
    released = store.hold_next("etag")
    kim_saves_after_the_read(monkeypatch, store, tab.device_table.repo)
    release_when_releasing_db(monkeypatch, tab, released)
    tab._poll_remote_changes()
    first = tab._poll_task
    reconnect(main_window)

    second_release = store.hold_next("etag")
    try:
        tab._poll_remote_changes()
        second = tab._poll_task
        assert second is not None and second is not first

        qtbot.waitUntil(lambda: not shiboken6.isValid(first))
        assert shiboken6.isValid(second) and second.isRunning()
        assert tab._poll_task is second
        assert tab.ui.refresh_banner.isHidden()
    finally:
        second_release.set()

    qtbot.waitUntil(lambda: tab._poll_task is None)
    assert tab.ui.refresh_banner.isHidden()  # 새 DB 의 etag 는 새 기준점과 같다


# ----------------------------------------------------------------------
# 회귀: 같은 process·같은 DB 는 지금처럼
# ----------------------------------------------------------------------


def test_three_failed_polls_on_the_same_process_stop_polling(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    lines: list[str] = []
    ctrl.logRequested.connect(lines.append)
    n = len(store.calls_of("etag"))

    for k in range(1, POLL_FAILURE_LIMIT + 1):
        assert ctrl._poll_timer.isActive()
        store.fail_next("etag", RuntimeError("x"))

        ctrl._poll_remote_changes()

        qtbot.waitUntil(
            lambda k=k: len(store.calls_of("etag")) == n + k and ctrl._poll_task is None
        )
        assert ctrl._poll_failures == k

    assert not ctrl._poll_timer.isActive()
    assert [line for line in lines if line.startswith(POLL_STOPPED)] == [POLL_STOPPED + "x"]
