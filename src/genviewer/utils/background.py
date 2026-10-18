"""블로킹 호출을 GUI 스레드 밖으로 내보낸다.

DB 가 로컬 `.sqlite` 파일이었을 때는 모든 호출을 GUI 스레드에서 해도 티가 나지
않았다. TCP 로 바뀌면 사정이 다르다. 죽은 호스트에 붙으려 하면
`connect_timeout` 만큼, 다른 사용자의 `FOR UPDATE` 뒤에서 기다리면
`lock_timeout` 만큼 이벤트 루프가 통째로 멈춘다 — 창이 하얗게 비고 OS 가
"응답 없음" 을 붙인다.

두 가지를 제공한다.

`run_blocking(fn)`
    호출부의 제어 흐름은 그대로 둔다. 값을 반환하고 예외를 올린다. 대기
    구간만 워커 스레드로 옮기고, GUI 스레드는 그동안 이벤트를 처리하되
    **입력은 버린다**(`ExcludeUserInputEvents`). 저장·접속처럼 "끝나야 다음
    단계로 갈 수 있는" 호출용이다.

    입력을 버리는 게 핵심이다. 저장이 날아가는 동안 사용자가 process 를
    바꾸거나 행을 지울 수 있으면, 방금 보낸 것과 다른 내용이 저장된 것처럼
    보인다. 호출부를 콜백으로 뒤집지 않고도 그 창을 닫는다.

`Task`
    진짜 비동기. 반환값을 기다리는 사람이 없는 호출용이다(변경 감지 폴링).
    완료는 시그널로 온다. 시그널은 워커에서 emit 되지만 수신자가 GUI 스레드에
    있으면 Qt 가 큐로 전달하므로, 슬롯은 GUI 스레드에서 돈다.

psycopg 의 커넥션 풀은 스레드 안전하다. 워커는 풀에서 커넥션을 하나 빌려
쓰고 돌려준다.
"""

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QEventLoop, Qt, QThread, Signal
from PySide6.QtGui import QGuiApplication

# 20ms 씩 끊어 기다린다. 사람이 느끼기에는 즉시이고, 그 사이에 다시 그린다.
_SLICE_MS = 20

_nesting = 0


class Task(QThread):
    """콜러블 하나를 워커 스레드에서 실행한다."""

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, fn: Callable, parent=None):
        super().__init__(parent)
        self._fn = fn
        self.result = None
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            self.result = self._fn()
        except Exception as e:
            # 워커에서 예외를 흘려보내면 스레드만 조용히 죽는다. 붙잡아
            # 두었다가 run_blocking 이 호출부에서 다시 올리거나, failed 로
            # 넘긴다.
            self.error = e
            self.failed.emit(e)
        else:
            self.done.emit(self.result)


def is_busy() -> bool:
    """지금 run_blocking 안인가.

    타이머 콜백이 재진입해서 저장 도중에 또 DB 를 부르지 않게 확인하는 용도다.
    """
    return _nesting > 0


def run_blocking(fn: Callable, parent=None):
    """fn 을 워커에서 실행하고 끝날 때까지 이벤트를 돌린다. 값/예외를 그대로 준다."""
    global _nesting

    app = QCoreApplication.instance()
    if app is None:
        # Qt 애플리케이션이 없으면(테스트 등) 그냥 부른다.
        return fn()

    task = Task(fn, parent)
    _nesting += 1
    QGuiApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        task.start()
        # QEventLoop + finished.connect(loop.quit) 이 아니라 wait 슬라이스를
        # 쓰는 이유: fn 이 아주 빨리 끝나면 quit() 이 아직 돌지 않는 루프에
        # 도착해 무시되고 그대로 멈춘다.
        while not task.wait(_SLICE_MS):
            app.processEvents(
                QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, _SLICE_MS
            )
    finally:
        QGuiApplication.restoreOverrideCursor()
        _nesting -= 1

    error, result = task.error, task.result
    # 여기까지 왔으면 wait() 가 True 였다(끝났다). 지우지 않으면 parent 의 자식으로 남아
    # 부를 때마다 하나씩 쌓인다. 기다림이 예외로 끊겼으면 아직 돌 수 있어서 지우지 않는다.
    task.deleteLater()
    if error is not None:
        raise error
    return result
