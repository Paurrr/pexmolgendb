"""컨트롤러 테스트 헬퍼: 시드, 가짜 DB 설치, 사용자 동작.

`tests/gui/conftest.py` 의 `store`/`device_tab_ctrl`/`main_window`/`history_ctrl` fixture 가 쓰고,
테스트도 `from gui_support.helpers import select_process, ...` 로 쓴다.

사용자 동작 헬퍼는 동작 하나만 흉내 내고 **기다리지 않는다**. 결과(탭 로드, 저장)는 테스트가
`qtbot.waitUntil` 로 기다린다. 탭 로드나 첫 접속이 비동기로 옮겨가도 헬퍼는 그대로 쓰기 위해서다.
전제가 틀리면(없는 process, 없는 행, 고르지 않은 device) 메시지가 있는 `AssertionError` 를 낸다.
"""

from PySide6.QtCore import Qt

from genviewer.controllers import device_tab as device_tab_module
from genviewer.controllers import history_tab as history_tab_module
from genviewer.controllers.device_tab import DeviceTabController
from gui_support.fakes import (
    FakeAuditRepository,
    FakeDeviceRepository,
    FakeIORepository,
    FakeParameterRepository,
    FakeProcessRepository,
    FakeStore,
)

# 시드. (process, device, celltype, order, InstTerm 쌍, InstSchParam 쌍). 이 순서로 넣는다.
# id 는 FakeStore 가 매긴다(process sf2p=1, sf4u=2 / device nfet_a=1, nfet_b=2, pfet_a=3).
# 테스트는 숫자 대신 store.find_device("nfet_a")["id"] 를 쓴다.
# 값은 delegate_config 검증을 통과한다.
SEED_PROCESSES = ("sf2p", "sf4u")
SEED_DEVICES = (
    (
        "sf2p",
        "nfet_a",
        "NFET",
        0,
        (("DRN", "d"), ("GATE", "g"), ("SRC", "s"), ("BULK", "b")),
        (("LENGTH", "l"), ("WIDTH", "w")),
    ),
    ("sf2p", "nfet_b", "NFET", 1, (("DRN", "d2"), ("GATE", "g2")), (("NF", "nf2"),)),
    ("sf4u", "pfet_a", "PFET", 0, (("DRN", "pd"), ("GATE", "pg")), (("LENGTH", "pl"),)),
)

# 가짜로 바꾸는 이름. 컨트롤러가 `set_repo` 에서 이 모듈의 이름으로 repo 를 만든다.
FAKE_REPOSITORIES = {
    "DeviceRepository": FakeDeviceRepository,
    "ParameterRepository": FakeParameterRepository,
    "ProcessRepository": FakeProcessRepository,
    "IORepository": FakeIORepository,
}

# History 화면이 `set_db` 에서 이 모듈의 이름으로 만드는 repo.
FAKE_HISTORY_REPOSITORIES = {
    "AuditRepository": FakeAuditRepository,
    "ProcessRepository": FakeProcessRepository,
}


def seeded_store() -> FakeStore:
    """process 둘, device 셋, 탭 InstTerm(inst_terms)·InstSchParam(inst_sch_params) 행을 넣는다."""
    store = FakeStore()
    process_ids = {name: store.add_process(name) for name in SEED_PROCESSES}
    for process, name, celltype, order, terms, params in SEED_DEVICES:
        device = store.add_device(process_ids[process], name, celltype, order=order)
        store.set_rows(
            "inst_terms",
            device["id"],
            [{"reserved_key": k, "cds_inst_term_name": v} for k, v in terms],
        )
        store.set_rows(
            "inst_sch_params",
            device["id"],
            [{"reserved_key": k, "cds_inst_parameter_name": v} for k, v in params],
        )
    return store


def install_fake_db(monkeypatch, store: FakeStore) -> None:
    """`DeviceTabController` 가 실제 DB 대신 store 에 붙게 한다. monkeypatch 가 되돌린다.

    접속 전에 store 를 손봐야 하는 테스트(첫 접속 실패 등)는 이것을 부른 뒤 컨트롤러를 직접 만든다.
    """
    monkeypatch.setattr(
        DeviceTabController, "_open_database", staticmethod(store.open_database)
    )
    for name, fake in FAKE_REPOSITORIES.items():
        monkeypatch.setattr(device_tab_module, name, fake)


