from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from genviewer.dialogs.add_process import NO_RELEASE_TEXT
from genviewer.dialogs.connection import ConnectionDialog
from genviewer.utils.file_dialogs import open_file
from genviewer.utils.table_utils import (
    build_searchable_labeled_view,
    setup_tableview,
)
from genviewer.views.device_state_table import FilteredDeviceTableView, VirtuosoDeviceTableView
from genviewer.views.device_tab_toolbar import DeviceTabToolBar
from genviewer.views.device_table import DeviceTableView
from genviewer.views.parameter_tab import ParameterTab


class RefreshBanner(QFrame):
    """"이 process 가 남의 손에 바뀌었다" 를 알리는 비모달 줄.

    자동으로 다시 읽지 않는다. 편집 중인 내용이 말없이 사라지는 것은 이번
    작업에서 없애려던 바로 그 부류의 동작이다. 읽을지 말지는 사용자가 정한다.
    """

    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RefreshBanner")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFrameShape(QFrame.NoFrame)

        self.label = QLabel("")
        self.label.setObjectName("RefreshBannerText")
        self.label.setWordWrap(True)

        refresh_btn = QPushButton("새로고침")
        refresh_btn.setToolTip("서버 내용을 다시 읽는다. 저장하지 않은 편집은 사라진다.")
        refresh_btn.setFixedWidth(76)
        refresh_btn.clicked.connect(self.refreshRequested)

        close_btn = QPushButton("닫기")
        close_btn.setToolTip("알림만 숨긴다. 서버 내용은 여전히 다르다.")
        close_btn.setFixedWidth(52)
        close_btn.clicked.connect(self.hide)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 6, 3)
        layout.setSpacing(6)
        layout.addWidget(self.label, 1)
        layout.addWidget(refresh_btn)
        layout.addWidget(close_btn)
        self.hide()

    def show_change(self, who: str) -> None:
        actor = who or "다른 사용자"
        self.label.setText(f"이 process 가 {actor} 님에 의해 변경되었습니다.")
        self.show()


class DeviceTab(QWidget):
    dbConnectRequested = Signal(str)
    # (경로, 버전). 빈 버전은 "" 이다.
    loadCsvRequested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_tab_toolbar_view = DeviceTabToolBar(self)
        self.refresh_banner = RefreshBanner(self)
        self.virtuoso_device_table = VirtuosoDeviceTableView(self)
        self.filtered_device_table = FilteredDeviceTableView(self)
        self.device_table_view = DeviceTableView(self)
        self.parameter_tab_view = ParameterTab(self)

        setup_tableview(self.virtuoso_device_table, [0], "fixed")
        setup_tableview(self.filtered_device_table, [0], "fixed")
        setup_tableview(self.device_table_view, [2])

        splitter = QSplitter(Qt.Horizontal)
        self.search_labeled_virtuoso_device = build_searchable_labeled_view(
            "Device List", self.virtuoso_device_table
        )
        self.search_labeled_filter = build_searchable_labeled_view(
            "Filtered List", self.filtered_device_table
        )
        self.search_labeled_device = build_searchable_labeled_view(
            "Device Info",
            self.device_table_view,
            actions=[
                ("Insert", self.device_table_view.open_insert_dialog),
                ("Edit", self.device_table_view.edit_selected_row),
                ("Delete", self.device_table_view.delete_selected_rows),
                ("Copy", self.device_table_view.copy_selected_rows),
                ("Paste", self.device_table_view.paste_selected_rows),
                ("Clear Sel", self.device_table_view.clearSelection),
            ],
        )

        splitter.addWidget(self.search_labeled_virtuoso_device)
        splitter.addWidget(self.search_labeled_filter)
        splitter.addWidget(self.search_labeled_device)
        splitter.addWidget(self.parameter_tab_view)
        splitter.setSizes([300, 300, 300, 500])

        layout = QVBoxLayout()
        layout.addWidget(self.device_tab_toolbar_view)
        layout.addWidget(self.refresh_banner)
        layout.addWidget(splitter)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(1)
        self.setLayout(layout)
        self.hide_views()

    def show_views(self):
        self.search_labeled_virtuoso_device.show()
        self.search_labeled_filter.show()

    def hide_views(self):
        self.search_labeled_virtuoso_device.hide()
        self.search_labeled_filter.hide()

    def show_refresh_banner(self, who: str):
        self.refresh_banner.show_change(who)

    def hide_refresh_banner(self):
        self.refresh_banner.hide()

    @Slot()
    def _open_connect(self):
        dialog = ConnectionDialog(self)
        if dialog.exec():
            self.dbConnectRequested.emit(dialog.dsn())

    @Slot()
    def _ask_load_csv(self):
        path = open_file(self, "Load CSV", "csv file (*.csv)", "")
        if not path:
            return
        # CSV 에는 버전 컬럼이 없다. 모든 행을 넣을 버전을 여기서 정한다.
        release = self._ask_release()
        if release is None:
            return
        self.loadCsvRequested.emit(path, release)

    def _ask_release(self) -> str | None:
        """불러올 버전. 취소면 None, 버전 없음이면 "".

        후보는 툴바가 이미 들고 있는 쌍의 서로 다른 버전이다(DB 를 부르지 않는다). 빈 버전은
        NO_RELEASE_TEXT 로 맨 앞에 보이고, 처음 자리는 지금 쌍의 버전이다. 목록에 없는 버전도 친다.
        """
        toolbar = self.device_tab_toolbar_view
        releases = sorted({release for _name, release in toolbar.pairs()})
        current = toolbar.current_pair()[1]
        items = [release or NO_RELEASE_TEXT for release in releases]
        text, ok = QInputDialog.getItem(
            self,
            "Load CSV",
            "불러올 버전 (비우면 버전 없음):",
            items,
            releases.index(current) if current in releases else 0,
            editable=True,
        )
        if not ok:
            return None
        release = (text or "").strip()
        return "" if release == NO_RELEASE_TEXT else release
