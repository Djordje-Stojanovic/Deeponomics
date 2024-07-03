from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QTabWidget, QInputDialog, QMessageBox, QPushButton, QLabel, QHBoxLayout
from PySide6.QtCore import QTimer, QDateTime, Qt
from .market_data_widget import MarketDataWidget
from .trading_widget import TradingWidget
from .portfolio_widget import PortfolioWidget
from .ceo_widget import CEOWidget
from .financials_widget import FinancialsWidget
import crud
from database import SessionLocal
from datetime import time, datetime
from sqlalchemy import func
from models import DBCompany

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Financial Market Simulation")
        self.current_user_id = None
        self.current_company_id = None
        self.simulation_date = self.get_latest_simulation_date()  # Use the new method here
        self.is_paused = False
        self.setup_ui()
        self.setup_data_update_timer()
        if not self.login():
            self.close()

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
        
        control_bar.addWidget(self.pause_button)
        control_bar.addWidget(self.date_label)
        control_bar.addStretch()  # This pushes the date label to the right
        
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
            self.simulation_date = self.simulation_date.addDays(1)
            self.update_date_display()
            self.market_data_widget.update_data()
            self.trading_widget.update_companies()
            if self.current_user_id:
                self.portfolio_widget.update_data(self.current_user_id)
            if self.current_company_id:
                self.financials_widget.update_data()

    def update_date_display(self):
        self.date_label.setText(f"Simulation Date: {self.simulation_date.toString('yyyy-MM-dd')}")

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
                self.current_user_id = shareholder.id
                self.trading_widget.current_user_id = shareholder.id
                
                company = crud.get_company_by_founder(db, shareholder.id)
                if company:
                    self.current_company_id = company.id
                    self.ceo_widget.set_company_id(company.id)
                    self.financials_widget.company_id = company.id
                    self.ceo_widget.load_company_settings()
                    self.financials_widget.update_data()
                else:
                    QMessageBox.warning(self, "Notice", "This shareholder is not a founder of any company.")
                
                db.close()
                self.setWindowTitle(f"Financial Market Simulation - Logged in as {name}")
                return True
            else:
                db.close()
                QMessageBox.warning(self, "Error", f"Shareholder {name} not found.")
                return False
        else:
            return False
        
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