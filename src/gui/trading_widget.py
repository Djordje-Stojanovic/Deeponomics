# src/gui/trading_widget.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLineEdit, QPushButton, QComboBox, QTableView, QLabel, QMessageBox, QTabWidget)
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
                        return f"${order.price:.2f}" if order.price is not None else "Market"
                    elif col == 2:
                        return str(order.shares)
            else:  # Sell orders
                if row < len(self.sell_orders):
                    order = self.sell_orders[row]
                    if col == 3:
                        return "Sell"
                    elif col == 4:
                        return f"${order.price:.2f}" if order.price is not None else "Market"
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
        self.buy_orders = sorted(order_book['buy'], key=lambda x: x.price or float('inf'), reverse=True)
        self.sell_orders = sorted(order_book['sell'], key=lambda x: x.price or float('inf'))
        db.close()
        self.layoutChanged.emit()

class OpenOrdersModel(QAbstractTableModel):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.orders = []
        self.headers = ["Company", "Type", "Subtype", "Price", "Shares"]

    def rowCount(self, parent=QModelIndex()):
        return len(self.orders)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            order = self.orders[index.row()]
            col = index.column()
            if col == 0:
                return order['company_name']
            elif col == 1:
                return order['order_type']
            elif col == 2:
                return order['order_subtype']
            elif col == 3:
                return f"${order['price']:.2f}" if order['price'] is not None else "Market"
            elif col == 4:
                return str(order['shares'])
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def update_data(self):
        db = SessionLocal()
        try:
            orders = crud.get_shareholder_orders(db, self.user_id)
            self.orders = []
            for order in orders:
                company = crud.get_company(db, order.company_id)
                self.orders.append({
                    'company_name': company.name if company else "Unknown",
                    'order_type': order.order_type.value,
                    'order_subtype': order.order_subtype.value,
                    'price': order.price,
                    'shares': order.shares,
                    'id': order.id
                })
        finally:
            db.close()
        self.layoutChanged.emit()

class TradingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_user_id = None
        self.companies = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        
        # Order entry and order book tab
        order_entry_widget = QWidget()
        order_entry_layout = QVBoxLayout(order_entry_widget)
        
        # Order entry form
        form_layout = QFormLayout()
        self.company_combo = QComboBox()
        self.company_combo.currentIndexChanged.connect(self.on_company_changed)
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

        order_entry_layout.addLayout(form_layout)

        # Order book
        self.order_book_label = QLabel("Order Book")
        order_entry_layout.addWidget(self.order_book_label)
        self.order_book_view = QTableView()
        self.order_book_model = OrderBookModel()
        self.order_book_view.setModel(self.order_book_model)
        order_entry_layout.addWidget(self.order_book_view)

        self.submit_button.clicked.connect(self.place_order)
        
        self.tab_widget.addTab(order_entry_widget, "Order Entry")
        
        # Update the Open orders tab setup
        open_orders_widget = QWidget()
        open_orders_layout = QVBoxLayout(open_orders_widget)
        self.open_orders_view = QTableView()
        self.open_orders_model = OpenOrdersModel(self.current_user_id)
        self.open_orders_view.setModel(self.open_orders_model)
        open_orders_layout.addWidget(self.open_orders_view)
        
        cancel_button = QPushButton("Cancel Selected Order")
        cancel_button.clicked.connect(self.cancel_selected_order)
        open_orders_layout.addWidget(cancel_button)
        
        self.tab_widget.addTab(open_orders_widget, "Open Orders")
        
        layout.addWidget(self.tab_widget)

    def set_current_user_id(self, user_id):
        self.current_user_id = user_id
        self.open_orders_model.user_id = user_id
        self.open_orders_model.update_data()

    def cancel_selected_order(self):
        selected_indexes = self.open_orders_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Error", "No order selected.")
            return

        selected_row = selected_indexes[0].row()
        order_id = self.open_orders_model.orders[selected_row]['id']

        db = SessionLocal()
        try:
            success = crud.cancel_order(db, order_id)
            if success:
                QMessageBox.information(self, "Success", "Order cancelled successfully.")
                self.open_orders_model.update_data()
                self.update_order_book(self.company_combo.currentData())
            else:
                QMessageBox.warning(self, "Error", "Failed to cancel order.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred: {str(e)}")
        finally:
            db.close()

    def update_companies(self):
        db = SessionLocal()
        self.companies = crud.get_all_companies(db)
        db.close()
        
        current_company_id = self.company_combo.currentData()
        
        self.company_combo.clear()
        for company in self.companies:
            self.company_combo.addItem(f"{company.name} ({company.sector.value})", company.id)
        
        if current_company_id:
            index = self.company_combo.findData(current_company_id)
            if index >= 0:
                self.company_combo.setCurrentIndex(index)

    def on_company_changed(self, index):
        if index >= 0:
            company_id = self.company_combo.itemData(index)
            self.update_order_book(company_id)

    def place_order(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "Error", "No user logged in.")
            return

        company_id = self.company_combo.currentData()
        if not company_id:
            QMessageBox.warning(self, "Error", "No company selected.")
            return

        try:
            shares = int(self.shares_edit.text())
            order_subtype = OrderSubType.LIMIT if self.order_subtype_combo.currentText() == "Limit" else OrderSubType.MARKET
            price = float(self.price_edit.text()) if order_subtype == OrderSubType.LIMIT else None
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid shares or price value.")
            return

        db = SessionLocal()
        try:
            order_type = OrderType.BUY if self.order_type_combo.currentText() == "Buy" else OrderType.SELL
            shareholder = crud.get_shareholder(db, self.current_user_id)
            company = crud.get_company(db, company_id)

            # Check if the user has conflicting orders
            existing_orders = crud.get_shareholder_orders(db, self.current_user_id)
            conflicting_orders = [o for o in existing_orders if o.company_id == company_id and o.order_type != order_type]
            if conflicting_orders:
                QMessageBox.warning(self, "Error", "You have existing orders for this company in the opposite direction. Please cancel them before placing a new order.")
                return

            if order_type == OrderType.BUY:
                if order_subtype == OrderSubType.LIMIT:
                    required_funds = shares * price
                else:  # Market order
                    lowest_sell_order = crud.get_lowest_sell_order(db, company_id)
                    if lowest_sell_order:
                        estimated_price = lowest_sell_order.price
                    else:
                        # Use update_stock_price to get the most accurate current price
                        estimated_price = crud.update_stock_price(db, company_id)
                    
                    required_funds = shares * estimated_price

                if shareholder.cash < required_funds:
                    QMessageBox.warning(self, "Error", f"Insufficient funds. You need approximately ${required_funds:.2f}, but you only have ${shareholder.cash:.2f}.")
                    return

                # Check if there are enough outstanding shares
                total_buy_orders = crud.get_total_buy_orders(db, company_id)
                if total_buy_orders + shares > company.outstanding_shares:
                    QMessageBox.warning(self, "Error", f"Not enough outstanding shares. You can buy up to {company.outstanding_shares - total_buy_orders} shares.")
                    return

                if order_subtype == OrderSubType.MARKET:
                    reply = QMessageBox.question(self, "Market Order Warning", 
                        "The actual execution price for a market order may differ from the estimated price. Do you want to proceed?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.No:
                        return

            elif order_type == OrderType.SELL:
                portfolio = crud.get_portfolio(db, self.current_user_id, company_id)
                if not portfolio:
                    QMessageBox.warning(self, "Error", "You don't own any shares of this company.")
                    return
                available_shares = portfolio.shares
                pending_sell_orders = crud.get_pending_sell_orders(db, self.current_user_id, company_id)
                available_shares -= pending_sell_orders
                if shares > available_shares:
                    QMessageBox.warning(self, "Error", f"Not enough shares. You can sell up to {available_shares} shares.")
                    return

            order = OrderCreate(
                shareholder_id=self.current_user_id,
                company_id=company_id,
                order_type=order_type,
                order_subtype=order_subtype,
                shares=shares,
                price=price
            )
            created_order = crud.create_order(db, order)
            if created_order:
                QMessageBox.information(self, "Success", "Order placed successfully.")
                self.update_order_book(company_id)
                self.open_orders_model.update_data()  # Update open orders after placing a new order
            else:
                QMessageBox.warning(self, "Error", "Failed to create order. Please check your inputs and try again.")
                print(f"Order creation failed. Inputs: {order}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred: {str(e)}")
            print(f"Exception occurred: {str(e)}")
        finally:
            db.close()

    def update_order_book(self, company_id):
        self.order_book_model.update_data(company_id)
