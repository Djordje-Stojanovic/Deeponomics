# services/order_matching.py
from sqlalchemy.orm import Session
from models import Order, Transaction, DBCompany, DBShareholder, DBPortfolio
from schemas import OrderType, OrderSubType
import crud
import uuid
import logging

logger = logging.getLogger(__name__)

def match_orders(company_id: str, db: Session):
    buy_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.BUY
    ).order_by(Order.price.desc()).all()

    sell_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL
    ).order_by(Order.price.asc()).all()

    for buy_order in buy_orders:
        for sell_order in sell_orders:
            if buy_order.price >= sell_order.price:
                execute_trade(buy_order, sell_order, db)
                if buy_order.shares == 0:
                    db.delete(buy_order)
                    break
            else:
                break  # No more matches possible
        if buy_order.shares > 0:
            db.add(buy_order)
    
    db.commit()
    logger.info(f"Matching completed for company {company_id}")

def execute_trade(buy_order: Order, sell_order: Order, db: Session):
    trade_shares = min(buy_order.shares, sell_order.shares)
    trade_price = sell_order.price

    transaction = Transaction(
        id=str(uuid.uuid4()),
        buyer_id=buy_order.shareholder_id,
        seller_id=sell_order.shareholder_id,
        company_id=buy_order.company_id,
        shares=trade_shares,
        price_per_share=trade_price
    )

    db.add(transaction)

    buy_order.shares -= trade_shares
    sell_order.shares -= trade_shares

    if sell_order.shares == 0:
        db.delete(sell_order)
    else:
        db.add(sell_order)

    crud.update_shareholder_portfolio(db, buy_order.shareholder_id, buy_order.company_id, trade_shares)
    crud.update_shareholder_portfolio(db, sell_order.shareholder_id, sell_order.company_id, -trade_shares)
    crud.update_shareholder_cash(db, buy_order.shareholder_id, -trade_shares * trade_price)
    crud.update_shareholder_cash(db, sell_order.shareholder_id, trade_shares * trade_price)

    company = crud.get_company(db, buy_order.company_id)
    company.stock_price = trade_price
    db.add(company)

    db.commit()
    logger.info(f"Trade executed: {trade_shares} shares at ${trade_price} per share")

def execute_market_order(order: Order, db: Session):
    company = crud.get_company(db, order.company_id)
    shareholder = crud.get_shareholder(db, order.shareholder_id)

    matching_orders = db.query(Order).filter(
        Order.company_id == order.company_id,
        Order.order_type == (OrderType.SELL if order.order_type == OrderType.BUY else OrderType.BUY)
    ).order_by(Order.price.asc() if order.order_type == OrderType.BUY else Order.price.desc()).all()
    
    executed_shares = 0
    transactions = []
    
    for matching_order in matching_orders:
        if executed_shares >= order.shares:
            break
        
        trade_shares = min(matching_order.shares, order.shares - executed_shares)
        trade_price = matching_order.price or company.stock_price

        transaction = Transaction(
            id=str(uuid.uuid4()),
            buyer_id=order.shareholder_id if order.order_type == OrderType.BUY else matching_order.shareholder_id,
            seller_id=matching_order.shareholder_id if order.order_type == OrderType.BUY else order.shareholder_id,
            company_id=order.company_id,
            shares=trade_shares,
            price_per_share=trade_price
        )
        
        db.add(transaction)
        transactions.append(transaction)
        
        executed_shares += trade_shares
        matching_order.shares -= trade_shares
        
        if matching_order.shares == 0:
            db.delete(matching_order)
        else:
            db.add(matching_order)

        crud.update_shareholder_portfolio(db, transaction.buyer_id, order.company_id, trade_shares)
        crud.update_shareholder_portfolio(db, transaction.seller_id, order.company_id, -trade_shares)
        crud.update_shareholder_cash(db, transaction.buyer_id, -trade_shares * trade_price)
        crud.update_shareholder_cash(db, transaction.seller_id, trade_shares * trade_price)

        company.stock_price = trade_price
        db.add(company)

    # Remove the market order after execution
    db.delete(order)
    
    db.commit()

    if executed_shares == 0:
        raise ValueError("Could not execute market order")

    logger.info(f"Market order executed: {executed_shares} shares in {len(transactions)} transactions")
    return transactions

def update_portfolio(db: Session, shareholder_id: str, company_id: str, shares_change: int):
    portfolio = crud.get_portfolio(db, shareholder_id, company_id)
    if portfolio:
        portfolio.shares += shares_change
        if portfolio.shares <= 0:
            db.delete(portfolio)
    elif shares_change > 0:
        new_portfolio = DBPortfolio(shareholder_id=shareholder_id, company_id=company_id, shares=shares_change)
        db.add(new_portfolio)

def update_shareholder_cash(db: Session, shareholder_id: str, cash_change: float):
    shareholder = crud.get_shareholder(db, shareholder_id)
    if shareholder:
        shareholder.cash += cash_change
        db.add(shareholder)