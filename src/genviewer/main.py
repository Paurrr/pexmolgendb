"""창을 띄운다.

명령줄을 읽는 것은 cli.py 가 한다. 여기는 Qt 부팅과 마지막 예외 그물만 맡는다.
그 둘을 나눈 이유는 status 같은 명령이 Qt 를 통째로 올리지 않게 하려는 것이다 -
X 가 없는 서버에서도 돌아야 한다.
"""

import logging
import sys
import threading

from PySide6.QtWidgets import QApplication, QMessageBox

from genviewer.controllers.main_window import MainWindowController
from genviewer.service.errors import user_message
from genviewer.service.repo import audit
from genviewer.utils import logs
from genviewer.utils.palette import apply_theme
from genviewer.views.main_window import MainWindow

log = logging.getLogger(__name__)

# 상자가 겹쳐 뜨는 것을 막는다. 종료 중에 예외가 줄줄이 나면 사용자가 상자를 수십 번
# 닫아야 한다.
_reporting = False


def _show_unexpected(exc: BaseException) -> None:
    global _reporting
    if _reporting or QApplication.instance() is None:
        return
    _reporting = True
    try:
        where = logs.active_path()
        tail = f"\n\n자세한 내용: {where}" if where else ""
        QMessageBox.critical(None, "예기치 못한 오류", f"{user_message(exc)}{tail}")
    except Exception:
        log.exception("오류 상자를 띄우지 못했다")
    finally:
        _reporting = False


def install_excepthooks() -> None:
    """어디서도 잡히지 않은 예외의 마지막 그물.

    Qt 슬롯에서 예외가 올라오면 트레이스백이 stderr 로 나가는데, 배포본은 런처로
    뜨기 때문에 붙어 있는 터미널이 없다. 즉 아무 데도 남지 않고 사용자는 화면이
    안 바뀌는 것만 본다. 여기서 로그에 남기고 화면에 알린다.
    """

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("처리되지 않은 예외", exc_info=(exc_type, exc, tb))
        _show_unexpected(exc)

    sys.excepthook = hook

    def thread_hook(args):
        # 워커 스레드에서는 상자를 띄우지 않는다 - Qt 위젯은 GUI 스레드 것이다.
        if issubclass(args.exc_type, SystemExit):
            return
        log.critical(
            "처리되지 않은 예외 (스레드 %s)",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = thread_hook


def run_gui(dsn: str = "", host: str = "", history: bool = False) -> int:
    """창을 띄우고 닫힐 때까지 돈다. 종료 코드를 돌려준다.

    인자를 스스로 읽지 않는다 - cli.py 가 파싱해서 넘긴다.

    history 가 참일 때만 왼쪽 목록에 이력 화면이 생긴다. 기본은 꺼짐이라
    항목도 위젯도 만들어지지 않는다 (genviewer --history 로 켠다).
    """
    logs.setup()
    install_excepthooks()
    # 이력에 남길 출처. 같은 저장이라도 창에서 한 것과 명령줄에서 한 것을 구분한다.
    audit.set_source("gui")

    # Qt 에는 프로그램 이름만 넘긴다. 우리 인자를 Qt 가 다시 해석하면 안 된다.
    app = QApplication(sys.argv[:1])
    QApplication.setStyle("Fusion")
    apply_theme(app, "graphite")
    main_window = MainWindow(host, show_history=history)
    controller = MainWindowController(main_window, dsn)
    main_window.show()

    rc = app.exec()
    # 풀을 닫고 나서 나간다. 안 그러면 인터프리터 종료 중에 멈춘다.
    controller.shutdown()
    return rc
