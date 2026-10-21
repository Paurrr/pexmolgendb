"""GUI 테스트(pytest-qt) 공통 fixture.

창은 띄우지 않는다(offscreen). 모달은 autouse `dialogs` 가 대신한다.
컨트롤러 테스트는 `store`(시드: tests/gui_support/helpers.py) 위에 붙은 `device_tab_ctrl` 또는
`main_window` 로 쓴다. 사용자 동작은 `gui_support.helpers` 의 select_*/edit_* 로 흉내 낸다.
History 화면은 `history_ctrl` 로 쓴다(`main_window` 는 History 를 만들지 않는다).
"""

import gc
import os
from collections.abc import Iterator

import pytest

# PySide6 를 import 하기 전에 둔다. 이미 정해 둔 값이 있으면 그것을 쓴다.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui_support.dialogs import FakeDialogs, install_dialogs  # noqa: E402
from gui_support.fakes import FakeDatabase, FakeStore  # noqa: E402
from gui_support.helpers import (  # noqa: E402
    install_fake_db,
    install_fake_history,
    seeded_store,
)
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402

from genviewer.controllers.device_tab import DeviceTabController  # noqa: E402
from genviewer.controllers.history_tab import HistoryTabController  # noqa: E402
from genviewer.controllers.main_window import MainWindowController  # noqa: E402
from genviewer.views.device_tab import DeviceTab  # noqa: E402
from genviewer.views.history_tab import HistoryTab  # noqa: E402
from genviewer.views.main_window import MainWindow  # noqa: E402


@pytest.fixture(autouse=True)
def dialogs(monkeypatch) -> Iterator[FakeDialogs]:
    """모달 대화상자 가짜. 답은 `answer_question`/`answer_conflict` 로 미리 정한다.

    teardown 에서 `problems()` 를 다시 본다. `@report`, `connect_db` 등이 `AssertionError`
    를 알림으로 바꿔 삼키고, device_tab 단독 fixture 에서는 그 알림이 아무 데도 가지 않는다.
    쓰이지 않은 답도 실패로 본다. 테스트가 기대한 질문이 뜨지 않았다는 뜻이다.
    """
    fake = install_dialogs(monkeypatch)
    yield fake
    problems = fake.problems()
    if problems:
        pytest.fail("\n".join(problems), pytrace=False)


@pytest.fixture(autouse=True)
def _collect_previous_garbage() -> None:
    """앞 테스트가 남긴 Qt 객체 순환을 이 테스트 본문 전에 GUI 스레드에서 푼다.

    `run_blocking`/`Task` 와 가짜 repo 가 워커 스레드에서 파이썬 코드를 돌리므로 순환 GC 가
    워커 스레드에서 돌 수 있다. 그때 부모 없는 Qt 객체(`MainWindowController` 는 부모가 없다)가
    회수되면 C++ 소멸자가 GUI 스레드 밖에서 돌아 "Fatal Python error: Aborted" 가 난다
    (pexqa phase 7).

    - teardown 이 아니라 setup 에서 푼다. teardown 때는 `item.funcargs` 가 아직 객체를 잡고
      있고 C++ 쪽도 DeferredDelete 전이다. 그래서 DeferredDelete 를 먼저 처리한 뒤 GC 한다.
    - GC 뒤 `gc.freeze()` 로 살아남은 객체를 다음 GC 에서 뺀다. 매번 힙 전체를 훑으면 느려진다
      (pexqa 에서 2.5배). 얼린 객체가 나중에 쓰레기가 되면 풀리지 않고 남지만 워커 스레드 GC
      에서도 지워지지 않는다.
    """
    if QCoreApplication.instance() is not None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    gc.freeze()


@pytest.fixture(autouse=True)
def _app_user(monkeypatch) -> None:
    """current_user() 를 "tester" 로 정한다. 저장의 actor 와 updated_by 가 이 이름이 된다."""
    monkeypatch.setenv("GENDB_APP_USER", "tester")


@pytest.fixture
def store() -> FakeStore:
    """시드한 가짜 서버. sf2p(nfet_a, nfet_b), sf4u(pfet_a), 탭 InstTerm·InstSchParam."""
    return seeded_store()


@pytest.fixture
def device_tab_ctrl(qtbot, monkeypatch, store, dialogs) -> Iterator[DeviceTabController]:
    """store 에 붙은 실제 DeviceTabController (MainWindow 없이).

    접속 직후에는 첫 쌍 ("sf2p", "")이 골라져 있다(view 의 set_pairs 가 selectionChanged 를 낸다).
    알림은 MainWindow 대신 `dialogs.shown` 에 남는다. 생성 **뒤에** 잇는 것은
    MainWindowController 와 같은 순서다. 첫 접속은 생성자가 예약만 하므로 그 알림도 여기 닿는다.
    """
    install_fake_db(monkeypatch, store)
    view = DeviceTab()
    qtbot.addWidget(view)
    ctrl = DeviceTabController(view, "")
    ctrl.notifyRequested.connect(dialogs.record_notify)
    # 첫 접속은 QTimer.singleShot(0, …) 으로 예약된다. 기다려야 다음 테스트로 새지 않는다.
    qtbot.waitUntil(lambda: ctrl.connected is not None)
    yield ctrl
    ctrl.close_db()  # 이미 닫혔으면 아무것도 하지 않는다


@pytest.fixture
def main_window(qtbot, monkeypatch, store, dialogs) -> Iterator[MainWindowController]:
    """store 에 붙은 실제 MainWindowController. `.ui` 가 MainWindow, `.device_tab` 이 컨트롤러다.

    창은 띄우지 않는다. 포커스가 필요한 테스트는 `main_window.ui.show()` 와
    `qtbot.waitExposed(main_window.ui)` 를 직접 한다. History 화면은 만들지 않는다.
    """
    install_fake_db(monkeypatch, store)
    ui = MainWindow("localhost")
    made: list[MainWindowController] = []
    # pytest-qt 는 이 fixture 의 정리보다 먼저 등록한 창을 닫는다. 그 전에 shutdown 으로 닫기
    # 확인을 떼야 편집을 남긴 테스트가 정리 때 "Save Changes" 를 묻지 않는다.
    qtbot.addWidget(ui, before_close_func=lambda _ui: [c.shutdown() for c in made])
    controller = MainWindowController(ui, "")
    made.append(controller)
    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)
    yield controller
    controller.shutdown()  # 테스트가 먼저 불렀어도 안전하다
    ui.close()


@pytest.fixture
def history_ctrl(qtbot, monkeypatch, store) -> Iterator[HistoryTabController]:
    """store 에 붙은 실제 HistoryTabController. `.ui` 가 HistoryTab 이고, 첫 다시 읽기가 끝나 있다.

    기간은 "전체" 로 둔다. 기본값(최근 7일)은 벽시계 기준이라 store 시계(2026-10-17)로 넣은
    줄이 날짜가 지나면 걸러진다. 이력 줄은 `store.add_audit` 로 넣고 `reload()` 한다.
    자동 갱신 타이머(10초)는 켜진 채다.
    """
    install_fake_history(monkeypatch)
    view = HistoryTab()
    qtbot.addWidget(view)
    view.range_cb.setCurrentIndex(view.range_cb.findData(""))
    ctrl = HistoryTabController(view)
    ctrl.set_db(FakeDatabase(store))
    qtbot.waitUntil(lambda: ctrl._task is None and store.calls_of("recent") != [])
    yield ctrl
    ctrl.shutdown()
