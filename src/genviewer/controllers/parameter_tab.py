from PySide6.QtCore import QObject, Signal

from genviewer.config.config import tab_config
from genviewer.controllers.tab_section import TabSectionController
from genviewer.dialogs.conflict import OVERWRITE, RELOAD, ask_conflict
from genviewer.dialogs.tab_selector import TabSelectorDialog
from genviewer.service.errors import StaleWriteError
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.utils.background import run_blocking
from genviewer.utils.user import current_user
from genviewer.views.parameter_tab import ParameterTab
from genviewer.views.tab_section import TabSection


class ParameterTabController(QObject):
    notifyRequested = Signal(str, str, str)
    logRequested = Signal(str)
    deviceVersionChanged = Signal(int, int)

    def __init__(self, ui: ParameterTab, repo: ParameterRepository | None = None):
        super().__init__(ui)
        self.ui = ui
        self.repo = repo
        self._sections: dict[str, TabSectionController] = {}
        self.current_device_id: int | None = None
        self.current_version: int | None = None
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
        # 이 줄이 없어서 탭 섹션이 알리는 것은 전부 바닥에 떨어지고 있었다.
        ctrl.notifyRequested.connect(self.notifyRequested)
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

    def save_all(self) -> bool:
        """dirty 탭을 한 번에 저장한다.

        True: 저장했다(덮어쓰기 포함), 또는 dirty 탭이 없었다.
        False: 충돌 대화상자에서 취소(창 닫기 포함)나 다시 읽기를 골랐다, 또는 접속 전이거나
        고른 device 가 없다.
        예외는 잡지 않는다(접속 끊김 등). 호출부가 이 값을 보고 넘어갈지 정한다.
        """
        dirty = [sec for sec in self._sections.values() if sec.is_dirty()]
        if not dirty:
            return True
        if not self._write(dict(sec.payload_fragment() for sec in dirty)):
            return False

        # mark_saved 가 기준점을 옮기므로 요약을 먼저 만든다.
        summary = "\n".join(
            f"{sec.ui.title}: {sec.describe_save()}" for sec in dirty
        )
        for sec in dirty:
            sec.mark_saved()
        names = [sec.table_name for sec in dirty]
        self.notifyRequested.emit("info", "Saved", summary)
        self.logRequested.emit(f"Saved tab data: {', '.join(names)}.")
        return True

    def _write(self, payload: dict) -> bool:
        """탭들을 한 트랜잭션으로 쓴다. 충돌하면 사용자에게 물어본다."""
        if self.repo is None or self.current_device_id is None:
            return False
        try:
            self._apply(payload)
            return True
        except StaleWriteError as e:
            choice = ask_conflict(self.ui, e.conflicts)
            if choice == RELOAD:
                for sec in self._sections.values():
                    sec.update_model()
                self.logRequested.emit("Tab conflict: 서버 내용으로 다시 읽었다.")
                return False
            if choice == OVERWRITE:
                self._apply(payload, force=True)
                self.logRequested.emit("Tab conflict: 내 변경으로 덮어썼다.")
                return True
            self.logRequested.emit("Tab conflict: 저장을 취소했다.")
            return False

    def _apply(self, payload: dict, *, force: bool = False) -> None:
        # 탭 전부를 한 트랜잭션으로 쓴다. 부모 device 행에 FOR UPDATE 를 걸므로
        # 다른 사용자 뒤에서 대기할 수 있어 워커 스레드에서 돌린다.
        version = run_blocking(
            lambda: self.repo.replace_many_for_device(
                self.current_device_id,
                payload,
                expected_version=self.current_version,
                actor=current_user(),
                force=force,
            ),
            self,
        )
        # 탭 저장도 device 의 version 을 올린다. 반영하지 않으면 다음 저장이
        # 엉뚱하게 충돌한다.
        self.current_version = version
        self.deviceVersionChanged.emit(self.current_device_id, version)

    def discard_all(self):
        for sec in self._sections.values():
            if sec.is_dirty():
                sec.update_model()
                self.logRequested.emit(f"Discarded changes in {sec.ui.title}.")

    def set_device_to_section(
        self,
        device_id: int,
        device_celltype: str | None = None,
        version: int | None = None,
    ):
        self.current_device_id = device_id
        self.current_version = version
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

    def paste_payload(
        self,
        device_id: int,
        device_type: str,
        payload: dict[str, list],
        version: int | None = None,
    ):
        self.set_device_to_section(device_id, device_type, version)
        pasted = []
        for tab_name, rows in payload.items():
            if sec := self._sections.get(tab_name):
                sec._paste_rows(0, rows)
                pasted.append(sec)
        if not pasted:
            return
        # N번이 아니라 한 번. version 은 한 번만 올라간다.
        if self._write(dict(sec.payload_fragment() for sec in pasted)):
            for sec in pasted:
                sec.mark_saved()

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
                    zip(ctrl.headers, ctrl.columns, strict=True)
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
