from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QTabWidget, QInputDialog, QMessageBox, QPushButton, QLabel, QHBoxLayout, QComboBox
from PySide6.QtCore import QTimer, QDateTime, Qt
from .market_data_widget import MarketDataWidget
from .trading_widget import TradingWidget
from .portfolio_widget import PortfolioWidget
from .ceo_widget import CEOWidget
from .financials_widget import FinancialsWidget
import crud
from database import SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import func
from models import DBCompany

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Financial Market Simulation")
        self.current_user_id = None
        self.current_company_id = None
        self.db = SessionLocal()
        self.simulation_date = crud.get_simulation_date(self.db)
        self.ceo_widget = CEOWidget()
        self.ceo_widget.settings_updated.connect(self.update_after_stock_split)
        self.is_paused = False
        self.setup_ui()
        self.setup_data_update_timer()
        if not self.login():
            self.close()
        self.populate_shareholder_selector()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.ceo_widget = CEOWidget()
        self.ceo_widget.settings_updated.connect(self.update_after_stock_split)
        main_layout = QVBoxLayout(central_widget)
        
        # Add control bar with pause button and date display
        control_bar = QHBoxLayout()
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.date_label = QLabel()
        self.update_date_display()
        
        # Add shareholder selector
        self.shareholder_selector = QComboBox()
        self.shareholder_selector.setFixedWidth(200)  # Adjust width as needed
        self.shareholder_selector.currentIndexChanged.connect(self.change_shareholder)

        control_bar.addWidget(self.pause_button)
        control_bar.addWidget(self.date_label)
        control_bar.addStretch()
        control_bar.addWidget(QLabel("Current User:"))
        control_bar.addWidget(self.shareholder_selector)
        
        main_layout.addLayout(control_bar)
        
        self.tab_widget = QTabWidget()
        self.market_data_widget = MarketDataWidget()
        self.trading_widget = TradingWidget()
        self.portfolio_widget = PortfolioWidget()
        self.ceo_widget = CEOWidget()
        self.financials_widget = FinancialsWidget(self.current_company_id)
        
        self.tab_widget.addTab(self.market_data_widget, "Market Data")
        self.tab_widget.addTab(self.trading_widget, "Trading")
        self.tab_widget.addTab(self.portfolio_widget, "Portfolio")
        self.tab_widget.addTab(self.ceo_widget, "CEO Dashboard")
        self.tab_widget.addTab(self.financials_widget, "Financials")
        
        main_layout.addWidget(self.tab_widget)

    def update_after_stock_split(self):
        self.market_data_widget.update_data()
        self.trading_widget.update_companies()
        if self.current_user_id:
            self.portfolio_widget.update_data(self.current_user_id)
        if self.current_company_id:
            self.financials_widget.update_data()

    def setup_data_update_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)  # Update every second

    def update_data(self):
        if not self.is_paused:
            self.simulation_date += timedelta(days=1)
            crud.update_simulation_date(self.db, self.simulation_date)
            self.update_date_display()
            self.market_data_widget.update_data()
            self.trading_widget.update_companies()
            if self.current_user_id:
                self.portfolio_widget.update_data(self.current_user_id)
            if self.current_company_id:
                self.financials_widget.update_data()
            self.ceo_widget.update_data()
            self.ceo_widget.update_change_ceo_button_visibility()  # Add this line

    def update_date_display(self):
        self.date_label.setText(f"Simulation Date: {self.simulation_date.strftime('%Y-%m-%d')}")    

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_button.setText("Resume")
        else:
            self.pause_button.setText("Pause")

    def login(self):
        db = SessionLocal()
        shareholders = crud.get_all_shareholders(db)
        db.close()
        
        if not shareholders:
            QMessageBox.warning(self, "Error", "No shareholders found in the database.")
            return False
        
        shareholder_names = [s.name for s in shareholders]
        name, ok = QInputDialog.getItem(self, "Login", "Select a shareholder:", shareholder_names, 0, False)
        
        if ok and name:
            db = SessionLocal()
            shareholder = next((s for s in shareholders if s.name == name), None)
            if shareholder:
                self.set_current_shareholder(shareholder.id, db)
                db.close()
                return True
            else:
                db.close()
                QMessageBox.warning(self, "Error", f"Shareholder {name} not found.")
                return False
        else:
            return False

    def change_shareholder(self, index):
        shareholder_id = self.shareholder_selector.itemData(index)
        if shareholder_id and shareholder_id != self.current_user_id:
            db = SessionLocal()
            self.set_current_shareholder(shareholder_id, db)
            db.close()

    def set_current_shareholder(self, shareholder_id, db):
        self.current_user_id = shareholder_id
        self.trading_widget.set_current_user_id(shareholder_id)
        self.ceo_widget.set_current_user_id(shareholder_id)  # Add this line

        shareholder = crud.get_shareholder(db, shareholder_id)
        company = crud.get_company_by_founder(db, shareholder_id)

        if company:
            self.current_company_id = company.id
            self.ceo_widget.set_company_id(company.id)
            self.financials_widget.company_id = company.id
            self.ceo_widget.load_company_settings()
            self.financials_widget.update_data()
        else:
            self.current_company_id = None
            self.ceo_widget.set_company_id(None)
            self.financials_widget.company_id = None

        self.setWindowTitle(f"Financial Market Simulation - Logged in as {shareholder.name}")
        self.portfolio_widget.update_data(shareholder_id)
        self.ceo_widget.update_change_ceo_button_visibility()  # Add this line

    def get_latest_simulation_date(self):
        db = SessionLocal()
        try:
            # Query the latest update date from the companies table
            latest_date = db.query(func.max(DBCompany.last_update)).scalar()
            
            if latest_date:
                # If we have a date in the database, use it
                return QDateTime(latest_date)
            else:
                # If no date is found (fresh database), return the default start date
                return QDateTime(2020, 1, 1, 0, 0, 0)
        except Exception as e:
            print(f"Error fetching latest simulation date: {str(e)}")
            # In case of any error, return the default start date
            return QDateTime(2020, 1, 1, 0, 0, 0)
        finally:
            db.close()

    def populate_shareholder_selector(self):
        self.shareholder_selector.clear()
        db = SessionLocal()
        shareholders = crud.get_all_shareholders(db)
        db.close()

        for shareholder in shareholders:
            self.shareholder_selector.addItem(shareholder.name, shareholder.id)

        # Set the current shareholder
        index = self.shareholder_selector.findData(self.current_user_id)
        if index >= 0:
            self.shareholder_selector.setCurrentIndex(index)

    def closeEvent(self, event):
        crud.update_simulation_date(self.db, self.simulation_date)
        self.db.close()
        super().closeEvent(event)