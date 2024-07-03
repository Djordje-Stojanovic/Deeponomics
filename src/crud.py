# crud.py
import logging
import random
from sqlalchemy.orm import Session
from models import DBShareholder, DBCompany, DBPortfolio, Order, Transaction, Sector, GlobalSettings
from schemas import OrderCreate, OrderType, OrderSubType
from fastapi import BackgroundTasks
import asyncio
import uuid
from sqlalchemy import func
from database import SessionLocal 
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def update_company_performance(db: Session, company_id: str):
    company = get_company(db, company_id)
    if not company:
        return None

    # Simple revenue generation (based on company size)
    base_revenue = company.outstanding_shares * company.stock_price * 0.001  # Adjusted for daily revenue
    revenue_fluctuation = random.uniform(0.95, 1.05)  # 5% daily fluctuation
    company.revenue = base_revenue * revenue_fluctuation

    # Simple cost calculation (70-90% of revenue)
    cost_ratio = random.uniform(0.7, 0.9)
    company.costs = company.revenue * cost_ratio

    # Calculate daily profit
    daily_profit = company.revenue - company.costs
    
    # Update company financials
    company.profit = daily_profit
    company.total_profit += daily_profit
    company.days_active += 1

    db.add(company)
    db.commit()
    db.refresh(company)

    return company

async def run_company_ticks():
    while True:
        db = SessionLocal()
        try:
            companies = get_all_companies(db)
            for company in companies:
                update_company_performance(db, company.id)
            db.commit()
            await asyncio.sleep(1)  # Wait for 1 second before the next tick
        except Exception as e:
            logger.error(f"Error in run_company_ticks: {str(e)}")
            db.rollback()
        finally:
            db.close()

def update_stock_price(db: Session, company_id: str):
    company = get_company(db, company_id)
    if not company:
        logger.error(f"Company not found: {company_id}")
        return None

    # First, check for the lowest current sell limit order price
    lowest_sell_limit = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL,
        Order.order_subtype == OrderSubType.LIMIT
    ).order_by(Order.price.asc()).first()

    if lowest_sell_limit:
        new_price = lowest_sell_limit.price
        logger.info(f"Setting price based on lowest sell limit order: ${new_price}")
    else:
        # If no sell limit orders, get the latest transaction price
        latest_transaction = db.query(Transaction).filter(
            Transaction.company_id == company_id
        ).order_by(Transaction.id.desc()).first()
        
        if latest_transaction:
            new_price = latest_transaction.price_per_share
            logger.info(f"Setting price based on latest transaction: ${new_price}")
        else:
            # If no transactions and no sell limit orders, keep the current price
            new_price = company.stock_price
            logger.info(f"No new price found, keeping current price: ${new_price}")

    if new_price != company.stock_price:
        company.stock_price = new_price
        db.add(company)
        db.commit()
        logger.info(f"Updated stock price for company {company_id} to ${new_price}")
    else:
        logger.info(f"Stock price for company {company_id} remains unchanged at ${new_price}")

    return company.stock_price

def create_shareholder(db: Session, name: str, initial_cash: float):
    shareholder_id = str(uuid.uuid4())
    db_shareholder = DBShareholder(id=shareholder_id, name=name, cash=initial_cash)
    db.add(db_shareholder)
    db.commit()
    db.refresh(db_shareholder)
    return db_shareholder

def get_shareholder(db: Session, shareholder_id: str):
    return db.query(DBShareholder).filter(DBShareholder.id == shareholder_id).first()

def get_all_shareholders(db: Session):
    return db.query(DBShareholder).all()

