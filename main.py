import sys

from PySide6.QtWidgets import QApplication

from controllers.main_window import MainWindowController
from utils.palette import apply_theme
from views.main_window import MainWindow


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else ""
    hostname = sys.argv[2] if len(sys.argv) > 2 else ""
    app = QApplication(sys.argv)
    QApplication.setStyle("Fusion")
    apply_theme(app, "graphite")
    main_window = MainWindow(hostname)
    MainWindowController(main_window, db_path)
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
