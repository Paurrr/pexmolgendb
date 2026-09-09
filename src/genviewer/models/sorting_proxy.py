from PySide6.QtCore import QSortFilterProxyModel, Qt


class SortingProxyModel(QSortFilterProxyModel):
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return section + 1
        return super().headerData(section, orientation, role)
