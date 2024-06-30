# crud.py
import logging
import random
from sqlalchemy.orm import Session
from models import DBShareholder, DBCompany, DBPortfolio, Order, Transaction
from schemas import OrderCreate, OrderType, OrderSubType
from fastapi import BackgroundTasks
import asyncio
import uuid
from sqlalchemy import func
from database import SessionLocal 
from typing import Optional

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

def create_company(db: Session, name: str, initial_stock_price: float, initial_shares: int, founder_id: str):
    founder = get_shareholder(db, founder_id)
    if not founder:
        return None
    
    try:
        company_id = str(uuid.uuid4())
        db_company = DBCompany(id=company_id, name=name, stock_price=initial_stock_price, outstanding_shares=initial_shares)
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
    
    return db_company

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