"""History 화면의 기본 동작. 가짜 이력(`store.add_audit`) 위에 붙은 `history_ctrl` 로 본다."""

from genviewer.controllers.history_tab import PAGE
from genviewer.service.repo import audit


def _reload(qtbot, ctrl, store) -> None:
    n = len(store.calls_of("recent"))
    ctrl.reload()
    qtbot.waitUntil(lambda: ctrl._task is None and len(store.calls_of("recent")) == n + 1)


def test_reload_shows_the_newest_line_first(qtbot, history_ctrl, store):
    assert history_ctrl.ui.count_label.text() == "조건에 맞는 이력이 없다."  # 첫 다시 읽기

    store.add_audit("kim", audit.process_add("sf9x"))
    store.add_audit(
        "lee", audit.device_insert("sf2p", {"id": 1, "name": "nfet_a", "celltype": "NFET"})
    )
    _reload(qtbot, history_ctrl, store)

    rows = history_ctrl.model.get_data()
    assert [(r["actor"], r["where"], r["summary"]) for r in rows] == [
        ("lee", "sf2p/nfet_a", "device 추가  nfet_a (NFET)"),
        ("kim", "sf9x", "process 추가  sf9x"),
    ]
    assert history_ctrl.ui.count_label.text() == "2줄"
    combo = history_ctrl.ui.process_cb
    assert [combo.itemText(i) for i in range(combo.count())] == ["(전체)", "sf2p", "sf4u"]


def test_the_who_filter_goes_to_recent_as_actor(qtbot, history_ctrl, store):
    store.add_audit("kim", audit.process_add("sf9x"))
    store.add_audit("lee", audit.process_add("sf8x"))
    n = len(store.calls_of("recent"))

    history_ctrl.ui.who_field.setText("kim")
    history_ctrl.ui.who_field.returnPressed.emit()
    qtbot.waitUntil(
        lambda: history_ctrl._task is None and len(store.calls_of("recent")) == n + 1
    )

    # 기간은 fixture 가 "전체" 로 두었다
    assert store.calls_of("recent")[-1] == {
        "limit": PAGE,
        "since": None,
        "until": None,
        "actor": "kim",
        "process": "",
        "device": "",
        "contains": "",
        "after_id": None,
    }
    assert [r["summary"] for r in history_ctrl.model.get_data()] == ["process 추가  sf9x"]
    assert history_ctrl.ui.count_label.text() == "1줄"
