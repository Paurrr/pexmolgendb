from pathlib import Path

from PySide6.QtCore import QModelIndex, QObject, QPoint, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from config.config import delegate_config, tab_config
from delegates.combo_box import ComboBoxDelegate
from dialogs.conflict import OVERWRITE, RELOAD, ask_conflict
from service.errors import StaleWriteError
from service.repo.device import DeviceRepository
from service.repo.io import IORepository
from service.repo.parameter import ParameterRepository
from utils.exporter import write_csv, write_xlsx
from utils.menus import build_device_table_menu
from utils.user import current_user
from views.device_table import DeviceTableView


class DeviceTableController(QObject):
    pasteRequested = Signal(object, str, dict)
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)

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
        self.ui.proxy_model.sort(col, order)
        model = self.ui.model_safe()
        sorted_data = []
        for row in range(self.ui.proxy_model.rowCount()):
            proxy_index = self.ui.proxy_model.index(row, 0)
            source_index = self.ui.proxy_model.mapToSource(proxy_index)
            sorted_data.append(model.get_devices()[source_index.row()])

        model.set_devices(sorted_data)
        self.ui.proxy_model.sort(-1)
        self.ui.proxy_model.invalidate()

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

    def paste_rows(self, rows: list[int]):
        model = self.ui.model_safe()
        if not model or not self._copied_rows:
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

    def save_device(self, device: dict) -> dict:
        if self.repo is None:
            return device
        saved = self.repo.upsert_device(
            self.current_process_id, device, actor=current_user()
        )
        saved["process_id"] = self.current_process_id
        saved["process_name"] = self.current_process
        return saved

    def save_all(self):
        if self.repo is None:
            return

        valid_celltypes = self._valid_celltypes()

        model = self.ui.model_safe()
        devices = model.get_devices()
        invalid_devices: list[str] = []
        to_save: list[dict] = []

        for i, d in enumerate(devices):
            d["order"] = i
            if d.get("celltype") in valid_celltypes:
                to_save.append(d)
            else:
                invalid_devices.append(d.get("name", "<Unknown>"))

        deleted = model.deleted_devices()
        if not self._write_devices(to_save, deleted):
            return

        for d in to_save:
            d["process_id"] = self.current_process_id
            d["process_name"] = self.current_process

        self.notifyRequested.emit(
            "info", "Save Complete", f"{len(to_save)} device(s) saved to DB."
        )
        self.refresh_devices()
        self.logRequested.emit(f"Device Info: saved {len(to_save)} device(s).")

    def _write_devices(self, to_save: list[dict], deleted: dict[int, int]) -> bool:
        """저장하고, 충돌하면 사용자에게 물어본다. 저장했으면 True."""
        if not to_save and not deleted:
            return True
        try:
            self.repo.upsert_devices(
                self.current_process_id, to_save, deleted=deleted, actor=current_user()
            )
            return True
        except StaleWriteError as e:
            choice = ask_conflict(self.ui, e.conflicts)
            if choice == RELOAD:
                self.refresh_devices()
                self.logRequested.emit("Save conflict: 서버 내용으로 다시 읽었다.")
                return False
            if choice == OVERWRITE:
                self.repo.upsert_devices(
                    self.current_process_id,
                    to_save,
                    deleted=deleted,
                    actor=current_user(),
                    force=True,
                )
                self.logRequested.emit("Save conflict: 내 변경으로 덮어썼다.")
                return True
            self.logRequested.emit("Save conflict: 저장을 취소했다.")
            return False

    def set_device_version(self, device_id: int, version: int) -> None:
        """탭 저장 등으로 올라간 version 을 모델에 반영한다."""
        self.ui.model_safe().set_version(device_id, version)

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

        if fmt.lower() == "csv":
            ok = write_csv(save_path, headers, rows)
            title = "Save CSV"
        else:
            ok = write_xlsx(save_path, headers, rows)
            title = "Save XLSX"

        leaf = Path(save_path).name
        if ok:
            self.notifyRequested.emit("info", title, f"Success!\n - {leaf}")
            self.logRequested.emit(f"Exported {len(rows)} row(s) to {leaf}.")
        else:
            self.notifyRequested.emit("error", title, f"Fail\n - {leaf}")

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
