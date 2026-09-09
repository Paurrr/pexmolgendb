from PySide6.QtWidgets import QMenu, QWidget


def _build_common_actions(menu: QMenu, selected_rows: list[int]):
    multi = len(selected_rows) >= 2
    has_row = len(selected_rows) == 1

    acts = {
        "insert": menu.addAction("Insert Row"),
        "edit": menu.addAction("Edit Row") if has_row else None,
        "delete": menu.addAction("Delete Selected Rows") if (has_row or multi) else None,
        "clear": None,
        "copy": None,
    }

    if has_row or multi:
        acts["clear"] = menu.addAction("Clear Selection")
        menu.addSeparator()
        acts["copy"] = menu.addAction("Copy")

    acts["paste"] = menu.addAction("Paste")
    return acts


def build_device_table_menu(parent: QWidget, selected_rows: list[int]):
    menu = QMenu(parent)
    acts = _build_common_actions(menu, selected_rows)
    menu.addSeparator()
    acts["csv"] = menu.addAction("Export CSV")
    acts["xlsx"] = menu.addAction("Export XLSX")
    return menu, acts


def build_parameter_table_menu(parent: QWidget, selected_rows: list[int]):
    menu = QMenu(parent)
    acts = _build_common_actions(menu, selected_rows)
    return menu, acts
