from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QTabWidget, QWidget

from genviewer.views.parameter_summary import ParameterSummaryView
from genviewer.views.tab_section import TabSection


class ParameterTab(QTabWidget):
    summaryRequested = Signal()
    summarySourceActivated = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(False)
        self.setDocumentMode(True)
        self.tabBar().setExpanding(False)
        self.setUsesScrollButtons(True)
        self.summary_view = ParameterSummaryView(self)
        self.summary_view.sourceActivated.connect(self.summarySourceActivated)
        self.addTab(self.summary_view, "Summary")
        self.addTab(QWidget(), "+")

    def rebuild_tabs(self, available_tabs: dict, on_created=None):
        self.clear()
        self.addTab(self.summary_view, "Summary")

        for name, cfg in available_tabs.items():
            self._insert_section(self.count(), name, cfg, on_created)

        self.addTab(QWidget(), "+")
        if self.count() > 2:
            self.setCurrentIndex(1)

    def add_tab(self, name: str, cfg: dict, on_created=None) -> TabSection:
        """"+" 에서 고른 탭을 "+" 바로 앞에 붙이고 현재 탭으로 만든다.

        이미 있는 이름이면 새로 만들지 않고 그 섹션을 돌려준다.
        """
        idx = self.find_tab(name)
        if idx != -1:
            return self.widget(idx)
        section = self._insert_section(self.count() - 1, name, cfg, on_created)
        self.setCurrentWidget(section)
        return section

    def _insert_section(self, index: int, name: str, cfg: dict, on_created) -> TabSection:
        # rebuild_tabs 와 add_tab 이 함께 쓴다. 둘이 어긋나면 같은 탭이 경로에 따라 다르게 동작한다.
        section = TabSection(
            columns=cfg["columns"],
            headers=cfg["headers"],
            table_name=cfg["table"],
            title=name,
            parent=self,
        )
        section.setObjectName(name)
        self.insertTab(index, section, name)

        if callable(on_created):
            on_created(name, section)

        if hasattr(section, "dirtyChanged"):
            section.dirtyChanged.connect(
                lambda on, w=section: self._set_dirty_marker(w, on)
            )
        return section

    def set_summary_rows(self, rows: list[dict]):
        self.summary_view.set_rows(rows)

    def show_source_cell(self, tab_name: str, row: int, col: int):
        idx = self.find_tab(tab_name)
        if idx < 0:
            return

        self.setCurrentIndex(idx)
        section = self.widget(idx)
        if not isinstance(section, TabSection):
            return

        model = section.table_view.model()
        if not model or row >= model.rowCount() or col >= model.columnCount():
            return

        target = model.index(row, col)
        section.table_view.selectRow(row)
        section.table_view.setCurrentIndex(target)
        section.table_view.scrollTo(target)

    @Slot()
    def _set_dirty_marker(self, child: QWidget, dirty: bool):
        idx = self.indexOf(child)
        if idx < 0:
            return
        base = self.tabText(idx).rstrip(" *")
        self.setTabText(idx, f"{base} *" if dirty else base)

    def iter_sections(self):
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, TabSection):
                yield w

    def find_tab(self, name):
        for i in range(self.count()):
            if self.widget(i) is self.summary_view:
                continue
            if self.tabText(i).rstrip(" *") == name:
                return i
        return -1

    def on_tab_changed(self, index):
        widget = self.widget(index)
        if isinstance(widget, TabSection):
            self.current_tab_section = widget
        elif widget is self.summary_view:
            self.current_tab_section = None
            self.summaryRequested.emit()
        else:
            self.current_tab_section = None
