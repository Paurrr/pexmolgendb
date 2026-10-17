"""GUI 테스트(pytest-qt) 공통 fixture.

창은 띄우지 않는다(offscreen). 모달은 autouse `dialogs` 가 대신한다.
"""

import gc
import os
from collections.abc import Iterator

import pytest

# PySide6 를 import 하기 전에 둔다. 이미 정해 둔 값이 있으면 그것을 쓴다.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui_support.dialogs import FakeDialogs, install_dialogs  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402


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
