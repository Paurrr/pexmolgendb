"""내 device 저장 뒤 "Save Complete" 상자가 떠 있는 동안의 폴링이 배너를 띄우지 않는다 (K43).

`DeviceTableController.save_all` 은 "Save Complete" 알림을 `refresh_devices()`(→ `remember_etag()`)
보다 먼저 냈다. 실제 앱에서 그 알림은 모달 `QMessageBox.information` 이라 상자가 떠 있는 동안
중첩 이벤트 루프가 돌고 10초 폴링도 돈다(`is_busy()` 는 `run_blocking` 안에서만 True 다). 그 폴링은
저장 **뒤**의 etag 를 저장 **전** 기준점과 비교해 "이 process 가 <나> 님에 의해 변경되었습니다."
배너를 띄웠다.

이제 기준점을 먼저 잡고 알린다. 테스트는 "Save Complete" 가 나오는 순간 폴링 틱을 한 번 돌려
모달 안의 중첩 루프를 흉내 낸다.
"""

import pytest
from gui_support.helpers import edit_device_cell

from genviewer.dialogs.conflict import OVERWRITE


def poll_inside_save_complete(ctrl, store, qtbot, *, before_poll=None) -> list[str]:
    """"Save Complete" 알림이 나오는 순간 폴링 틱을 한 번 돌린다(모달 안에서 타이머가 울린 것).

    before_poll 은 그 폴링 전에 부른다(상자가 떠 있는 동안 남이 저장한 것). 슬롯이 돈 횟수를
    확인할 수 있게 받은 요약 문구를 담는 리스트를 준다.
    """
    ran: list[str] = []

    def on_notify(severity: str, title: str, text: str) -> None:
        if title != "Save Complete":
            return
        if before_poll is not None:
            before_poll()
        n = len(store.calls_of("etag"))
        ctrl._poll_remote_changes()
        qtbot.waitUntil(
            lambda: len(store.calls_of("etag")) == n + 1 and ctrl._poll_task is None
        )
        ran.append(text)

    ctrl.device_table.notifyRequested.connect(on_notify)
    return ran


def add_row(ctrl, store) -> None:
    model = ctrl.ui.device_table_view.model_safe()
    celltype = ctrl.device_table._valid_celltypes()[0]
    assert model.insert_row(
        model.rowCount(), {"name": "new_dev", "celltype": celltype, "description": ""}
    )


def edit_row(ctrl, store) -> None:
    edit_device_cell(ctrl, 0, "description", "edited")


def delete_row(ctrl, store) -> None:
    assert ctrl.ui.device_table_view.model_safe().remove_rows([1]) == 1


@pytest.mark.parametrize(
    ("change", "summary"),
    [(add_row, "1 added."), (edit_row, "1 updated."), (delete_row, "1 deleted.")],
    ids=["add", "edit", "delete"],
)
def test_my_save_does_not_show_the_banner_while_the_notice_is_up(
    device_tab_ctrl, store, qtbot, change, summary
):
    ctrl = device_tab_ctrl
    banner = ctrl.ui.refresh_banner
    ran = poll_inside_save_complete(ctrl, store, qtbot)
    change(ctrl, store)

    assert ctrl.device_table.save_all() is True

    assert ran == [summary]
    assert banner.isHidden(), banner.label.text()


def test_an_overwrite_does_not_show_the_banner_while_the_notice_is_up(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    banner = ctrl.ui.refresh_banner
    ran = poll_inside_save_complete(ctrl, store, qtbot)
    edit_row(ctrl, store)
    store.touch_device(store.find_device("nfet_a")["id"], actor="kim")
    dialogs.answer_conflict(OVERWRITE)

    assert ctrl.device_table.save_all() is True

    assert [c["force"] for c in store.calls_of("upsert_devices")] == [False, True]
    assert ran == ["1 updated."]
    assert banner.isHidden(), banner.label.text()


def test_another_users_save_while_the_notice_is_up_shows_the_banner(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    banner = ctrl.ui.refresh_banner
    nfet_b = store.find_device("nfet_b")["id"]
    fetches = len(store.calls_of("fetch_devices_by_process"))
    ran = poll_inside_save_complete(
        ctrl, store, qtbot, before_poll=lambda: store.touch_device(nfet_b, actor="kim")
    )
    edit_row(ctrl, store)

    assert ctrl.device_table.save_all() is True

    assert ran == ["1 updated."]
    assert not banner.isHidden()
    assert "kim" in banner.label.text()
    # 저장 끝의 다시 읽기 한 번뿐이다. 남의 변경을 자동으로 다시 읽지 않는다(ADR-004).
    assert len(store.calls_of("fetch_devices_by_process")) == fetches + 1


def test_the_next_tick_after_my_save_keeps_the_banner_hidden(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    banner = ctrl.ui.refresh_banner
    ran = poll_inside_save_complete(ctrl, store, qtbot)
    add_row(ctrl, store)
    assert ctrl.device_table.save_all() is True
    assert ran == ["1 added."]

    n = len(store.calls_of("etag"))
    ctrl._poll_remote_changes()
    qtbot.waitUntil(lambda: len(store.calls_of("etag")) == n + 1 and ctrl._poll_task is None)

    assert banner.isHidden(), banner.label.text()


def test_a_failed_reload_after_saving_is_reported_before_save_complete(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    edit_row(ctrl, store)
    store.fail_next("fetch_devices_by_process", RuntimeError("boom"))

    assert ctrl.device_table.save_all() is True

    assert store.find_device("nfet_a")["description"] == "edited"
    titles = [title for _kind, title, _text in dialogs.shown]
    assert titles == ["Load Failed", "Save Complete"]
