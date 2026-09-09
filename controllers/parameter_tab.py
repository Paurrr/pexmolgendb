from PySide6.QtCore import QObject, Signal
from config.config import tab_config
from views.parameter_tab import ParameterTab
from views.tab_section import TabSection
from controllers.tab_section import TabSectionController
from service.repo.parameter import ParameterRepository
from dialogs.tab_selector import TabSelectorDialog


class ParameterTabController(QObject):
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)

    def __init__(self, ui: ParameterTab, repo: ParameterRepository | None = None):
        super().__init__(ui)
        self.ui = ui
        self.repo = repo
        self._sections: dict[str, TabSectionController] = {}
        self.ui.currentChanged.connect(self.ui.on_tab_changed)
        self.ui.tabBarClicked.connect(self.on_tab_clicked)
        self.ui.summaryRequested.connect(self.refresh_summary)
        self.ui.summarySourceActivated.connect(self._open_source_from_summary)

    def set_repo(self, repo: ParameterRepository):
        self.repo = repo

    def _attach_section(self, name: str, tab_view: TabSection):
        ctrl = TabSectionController(tab_view, repo=self.repo)
        ctrl.setParent(tab_view)
        ctrl.logRequested.connect(self.logRequested)
        tab_view.dirtyChanged.connect(lambda *_: self._refresh_summary_if_visible())
        self._sections[name] = ctrl

    def section(self, name: str) -> TabSectionController | None:
        return self._sections.get(name)

    def is_dirty(self) -> bool:
        return any(sec.is_dirty() for sec in self._sections.values())

    def sections_for_device(self, device_id: int):
        for sec in self.ui.iter_sections():
            if sec.device_id == device_id:
                yield sec

    def save_all(self):
        saved_table: list[str] = []
        for sec in self._sections.values():
            if sec.is_dirty():
                sec.save()
                saved_table.append(sec.table_name)

        if saved_table:
            self.notifyRequested.emit(
                "info", "Saved", f"{', '.join(saved_table)} saved."
            )
            self.logRequested.emit(f"Saved tab data: {', '.join(saved_table)}.")

    def discard_all(self):
        for sec in self._sections.values():
            if sec.is_dirty():
                sec.update_model()
                self.logRequested.emit(f"Discarded changes in {sec.ui.title}.")

    def set_device_to_section(self, device_id: int, device_celltype: str | None = None):
        for sec in self._sections.values():
            sec.set_device(device_id, device_celltype)
        self._refresh_summary_if_visible()

    def clear_sections(self):
        self._sections.clear()

    def _clear_tabs(self):
        for sec in self._sections.values():
            sec.set_device(None, None)
        self.refresh_summary()

    def rebuild_all_sections(self):
        self.clear_sections()
        self.ui.rebuild_tabs(tab_config, on_created=self._attach_section)
        self.refresh_summary()

    def on_tab_clicked(self, index):
        if self.ui.tabText(index) != "+":
            return
        options = [name for name in tab_config if self.ui.find_tab(name) == -1]
        if not options:
            return
        dialog = TabSelectorDialog(options, self.ui)
        if dialog.exec_():
            selected = dialog.get_selected_tab()
            if selected:
                self.ui.add_tab(selected)

    def paste_payload(self, device_id: int, device_type: str, payload: dict[str, list]):
        self.set_device_to_section(device_id, device_type)
        for tab_name, rows in payload.items():
            if sec := self._sections.get(tab_name):
                sec._paste_rows(0, rows)
                sec.save()

    def undo_current(self) -> bool:
        ctrl = self._current_section_controller()
        return ctrl.undo_row() if ctrl else False

    def redo_current(self) -> bool:
        ctrl = self._current_section_controller()
        return ctrl.redo_row() if ctrl else False

    def _current_section_controller(self) -> TabSectionController | None:
        section = getattr(self.ui, "current_tab_section", None)
        if not section:
            return None
        for ctrl in self._sections.values():
            if ctrl.ui is section:
                return ctrl
        return None

    def refresh_summary(self):
        summary_rows = []

        for tab_name, ctrl in self._sections.items():
            model = ctrl.model
            if not model:
                continue

            section_started = False
            for row_idx, row_data in enumerate(model.get_data()):
                for col_idx, (header, col_name) in enumerate(
                    zip(ctrl.headers, ctrl.columns)
                ):
                    summary_rows.append(
                        {
                            "section": tab_name if not section_started else "",
                            "row": str(row_idx + 1),
                            "column": header,
                            "value": row_data.get(col_name, ""),
                            "tab_name": tab_name,
                            "source_row": row_idx,
                            "source_col": col_idx,
                        }
                    )
                    section_started = True

        self.ui.set_summary_rows(summary_rows)

    def _refresh_summary_if_visible(self):
        if self.ui.currentWidget() is self.ui.summary_view:
            self.refresh_summary()

    def _open_source_from_summary(self, tab_name: str, row: int, col: int):
        self.ui.show_source_cell(tab_name, row, col)
        self.logRequested.emit(
            f"Summary: opened {tab_name} row {row + 1}, column {col + 1}."
        )
