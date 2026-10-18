"""변경 이력 화면의 배선.

변경 감지 배너(controllers/device_tab.py)와 같은 뼈대를 쓴다: QTimer 로 10초마다
Task 를 띄우고, 결과를 시그널로 받고, 연달아 실패하면 멈춘다. run_blocking 은
쓰지 않는다 - 결과를 기다리는 사람이 없는데 입력을 막으면 안 된다.

표 모델은 새로 만들지 않고 GenericTableModel 을 editable=False 로 쓴다.
"""

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from genviewer.models.generic_table import GenericTableModel
from genviewer.service.errors import user_message
from genviewer.service.repo import audit
from genviewer.service.repo.audit import AuditRepository
from genviewer.service.repo.process import ProcessRepository
from genviewer.utils.background import Task, is_busy
from genviewer.views.history_tab import COLUMNS, HEADERS, HistoryTab

log = logging.getLogger(__name__)

# device_tab 의 변경 감지와 같은 주기. 이력도 같은 속도로 따라오면 충분하다.
POLL_INTERVAL_MS = 10_000
POLL_FAILURE_LIMIT = 3

# 한 번에 들고 오는 줄 수. 더 옛날 것은 기간을 넓히거나 genviewer log 를 쓴다.
PAGE = 500


def _display(row: dict) -> dict:
    return {
        "at": row["at"].strftime("%Y-%m-%d %H:%M:%S"),
        "actor": row["actor"] or "(모름)",
        "source": row["source"],
        "where": audit.where_of(row),
        "summary": row["summary"],
    }


