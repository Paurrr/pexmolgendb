from PySide6.QtCore import QObject, Signal, Slot

from genviewer.service.repo.process import ProcessRepository
from genviewer.utils.dialogs import question
from genviewer.utils.reporting import report, report_error
from genviewer.utils.user import current_user
from genviewer.views.device_tab_toolbar import DeviceTabToolBar


class DeviceTabToolBarController(QObject):
    loadVirtuosoProcessRequested = Signal(str)
    loadLibrariesRequested = Signal()
    processChanged = Signal(str)
    libraryChanged = Signal(str)
    showViewRequested = Signal(bool)
    setProcessesRequested = Signal(list)
    setProcessRequested = Signal(str)
    setLibrariesRequested = Signal(list)
    clearTabRequested = Signal(bool)
    runModeRequested = Signal(str)
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)

    def __init__(self, ui: DeviceTabToolBar, repo: ProcessRepository | None = None):
        super().__init__(ui)
        self.ui = ui
        self.repo = repo

        self.ui.process_selector.currentTextChanged.connect(self.on_process_changed)
        self.ui.library_selector.currentTextChanged.connect(self.on_library_changed)
        self.ui.load_virtuoso_btn.clicked.connect(self.load_virtuoso)
        self.ui.load_virtuoso_btn.clicked.connect(self.show_views)
        self.ui.load_libraries_btn.clicked.connect(self.load_libraries)
        self.ui.selected_run_btn.clicked.connect(self.run_selected)
        self.ui.all_run_btn.clicked.connect(self.run_all)
        self.ui.gen_layout_toggle.toggled.connect(self.on_gen_layout_toggled)
        self.ui.addProcessRequested.connect(self.add_process)
        self.ui.removeProcessRequested.connect(self.remove_process)
        self.ui.addLibraryRequested.connect(self.add_library)
        self.setProcessRequested.connect(self.ui.select_process)
        self.setProcessesRequested.connect(self.ui.set_processes)
        self.setLibrariesRequested.connect(self.ui.set_libraries)

    def set_repo(self, repo: ProcessRepository):
        self.repo = repo

    def _require_repo(self) -> bool:
        if not self.repo:
            self.notifyRequested.emit(
                "warn", "Database Not Loaded", "먼저 DB를 Load 해야 합니다."
            )
            return False
        return True

    def connect_load_virtuoso(self, callback):
        self.ui.load_virtuoso_btn.clicked.connect(lambda *_: callback())

    def connect_load_libraries(self, callback):
        self.ui.load_libraries_btn.clicked.connect(lambda *_: callback())

    @Slot(str)
    def on_process_changed(self, process: str):
        self.processChanged.emit(process)

    @Slot(str)
    def on_library_changed(self, library: str):
        self.libraryChanged.emit(library)

    def run_selected(self):
        self.logRequested.emit("Run requested for selected devices.")
        self.runModeRequested.emit("selected")

    def run_all(self):
        self.logRequested.emit("Run requested for all devices.")
        self.runModeRequested.emit("all")

    @Slot(bool)
    def on_gen_layout_toggled(self, checked: bool):
        self.logRequested.emit(f"Gen Layout {'enabled' if checked else 'disabled'}.")

    @Slot(str)
    @report("Process Add Failed")
    def add_process(self, name: str):
        if not self._require_repo():
            return
        created = self.repo.add(name, actor=current_user())
        if not created:
            self.notifyRequested.emit(
                "warn", "Duplicate", f"Process '{name}' already exists."
            )
            self.setProcessesRequested.emit(self.repo.list_all())
            self.setProcessRequested.emit(name)
            return

        self.setProcessesRequested.emit(self.repo.list_all())
        # 탭은 비우지 않는다. 넘어가면 on_process_changed 가 비우고, 저장이 취소돼 이전
        # process 에 머물렀으면 남겨 둔 탭 편집을 버리게 된다.
        self.setProcessRequested.emit(name)
        self.notifyRequested.emit("info", "Success", f"Process '{name}' added.")
        self.logRequested.emit(f"Process added: {name}.")

    @Slot()
    @report("Process Remove Failed")
    def remove_process(self, name: str):
        if not self._require_repo():
            return
        if not self.repo.exists(name):
            self.notifyRequested.emit(
                "warn", "Not Found", f"Process '{name}' does not exist."
            )
            return
        n = self.repo.count_devices(name)
        if not question(
            self.ui,
            "Remove Process",
            f"Process '{name}' 을(를) 삭제하면 device {n}개와 그 파라미터가\n"
            "모두 함께 삭제됩니다. 계속할까요?",
        ):
            return

        try:
            if self.repo.delete(name, actor=current_user()):
                self.notifyRequested.emit(
                    "info", "Removed", f"Process '{name}' removed."
                )
                # 비편집 콤보의 setCurrentText("") 는 아무것도 하지 않아 지운 이름이 목록에
                # 남았다. 다시 고르면 get_or_create_id 가 빈 process 를 새로 만든다.
                self.refresh_processes()
                self.logRequested.emit(f"Process removed: {name}.")
        except Exception as e:
            report_error(self, f"Remove Failed: {name}", e)

    @report("Process List Failed")
    def refresh_processes(self):
        if not self.repo:
            return
        self.setProcessesRequested.emit(self.repo.list_all())
        self.logRequested.emit("Process list refreshed.")

    def select_process_silently(self, name: str) -> bool:
        """processChanged 없이 콤보만 name 으로 바꾼다. 목록에 없으면 그대로 두고 False."""
        return self.ui.select_process_silently(name)

    def get_current_process(self) -> str:
        return self.ui.process_selector.currentText()

    def get_current_library(self) -> str:
        return self.ui.library_selector.currentText()

    def get_process_id(self, name: str) -> int | None:
        if not self._require_repo():
            return None
        try:
            return self.repo.get_or_create_id(name, actor=current_user())
        except Exception as e:
            self.notifyRequested.emit("error", "Process Lookup Failed", str(e))
            return None

    def load_virtuoso(self):
        if current_process := self.get_current_process():
            self.logRequested.emit(f"Load Virtuoso requested for {current_process}.")
            self.loadVirtuosoProcessRequested.emit(current_process)

    def load_libraries(self):
        self.logRequested.emit("Load Virtuoso libraries requested.")
        self.loadLibrariesRequested.emit()

    @Slot(str)
    def add_library(self, name: str):
        self.ui.add_library(name)
        self.logRequested.emit(f"Library added manually: {name}.")

    def set_libraries(self, items: list[str]):
        self.setLibrariesRequested.emit(items)

    def show_views(self):
        self.showViewRequested.emit(True)