def create_company(db: Session, name: str, initial_stock_price: float, initial_shares: int, founder_id: str, sector: Sector):
    founder = get_shareholder(db, founder_id)
    if not founder:
        return None
    
    try:
        company_id = str(uuid.uuid4())
        db_company = DBCompany(
            id=company_id, 
            name=name, 
            stock_price=initial_stock_price, 
            outstanding_shares=initial_shares,
            founder_id=founder_id,
            sector=sector  # Add the sector here
        )
        db.add(db_company)
        
        db_portfolio = DBPortfolio(shareholder_id=founder_id, company_id=company_id, shares=initial_shares)
        db.add(db_portfolio)
        
        db.commit()
        db.refresh(db_company)
        return db_company
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating company: {str(e)}")
        return None

def get_company(db: Session, company_id: str):
    return db.query(DBCompany).filter(DBCompany.id == company_id).first()

def get_all_companies(db: Session):
    return db.query(DBCompany).all()

def create_order(db: Session, order: OrderCreate):
    # Check if the shareholder exists
    shareholder = db.query(DBShareholder).filter(DBShareholder.id == order.shareholder_id).first()
    if not shareholder:
        return None, f"Shareholder not found: {order.shareholder_id}"

    # Check if the company exists
    company = get_company(db, order.company_id)
    if not company:
        return None, f"Company not found: {order.company_id}"

    if order.order_type == OrderType.BUY:
        if order.order_subtype == OrderSubType.LIMIT:
            # Check if the shareholder has enough cash for limit buy orders
            total_cost = order.shares * order.price
            if shareholder.cash < total_cost:
                return None, f"Insufficient funds. Required: {total_cost}, Available: {shareholder.cash}"

        # Get shareholder's current portfolio
        portfolio = get_portfolio(db, order.shareholder_id, order.company_id)
        current_shares = portfolio.shares if portfolio else 0

        # Get shareholder's current buy orders
        current_buy_orders = db.query(func.sum(Order.shares)).filter(
            Order.shareholder_id == order.shareholder_id,
            Order.company_id == order.company_id,
            Order.order_type == OrderType.BUY
        ).scalar() or 0

        # Calculate available shares for this shareholder
        available_shares = company.outstanding_shares - current_shares - current_buy_orders

        if order.shares > available_shares:
            return None, f"Not enough available shares. Requested: {order.shares}, Available: {available_shares}"

        if order.order_subtype == OrderSubType.LIMIT:
            # Check if total cost of all buy orders (including this one) exceeds available cash
            total_buy_orders_cost = db.query(func.sum(Order.shares * Order.price)).filter(
                Order.shareholder_id == order.shareholder_id,
                Order.company_id == order.company_id,
                Order.order_type == OrderType.BUY,
                Order.order_subtype == OrderSubType.LIMIT
            ).scalar() or 0
            total_buy_orders_cost += total_cost

            if total_buy_orders_cost > shareholder.cash:
                return None, f"Insufficient funds for all buy orders. Required: {total_buy_orders_cost}, Available: {shareholder.cash}"

    elif order.order_type == OrderType.SELL:
        # Check if the shareholder owns enough shares
        portfolio = get_portfolio(db, order.shareholder_id, order.company_id)
        if not portfolio or portfolio.shares < order.shares:
            return None, f"Insufficient shares. Required: {order.shares}, Available: {portfolio.shares if portfolio else 0}"

    # If all checks pass, create the order
    db_order = Order(
        id=str(uuid.uuid4()),
        shareholder_id=order.shareholder_id,
        company_id=order.company_id,
        order_type=order.order_type,
        order_subtype=order.order_subtype,
        shares=order.shares,
        price=order.price if order.order_subtype == OrderSubType.LIMIT else None
    )
    db.add(db_order)
    try:
        db.commit()
        db.refresh(db_order)
        return db_order, None
    except Exception as e:
        db.rollback()
        return None, f"Error committing order to database: {str(e)}"
    
def cancel_order(db: Session, order_id: str):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        db.delete(order)
        db.commit()
        return True
    return False

def get_shareholder_orders(db: Session, shareholder_id: str):
    return db.query(Order).filter(Order.shareholder_id == shareholder_id).all()

