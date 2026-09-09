import argparse
import sys

from PySide6.QtWidgets import QApplication

from controllers.main_window import MainWindowController
from service.config import DSN_ENV
from utils.palette import apply_theme
from views.main_window import MainWindow


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="molgenviewer")
    ap.add_argument(
        "--dsn",
        default="",
        help=f"PostgreSQL 접속 문자열. 없으면 {DSN_ENV} 환경변수를 쓴다.",
    )
    ap.add_argument("--host", default="", help="Virtuoso 소켓 호스트 이름")
    return ap.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])

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
