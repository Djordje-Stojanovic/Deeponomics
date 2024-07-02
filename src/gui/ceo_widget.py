from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSlider, QPushButton, QSpinBox, QMessageBox)
from PySide6.QtCore import Qt, Signal
import crud
from database import SessionLocal

class CEOWidget(QWidget):
    settings_updated = Signal()

    def __init__(self):
        super().__init__()
        self.company_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

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