def get_shareholder_portfolio(db: Session, shareholder_id: str):
    return db.query(DBPortfolio).filter(DBPortfolio.shareholder_id == shareholder_id).all()

def get_order_book(db: Session, company_id: str):
    buy_orders = db.query(Order).filter(Order.company_id == company_id, Order.order_type == OrderType.BUY).all()
    sell_orders = db.query(Order).filter(Order.company_id == company_id, Order.order_type == OrderType.SELL).all()
    return {'buy': buy_orders, 'sell': sell_orders}

def get_pending_sell_orders(db: Session, shareholder_id: str, company_id: str) -> int:
    pending_shares = db.query(func.sum(Order.shares)).filter(
        Order.shareholder_id == shareholder_id,
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL
    ).scalar()
    return pending_shares or 0

def get_portfolio(db: Session, shareholder_id: str, company_id: str) -> Optional[DBPortfolio]:
    return db.query(DBPortfolio).filter(
        DBPortfolio.shareholder_id == shareholder_id,
        DBPortfolio.company_id == company_id
    ).first()

def update_company_shares(db: Session, company_id: str):
    company = get_company(db, company_id)
    if company:
        total_shares = db.query(func.sum(DBPortfolio.shares)).filter(
            DBPortfolio.company_id == company_id
        ).scalar() or 0
        company.outstanding_shares = total_shares
        db.commit()
        return True
    return False

def execute_transaction(db: Session, transaction: Transaction):
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction

def update_shareholder_portfolio(db: Session, shareholder_id: str, company_id: str, shares_change: int):
    portfolio = get_portfolio(db, shareholder_id, company_id)
    if portfolio:
        portfolio.shares += shares_change
        if portfolio.shares <= 0:
            db.delete(portfolio)
        else:
            db.add(portfolio)
    elif shares_change > 0:
        new_portfolio = DBPortfolio(shareholder_id=shareholder_id, company_id=company_id, shares=shares_change)
        db.add(new_portfolio)
    db.commit()
    logger.info(f"Updated portfolio for shareholder {shareholder_id}: {shares_change} shares change")

def update_shareholder_cash(db: Session, shareholder_id: str, cash_change: float):
    shareholder = get_shareholder(db, shareholder_id)
    if shareholder:
        shareholder.cash += cash_change
        db.add(shareholder)
        db.commit()
        logger.info(f"Updated cash for shareholder {shareholder_id}: ${cash_change} change")
    else:
        logger.error(f"Shareholder {shareholder_id} not found for cash update")

def get_transaction_history(db: Session, company_id: str = None, shareholder_id: str = None):
    query = db.query(Transaction)
    if company_id:
        query = query.filter(Transaction.company_id == company_id)
    if shareholder_id:
        query = query.filter((Transaction.buyer_id == shareholder_id) | (Transaction.seller_id == shareholder_id))
    return query.order_by(Transaction.id.desc()).all()

def get_total_buy_orders(db: Session, company_id: str) -> int:
    total_shares = db.query(func.sum(Order.shares)).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.BUY
    ).scalar()
    return total_shares or 0

def get_lowest_sell_order(db: Session, company_id: str):
    return db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL
    ).order_by(Order.price.asc()).first()

def get_total_shares_held(db: Session, company_id: str) -> int:
    total_shares = db.query(func.sum(DBPortfolio.shares)).filter(DBPortfolio.company_id == company_id).scalar()
    return total_shares or 0

from datetime import datetime, timedelta

