from collections import defaultdict

from PySide6.QtCore import QModelIndex, QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from controllers.device_tab_toolbar import DeviceTabToolBarController
from controllers.device_table import DeviceTableController
from controllers.parameter_tab import ParameterTabController
from service.config import load_config
from service.errors import DbUnavailableError
from service.pool import Database
from service.repo.device import DeviceRepository
from service.repo.io import IORepository
from service.repo.parameter import ParameterRepository
from service.repo.process import ProcessRepository
from utils.dialogs import question
from utils.lisp import to_lisp_list_string
from views.device_tab import DeviceTab


class DeviceTabController(QObject):
    sendDataRequested = Signal(str)
    statusMessageRequested = Signal(str, int)
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)

    def __init__(self, ui: DeviceTab, dsn: str = ""):
        super().__init__(ui)
        self.ui = ui
        self.connected: bool | None = None
        self.db: Database | None = None
        self.client = None
        self.device_state_data: dict = {}

        self.device_tab_toolbar = DeviceTabToolBarController(
            self.ui.device_tab_toolbar_view
        )
        self.device_table = DeviceTableController(self.ui.device_table_view)
        self.parameter_tab = ParameterTabController(self.ui.parameter_tab_view)

        self.ui.dbConnectRequested.connect(self._on_connect)
        self.ui.loadCsvRequested.connect(self.on_load_csv_requested)

        self.device_tab_toolbar.processChanged.connect(self.on_process_changed)
        self.device_tab_toolbar.runModeRequested.connect(self.send_device_data)
        self.device_tab_toolbar.showViewRequested.connect(lambda _on: self.show_views())
        self.device_tab_toolbar.clearTabRequested.connect(
            lambda _on: self.parameter_tab._clear_tabs()
        )
        self.ui.device_table_view.selectionModel().currentRowChanged.connect(
            self.on_current_row_changed
        )

        self.device_tab_toolbar.notifyRequested.connect(self.notifyRequested)
        self.device_tab_toolbar.logRequested.connect(self.logRequested)
        self.parameter_tab.notifyRequested.connect(self.notifyRequested)
        self.device_table.notifyRequested.connect(self.notifyRequested)
        self.device_table.pasteRequested.connect(self.on_paste_requested)
        self.device_table.logRequested.connect(self.logRequested)
        self.parameter_tab.logRequested.connect(self.logRequested)
        self.parameter_tab.deviceVersionChanged.connect(
            self.device_table.set_device_version
        )

        self.connect_db(dsn)

    def set_repo(self, db: Database):
        self.io_repo = IORepository(db)
        self.device_table.set_repo(
            DeviceRepository(db), ParameterRepository(db), self.io_repo
        )
        self.device_tab_toolbar.set_repo(ProcessRepository(db))
        self.parameter_tab.set_repo(ParameterRepository(db))

    def set_client(self, client):
        self.client = client

    @Slot(str)
    def _on_connect(self, dsn: str):
        if self.connect_db(dsn):
            self.notifyRequested.emit("info", "Connected", "데이터베이스에 연결했다.")
        else:
            self.notifyRequested.emit(
                "error", "Connect Failed", "데이터베이스에 연결하지 못했다."
            )

    def save_db(self):
        try:
            self.device_table.save_all()
        except Exception as e:
            self.notifyRequested.emit("error", "Save Devices Failed", str(e))
            return

        current = getattr(self, "current_device", None)
        if current:
            try:
                self.parameter_tab.save_all()
            except Exception as e:
                self.notifyRequested.emit("error", "Save Tabs Failed", str(e))
                return

        self.notifyRequested.emit("info", "Saved", "All changes have been saved.")
        self.logRequested.emit("Saved all device/tab changes.")

    def connect_db(self, dsn: str) -> bool:
        """DSN 으로 접속한다. dsn 이 비면 MOLGEN_PG_DSN 환경변수를 쓴다."""
        if self.db is not None:
            self.db.close()
            self.db = None

        try:
            db = Database(load_config(dsn))
            db.open()
            if not db.ping():
                raise DbUnavailableError("서버가 응답하지 않는다")
        except (RuntimeError, DbUnavailableError) as e:
            self.connected = False
            self.logRequested.emit(f"Database connect failed: {e}")
            return False

        self.db = db
        self.connected = True
        self.set_repo(db)
        self.apply_db()
        self.logRequested.emit(f"Database connected: {db.cfg.dsn}.")
        return True

    def close_db(self) -> None:
        """커넥션 풀을 닫는다.

        닫지 않으면 인터프리터 종료 시 ConnectionPool.__del__ 이 워커 스레드를
        join 하려다 PythonFinalizationError 로 멈춘다 — 창을 닫아도 프로세스가
        살아 있는 것처럼 보인다.
        """
        if self.db is not None:
            self.db.close()
            self.db = None
        self.connected = False

    def apply_db(self):
        self.device_table.device_state_data = (
            self.ui.virtuoso_device_table.get_devices()
        )
        self.device_table.refresh_devices()
        self.device_tab_toolbar.refresh_processes()
        self.parameter_tab.rebuild_all_sections()

    def show_views(self):
        if self.connected and self.client:
            self.ui.show_views()

    def clear(self):
        self.ui.virtuoso_device_table.clear_devices()
        self.ui.filtered_device_table.clear_devices()

    def send_device_data(self, mode: str):
        selected_devices = self.device_table.get_selected_devices(
            fallback_to_all=(mode == "all")
        )
        if not selected_devices:
            self.statusMessageRequested.emit("No device selected", 2000)
            return

        device_info = [
            {
                "id": dev["id"],
                "process_id": dev["process_id"],
                "process_name": dev["process_name"],
                "name": dev["name"],
                "celltype": dev["celltype"],
            }
            for dev in selected_devices
        ]

        headers, rows = self.io_repo.fetch_export_data(device_info)

        tab_indices = defaultdict(list)
        for i, h in enumerate(headers):
            if i <= 2:
                continue
            tab_indices[h].append(i)

        celltype_idx = headers.index("CellType")
        cds_idx = headers.index("CdsLibName")
        inst_idx = headers.index("InstCellName")

        data: list[dict] = []
        for row in rows:
            unit_data = {
                "celltype": row[celltype_idx],
                "name": row[inst_idx],
                "tabs": {
                    "CellType": row[celltype_idx],
                    "CdsLibName": row[cds_idx],
                    "InstCellName": row[inst_idx],
                },
            }
            for tab_name, idx_list in tab_indices.items():
                unit_data["tabs"][tab_name] = [row[idx] for idx in idx_list]
            data.append(unit_data)

        all_parts = [to_lisp_list_string(d.get("tabs", {})) for d in data]
        result = "pydata = list(" + "\n ".join(all_parts) + ")"

        try:
            self.sendDataRequested.emit(result)
            self.logRequested.emit(
                f"Generated {mode} device payload for {len(selected_devices)} device(s)."
            )
        except Exception as e:
            self.statusMessageRequested.emit(f"Send failed: {e}", 5000)

    @Slot(str)
    def on_load_csv_requested(self, path: str):
        if not self.connected:
            self.notifyRequested.emit(
                "warn", "Database Not Loaded", "먼저 DB를 Load 해야 합니다."
            )
            return
        try:
            ok = self.io_repo.import_data(path)
            if ok:
                self.device_tab_toolbar.refresh_processes()
                self.device_table.refresh_devices()
                self.notifyRequested.emit("info", "Load CSV", "Success")
                self.logRequested.emit(f"Imported CSV: {path}.")
            else:
                self.notifyRequested.emit("error", "Load CSV", "Fail")
        except Exception as e:
            self.notifyRequested.emit("error", "Load CSV Failed", str(e))

    @Slot()
    def on_current_row_changed(self, current: QModelIndex, previous: QModelIndex):
        if not self.connected:
            QMessageBox.warning(
                self.ui, "Database Not Loaded", "먼저 DB를 Load 해야 합니다."
            )
            self.ui.device_table_view.clearSelection()
            self.parameter_tab._clear_tabs()
            return

        if not current.isValid():
            self.parameter_tab._clear_tabs()
            return

        self._switch_device_by_index()

    @Slot()
    def load_virtuoso(self):
        self.device_table.refresh_devices()
        self.parameter_tab._clear_tabs()

    @Slot()
    def on_process_changed(self, process_name: str):
        self.clear()
        self.ui.hide_views()
        if not process_name:
            self.device_table.set_current_process("")
            self.device_table.set_current_process_id(None)
            self.parameter_tab._clear_tabs()
            return
        self.logRequested.emit(f"Selected process: {process_name}.")
        if self.device_table.is_dirty():
            if question(
                self.ui,
                "Save Changes",
                "You have unsaved changes. Do you want to save them?",
            ):
                self.device_table.save_all()

        process_id = self.device_tab_toolbar.get_process_id(process_name)
        self.device_table.set_current_process(process_name)
        self.device_table.set_current_process_id(process_id)
        self.device_table.refresh_devices()
        self.parameter_tab._clear_tabs()

    @Slot()
    def on_paste_requested(self, device_id, device_type, payload: dict):
        version = None
        for dev in self.device_table.ui.model_safe().get_devices():
            if dev.get("id") == device_id:
                version = dev.get("version")
                break
        self.parameter_tab.paste_payload(device_id, device_type, payload, version)

    def undo_current(self) -> bool:
        return self.device_table.undo()

    def redo_current(self) -> bool:
        return self.device_table.redo()

    def _switch_device_by_index(self):
        prev_dev = self.device_table.prev_selected_device()
        cur_dev = self.device_table.last_selected_device()
        if not prev_dev:
            prev_dev = cur_dev

        if prev_dev.get("id") is None:
            return

        if prev_dev and prev_dev.get("id") == cur_dev.get("id"):
            self.parameter_tab.set_device_to_section(
                cur_dev["id"], cur_dev.get("celltype"), cur_dev.get("version")
            )
            return

        if self.parameter_tab.is_dirty():
            choice = question(
                self.ui,
                "Save Changes",
                "You have unsaved changes. Do you want to save them?",
            )
            if choice is None:
                return
            if choice:
                self.parameter_tab.save_all()
            else:
                self.parameter_tab.discard_all()

        if not cur_dev or not cur_dev.get("id"):
            self.parameter_tab._clear_tabs()
            return

        self.parameter_tab.set_device_to_section(
            cur_dev["id"], cur_dev.get("celltype"), cur_dev.get("version")
        )