class HistoryTabController(QObject):
    logRequested = Signal(str)

    def __init__(self, ui: HistoryTab, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.repo: AuditRepository | None = None
        self.process_repo: ProcessRepository | None = None

        # 화면에 보이는 순서(최신이 위)로 들고 있는다. 표의 행 번호가 곧 이
        # 목록의 첨자라서 선택한 줄의 원본을 바로 찾을 수 있다.
        self._rows: list[dict] = []
        self._task: Task | None = None
        # 도는 동안 다시 읽어 달라는 요청(필터·DB 변경)이 왔다. 끝나면 그때의 필터로 한 번
        # 더 읽는다.
        self._pending = False
        # 도는 작업이 시작된 뒤 필터나 DB 가 바뀌었다. 그 결과·실패는 화면과 맞지 않아 버린다.
        self._stale = False
        self._failures = 0

        self.model = GenericTableModel(HEADERS, COLUMNS, editable=False)
        ui.set_model(self.model)

        ui.refresh_btn.clicked.connect(self.reload)
        ui.range_cb.currentIndexChanged.connect(self.reload)
        ui.process_cb.currentIndexChanged.connect(self.reload)
        ui.who_field.returnPressed.connect(self.reload)
        ui.find_field.returnPressed.connect(self.reload)
        ui.auto_cb.toggled.connect(self._on_auto_toggled)
        ui.table.selectionModel().selectionChanged.connect(self._on_selected)

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # 수명
    # ------------------------------------------------------------------

    def set_db(self, db) -> None:
        """Device 화면이 붙거나 끊을 때 같은 Database 를 받는다."""
        self._timer.stop()
        if db is None:
            self.repo = None
            self.process_repo = None
            self._pending = False
            self._stale = True
            self._rows = []
            self.model.set_data([])
            self.ui.show_detail("")
            self.ui.show_count("데이터베이스에 붙어 있지 않다.")
            return

        self.repo = AuditRepository(db)
        self.process_repo = ProcessRepository(db)
        self._failures = 0
        # 옛 DB 로 도는 작업이 있으면 보류가 되고, 그 작업이 끝난 뒤 새 DB 로 읽는다.
        self.reload()
        if self.ui.auto_cb.isChecked():
            self._timer.start()

    def shutdown(self) -> None:
        self._timer.stop()
        # 기다린 작업의 finished 는 나중에 온다. 그때 보류된 다시 읽기를 띄우지 않는다.
        self._pending = False
        # 아직 도는 작업이 커넥션을 들고 있을 수 있다. 그대로 풀을 닫으면 터진다.
        if self._task is not None:
            self._task.wait()
            self._task = None

    # ------------------------------------------------------------------
    # 읽기
    # ------------------------------------------------------------------

    @Slot()
    def _tick(self) -> None:
        """자동 갱신. 사람이 한 줄을 골라 읽는 중이면 건드리지 않는다.

        표가 10초마다 통째로 다시 그려지면 선택이 풀려서 상세창이 비고, 읽던
        자리를 잃는다. 자동 갱신이 방해가 되는 순간이 정확히 그때다.
        """
        if self._selected_row() is not None:
            self.ui.show_count(
                f"{len(self._rows)}줄  (줄을 고른 동안은 자동 갱신을 멈춘다)"
            )
            return
        # 도는 작업이 이미 지금 필터로 읽고 있다. 보류로 만들면 10초보다 오래 걸리는 서버에서
        # 결과가 매번 버려진다.
        if self._task is not None:
            return
        self.reload()

    @Slot()
    def reload(self) -> None:
        if self.repo is None or is_busy():
            return
        if self._task is not None:
            # 동시에 둘을 돌리지 않는다. 끝난 뒤(_clear_task) 그때의 필터로 한 번 더 읽는다.
            self._pending = True
            self._stale = True
            return
        self._pending = False
        self._stale = False

        since_text = self.ui.range_cb.currentData() or ""
        since = _since(since_text)
        who = self.ui.who_field.text().strip()
        process = self.ui.selected_process()
        find = self.ui.find_field.text().strip()
        repo, process_repo = self.repo, self.process_repo

        def work():
            return (
                repo.recent(
                    limit=PAGE,
                    since=since,
                    actor=who,
                    process=process,
                    contains=find,
                ),
                process_repo.list_all(),
            )

        task = Task(work)
        task.done.connect(self._on_result)
        task.failed.connect(self._on_failed)
        task.finished.connect(self._clear_task)
        self._task = task
        task.start()

    @Slot()
    def _clear_task(self) -> None:
        # 끝난 그 작업만 지운다. shutdown 이 기다린 작업의 finished 는 나중에 오고, 그때
        # self._task 는 비었거나 새로 띄운(돌고 있는) 작업이다.
        task = self.sender()
        if task is not None and task is self._task:
            self._task = None
        if task is not None:
            task.deleteLater()
        if self._task is None and self._pending:
            self.reload()

    def _is_current(self) -> bool:
        """시그널을 낸 작업이 지금 작업이고, 시작한 뒤 필터나 DB 가 바뀌지 않았는가."""
        task = self.sender()
        return task is not None and task is self._task and not self._stale

    @Slot(object)
    def _on_result(self, result) -> None:
        if not self._is_current():
            return
        self._failures = 0
        rows, processes = result
        # repo 는 오래된 것부터 준다. 화면에서는 최신이 위라야 읽힌다.
        self._rows = list(reversed(rows))
        self.ui.set_processes(processes)
        self.model.set_data([_display(r) for r in self._rows])
        self.ui.show_detail("")
        if not self._rows:
            self.ui.show_count("조건에 맞는 이력이 없다.")
        elif len(self._rows) >= PAGE:
            self.ui.show_count(f"{len(self._rows)}줄  (더 있다. 기간을 좁힐 것)")
        else:
            self.ui.show_count(f"{len(self._rows)}줄")

    @Slot(object)
    def _on_failed(self, exc: Exception) -> None:
        if not self._is_current():
            return
        self._failures += 1
        # 개수 칸은 한 줄짜리 라벨이고, 로그 패널은 scrub 포매터를 지나지 않고(ADR-013)
        # 줄 단위다. user_message 는 여러 줄일 수 있다.
        reason = " ".join(user_message(exc).split())
        self.ui.show_count(f"이력을 읽지 못했다: {reason}")
        if self._failures >= POLL_FAILURE_LIMIT:
            self._timer.stop()
            self.logRequested.emit(f"이력 자동 갱신을 중단했다: {reason}")

    # ------------------------------------------------------------------
    # 선택
    # ------------------------------------------------------------------

    def _selected_row(self) -> int | None:
        rows = self.ui.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    @Slot()
    def _on_selected(self) -> None:
        index = self._selected_row()
        if index is None or index >= len(self._rows):
            self.ui.show_detail("")
            return

        row = self._rows[index]
        when = row["at"].strftime("%Y-%m-%d %H:%M:%S")
        who = row["actor"] or "(모름)"
        head = [f"{when}  {who}  {audit.where_of(row)}", row["summary"]]
        body = audit.format_detail(row, indent="")
        self.ui.show_detail("\n".join(head + ([""] + body if body else [])))

    @Slot(bool)
    def _on_auto_toggled(self, on: bool) -> None:
        if on and self.repo is not None:
            self._failures = 0
            self._timer.start()
        else:
            self._timer.stop()


def _since(text: str) -> datetime | None:
    """콤보의 값(1d / 7d / 30d / 빈 문자열)을 시각으로. 빈 값은 전체."""
    if not text:
        return None
    return datetime.now() - timedelta(days=int(text.rstrip("d")))
