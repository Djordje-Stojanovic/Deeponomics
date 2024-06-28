# services/order_matching.py
from sqlalchemy.orm import Session
from models import Order, Transaction, DBCompany, DBShareholder, DBPortfolio
from schemas import OrderType, OrderSubType
import crud
import uuid
import logging
from crud import update_stock_price

logger = logging.getLogger(__name__)

def match_orders(company_id: str, db: Session):
    # First, execute all market buy orders
    market_buy_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.BUY,
        Order.order_subtype == OrderSubType.MARKET
    ).all()

    for market_buy_order in market_buy_orders:
        try:
            execute_market_order(market_buy_order, db)
        except ValueError as e:
            logger.warning(f"Failed to execute market buy order: {str(e)}")

    # Then, execute all market sell orders
    market_sell_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL,
        Order.order_subtype == OrderSubType.MARKET
    ).all()

    for market_sell_order in market_sell_orders:
        try:
            execute_market_order(market_sell_order, db)
        except ValueError as e:
            logger.warning(f"Failed to execute market sell order: {str(e)}")

    # Finally, match limit orders as before
    limit_buy_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.BUY,
        Order.order_subtype == OrderSubType.LIMIT
    ).order_by(Order.price.desc()).all()

    limit_sell_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL,
        Order.order_subtype == OrderSubType.LIMIT
    ).order_by(Order.price.asc()).all()

    for buy_order in limit_buy_orders:
        for sell_order in limit_sell_orders:
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
    update_stock_price(db, company_id)
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
    update_stock_price(db, buy_order.company_id)
    db.add(company)

    db.commit()
    logger.info(f"Trade executed: {trade_shares} shares at ${trade_price} per share")

def execute_market_order(order: Order, db: Session):
    company = crud.get_company(db, order.company_id)
    buyer = crud.get_shareholder(db, order.shareholder_id)

    opposing_orders = db.query(Order).filter(
        Order.company_id == order.company_id,
        Order.order_type != order.order_type
    ).order_by(Order.price.asc() if order.order_type == OrderType.BUY else Order.price.desc()).all()
    
    executed_shares = 0
    transactions = []
    
    for opposing_order in opposing_orders:
        if executed_shares >= order.shares:
            break
        
        trade_shares = min(opposing_order.shares, order.shares - executed_shares)
        trade_price = opposing_order.price or company.stock_price

        # Check if buyer has enough cash for buy orders
        if order.order_type == OrderType.BUY:
            max_affordable_shares = int(buyer.cash // trade_price)
            if max_affordable_shares < trade_shares:
                if max_affordable_shares > 0:
                    trade_shares = max_affordable_shares
                else:
                    break  # Can't afford any shares at this price

        transaction = Transaction(
            id=str(uuid.uuid4()),
            buyer_id=order.shareholder_id if order.order_type == OrderType.BUY else opposing_order.shareholder_id,
            seller_id=opposing_order.shareholder_id if order.order_type == OrderType.BUY else order.shareholder_id,
            company_id=order.company_id,
            shares=trade_shares,
            price_per_share=trade_price
        )
        
        db.add(transaction)
        transactions.append(transaction)
        
        executed_shares += trade_shares
        opposing_order.shares -= trade_shares
        
        if opposing_order.shares == 0:
            db.delete(opposing_order)
        else:
            db.add(opposing_order)

        crud.update_shareholder_portfolio(db, transaction.buyer_id, order.company_id, trade_shares)
        crud.update_shareholder_portfolio(db, transaction.seller_id, order.company_id, -trade_shares)
        crud.update_shareholder_cash(db, transaction.buyer_id, -trade_shares * trade_price)
        crud.update_shareholder_cash(db, transaction.seller_id, trade_shares * trade_price)

    # Remove the market order after execution
    db.delete(order)
    
    db.commit()
    update_stock_price(db, order.company_id)

    if executed_shares == 0:
        raise ValueError("Could not execute market order. No matching orders or insufficient funds.")

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