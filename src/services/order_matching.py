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
    logger.info(f"Starting order matching for company {company_id}")
    
    # Market Buy Orders
    market_buy_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.BUY,
        Order.order_subtype == OrderSubType.MARKET
    ).all()
    logger.info(f"Found {len(market_buy_orders)} market buy orders")

    for market_buy_order in market_buy_orders:
        try:
            execute_market_order(market_buy_order, db)
        except ValueError as e:
            logger.warning(f"Failed to execute market buy order: {str(e)}")

    # Market Sell Orders
    market_sell_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL,
        Order.order_subtype == OrderSubType.MARKET
    ).all()
    logger.info(f"Found {len(market_sell_orders)} market sell orders")

    for market_sell_order in market_sell_orders:
        try:
            execute_market_order(market_sell_order, db)
        except ValueError as e:
            logger.warning(f"Failed to execute market sell order: {str(e)}")

    # Limit Orders
    limit_buy_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.BUY,
        Order.order_subtype == OrderSubType.LIMIT
    ).order_by(Order.price.desc()).all()
    logger.info(f"Found {len(limit_buy_orders)} limit buy orders")

    limit_sell_orders = db.query(Order).filter(
        Order.company_id == company_id,
        Order.order_type == OrderType.SELL,
        Order.order_subtype == OrderSubType.LIMIT
    ).order_by(Order.price.asc()).all()
    logger.info(f"Found {len(limit_sell_orders)} limit sell orders")

    matches = 0
    for buy_order in limit_buy_orders:
        for sell_order in limit_sell_orders:
            logger.info(f"Comparing buy order {buy_order.id} (price: {buy_order.price}) with sell order {sell_order.id} (price: {sell_order.price})")
            if buy_order.price >= sell_order.price:
                logger.info(f"Matching buy order {buy_order.id} with sell order {sell_order.id}")
                execute_trade(buy_order, sell_order, db)
                matches += 1
                if buy_order.shares == 0:
                    db.delete(buy_order)
                    break
            else:
                break  # No more matches possible
        if buy_order.shares > 0:
            db.add(buy_order)

    db.commit()
    crud.update_stock_price(db, company_id)
    logger.info(f"Matching completed for company {company_id}. Executed {matches} trades.")
    
def execute_trade(buy_order: Order, sell_order: Order, db: Session):
    company = crud.get_company(db, buy_order.company_id)
    trade_shares = min(buy_order.shares, sell_order.shares)

    # Check if this trade would exceed the company's outstanding shares
    total_shares = db.query(func.sum(DBPortfolio.shares)).filter(DBPortfolio.company_id == company.id).scalar() or 0
    if total_shares + trade_shares > company.outstanding_shares:
        logger.warning(f"Trade would exceed outstanding shares. Adjusting trade size.")
        trade_shares = company.outstanding_shares - total_shares
        if trade_shares <= 0:
            logger.warning(f"No shares available for trade. Cancelling trade.")
            return

    trade_price = sell_order.price

    logger.info(f"Executing trade: {trade_shares} shares at ${trade_price} per share")
    logger.info(f"Updating buyer (ID: {buy_order.shareholder_id}) portfolio and cash")
    logger.info(f"Updating seller (ID: {sell_order.shareholder_id}) portfolio and cash")

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
    buyer = crud.get_shareholder(db, order.shareholder_id) if order.order_type == OrderType.BUY else None

    opposing_orders = db.query(Order).filter(
        Order.company_id == order.company_id,
        Order.order_type != order.order_type,
        Order.order_subtype == OrderSubType.LIMIT  # Only match with limit orders
    ).order_by(Order.price.asc() if order.order_type == OrderType.BUY else Order.price.desc()).all()
    
    executed_shares = 0
    transactions = []
    
    for opposing_order in opposing_orders:
        if executed_shares >= order.shares:
            break
        
        trade_shares = min(opposing_order.shares, order.shares - executed_shares)
        trade_price = opposing_order.price

        # Check if this trade would exceed the company's outstanding shares
        if order.order_type == OrderType.BUY:
            total_shares = crud.get_total_shares_held(db, company.id)
            if total_shares + trade_shares > company.outstanding_shares:
                logger.warning(f"Trade would exceed outstanding shares. Adjusting trade size.")
                trade_shares = company.outstanding_shares - total_shares
                if trade_shares <= 0:
                    logger.warning(f"No shares available for trade. Skipping this order.")
                    continue

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

    # Update the market order
    order.shares -= executed_shares
    if order.shares > 0:
        db.add(order)  # Keep the order in the book if not fully executed
    else:
        db.delete(order)  # Remove the order if fully executed
    
    db.commit()
    # After processing the market order
    crud.update_stock_price(db, order.company_id)

    if executed_shares == 0:
        logger.info(f"Market order {order.id} couldn't be executed. Keeping in the order book.")
    else:
        logger.info(f"Market order partially executed: {executed_shares} shares in {len(transactions)} transactions")
    
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