from pathlib import Path

from PySide6.QtCore import QModelIndex, QObject, QPoint, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from genviewer.config.config import delegate_config, tab_config
from genviewer.delegates.combo_box import ComboBoxDelegate
from genviewer.dialogs.conflict import OVERWRITE, RELOAD, ask_conflict
from genviewer.service.errors import StaleWriteError
from genviewer.service.repo.device import DeviceRepository, SaveResult
from genviewer.service.repo.io import IORepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.utils.background import run_blocking
from genviewer.utils.exporter import write_csv, write_xlsx
from genviewer.utils.menus import build_device_table_menu
from genviewer.utils.reporting import report
from genviewer.utils.user import current_user
from genviewer.views.device_table import DeviceTableView


def _describe_save(result: SaveResult) -> str:
    """DB 가 실제로 쓴 행만 세어 문장으로 만든다."""
    parts = []
    if result.updated:
        parts.append(f"{result.updated} updated")
    if result.inserted:
        parts.append(f"{result.inserted} added")
    if result.deleted:
        parts.append(f"{result.deleted} deleted")
    if not parts:
        return "No changes to save."
    return f"{', '.join(parts)}."


class DeviceTableController(QObject):
    pasteRequested = Signal(object, str, dict)
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)
    # device_id, old_version, new_version. 내 저장(save_all)이 실제로 올린 행만 낸다.
    deviceVersionBumped = Signal(int, int, int)

    def __init__(self, ui: DeviceTableView, repo: DeviceRepository | None = None):
        super().__init__(ui)
        self.ui = ui
        self.repo = repo
        self.table_name = "device"
        self.current_process = ""
        self.current_process_id: int | None = None
        self.device_state_data: dict[str, dict] | None = None
        self._prev_proxy_index = QModelIndex()
        self._cur_proxy_index = QModelIndex()
        self.dirty_by_process_id: dict[int, bool] = {}
        self._copied_rows: list[dict] = []
        self._etag: dict | None = None

        self.ui.headerMenuRequested.connect(self._on_header_menu)
        self.ui.contextMenuRequested.connect(self._on_context_menu)
        self.ui.insertRequested.connect(self.insert_row)
        self.ui.editRequested.connect(self.update_row)
        self.ui.deleteRequested.connect(self.remove_rows)
        self.ui.copyRequested.connect(self.copy_rows)
        self.ui.pasteRequested.connect(self.paste_rows)
        self.ui.dirtyChanged.connect(self._on_dirty_changed)
        self.ui._wire_model_dirty(self.ui.model_safe())
        self.apply_delegates_and_constraints()

        self.ui.selectionModel().currentChanged.connect(self._on_current_changed)

    def set_repo(
        self,
        repo: DeviceRepository,
        parameter_repo: ParameterRepository,
        io_repo: IORepository,
    ):
        self.repo = repo
        self.parameter_repo = parameter_repo
        self.io_repo = io_repo

    def _on_context_menu(self, selected_rows: list[int], global_pos: QPoint):
        menu, acts = build_device_table_menu(self.ui, selected_rows)
        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen is acts["insert"]:
            self.ui.open_insert_dialog()
        elif chosen is acts["edit"] and selected_rows:
            self.ui.open_edit_dialog(selected_rows[0])
        elif chosen is acts["delete"] and selected_rows:
            self.ui.delete_rows(selected_rows)
        elif chosen is acts["clear"]:
            self.ui.clearSelection()
        elif chosen is acts["copy"]:
            self.ui.copy_selected_from_rows(selected_rows)
        elif chosen is acts["paste"]:
            self.paste_rows(selected_rows)
        elif chosen is acts["csv"]:
            self.export_selected_devices("csv")
        elif chosen is acts["xlsx"]:
            self.export_selected_devices("xlsx")

    def _on_header_menu(self, logical_index: int, global_pos: QPoint):
        menu = QMenu(self.ui)
        asc_action = QAction("오름차순 정렬", self.ui)
        desc_action = QAction("내림차순 정렬", self.ui)

        asc_action.triggered.connect(
            lambda: self.sort_and_commit(logical_index, Qt.AscendingOrder)
        )
        desc_action.triggered.connect(
            lambda: self.sort_and_commit(logical_index, Qt.DescendingOrder)
        )

        menu.addAction(asc_action)
        menu.addAction(desc_action)
        menu.exec_(global_pos)

    def sort_and_commit(self, col: int, order: Qt.SortOrder):
        # 모델의 모든 행을 정렬한다. 프록시가 보여 주는 행으로 모델을 다시 만들면 필터에 가려진
        # device 가 사라지고, set_devices 는 기준점까지 새로 잡아 지운 device·편집 표시·undo 를
        # 지운다. 프록시는 정렬하지 않으므로 화면은 모델 순서 그대로이고 필터도 그대로다.
        model = self.ui.model_safe()
        if model:
            model.sort_rows(col, order)

    def insert_row(self, values: dict):
        model = self.ui.model_safe()
        if not model:
            return
        rows = self.ui._selected_source_rows()
        r = rows[-1] if rows else model.rowCount()
        if model.insert_row(r, values):
            self.logRequested.emit("Device Info: inserted 1 row.")

    def update_row(self, row: int, values: dict):
        model = self.ui.model_safe()
        if not model:
            return
        if model.update_row(row, values):
            self.logRequested.emit(f"Device Info: updated row {row + 1}.")

    def remove_rows(self, rows: list[int]):
        model = self.ui.model_safe()
        if not model:
            return
        removed = model.remove_rows(rows)
        if removed:
            self.logRequested.emit(f"Device Info: deleted {removed} row(s).")

    @report("Copy Failed")
    def copy_rows(self, rows: list[int]):
        model = self.ui.model_safe()
        if not model:
            return

        copied_rows = []
        for row in rows:
            device_row = model.get_device(row)
            device_id = device_row.get("id")
            # 표시 컬럼만 복사한다. id/process_id/version 같은 영속 필드가
            # 붙어 나가면 붙여넣기가 신규 생성이 아니라 기존 행 수정처럼 보인다.
            copied_device = {c: device_row.get(c, "") for c in model._columns}
            related_data = {}
            for tab_name, tab_info in tab_config.items():
                fetched_rows = self.parameter_repo.fetch_by_device(
                    tab_info["table"], tab_info["columns"], device_id
                )
                related_data[tab_name] = fetched_rows

            copied_rows.append({"device": copied_device, "related": related_data})

        self._copied_rows = copied_rows
        self.logRequested.emit(f"Device Info: copied {len(copied_rows)} row(s).")

    @report("Paste Failed")
    def paste_rows(self, rows: list[int]):
        model = self.ui.model_safe()
        if not model or not self._copied_rows:
            return
        if self.is_dirty():
            # 붙여넣기는 바로 저장하고 목록을 다시 읽는다. 그러면 저장하지 않은 다른
            # device 편집이 말없이 사라진다.
            self.notifyRequested.emit(
                "warn",
                "Unsaved Changes",
                "저장하지 않은 device 편집이 있어 붙여넣지 않았다.\n"
                "붙여넣기는 바로 저장하고 목록을 다시 읽으므로 그 편집이 사라진다. 먼저 저장할 것.",
            )
            return

        insert_row = rows[0] + 1 if rows else model.rowCount()
        columns = model._columns
        pasted = 0
        for copied_row in self._copied_rows:
            device_row_dict = copied_row.get("device", {})
            row_data = {col: device_row_dict.get(col, "") for col in columns}
            if not model.insert_row(insert_row, row_data):
                continue
            insert_row += 1
            pasted += 1
            saved = self.save_device(row_data)

            device_id = saved.get("id")
            cell_type = saved.get("celltype", "")
            related_row_dict = copied_row.get("related", {})
            self.pasteRequested.emit(device_id, cell_type, related_row_dict)

        self.refresh_devices()
        if pasted:
            self.logRequested.emit(f"Device Info: pasted {pasted} row(s).")

    @Slot()
    def _on_dirty_changed(self, dirty: bool):
        if self.current_process_id is None:
            return
        self.dirty_by_process_id[self.current_process_id] = dirty

    def is_dirty(self) -> bool:
        if self.current_process_id is None:
            return False
        return self.dirty_by_process_id.get(self.current_process_id, False)

    def set_dirty(self, on: bool):
        if self.current_process_id is None:
            return
        self.dirty_by_process_id[self.current_process_id] = on

    def _on_current_changed(self, new: QModelIndex, old: QModelIndex):
        if self._cur_proxy_index.isValid():
            self._prev_proxy_index = self._cur_proxy_index
        else:
            self._prev_proxy_index = old
        self._cur_proxy_index = new

    def prev_selected_device(self):
        row = self.ui._map_to_source_row(self._prev_proxy_index.row())
        if row < 0:
            return None
        return self.ui.model_safe().get_device(row)

    def last_selected_device(self):
        row = self.ui._map_to_source_row(
            self._cur_proxy_index.row() or self.ui.currentIndex().row()
        )
        if row < 0:
            return None
        return self.ui.model_safe().get_device(row)

    def get_selected_device(self, index: QModelIndex):
        model = self.ui.model_safe()
        source_index = self.ui.proxy_model.mapToSource(index)
        return model.get_device(source_index.row())

    def get_selected_devices(self, fallback_to_all: bool = True):
        model = self.ui.model_safe()
        rows = self.ui._selected_source_rows()
        if rows:
            return [model.get_device(r) for r in rows]
        return model.get_devices() if fallback_to_all else []

    @report("Load Failed")
    def refresh_devices(self):
        if not self.repo:
            return

        if self.current_process_id is None:
            rows: list[dict] = []
        else:
            rows = self.repo.fetch_devices_by_process(self.current_process_id)

        known_names: set[str] = {r["name"] for r in rows}

        visible_devices: list[dict] = []
        for r in rows:
            # repo 가 dict 를 돌려준다. version 도 실려 오는데, 모델의 표시
            # 컬럼이 아니므로 화면에는 나타나지 않고 저장할 때만 쓰인다.
            device = {
                "id": r["id"],
                "process_id": r["process_id"],
                "process_name": self.current_process,
                "name": r["name"],
                "celltype": r["celltype"],
                "description": r["description"],
                "order": r["order"],
                "version": r["version"],
            }
            if not self.device_state_data:
                visible_devices.append(device)
                continue

            # Virtuoso 에서 읽어온 device 목록과 이름이 겹치는 것만 보여준다.
            for name, state in self.device_state_data.items():
                if state.get("S") != "O":
                    continue
                if name in r["name"]:
                    visible_devices.append(device)
                    break

        model = self.ui.model_safe()
        model.update_devices(visible_devices, known_names)
        model.clear_dirty()
        self.set_dirty(False)
        self.remember_etag()

    def remember_etag(self) -> None:
        """"지금 화면이 서버와 같다" 는 기준점을 다시 잡는다.

        여기가 유일한 통로다. 불러오기, device 저장, CSV 임포트, 붙여넣기가 전부
        refresh_devices() 로 끝나고, 탭 저장은 set_device_version() 으로 들어온다.
        기준점을 갱신하지 않으면 내가 방금 한 저장을 보고 "남이 바꿨다" 배너가
        뜬다.
        """
        if self.repo is None or self.current_process_id is None:
            self._etag = None
            return
        try:
            self._etag = self.repo.etag(self.current_process_id)
        except Exception:
            # 기준점을 못 잡으면 폴링이 비교를 건너뛴다. 배너가 안 뜰 뿐이지
            # 저장은 낙관적 잠금이 따로 막는다.
            self._etag = None

    def remembered_etag(self) -> dict | None:
        return self._etag

    def save_device(self, device: dict) -> dict:
        if self.repo is None:
            return device
        saved = self.repo.upsert_device(
            self.current_process_id, device, actor=current_user()
        )
        saved["process_id"] = self.current_process_id
        saved["process_name"] = self.current_process
        return saved

    def save_all(self) -> bool:
        """화면의 device 를 저장한다.

        True: 저장했다(덮어쓰기 포함), 또는 쓸 것이 없었다.
        False: 충돌 대화상자에서 취소(창 닫기 포함)나 다시 읽기를 골랐다, 또는 접속 전이다.
        편집한 행 일부를 CellType 때문에 저장하지 못했을 때도 False 다(나머지는 저장하고
        "Save Skipped" 경고를 띄운다).
        예외는 잡지 않는다(접속 끊김 등). 호출부가 이 값을 보고 "Saved" 를 띄울지 정한다.
        """
        if self.repo is None:
            return False

        valid_celltypes = self._valid_celltypes()

        model = self.ui.model_safe()
        devices = model.get_devices()
        # CellType 이 목록에 없는 행은 저장하지 않는다. 그중 편집한 행은 쓰기 뒤의
        # refresh_devices 가 편집을 지우므로(기준점도 지운다) 쓰기 전에 이름을 모은다.
        skipped_edits: list[str] = []
        to_save: list[dict] = []

        for i, d in enumerate(devices):
            d["order"] = i
            if d.get("celltype") in valid_celltypes:
                to_save.append(d)
            elif model.is_row_changed(i):
                skipped_edits.append(d.get("name", "<Unknown>"))

        deleted = model.deleted_devices()
        # 쓰기가 새 version 을 이 dict 들에 덮어쓰므로 쓰기 전에 잡아 둔다.
        sent_versions = {
            d["id"]: d.get("version") for d in to_save if d.get("id") is not None
        }
        result = self._write_devices(to_save, deleted)
        if result is None:
            return False
        self._emit_version_bumps(sent_versions, result)

        for d in to_save:
            d["process_id"] = self.current_process_id
            d["process_name"] = self.current_process

        # to_save 는 화면의 모든 device 다. 그 길이를 저장 건수로 보고하면
        # 20개 중 1개만 고쳐도 "20개 저장됨" 이 된다. DB 가 실제로 쓴 행 수를
        # 쓴다 (DeviceRepository.SaveResult).
        summary = _describe_save(result)
        self.notifyRequested.emit("info", "Save Complete", summary)
        self.refresh_devices()
        self.logRequested.emit(f"Device Info: {summary}")
        if skipped_edits:
            self.notifyRequested.emit(
                "warn",
                "Save Skipped",
                "CellType 이 목록에 없어 다음 device 의 편집은 저장하지 않았다"
                "(다시 읽으면서 사라졌다).\n"
                + "\n".join(f" - {name}" for name in skipped_edits),
            )
            return False
        return True

    def _emit_version_bumps(
        self, sent_versions: dict[int, int | None], result: SaveResult
    ) -> None:
        """이 쓰기가 version 을 바꾼 행마다 deviceVersionBumped 를 낸다.

        탭이 같은 device 를 열어 두고 있으면 이 version 을 따라가야 다음 탭 저장이 나 자신과
        충돌하지 않는다. 다시 읽은 목록이 아니라 쓰기가 돌려준 version 을 쓴다. 다시 읽은
        version 에는 그 사이 남이 저장한 것이 섞일 수 있다. 새로 넣은 행(쓰기 전에 id 가
        없었다)과 값이 같아 쓰이지 않은 행은 내지 않는다.
        """
        for d in result.devices:
            old = sent_versions.get(d.get("id"))
            if old is None or d.get("version") == old:
                continue
            self.deviceVersionBumped.emit(d["id"], old, d["version"])

    def _write_devices(
        self, to_save: list[dict], deleted: dict[int, int]
    ) -> SaveResult | None:
        """저장하고, 충돌하면 사용자에게 물어본다. 취소했으면 None."""
        if not to_save and not deleted:
            return SaveResult()

        def write(force: bool):
            # 워커 스레드에서 돈다. advisory lock 과 FOR UPDATE 때문에 다른
            # 사용자 뒤에서 lock_timeout(기본 5초) 까지 기다릴 수 있다.
            return self.repo.upsert_devices(
                self.current_process_id,
                to_save,
                deleted=deleted,
                actor=current_user(),
                force=force,
            )

        try:
            return run_blocking(lambda: write(False), self)
        except StaleWriteError as e:
            # 다이얼로그는 run_blocking 이 끝난 뒤 GUI 스레드에서 뜬다.
            choice = ask_conflict(self.ui, e.conflicts)
            if choice == RELOAD:
                self.refresh_devices()
                self.logRequested.emit("Save conflict: 서버 내용으로 다시 읽었다.")
                return None
            if choice == OVERWRITE:
                forced = run_blocking(lambda: write(True), self)
                self.logRequested.emit("Save conflict: 내 변경으로 덮어썼다.")
                return forced
            self.logRequested.emit("Save conflict: 저장을 취소했다.")
            return None

    def set_device_version(self, device_id: int, version: int) -> None:
        """탭 저장 등으로 올라간 version 을 모델에 반영한다."""
        self.ui.model_safe().set_version(device_id, version)
        # 탭 저장은 device 목록을 다시 읽지 않지만 device.version 은 올린다.
        # 여기서 기준점을 다시 잡지 않으면 내 저장이 남의 변경으로 보인다.
        self.remember_etag()

    @report("Export Failed")
    def export_selected_devices(self, fmt: str):
        selected = self.get_selected_devices()
        if not selected:
            self.notifyRequested.emit("warn", "Export", "No device selected.")
            return

        device_info = [
            {
                "id": d.get("id"),
                "process_id": d.get("process_id"),
                "process_name": d.get("process_name"),
                "name": d.get("name"),
                "celltype": d.get("celltype"),
            }
            for d in selected
        ]

        headers, rows = self.io_repo.fetch_export_data(device_info)
        suggested = f"{(self.current_process or 'process')}.{fmt}"
        save_path = self.ui._ask_export_path(suggested)
        if not save_path:
            return

        # 쓰다 실패하면 예외가 올라간다. @report 가 이유까지 담아 상자로 띄운다.
        if fmt.lower() == "csv":
            write_csv(save_path, headers, rows)
            title = "Save CSV"
        else:
            write_xlsx(save_path, headers, rows)
            title = "Save XLSX"

        leaf = Path(save_path).name
        self.notifyRequested.emit("info", title, f"Success!\n - {leaf}")
        self.logRequested.emit(f"Exported {len(rows)} row(s) to {leaf}.")

    def set_current_process(self, process: str):
        self.current_process = process

    def set_current_process_id(self, process_id: int):
        self.current_process_id = process_id

    def _valid_celltypes(self) -> list[str]:
        return (
            delegate_config.get(self.table_name, {})
            .get("celltype", {})
            .get("items", [])
        )

    def apply_delegates_and_constraints(self):
        model = self.ui.model_safe()
        columns = model._columns
        table_cfg = delegate_config.get(self.table_name, {})

        for col_name, cfg in table_cfg.items():
            if col_name not in columns:
                continue

            if cfg.get("required", False):
                model.set_required_column(col_name)

            items = cfg.get("items") or []
            if items:
                delegate = ComboBoxDelegate(
                    items=items,
                    required=cfg.get("required", False),
                    strict=cfg.get("strict", False),
                    parent=self.ui,
                )
                self.ui.install_delegate(col_name, delegate)

    def undo(self) -> bool:
        model = self.ui.model_safe()
        if model and model.undo():
            self.logRequested.emit("Device Info: undo.")
            return True
        return False

    def redo(self) -> bool:
        model = self.ui.model_safe()
        if model and model.redo():
            self.logRequested.emit("Device Info: redo.")
            return True
        return False
