import logging
from collections import defaultdict

from PySide6.QtCore import QModelIndex, QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from genviewer.controllers.device_tab_toolbar import DeviceTabToolBarController
from genviewer.controllers.device_table import DeviceTableController
from genviewer.controllers.parameter_tab import ParameterTabController
from genviewer.service.config import load_config
from genviewer.service.errors import DbUnavailableError, user_message
from genviewer.service.pool import Database
from genviewer.service.repo.device import DeviceRepository, etag_key
from genviewer.service.repo.io import IORepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository
from genviewer.utils.background import Task, is_busy, run_blocking
from genviewer.utils.dialogs import question
from genviewer.utils.lisp import to_lisp_list_string
from genviewer.utils.reporting import report, report_error
from genviewer.utils.user import current_user
from genviewer.views.device_tab import DeviceTab

log = logging.getLogger(__name__)

# 변경 감지 폴링 주기. 여러 명이 시간당 몇 번 저장하는 정도의 사용량이라
# 이보다 자주 볼 이유가 없다.
POLL_INTERVAL_MS = 10_000

# 연속으로 이만큼 실패하면 폴링을 멈춘다. 서버가 죽었을 때 10초마다 죽은
# 호스트에 붙으려 드는 것을 막는다. 다시 접속하면 되살아난다.
POLL_FAILURE_LIMIT = 3


