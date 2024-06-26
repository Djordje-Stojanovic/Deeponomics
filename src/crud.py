# crud.py
import logging
from sqlalchemy.orm import Session
from models import DBShareholder, DBCompany, DBPortfolio, Order, Transaction
from schemas import OrderCreate, OrderType
import uuid
from sqlalchemy import func

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
    db_order = Order(
        id=str(uuid.uuid4()),
        shareholder_id=order.shareholder_id,
        company_id=order.company_id,
        order_type=order.order_type,
        order_subtype=order.order_subtype,
        shares=order.shares,
        price=order.price
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

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

def get_portfolio(db: Session, shareholder_id: str, company_id: str):
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