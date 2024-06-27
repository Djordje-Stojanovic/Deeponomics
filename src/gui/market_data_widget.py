# src/gui/market_data_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import crud
from database import SessionLocal

class MarketDataModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.companies = []
        self.headers = ["Name", "Stock Price", "Revenue", "Profit"]

    def rowCount(self, parent=QModelIndex()):
        return len(self.companies)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            company = self.companies[index.row()]
            if index.column() == 0:
                return company.name
            elif index.column() == 1:
                return f"${company.stock_price:.2f}"
            elif index.column() == 2:
                return f"${company.revenue:.2f}"
            elif index.column() == 3:
                return f"${company.profit:.2f}"
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def update_data(self):
        db = SessionLocal()
        self.companies = crud.get_all_companies(db)
        db.close()
        self.layoutChanged.emit()

class MarketDataWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.table_view = QTableView()
        self.model = MarketDataModel()
        self.table_view.setModel(self.model)
        layout.addWidget(self.table_view)

    def update_data(self):
        self.model.update_data()