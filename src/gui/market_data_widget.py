# src/gui/market_data_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import crud
from database import SessionLocal

class MarketDataModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.companies = []
        self.headers = ["Name", "Stock Price", "Revenue", "CFO", "CAPEX", "FCF"]

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
                return f"${company.annual_revenue:.2f}"
            elif index.column() == 3:
                return f"${self.get_cfo(company):.2f}"
            elif index.column() == 4:
                return f"${company.annual_capex:.2f}"
            elif index.column() == 5:
                return f"${self.get_fcf(company):.2f}"
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

    def get_cfo(self, company):
        # Calculate CFO based on the cash flow statement logic
        net_income = company.annual_revenue * (1 - company.cost_of_revenue_percentage) * (1 - 0.21)  # Assuming 21% tax rate
        cfo = net_income + company.gain_loss_investments + company.interest_income - company.change_in_nwc
        return cfo

    def get_fcf(self, company):
        # Calculate Free Cash Flow
        cfo = self.get_cfo(company)
        return cfo - company.annual_capex

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