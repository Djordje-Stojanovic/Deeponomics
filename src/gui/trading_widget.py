# src/gui/trading_widget.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLineEdit, QPushButton, QComboBox, QTableView, QLabel)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import crud
from database import SessionLocal
from schemas import OrderCreate, OrderType, OrderSubType

class OrderBookModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.buy_orders = []
        self.sell_orders = []
        self.headers = ["Type", "Price", "Shares"]

    def rowCount(self, parent=QModelIndex()):
        return max(len(self.buy_orders), len(self.sell_orders))

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers) * 2  # Buy and Sell columns

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            col = index.column()
            row = index.row()
            if col < 3:  # Buy orders
                if row < len(self.buy_orders):
                    order = self.buy_orders[row]
                    if col == 0:
                        return "Buy"
                    elif col == 1:
                        return f"${order.price:.2f}"
                    elif col == 2:
                        return str(order.shares)
            else:  # Sell orders
                if row < len(self.sell_orders):
                    order = self.sell_orders[row]
                    if col == 3:
                        return "Sell"
                    elif col == 4:
                        return f"${order.price:.2f}"
                    elif col == 5:
                        return str(order.shares)
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < 3:
                return f"Buy {self.headers[section]}"
            else:
                return f"Sell {self.headers[section - 3]}"
        return None

    def update_data(self, company_id):
        db = SessionLocal()
        order_book = crud.get_order_book(db, company_id)
        self.buy_orders = order_book['buy']
        self.sell_orders = order_book['sell']
        db.close()
        self.layoutChanged.emit()

class TradingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_user_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Order entry form
        form_layout = QFormLayout()
        self.company_combo = QComboBox()
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["Buy", "Sell"])
        self.order_subtype_combo = QComboBox()
        self.order_subtype_combo.addItems(["Limit", "Market"])
        self.shares_edit = QLineEdit()
        self.price_edit = QLineEdit()
        self.submit_button = QPushButton("Place Order")

        form_layout.addRow("Company:", self.company_combo)
        form_layout.addRow("Order Type:", self.order_type_combo)
        form_layout.addRow("Order Subtype:", self.order_subtype_combo)
        form_layout.addRow("Shares:", self.shares_edit)
        form_layout.addRow("Price:", self.price_edit)
        form_layout.addRow(self.submit_button)

        layout.addLayout(form_layout)

        # Order book
        self.order_book_label = QLabel("Order Book")
        layout.addWidget(self.order_book_label)
        self.order_book_view = QTableView()
        self.order_book_model = OrderBookModel()
        self.order_book_view.setModel(self.order_book_model)
        layout.addWidget(self.order_book_view)

        self.submit_button.clicked.connect(self.place_order)

    def update_companies(self):
        db = SessionLocal()
        companies = crud.get_all_companies(db)
        db.close()
        self.company_combo.clear()
        self.company_combo.addItems([company.name for company in companies])

    def place_order(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "Error", "No user logged in.")
            return

        db = SessionLocal()
        order = OrderCreate(
            shareholder_id=self.current_user_id,
            company_id=self.company_combo.currentText(),
            order_type=OrderType.BUY if self.order_type_combo.currentText() == "Buy" else OrderType.SELL,
            order_subtype=OrderSubType.LIMIT if self.order_subtype_combo.currentText() == "Limit" else OrderSubType.MARKET,
            shares=int(self.shares_edit.text()),
            price=float(self.price_edit.text()) if self.order_subtype_combo.currentText() == "Limit" else None
        )
        crud.create_order(db, order)
        db.close()
        self.update_order_book()

    def update_order_book(self):
        selected_company = self.company_combo.currentText()
        db = SessionLocal()
        company = crud.get_company(db, selected_company)
        db.close()
        if company:
            self.order_book_model.update_data(company.id)