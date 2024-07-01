# src/gui/ceo_widget.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSlider, QPushButton, QSpinBox)
from PySide6.QtCore import Qt, Signal
import crud
from database import SessionLocal

class CEOWidget(QWidget):
    # Signal to notify when settings are updated
    settings_updated = Signal()

    def __init__(self, company_id):
        super().__init__()
        self.company_id = company_id
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

        # Cash vs Short-term Investments Slider
        cash_inv_layout = QHBoxLayout()
        self.cash_inv_slider = QSlider(Qt.Horizontal)
        self.cash_inv_slider.setRange(0, 100)
        self.cash_inv_slider.setValue(50)  # Default to 50/50 split
        self.cash_inv_label = QLabel("Cash: 50% | Investments: 50%")
        cash_inv_layout.addWidget(QLabel("Cash vs Investments:"))
        cash_inv_layout.addWidget(self.cash_inv_slider)
        cash_inv_layout.addWidget(self.cash_inv_label)
        layout.addLayout(cash_inv_layout)

        # Apply Button
        self.apply_button = QPushButton("Apply Changes")
        layout.addWidget(self.apply_button)

        # Connect signals
        self.capex_slider.valueChanged.connect(self.update_capex_label)
        self.cash_inv_slider.valueChanged.connect(self.update_cash_inv_label)
        self.apply_button.clicked.connect(self.apply_changes)

    def update_capex_label(self, value):
        self.capex_label.setText(f"CAPEX: {value}%")

    def update_cash_inv_label(self, value):
        self.cash_inv_label.setText(f"Cash: {value}% | Investments: {100-value}%")

    def apply_changes(self):
        capex_percentage = self.capex_slider.value() / 100
        cash_percentage = self.cash_inv_slider.value() / 100

        db = SessionLocal()
        try:
            company = crud.get_company(db, self.company_id)
            if company:
                # Update company settings
                company.capex_percentage = capex_percentage
                company.cash_allocation = cash_percentage
                db.commit()
                self.settings_updated.emit()
        finally:
            db.close()

    def load_company_settings(self):
        db = SessionLocal()
        try:
            company = crud.get_company(db, self.company_id)
            if company:
                self.capex_slider.setValue(int(company.capex_percentage * 100))
                self.cash_inv_slider.setValue(int(company.cash_allocation * 100))
        finally:
            db.close()