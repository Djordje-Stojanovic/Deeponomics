from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QTabWidget, QInputDialog, QMessageBox
from PySide6.QtCore import QTimer
from .market_data_widget import MarketDataWidget
from .trading_widget import TradingWidget
from .portfolio_widget import PortfolioWidget
from .ceo_widget import CEOWidget
from .financials_widget import FinancialsWidget
import crud
from database import SessionLocal

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Financial Market Simulation")
        self.current_user_id = None
        self.current_company_id = None
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
        self.ceo_widget = CEOWidget()
        self.financials_widget = FinancialsWidget(self.current_company_id)
        
        self.tab_widget.addTab(self.market_data_widget, "Market Data")
        self.tab_widget.addTab(self.trading_widget, "Trading")
        self.tab_widget.addTab(self.portfolio_widget, "Portfolio")
        self.tab_widget.addTab(self.ceo_widget, "CEO Dashboard")
        self.tab_widget.addTab(self.financials_widget, "Financials")
        
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
        if self.current_company_id:
            self.financials_widget.update_data()

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