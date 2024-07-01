from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
import crud
from database import SessionLocal

class FinancialsWidget(QWidget):
    def __init__(self, company_id):
        super().__init__()
        self.company_id = company_id
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        self.income_statement_table = QTableWidget()
        self.balance_sheet_table = QTableWidget()
        self.cash_flow_table = QTableWidget()
        
        self.tab_widget.addTab(self.income_statement_table, "Income Statement")
        self.tab_widget.addTab(self.balance_sheet_table, "Balance Sheet")
        self.tab_widget.addTab(self.cash_flow_table, "Cash Flow Statement")
        
        layout.addWidget(self.tab_widget)

    def update_data(self):
        self.update_income_statement()
        self.update_balance_sheet()
        self.update_cash_flow_statement()

    def update_income_statement(self):
        db = SessionLocal()
        income_statement = crud.get_income_statement(db, self.company_id)
        db.close()

        self.income_statement_table.setRowCount(len(income_statement))
        self.income_statement_table.setColumnCount(2)
        self.income_statement_table.setHorizontalHeaderLabels(["Item", "Amount"])

        for row, (item, amount) in enumerate(income_statement.items()):
            self.income_statement_table.setItem(row, 0, QTableWidgetItem(item.replace('_', ' ').title()))
            self.income_statement_table.setItem(row, 1, QTableWidgetItem(f"${amount:.2f}"))

        self.income_statement_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def update_balance_sheet(self):
        db = SessionLocal()
        balance_sheet = crud.get_balance_sheet(db, self.company_id)
        db.close()

        total_rows = sum(len(section) for section in balance_sheet.values())
        self.balance_sheet_table.setRowCount(total_rows + len(balance_sheet))
        self.balance_sheet_table.setColumnCount(2)
        self.balance_sheet_table.setHorizontalHeaderLabels(["Item", "Amount"])

        row = 0
        for section, items in balance_sheet.items():
            self.balance_sheet_table.setItem(row, 0, QTableWidgetItem(section))
            row += 1
            for item, amount in items.items():
                self.balance_sheet_table.setItem(row, 0, QTableWidgetItem(f"  {item.replace('_', ' ').title()}"))
                self.balance_sheet_table.setItem(row, 1, QTableWidgetItem(f"${amount:.2f}"))
                row += 1

        self.balance_sheet_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def update_cash_flow_statement(self):
        db = SessionLocal()
        cash_flow = crud.get_cash_flow_statement(db, self.company_id)
        db.close()

        total_rows = sum(len(section) for section in cash_flow.values() if isinstance(section, dict))
        self.cash_flow_table.setRowCount(total_rows + len(cash_flow))
        self.cash_flow_table.setColumnCount(2)
        self.cash_flow_table.setHorizontalHeaderLabels(["Item", "Amount"])

        row = 0
        for section, items in cash_flow.items():
            self.cash_flow_table.setItem(row, 0, QTableWidgetItem(section))
            row += 1
            if isinstance(items, dict):
                for item, amount in items.items():
                    self.cash_flow_table.setItem(row, 0, QTableWidgetItem(f"  {item.replace('_', ' ').title()}"))
                    self.cash_flow_table.setItem(row, 1, QTableWidgetItem(f"${amount:.2f}"))
                    row += 1
            else:
                self.cash_flow_table.setItem(row, 1, QTableWidgetItem(f"${items:.2f}"))
                row += 1

        self.cash_flow_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)