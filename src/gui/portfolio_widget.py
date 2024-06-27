# src/gui/portfolio_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import crud
from database import SessionLocal

class PortfolioModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.portfolio = []
        self.headers = ["Company", "Shares", "Current Price", "Total Value", "Profit/Loss"]

    def rowCount(self, parent=QModelIndex()):
        return len(self.portfolio)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            holding = self.portfolio[index.row()]
            col = index.column()
            if col == 0:
                return holding['company_name']
            elif col == 1:
                return str(holding['shares'])
            elif col == 2:
                return f"${holding['current_price']:.2f}"
            elif col == 3:
                return f"${holding['total_value']:.2f}"
            elif col == 4:
                return f"${holding['profit_loss']:.2f}"
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, shareholder_id):
        db = SessionLocal()
        portfolios = crud.get_shareholder_portfolio(db, shareholder_id)
        self.portfolio = []
        for portfolio in portfolios:
            company = crud.get_company(db, portfolio.company_id)
            total_value = portfolio.shares * company.stock_price
            # For simplicity, we're assuming the buy price was 90% of current price
            # In a real application, you'd calculate this based on actual purchase history
            assumed_buy_price = company.stock_price * 0.9
            profit_loss = total_value - (assumed_buy_price * portfolio.shares)
            self.portfolio.append({
                'company_name': company.name,
                'shares': portfolio.shares,
                'current_price': company.stock_price,
                'total_value': total_value,
                'profit_loss': profit_loss
            })
        db.close()
        self.layoutChanged.emit()

class PortfolioWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.total_value_label = QLabel("Total Portfolio Value: $0.00")
        layout.addWidget(self.total_value_label)

        self.table_view = QTableView()
        self.model = PortfolioModel()
        self.table_view.setModel(self.model)
        layout.addWidget(self.table_view)

    def update_data(self, shareholder_id):
        self.model.update_data(shareholder_id)
        total_value = sum(holding['total_value'] for holding in self.model.portfolio)
        self.total_value_label.setText(f"Total Portfolio Value: ${total_value:.2f}")