def install_fake_history(monkeypatch) -> None:
    """`HistoryTabController.set_db` 가 실제 repo 대신 가짜 repo 를 만들게 한다.

    monkeypatch 가 되돌린다. 가짜 repo 는 받은 DB 의 store 를 쓴다.
    그래서 `set_db(FakeDatabase(store))` 로 붙인다.
    """
    for name, fake in FAKE_HISTORY_REPOSITORIES.items():
        monkeypatch.setattr(history_tab_module, name, fake)


def select_process(ctrl: DeviceTabController, name: str, release: str = "") -> None:
    """process·version 콤보에서 (name, release) 를 사용자처럼 고른다.

    이름이 다르면 process 콤보를 바꾸고(view 가 버전을 고른다), 그 뒤 버전이 다르면 version 콤보를
    바꾼다(사용자 동작 두 번 = 전환 두 번). 첫 전환이 되돌려졌으면(저장 취소) 거기서 멈춘다.
    이미 골라져 있으면 콤보가 시그널을 내지 않는다. 한 번에 옮기려면 `ui.select_pair` 를 쓴다.
    """
    ui = ctrl.device_tab_toolbar.ui
    pairs = ui.pairs()
    assert (name, release) in pairs, f"process 목록에 {(name, release)!r} 가 없다: {pairs}"
    if ui.process_selector.currentText() != name:
        ui.process_selector.setCurrentIndex(ui.process_selector.findText(name))
    if ui.process_selector.currentText() == name and ui.current_pair() != (name, release):
        ui.release_selector.setCurrentIndex(ui.releases_of(name).index(release))


def select_device_row(ctrl: DeviceTabController, row: int) -> None:
    """device 표에서 화면에 보이는 순서(정렬 proxy)의 row 번째 행을 클릭한 것처럼 고른다."""
    view = ctrl.ui.device_table_view
    index = view.model().index(row, 0)
    assert index.isValid(), f"device 표에 {row}번 행이 없다 (행 {view.model().rowCount()}개)"
    view.setCurrentIndex(index)


def edit_device_cell(ctrl: DeviceTabController, row: int, column: str, value: str) -> None:
    """device 표(proxy 순서) row 행의 column("name"/"celltype"/"description")을 value 로 고친다."""
    view = ctrl.ui.device_table_view
    columns = view.model_safe()._columns
    assert column in columns, f"device 표에 없는 컬럼: {column!r} (가능: {columns})"
    proxy = view.model()
    index = proxy.index(row, columns.index(column))
    assert index.isValid(), f"device 표에 {row}번 행이 없다 (행 {proxy.rowCount()}개)"
    assert proxy.setData(index, value, Qt.EditRole), (
        f"device 표 {row}행 {column} 을 {value!r} 로 바꾸지 못했다 (같은 값이거나 검증 실패)"
    )


def edit_tab_cell(
    ctrl: DeviceTabController, tab_name: str, row: int, column: str, value: str
) -> None:
    """탭(tab_config 키, 예 "InstTerm") row 행의 column 을 value 로 고친다.

    device 를 먼저 골라야 한다(그래야 탭 섹션에 모델이 있다).
    """
    sec = ctrl.parameter_tab.section(tab_name)
    assert sec is not None, (
        f"탭 섹션이 없다: {tab_name!r} (있는 것: {list(ctrl.parameter_tab._sections)})"
    )
    assert sec.model is not None, f"{tab_name} 탭에 모델이 없다. device 를 먼저 골라야 한다"
    assert column in sec.columns, f"{tab_name} 탭에 없는 컬럼: {column!r} (가능: {sec.columns})"
    index = sec.model.index(row, sec.columns.index(column))
    assert index.isValid(), f"{tab_name} 탭에 {row}번 행이 없다 (행 {sec.model.rowCount()}개)"
    assert sec.model.setData(index, value, Qt.EditRole), (
        f"{tab_name} 탭 {row}행 {column} 을 {value!r} 로 바꾸지 못했다 (같은 값이거나 검증 실패)"
    )