def get_cash_flow_statement(db: Session, company_id: str):
    try:
        company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
        if not company:
            logger.error(f"Company with id {company_id} not found")
            return None

        # Get income statement for net income
        income_statement = get_income_statement(db, company_id)
        if not income_statement:
            return None

        net_income = income_statement['net_income']

        # Calculate Cash from Operations (CFO)
        cfo = net_income + company.gain_loss_investments + company.interest_income - company.change_in_nwc

        # Calculate Cash from Investing (CFI)
        cfi = -company.capex  # Daily CAPEX

        # Calculate daily dividend accrual
        daily_dividend_accrual = cfo * company.dividend_payout_percentage

        # Calculate Cash from Financing (CFF)
        cff = (company.debt_issued + company.stock_issued) - (company.debt_repaid + company.stock_buyback + daily_dividend_accrual)

        # Calculate Net Change in Cash
        net_change_in_cash = cfo + cfi + cff

        # Calculate Free Cash Flow
        free_cash_flow = cfo - company.capex

        return {
            "Cash from Operations (CFO)": {
                "Net Income": net_income,
                "Gain/Loss from Sale of Investments": company.gain_loss_investments,
                "Interest Income": company.interest_income,
                "Change in Net Working Capital": -company.change_in_nwc,  # Negative because increase in NWC reduces cash
                "Total CFO": cfo
            },
            "Cash from Investing (CFI)": {
                "Capital Expenditures (Capex)": -company.capex,
                "Total CFI": cfi
            },
            "Cash from Financing (CFF)": {
                "Debt Issued": company.debt_issued,
                "Debt Repaid": -company.debt_repaid,
                "Stock Issued/Repurchased": company.stock_issued - company.stock_buyback,
                "Dividend Accrual": -daily_dividend_accrual,  # Show as negative because it's cash outflow
                "Total CFF": cff
            },
            "Net Change in Cash": net_change_in_cash,
            "Free Cash Flow": free_cash_flow
        }
    except Exception as e:
        logger.error(f"Error generating cash flow statement for company {company_id}: {str(e)}")
        return None

def update_company_daily(db: Session, company_id: str):
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    if not company:
        logger.error(f"Company with id {company_id} not found")
        return None
    
    current_date = get_simulation_date(db)

    # Update revenue based on business assets
    company.annual_revenue = company.business_assets
    
    # Calculate daily values
    daily_revenue = company.annual_revenue / 365
    daily_cost_of_revenue = daily_revenue * company.cost_of_revenue_percentage
    daily_gross_profit = daily_revenue - daily_cost_of_revenue
    daily_rd_spend = daily_gross_profit * company.rd_spend_percentage
    daily_operating_income = daily_gross_profit - daily_rd_spend
    daily_interest_expense = (company.issued_bonds + company.issued_debt) * 0.05 / 365  # Assuming 5% annual interest rate
    daily_ebt = daily_operating_income - daily_interest_expense
    daily_taxes = daily_ebt * 0.21  # 21% tax rate
    daily_net_income = daily_ebt - daily_taxes

    # Calculate daily interest income from short-term investments
    daily_interest_income = company.short_term_investments * (0.03 / 365)
    company.interest_income = daily_interest_income
    company.short_term_investments += daily_interest_income

    # Calculate Cash from Operations (CFO)
    daily_cfo = daily_net_income + (company.gain_loss_investments / 365) + daily_interest_income

    # Update working capital (10% of business assets)
    required_working_capital = company.business_assets * 0.1
    working_capital_adjustment = required_working_capital - company.working_capital
    
    # Update change_in_nwc
    company.change_in_nwc = working_capital_adjustment

    if working_capital_adjustment > 0:
        # Need to increase working capital
        if daily_cfo >= working_capital_adjustment:
            company.working_capital += working_capital_adjustment
            daily_cfo -= working_capital_adjustment
        else:
            # Use CFO and short-term investments if needed
            company.working_capital += daily_cfo
            remaining_adjustment = working_capital_adjustment - daily_cfo
            daily_cfo = 0
            if company.short_term_investments >= remaining_adjustment:
                company.short_term_investments -= remaining_adjustment
                company.working_capital += remaining_adjustment
            else:
                company.working_capital += company.short_term_investments
                company.short_term_investments = 0
    elif working_capital_adjustment < 0:
        # Excess working capital, move to CFO
        company.working_capital = required_working_capital
        daily_cfo -= working_capital_adjustment  # This adds to CFO because adjustment is negative

    # Apply CEO's CAPEX decision
    daily_capex = daily_cfo * company.capex_percentage
    company.capex = daily_capex
    company.business_assets += daily_capex

    # Calculate remaining CFO after CAPEX
    remaining_cfo = daily_cfo - daily_capex

    # Accumulate dividends in the dividend account
    daily_dividends = remaining_cfo * company.dividend_payout_percentage
    company.dividend_account += daily_dividends

    # Check if it's time for quarterly dividend payout
    if is_quarter_end(current_date) and company.dividend_account > 0:
        distribute_quarterly_dividends(db, company, current_date)

    # Apply CEO's cash vs short-term investments decision to remaining CFO after dividend accumulation
    remaining_cfo_after_dividends = remaining_cfo - daily_dividends
    cash_increase = remaining_cfo_after_dividends * company.cash_allocation
    investments_increase = remaining_cfo_after_dividends * (1 - company.cash_allocation)

    company.cash += cash_increase
    company.short_term_investments += investments_increase

    # Simulate R&D effect on cost efficiency (simplified)
    if company.rd_spend_percentage > 0:
        company.cost_of_revenue_percentage *= 0.9999  # Small daily improvement

    company.last_update = current_date
    db.commit()
    return company

