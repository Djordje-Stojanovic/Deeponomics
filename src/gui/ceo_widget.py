from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSlider, QPushButton, QSpinBox, QMessageBox, QDialog, QComboBox)
from PySide6.QtCore import Qt, Signal
import crud
from database import SessionLocal
from sqlalchemy import func
from models import DBCompany
from datetime import datetime

class CEOWidget(QWidget):
    settings_updated = Signal()

    def __init__(self):
        super().__init__()
        self.company_id = None
        self.current_user_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # CEO Info
        self.ceo_name_label = QLabel("CEO: N/A")
        layout.addWidget(self.ceo_name_label)

        # CEO Attributes
        self.ceo_capex_label = QLabel("CEO CAPEX Allocation: N/A")
        self.ceo_dividend_label = QLabel("CEO Dividend Allocation: N/A")
        self.ceo_cash_inv_label = QLabel("CEO Cash/Investment Allocation: N/A")
        layout.addWidget(self.ceo_capex_label)
        layout.addWidget(self.ceo_dividend_label)
        layout.addWidget(self.ceo_cash_inv_label)

        # Add Next Dividend Date Label
        self.next_dividend_label = QLabel("Next Dividend Date: N/A")
        layout.addWidget(self.next_dividend_label)

        # Add Stock Split Button
        self.stock_split_button = QPushButton("Stock Split")
        self.stock_split_button.clicked.connect(self.show_stock_split_dialog)
        layout.addWidget(self.stock_split_button)

        # CAPEX Slider
        capex_layout = QHBoxLayout()
        self.capex_slider = QSlider(Qt.Horizontal)
        self.capex_slider.setRange(0, 100)
        self.capex_slider.setValue(50)  # Default to 50%
        self.capex_label = QLabel("CAPEX: 50%")
        capex_layout.addWidget(QLabel("CAPEX %:"))
        capex_layout.addWidget(self.capex_slider)
        capex_layout.addWidget(self.capex_label)
        layout.addLayout(capex_layout)

        # Dividend Payout Slider
        dividend_layout = QHBoxLayout()
        self.dividend_slider = QSlider(Qt.Horizontal)
        self.dividend_slider.setRange(0, 100)
        self.dividend_slider.setValue(0)  # Default to 0%
        self.dividend_label = QLabel("Dividend Payout: 0%")
        dividend_layout.addWidget(QLabel("Dividend Payout %:"))
        dividend_layout.addWidget(self.dividend_slider)
        dividend_layout.addWidget(self.dividend_label)
        layout.addLayout(dividend_layout)

        # Cash vs Short-term Investments Slider
        cash_inv_layout = QHBoxLayout()
        self.cash_inv_slider = QSlider(Qt.Horizontal)
        self.cash_inv_slider.setRange(0, 100)
        self.cash_inv_slider.setValue(50)  # Default to 50/50 split
        self.cash_inv_label = QLabel("Cash: 50% | Investments: 50%")
        cash_inv_layout.addWidget(QLabel("Remaining Cash Allocation:"))
        cash_inv_layout.addWidget(self.cash_inv_slider)
        cash_inv_layout.addWidget(self.cash_inv_label)
        layout.addLayout(cash_inv_layout)

        # Apply Button
        self.apply_button = QPushButton("Apply Changes")
        layout.addWidget(self.apply_button)

        # Change CEO Button
        self.change_ceo_button = QPushButton("Change CEO")
        self.change_ceo_button.clicked.connect(self.change_ceo)
        self.change_ceo_button.setVisible(False)
        layout.addWidget(self.change_ceo_button)

        # Connect signals
        self.capex_slider.valueChanged.connect(self.update_capex_label)
        self.dividend_slider.valueChanged.connect(self.update_dividend_label)
        self.cash_inv_slider.valueChanged.connect(self.update_cash_inv_label)
        self.apply_button.clicked.connect(self.apply_changes)

    def update_capex_label(self, value):
        self.capex_label.setText(f"CAPEX: {value}%")

    def update_dividend_label(self, value):
        self.dividend_label.setText(f"Dividend Payout: {value}%")

    def update_cash_inv_label(self, value):
        self.cash_inv_label.setText(f"Cash: {value}% | Investments: {100-value}%")

    def set_company_id(self, company_id):
        if self.company_id != company_id:
            self.company_id = company_id
            self.load_company_settings()
            self.update_data()
            self.update_ceo_info()

    def set_current_user_id(self, user_id):
        self.current_user_id = user_id
        self.update_change_ceo_button_visibility()

    def apply_changes(self):
        if not self.company_id:
            QMessageBox.warning(self, "Error", "No company selected.")
            return

        capex_percentage = self.capex_slider.value() / 100
        dividend_percentage = self.dividend_slider.value() / 100
        cash_percentage = self.cash_inv_slider.value() / 100

        db = SessionLocal()
        try:
            company = crud.get_company(db, self.company_id)
            if company:
                company.capex_percentage = capex_percentage
                company.dividend_payout_percentage = dividend_percentage
                company.cash_allocation = cash_percentage
                db.commit()
                db.refresh(company)
                self.settings_updated.emit()
                QMessageBox.information(self, "Success", f"Changes applied successfully. CAPEX: {capex_percentage:.2%}, Dividend Payout: {dividend_percentage:.2%}, Cash Allocation: {cash_percentage:.2%}")
            else:
                QMessageBox.warning(self, "Error", f"Company with ID {self.company_id} not found.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply changes: {str(e)}")
        finally:
            db.close()

    def load_company_settings(self):
        if not self.company_id:
            return

        db = SessionLocal()
        try:
            company = crud.get_company(db, self.company_id)
            if company:
                self.capex_slider.setValue(int(company.capex_percentage * 100))
                self.dividend_slider.setValue(int(company.dividend_payout_percentage * 100))
                self.cash_inv_slider.setValue(int(company.cash_allocation * 100))
                self.update_capex_label(self.capex_slider.value())
                self.update_dividend_label(self.dividend_slider.value())
                self.update_cash_inv_label(self.cash_inv_slider.value())
            else:
                QMessageBox.warning(self, "Error", f"Company with ID {self.company_id} not found.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load company settings: {str(e)}")
        finally:
            db.close()

    def update_data(self):
        if not self.company_id:
            return

        db = SessionLocal()
        try:
            current_date = crud.get_simulation_date(db)
            next_dividend_date = crud.get_next_dividend_date(current_date)
            self.next_dividend_label.setText(f"Next Dividend Date: {next_dividend_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            print(f"Error updating CEO widget data: {str(e)}")
            self.next_dividend_label.setText("Next Dividend Date: Error")
        finally:
            db.close()

    def update_ceo_info(self):
        if not self.company_id:
            return

        db = SessionLocal()
        try:
            company = crud.get_company(db, self.company_id)
            if company and company.ceo:
                self.ceo_name_label.setText(f"CEO: {company.ceo.name}")
                self.ceo_capex_label.setText(f"CEO CAPEX Allocation: {company.ceo.capex_allocation:.2%}")
                self.ceo_dividend_label.setText(f"CEO Dividend Allocation: {company.ceo.dividend_allocation:.2%}")
                self.ceo_cash_inv_label.setText(f"CEO Cash/Investment Allocation: {company.ceo.cash_investment_allocation:.2%}")
            else:
                self.ceo_name_label.setText("CEO: N/A")
                self.ceo_capex_label.setText("CEO CAPEX Allocation: N/A")
                self.ceo_dividend_label.setText("CEO Dividend Allocation: N/A")
                self.ceo_cash_inv_label.setText("CEO Cash/Investment Allocation: N/A")
        finally:
            db.close()

    def update_change_ceo_button_visibility(self):
        if not self.company_id or not self.current_user_id:
            self.change_ceo_button.setVisible(False)
            return

        db = SessionLocal()
        try:
            company = crud.get_company(db, self.company_id)
            portfolio = crud.get_portfolio(db, self.current_user_id, self.company_id)
            is_majority_shareholder = portfolio and portfolio.shares / company.outstanding_shares > 0.5
            self.change_ceo_button.setVisible(is_majority_shareholder)
        finally:
            db.close()

    def change_ceo(self):
        if not self.company_id or not self.current_user_id:
            return

        db = SessionLocal()
        try:
            result, message = crud.change_ceo(db, self.company_id, self.current_user_id)
            if result:
                QMessageBox.information(self, "Success", message)
                self.update_ceo_info()
                self.settings_updated.emit()
            else:
                QMessageBox.warning(self, "Error", message)
        finally:
            db.close()

    def show_stock_split_dialog(self):
        if not self.company_id:
            QMessageBox.warning(self, "Error", "No company selected.")
            return

        db = SessionLocal()
        try:
            company = crud.get_company(db, self.company_id)
            if not company:
                QMessageBox.warning(self, "Error", f"Company with ID {self.company_id} not found.")
                return

            if company.stock_price < 20 or company.stock_price > 100:
                dialog = StockSplitDialog(company.stock_price, self)
                if dialog.exec():
                    split_ratio = dialog.get_split_ratio()
                    success = crud.execute_stock_split(db, self.company_id, split_ratio)
                    if success:
                        QMessageBox.information(self, "Success", f"Stock split ({split_ratio}) executed successfully.")
                        self.settings_updated.emit()
                    else:
                        QMessageBox.warning(self, "Error", "Failed to execute stock split.")
            else:
                QMessageBox.information(self, "Information", "Stock split is only available when the stock price is below $20 or above $100.")
        finally:
            db.close()

class StockSplitDialog(QDialog):
    def __init__(self, stock_price, parent=None):
        super().__init__(parent)
        self.stock_price = stock_price
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Stock Split Options")
        layout = QVBoxLayout(self)

        self.combo_box = QComboBox()
        if self.stock_price > 100:
            self.combo_box.addItems(["2:1", "3:1", "4:1", "5:1"])
        elif self.stock_price < 20:
            self.combo_box.addItems(["1:2", "1:3", "1:4", "1:5"])

        layout.addWidget(QLabel("Select split ratio:"))
        layout.addWidget(self.combo_box)

        buttons = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)    

        layout.addLayout(buttons)

    def get_split_ratio(self):
        return self.combo_box.currentText()