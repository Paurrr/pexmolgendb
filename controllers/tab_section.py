from PySide6.QtCore import QObject, Signal, Slot, QPoint
from views.tab_section import TabSection
from service.repo.parameter import ParameterRepository
from utils.menus import build_parameter_table_menu
from models.generic_table import GenericTableModel
from delegates.combo_box import ComboBoxDelegate
from config.config import delegate_config


class TabSectionController(QObject):
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)
    deviceChanged = Signal(object, object)

    def __init__(self, ui: TabSection, repo: ParameterRepository):
        super().__init__(ui)
        self.ui = ui
        self.repo = repo
        self.table_name = self.ui.table_name
        self.columns = self.ui.columns
        self.headers = self.ui.headers
        self.device_id: int | None = None
        self.dirty_by_device: dict[int, bool] = {}
        self.model_by_device: dict[int, GenericTableModel] = {}
        self._copied_rows: list[dict] = []
        self.model: GenericTableModel | None = None

        self.deviceChanged.connect(ui.on_device_changed)
        self.ui.contextMenuRequested.connect(self._on_context_menu)
        self.ui.insertRequested.connect(self.insert_row)
        self.ui.editRequested.connect(self.update_row)
        self.ui.deleteRequested.connect(self.remove_rows)
        self.ui.copyRequested.connect(self.copy_rows)
        self.ui.pasteRequested.connect(self.paste_rows)
        self.ui.dirtyChanged.connect(self._on_dirty_changed)

    def _row_to_dict(self, src_row: int) -> dict:
        m = self.model
        return {col: m.data(m.index(src_row, c)) for c, col in enumerate(self.columns)}

    def _on_context_menu(self, selected_rows: list[int], global_pos: QPoint):
        menu, acts = build_parameter_table_menu(self.ui, selected_rows)
        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen is acts["insert"]:
            self.ui.open_insert_dialog()
        elif chosen is acts["edit"] and selected_rows:
            old_values = self._row_to_dict(selected_rows[0])
            self.ui.open_edit_dialog(selected_rows[0], old_values)
        elif chosen is acts["delete"] and selected_rows:
            self.ui.delete_rows(selected_rows)
        elif chosen is acts["clear"]:
            self.ui.table_view.clearSelection()
        elif chosen is acts["copy"]:
            self.ui.copy_selected_from_rows(selected_rows)
        elif chosen is acts["paste"]:
            self.paste_rows([])

    def set_device(self, device_id: int, device_celltype: str):
        self.device_id = device_id
        self.device_celltype = device_celltype
        self.deviceChanged.emit(device_id, device_celltype)
        self.update_model()

    def _paste_rows(self, start_row, rows):
        model = self.model
        inserted = 0
        for row_dict in rows:
            row_data = {col: row_dict.get(col, "") for col in self.columns}
            if model.insert_row(start_row, row_data):
                start_row += 1
                inserted += 1
        return inserted

    def insert_row(self, values: dict):
        if not self.model:
            return
        rows = self.ui.table_view._selected_rows()
        r = rows[-1] if rows else self.model.rowCount()
        if self.model.insert_row(r, values):
            self.logRequested.emit(f"{self.ui.title}: inserted 1 row.")

    def update_row(self, row: int, values: dict):
        if not self.model:
            return
        if self.model.update_row(row, values):
            self.logRequested.emit(f"{self.ui.title}: updated row {row + 1}.")

    def remove_rows(self, rows: list[int]):
        if not self.model:
            return
        if self.model.remove_rows(rows):
            self.logRequested.emit(f"{self.ui.title}: deleted {len(rows)} row(s).")

    def copy_rows(self, rows: list[int]):
        if not self.model:
            return
        data = self.model.get_data()
        self._copied_rows = [data[idx].copy() for idx in rows]
        self.logRequested.emit(f"{self.ui.title}: copied {len(self._copied_rows)} row(s).")

    def paste_rows(self, rows: list[int]):
        if not self._copied_rows or not self.model:
            return

        insert_row = rows[0] + 1 if rows else self.model.rowCount()
        inserted = self._paste_rows(insert_row, self._copied_rows)
        if inserted:
            self.logRequested.emit(f"{self.ui.title}: pasted {inserted} row(s).")

    def save(self):
        if self.device_id is None or self.device_id < 0:
            return
        rows = self.get_buffer_rows()
        self.repo.replace_all_for_device(
            self.table_name, self.columns, self.device_id, rows
        )
        self.set_dirty(False)
        self.logRequested.emit(f"{self.ui.title}: saved {len(rows)} row(s).")

    @Slot()
    def _on_dirty_changed(self, dirty: bool):
        if self.device_id is None:
            return
        self.dirty_by_device[self.device_id] = dirty

    def is_dirty(self) -> bool:
        if self.device_id is None:
            return False
        return self.dirty_by_device.get(self.device_id, False)

    def set_dirty(self, on: bool):
        if self.device_id is None:
            return
        self.dirty_by_device[self.device_id] = on
        self.ui.mark_dirty_ui(on)

    def get_buffer_rows(self) -> list[dict]:
        return self.model.get_data()

    def get_or_create_model(self, device_id: int) -> GenericTableModel:
        if device_id not in self.model_by_device:
            m = GenericTableModel(
                self.headers,
                self.columns,
                self.table_name,
                delegate_config=delegate_config,
            )
            self.ui._wire_model_dirty(m)
            self.apply_delegates_and_constraints(m)
            self.model_by_device[device_id] = m
        return self.model_by_device[device_id]

    def update_model(self):
        if not self.device_id:
            self.clear_model()
            return

        model = self.get_or_create_model(self.device_id)
        model.set_device_celltype(self.device_celltype)
        rows = self.repo.fetch_by_device(self.table_name, self.columns, self.device_id)
        self.bind_model(model)
        model.set_data(rows)
        self.set_dirty(False)

    def bind_model(self, model: GenericTableModel | None):
        self.model = model
        self.ui.table_view.setModel(model)

    def clear_model(self):
        self.bind_model(None)

    def redo_row(self):
        if self.model and self.model.redo():
            self.logRequested.emit(f"{self.ui.title}: redo.")
            return True
        return False

    def undo_row(self):
        if self.model and self.model.undo():
            self.logRequested.emit(f"{self.ui.title}: undo.")
            return True
        return False

    def apply_delegates_and_constraints(self, model: GenericTableModel):
        table_cfg = delegate_config.get(self.ui.table_name, {})

        for col_name, cfg in table_cfg.items():
            if col_name not in self.columns:
                continue

            if cfg.get("required", False):
                model.set_required_column(col_name)

            items = cfg.get("items") or []
            if items or cfg.get("items_by_celltype"):
                delegate = ComboBoxDelegate(
                    items=items,
                    items_by_celltype=cfg.get("items_by_celltype", {}),
                    required=cfg.get("required", False),
                    strict=cfg.get("strict", False),
                    parent=self.ui,
                )
                self.ui.install_delegate(model, col_name, delegate)
