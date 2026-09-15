import argparse
import logging
import os
import sys
import threading

from PySide6.QtWidgets import QApplication, QMessageBox

from genviewer.controllers.main_window import MainWindowController
from genviewer.service import env_file
from genviewer.service.config import CONFIG_ENV, DSN_ENV
from genviewer.service.errors import user_message
from genviewer.utils import logs
from genviewer.utils.palette import apply_theme
from genviewer.views.main_window import MainWindow

log = logging.getLogger(__name__)

# --check-config 가 보여줄 값들. 비밀은 값 대신 (설정됨) 만 찍는다.
_SHOWN = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGSERVICE", "PGSSLMODE")


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="genviewer")
    ap.add_argument(
        "--dsn",
        default="",
        help=f"PostgreSQL 접속 문자열. 없으면 {DSN_ENV} 환경변수와 설정 파일을 본다.",
    )
    ap.add_argument("--host", default="", help="Virtuoso 소켓 호스트 이름")
    ap.add_argument(
        "--check-config",
        action="store_true",
        help="어느 설정 파일이 쓰이고 무슨 값이 적용되는지 보여주고 끝낸다.",
    )
    return ap.parse_args(argv)


def check_config() -> int:
    """접속 설정을 진단한다. 창을 띄우지 않는다.

    "접속이 안 된다" 는 문의의 대부분은 '어느 파일이 읽혔나' 로 끝난다. 값을
    직접 보여주되 **비밀번호는 절대 찍지 않는다** - 로그나 화면 캡처로 샌다.
    """
    try:
        used, searched = env_file.load(os.environ.get(CONFIG_ENV, "").strip())
    except RuntimeError as e:
        print(f"설정 파일 오류: {e}", file=sys.stderr)
        return 1

    print(f"설정 파일: {used if used else '(없음)'}")
    print("찾아본 곳:")
    for path in searched:
        mark = "<-- 이것" if used == path else ""
        print(f"  {path} {mark}".rstrip())

    print("적용된 값:")
    shown = False
    dsn = os.environ.get(DSN_ENV, "").strip()
    if dsn:
        # DSN 안에 비밀번호가 들어 있을 수 있다. 그러면 통째로 감춘다.
        safe = "(설정됨, 비밀번호가 들어 있어 감춤)" if "password" in dsn.lower() else dsn
        print(f"  {DSN_ENV}={safe}")
        shown = True
    for key in _SHOWN:
        value = os.environ.get(key, "").strip()
        if value:
            print(f"  {key}={value}")
            shown = True
    for key in sorted(env_file.SECRET_KEYS):
        if os.environ.get(key):
            print(f"  {key}=(설정됨)")
    if not shown:
        print("  (없음)")

    print(f"로그 파일: {logs.log_path()}  ({logs.LOG_ENV} 로 바꿀 수 있다)")

    if dsn or env_file.libpq_env_present():
        return 0
    print("접속 정보가 없다. 위 경로 중 한 곳에 설정 파일을 둘 것.", file=sys.stderr)
    return 1


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


def main():
    args = parse_args(sys.argv[1:])
    if args.check_config:
        sys.exit(check_config())

    logs.setup()
    install_excepthooks()

    # Qt 에는 프로그램 이름만 넘긴다. 우리 인자를 Qt 가 다시 해석하면 안 된다.
    app = QApplication(sys.argv[:1])
    QApplication.setStyle("Fusion")
    apply_theme(app, "graphite")
    main_window = MainWindow(args.host)
    controller = MainWindowController(main_window, args.dsn)
    main_window.show()

    rc = app.exec()
    # 풀을 닫고 나서 나간다. 안 그러면 인터프리터 종료 중에 멈춘다.
    controller.shutdown()
    sys.exit(rc)


if __name__ == "__main__":
    main()