def is_quarter_end(date: datetime) -> bool:
    return date.month in [3, 6, 9, 12] and date.day == 31

def distribute_quarterly_dividends(db: Session, company: DBCompany, current_date: datetime):
    total_dividends = company.dividend_account
    shareholders = db.query(DBPortfolio).filter(DBPortfolio.company_id == company.id).all()
    total_shares = sum(shareholder.shares for shareholder in shareholders)
    
    for shareholder in shareholders:
        dividend_share = (shareholder.shares / total_shares) * total_dividends
        after_tax_dividend = dividend_share * 0.8  # 20% tax rate
        shareholder_account = db.query(DBShareholder).filter(DBShareholder.id == shareholder.shareholder_id).first()
        shareholder_account.cash += after_tax_dividend
    
    company.dividends_paid += total_dividends
    company.dividend_account = 0  # Empty the dividend account after payout
    company.last_dividend_payout_date = current_date
    db.commit()
    logger.info(f"Distributed quarterly dividends for company {company.id}: ${total_dividends:.2f}")

def get_income_statement(db: Session, company_id: str):
    try:
        company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
        if not company:
            logger.error(f"Company with id {company_id} not found")
            return None

        daily_revenue = company.annual_revenue / 365
        daily_cost_of_revenue = daily_revenue * company.cost_of_revenue_percentage
        daily_gross_profit = daily_revenue - daily_cost_of_revenue
        daily_rd_spend = daily_gross_profit * company.rd_spend_percentage
        daily_operating_income = daily_gross_profit - daily_rd_spend
        daily_interest_expense = (company.issued_bonds + company.issued_debt) * 0.05 / 365  # Assuming 5% annual interest rate
        daily_ebt = daily_operating_income - daily_interest_expense
        daily_taxes = daily_ebt * 0.21
        daily_net_income = daily_ebt - daily_taxes

        return {
            "revenue": daily_revenue,
            "cost_of_revenue": daily_cost_of_revenue,
            "gross_profit": daily_gross_profit,
            "rd_spend": daily_rd_spend,
            "operating_income": daily_operating_income,
            "interest_expense": daily_interest_expense,
            "ebt": daily_ebt,
            "taxes": daily_taxes,
            "net_income": daily_net_income
        }
    except Exception as e:
        logger.error(f"Error generating income statement for company {company_id}: {str(e)}")
        return None