class DeviceTabController(QObject):
    sendDataRequested = Signal(str)
    statusMessageRequested = Signal(str, int)
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)
    # 붙거나 끊을 때마다 현재 Database(또는 None). 이력 화면이 같은 풀을
    # 쓰려고 듣는다.
    dbChanged = Signal(object)

    def __init__(self, ui: DeviceTab, dsn: str = ""):
        super().__init__(ui)
        self.ui = ui
        self.connected: bool | None = None
        self.db: Database | None = None
        self.client = None
        self.device_state_data: dict = {}
        self._poll_task: Task | None = None
        self._poll_failures = 0

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
        self.device_table.deviceVersionBumped.connect(
            self.parameter_tab.adopt_device_version
        )
        self.ui.refresh_banner.refreshRequested.connect(self._on_refresh_requested)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_remote_changes)

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

    def save_db(self) -> bool:
        """device 와 탭을 저장한다. 둘 다 저장됐을 때만 True 이고 "Saved" 를 띄운다.

        device 저장을 취소해도 탭은 저장한다(탭 편집도 저장을 요청받은 것이다).
        device 저장이 예외로 실패하면 탭으로 가지 않는다. 접속이 끊겼으면 탭 저장도
        실패해 오류 상자가 두 번 뜬다.
        """
        try:
            devices_saved = self.device_table.save_all()
        except Exception as e:
            report_error(self, "Save Devices Failed", e, logger=log)
            return False

        # 예전에는 어디에서도 대입되지 않는 current_device 를 보고 있어서 탭을
        # 한 번도 저장하지 않으면서 "All changes have been saved." 를 띄웠다.
        # dirty 탭이 없으면 save_all 이 스스로 True 를 돌려준다.
        try:
            tabs_saved = self.parameter_tab.save_all()
        except Exception as e:
            report_error(self, "Save Tabs Failed", e, logger=log)
            return False

        if not (devices_saved and tabs_saved):
            return False
        self.notifyRequested.emit("info", "Saved", "All changes have been saved.")
        self.logRequested.emit("Saved all device/tab changes.")
        return True

    @staticmethod
    def _open_database(dsn: str) -> Database:
        """워커 스레드에서 도는 부분. ping 이 connect_timeout 만큼 걸릴 수 있다."""
        db = Database(load_config(dsn))
        db.open()
        if not db.ping():
            raise DbUnavailableError("서버가 응답하지 않는다")
        return db

    def connect_db(self, dsn: str) -> bool:
        """DSN 으로 접속한다. dsn 이 비면 GENDB_PG_DSN 환경변수를 쓴다."""
        if self.db is not None:
            self.db.close()
            self.db = None

        try:
            db = run_blocking(lambda: self._open_database(dsn), self)
        except Exception as e:
            # 좁은 예외 목록이면 안 된다. OperationalError 만 DbUnavailableError 로
            # 바뀌므로 인증 실패나 권한 오류는 그대로 여기까지 올라오는데, 이 함수는
            # __init__ 에서도 불리기 때문에 새면 창도 못 띄우고 죽는다.
            self.connected = False
            log.warning("데이터베이스 접속 실패", exc_info=e)
            # 로그 패널에 e 를 그대로 쓰면 안 된다. psycopg 의 접속 실패 문자열에는
            # conninfo 가 통째로 들어 있어 비밀번호가 화면에 찍힌다.
            self.logRequested.emit(f"Database connect failed: {user_message(e)}")
            return False

        self.db = db
        self.connected = True
        self.set_repo(db)
        self.dbChanged.emit(db)
        try:
            self.apply_db()
        except Exception as e:
            # 붙기는 했는데 첫 조회가 실패했다. 빈 화면으로라도 띄운다.
            report_error(self, "Load Failed", e, logger=log)
        self._poll_failures = 0
        self._poll_timer.start()
        self.logRequested.emit(f"Database connected: {db.cfg.dsn}.")
        return True

    # ------------------------------------------------------------------
    # 변경 감지
    # ------------------------------------------------------------------

    @Slot()
    def _poll_remote_changes(self) -> None:
        """남이 이 process 를 바꿨는지 본다. 절대 자동으로 다시 읽지 않는다."""
        if not self.connected or self._poll_task is not None or is_busy():
            return
        repo = self.device_table.repo
        process_id = self.device_table.current_process_id
        if repo is None or process_id is None:
            return
        if self.device_table.remembered_etag() is None:
            return

        # run_blocking 이 아니라 진짜 비동기다. 반환값을 기다리는 사람이 없는데
        # 입력을 막으면, 서버가 느릴 때 10초마다 클릭이 씹힌다.
        task = Task(lambda: repo.etag(process_id))
        task.done.connect(self._on_poll_result)
        task.failed.connect(self._on_poll_failed)
        task.finished.connect(self._clear_poll_task)
        self._poll_task = task
        task.start()

    @Slot()
    def _clear_poll_task(self) -> None:
        task, self._poll_task = self._poll_task, None
        if task is not None:
            task.deleteLater()

    @Slot(object)
    def _on_poll_result(self, etag: dict) -> None:
        self._poll_failures = 0
        base = self.device_table.remembered_etag()
        if base is None or etag_key(etag) == etag_key(base):
            self.ui.hide_refresh_banner()
            return
        self.ui.show_refresh_banner(etag.get("who") or "")

    @Slot(object)
    def _on_poll_failed(self, exc: Exception) -> None:
        self._poll_failures += 1
        if self._poll_failures >= POLL_FAILURE_LIMIT:
            self._poll_timer.stop()
            self.logRequested.emit(f"변경 감지 폴링을 중단했다: {exc}")

    @Slot()
    def _on_refresh_requested(self) -> None:
        self.ui.hide_refresh_banner()
        if (
            self.device_table.is_dirty() or self.parameter_tab.is_dirty()
        ) and not question(
            self.ui,
            "Refresh",
            "저장하지 않은 편집이 있습니다.\n"
            "서버 내용으로 다시 읽으면 그 편집은 사라집니다. 계속할까요?",
        ):
            return
        self.device_table.refresh_devices()
        self.parameter_tab._clear_tabs()
        self.logRequested.emit("서버 내용으로 다시 읽었다.")

    def close_db(self) -> None:
        """커넥션 풀을 닫는다.

        닫지 않으면 인터프리터 종료 시 ConnectionPool.__del__ 이 워커 스레드를
        join 하려다 PythonFinalizationError 로 멈춘다 — 창을 닫아도 프로세스가
        살아 있는 것처럼 보인다.
        """
        self._poll_timer.stop()
        # 폴링이 아직 커넥션을 들고 있을 수 있다. 그대로 풀을 닫으면 그쪽에서
        # 예외가 난다.
        if self._poll_task is not None:
            self._poll_task.wait()
            self._poll_task = None
        if self.db is not None:
            self.db.close()
            self.db = None
            self.dbChanged.emit(None)
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

    @report("Send Failed")
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
    @report("Load CSV Failed")
    def on_load_csv_requested(self, path: str):
        if not self.connected:
            self.notifyRequested.emit(
                "warn", "Database Not Loaded", "먼저 DB를 Load 해야 합니다."
            )
            return

        # 큰 CSV 는 몇 초씩 걸린다. GUI 스레드에서 돌리면 창이 얼어붙는다.
        # run_blocking 은 예외를 호출 지점에서 다시 내므로 @report 가 그대로 받는다.
        created = run_blocking(
            lambda: self.io_repo.import_data(path, actor=current_user()), self
        )

        self.device_tab_toolbar.refresh_processes()
        self.device_table.refresh_devices()
        # 개수를 반드시 보여준다. 임포트는 CSV 행마다 device 를 새로 만들므로 같은
        # 파일을 두 번 넣으면 두 배가 되는데, 사용자가 그것을 알아채는 유일한 방법이
        # 이 숫자다.
        self.notifyRequested.emit(
            "info",
            "Load CSV",
            f"device {created}개를 새로 추가했다.\n"
            "CSV 는 불러올 때마다 새로 쌓인다 — 같은 파일을 다시 넣으면 중복된다.",
        )
        self.logRequested.emit(f"Imported CSV: {path} (device {created}개 추가).")

    @Slot()
    @report("Load Failed")
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
    @report("Load Failed")
    def load_virtuoso(self):
        self.device_table.refresh_devices()
        self.parameter_tab._clear_tabs()

    @Slot()
    @report("Process Change Failed")
    def on_process_changed(self, process_name: str):
        if process_name and not self._save_before_process_change():
            # 저장이 취소되거나 실패해 편집이 남아 있다. 새 process 를 읽으면 그 편집이
            # 말없이 버려진다. 콤보만 이전 process 로 되돌린다(processChanged 를 내지 않는다).
            self.device_tab_toolbar.select_process_silently(
                self.device_table.current_process
            )
            return
        self.clear()
        self.ui.hide_views()
        # 배너는 직전 process 이야기다. 같이 넘어가면 안 된다.
        self.ui.hide_refresh_banner()
        if not process_name:
            self.device_table.set_current_process("")
            self.device_table.set_current_process_id(None)
            self.parameter_tab._clear_tabs()
            return
        self.logRequested.emit(f"Selected process: {process_name}.")

        process_id = self.device_tab_toolbar.get_process_id(process_name)
        self.device_table.set_current_process(process_name)
        self.device_table.set_current_process_id(process_id)
        self.device_table.refresh_devices()
        self.parameter_tab._clear_tabs()

    def _save_before_process_change(self) -> bool:
        """저장하지 않은 device·탭 편집을 한 번 묻고, 예면 dirty 인 쪽만 저장한다.

        넘어가도 되면 True. 예로 답했는데 저장이 취소(충돌 대화상자)되거나 예외로 실패해
        편집이 남아 있으면 False 다. 다시 읽기는 편집이 이미 서버 내용이 됐으므로 넘어간다.
        save_db 는 부르지 않는다("All changes have been saved." 가 하나 더 뜬다). 저장 예외는
        여기서 알린다. @report 까지 올라가면 되돌릴 수 없다.
        """
        if not (self.device_table.is_dirty() or self.parameter_tab.is_dirty()):
            return True
        if not question(
            self.ui,
            "Save Changes",
            "You have unsaved changes. Do you want to save them?",
        ):
            return True

        # dirty 가 아닌 쪽은 부르지 않는다. device 쪽은 쓸 것이 없어도
        # "No changes to save." 를 띄운다.
        if self.device_table.is_dirty():
            try:
                saved = self.device_table.save_all()
            except Exception as e:
                report_error(self, "Save Devices Failed", e, logger=log)
                return False
            if not saved and self.device_table.is_dirty():
                return False

        if self.parameter_tab.is_dirty():
            try:
                saved = self.parameter_tab.save_all()
            except Exception as e:
                report_error(self, "Save Tabs Failed", e, logger=log)
                return False
            if not saved and self.parameter_tab.is_dirty():
                return False
        return True

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
                # 충돌 대화상자에서 취소했으면 편집이 그대로 남아 있다. 새 device 를 읽으면
                # 그 편집이 말없이 버려진다. 다시 읽기는 이미 서버 내용이 됐으므로 넘어간다.
                if not self.parameter_tab.save_all() and self.parameter_tab.is_dirty():
                    return
            else:
                self.parameter_tab.discard_all()

        if not cur_dev or not cur_dev.get("id"):
            self.parameter_tab._clear_tabs()
            return

        self.parameter_tab.set_device_to_section(
            cur_dev["id"], cur_dev.get("celltype"), cur_dev.get("version")
        )
