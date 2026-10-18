from PySide6.QtCore import QItemSelectionModel, QObject, QPoint, Signal, Slot

from genviewer.config.config import delegate_config
from genviewer.delegates.combo_box import ComboBoxDelegate
from genviewer.models.generic_table import GenericTableModel
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.utils.menus import build_parameter_table_menu
from genviewer.utils.reporting import report
from genviewer.views.tab_section import TabSection


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
        # 콤보 컬럼마다 하나. 후보는 delegate 가 index.model() 의 celltype 으로 고르므로 모든 device
        # 모델이 같이 쓴다.
        self._combo_delegates: dict[str, ComboBoxDelegate] = {}

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

    def payload_fragment(self) -> tuple[str, tuple[list[str], list[dict]]]:
        """이 탭이 저장할 내용. ParameterTabController 가 모아서 한 번에 쓴다.

        탭이 직접 repo 를 부르면 안 된다. version 이 device 단위라서, 첫 탭의
        저장이 version 을 올리는 순간 두 번째 탭이 자기 검사에 실패한다.
        """
        return self.table_name, (self.columns, self.get_buffer_rows())

    def mark_saved(self) -> None:
        self.set_dirty(False)
        self.logRequested.emit(f"{self.ui.title}: {self.describe_save()}")
        # 다음 저장이 이번 저장분까지 "바뀐 행" 으로 세지 않게 기준점을 옮긴다.
        if self.model:
            self.model.reset_baseline()

    def describe_save(self) -> str:
        """무엇이 바뀌었는지와 무엇이 실제로 쓰였는지를 같이 말한다.

        탭 저장은 그 탭의 행을 전부 지우고 다시 넣는다 (ParameterRepository
        .replace_many_for_device). 자식 행에는 version 이 없고 순서가 곧 CSV
        컬럼 순서라, 행 단위로 갈라 쓰려면 순서 컬럼이 따로 있어야 한다.
        그래서 "N개 저장" 이라고만 하면 이번에는 반대 방향으로 사실과 달라진다.
        바뀐 수와 다시 쓴 수를 둘 다 남긴다.
        """
        total = len(self.get_buffer_rows())
        if not self.model:
            return f"saved {total} row(s)."
        added, removed = self.model.change_counts()
        changed = max(added, removed)
        return f"{changed} row(s) changed ({total} rewritten)."

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

    # 행을 하나 고르는 것만으로 여기서 SQL 이 돈다. 서버가 내려가 있으면 클릭
    # 한 번이 트레이스백이 됐다.
    @report("Load Failed")
    def update_model(self):
        if not self.device_id:
            self.clear_model()
            return

        model = self.get_or_create_model(self.device_id)
        model.set_device_celltype(self.device_celltype)
        try:
            rows = self.repo.fetch_by_device(self.table_name, self.columns, self.device_id)
        except Exception:
            # 표에는 아직 이전 device 의 모델(다시 읽기라면 버리려던 편집)이 붙어 있다. 그대로
            # 두면 그 행을 고쳐 저장했을 때 이 device 에 통째로 써진다. 읽지 못한 캐시 모델도
            # 붙이지 않는다("행 없음" 으로 보이고, 저장하면 서버 행을 지운다). 비우고 dirty 를
            # 풀어 저장 대상에서 뺀다. 다시 올려야 @report 가 "Load Failed" 를 띄운다.
            self.clear_model()
            self.set_dirty(False)
            raise
        self.bind_model(model)
        model.set_data(rows)
        self.set_dirty(False)

    def bind_model(self, model: GenericTableModel | None):
        self.model = model
        view = self.ui.table_view
        view.setModel(model)
        # setModel 은 표와 두 머리글에 QItemSelectionModel 을 하나씩 새로 만들고(머리글은 곧
        # 표의 것을 같이 쓴다) 옛 것을 지우지 않는다. device 를 고를 때마다 셋씩 쌓였다.
        # 지금 쓰는 것만 남긴다.
        in_use = (
            view.selectionModel(),
            view.horizontalHeader().selectionModel(),
            view.verticalHeader().selectionModel(),
        )
        for sel in view.findChildren(QItemSelectionModel):
            if sel not in in_use:
                sel.deleteLater()

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

            # 컬럼 delegate 는 표에 붙어 있어 모델을 바꿔도 남는다. 새 모델마다 만들면 밀려난
            # delegate 가 섹션의 자식으로 본 device 수만큼 쌓였다.
            if col_name in self._combo_delegates:
                continue
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
                self._combo_delegates[col_name] = delegate
