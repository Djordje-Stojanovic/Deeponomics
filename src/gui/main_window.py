# src/gui/main_window.py
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QTabWidget, QInputDialog, QMessageBox
from PySide6.QtCore import QTimer
from .market_data_widget import MarketDataWidget
from .trading_widget import TradingWidget
from .portfolio_widget import PortfolioWidget
import crud
from database import SessionLocal

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Financial Market Simulation")
        self.current_user_id = None
        self.setup_ui()
        self.setup_data_update_timer()
        if not self.login():
            self.close()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        self.tab_widget = QTabWidget()
        self.market_data_widget = MarketDataWidget()
        self.trading_widget = TradingWidget()
        self.portfolio_widget = PortfolioWidget()
        
        self.tab_widget.addTab(self.market_data_widget, "Market Data")
        self.tab_widget.addTab(self.trading_widget, "Trading")
        self.tab_widget.addTab(self.portfolio_widget, "Portfolio")
        
        layout.addWidget(self.tab_widget)

    def setup_data_update_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)  # Update every second

    def update_data(self):
        self.market_data_widget.update_data()
        self.trading_widget.update_companies()
        if self.current_user_id:
            self.portfolio_widget.update_data(self.current_user_id)

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
            db.close()
            if shareholder:
                self.current_user_id = shareholder.id
                self.trading_widget.current_user_id = shareholder.id
                self.setWindowTitle(f"Financial Market Simulation - Logged in as {name}")
                return True
            else:
                QMessageBox.warning(self, "Error", f"Shareholder {name} not found.")
                return False
        else:
            return False