def get_balance_sheet(db: Session, company_id: str):
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    if not company:
        logger.error(f"Company with id {company_id} not found")
        return None

    return {
        "Assets": {
            "Cash": company.cash,
            "Short-term Investments": company.short_term_investments,
            "Business Assets": company.business_assets,
            "Working Capital": company.working_capital,
            "Marketable Securities": company.marketable_securities,
            "Total Assets": company.total_assets
        },
        "Liabilities": {
            "Issued Bonds": company.issued_bonds,
            "Issued Debt": company.issued_debt,
            "Dividend Reserve": company.dividend_account,  # Add this line
            "Total Liabilities": company.total_liabilities + company.dividend_account  # Update this line
        },
        "Equity": {
            "Total Equity": company.total_equity - company.dividend_account  # Update this line
        }
    }

def get_company_by_founder(db: Session, founder_id: str):
    return db.query(DBCompany).filter(DBCompany.founder_id == founder_id).first()

def get_next_dividend_date(current_date: datetime) -> datetime:
    year = current_date.year
    month = current_date.month
    day = current_date.day

    if month < 3 or (month == 3 and day <= 31):
        return datetime(year, 3, 31)
    elif month < 6 or (month == 6 and day <= 30):
        return datetime(year, 6, 30)
    elif month < 9 or (month == 9 and day <= 30):
        return datetime(year, 9, 30)
    elif month < 12 or (month == 12 and day <= 31):
        return datetime(year, 12, 31)
    else:
        return datetime(year + 1, 3, 31)

def execute_stock_split(db: Session, company_id: str, split_ratio: str):
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    if not company:
        return False

    numerator, denominator = map(int, split_ratio.split(':'))
    
    # Determine if it's a regular split or reverse split
    is_reverse_split = numerator < denominator

    # Update company's outstanding shares and stock price
    if is_reverse_split:
        company.outstanding_shares = company.outstanding_shares * numerator // denominator
        company.stock_price = company.stock_price * denominator / numerator
    else:
        company.outstanding_shares = company.outstanding_shares * numerator // denominator
        company.stock_price = company.stock_price * denominator / numerator

    # Update all portfolios
    portfolios = db.query(DBPortfolio).filter(DBPortfolio.company_id == company_id).all()
    for portfolio in portfolios:
        if is_reverse_split:
            portfolio.shares = portfolio.shares * numerator // denominator
        else:
            portfolio.shares = portfolio.shares * numerator // denominator

    # Update all open orders
    orders = db.query(Order).filter(Order.company_id == company_id).all()
    for order in orders:
        if is_reverse_split:
            order.shares = order.shares * numerator // denominator
            if order.price:
                order.price = order.price * denominator / numerator
        else:
            order.shares = order.shares * numerator // denominator
            if order.price:
                order.price = order.price * denominator / numerator

    try:
        db.commit()
        return True
    except Exception as e:
        print(f"Error executing stock split: {str(e)}")
        db.rollback()
        return False
    
def get_simulation_date(db: Session) -> datetime:
    setting = db.query(GlobalSettings).filter(GlobalSettings.key == "simulation_date").first()
    if setting:
        return datetime.fromisoformat(setting.value)
    return datetime(2020, 1, 1)  # Default start date

def update_simulation_date(db: Session, new_date: datetime):
    setting = db.query(GlobalSettings).filter(GlobalSettings.key == "simulation_date").first()
    if setting:
        setting.value = new_date.isoformat()
        setting.last_updated = datetime.now()
    else:
        new_setting = GlobalSettings(key="simulation_date", value=new_date.isoformat(), last_updated=datetime.now())
        db.add(new_setting)
    db.commit()

def init_simulation_date(db: Session):
    setting = db.query(GlobalSettings).filter(GlobalSettings.key == "simulation_date").first()
    if not setting:
        default_start_date = datetime(2020, 1, 1)
        new_setting = GlobalSettings(
            key="simulation_date",
            value=default_start_date.isoformat(),
            last_updated=datetime.now()
        )
        db.add(new_setting)
        db.commit()
        print(f"Initialized simulation date to {default_start_date}")
    else:
        print(f"Simulation date already exists: {setting.value}")