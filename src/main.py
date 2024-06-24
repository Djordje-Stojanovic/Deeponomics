from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import uuid
import logging
from enum import Enum  # Add this line

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model definitions
class Shareholder(BaseModel):
    id: str
    name: str
    cash: float

class Portfolio(BaseModel):
    shareholder_id: str
    holdings: Dict[str, int]  # company_id: number of shares

class Company(BaseModel):
    id: str
    name: str
    stock_price: float
    outstanding_shares: int

class OrderType(str, Enum):
    BUY = 'buy'
    SELL = 'sell'

class OrderSubType(str, Enum):
    LIMIT = 'limit'
    MARKET = 'market'

class Order(BaseModel):
    id: str
    shareholder_id: str
    company_id: str
    order_type: OrderType
    order_subtype: OrderSubType
    shares: int
    price: float | None = None  # Make price optional

class Transaction(BaseModel):
    id: str
    buyer_id: str
    seller_id: str
    company_id: str
    shares: int
    price_per_share: float

# In-memory storage
shareholders: Dict[str, Shareholder] = {}
portfolios: Dict[str, Portfolio] = {}
companies: Dict[str, Company] = {}
order_book: Dict[str, Dict[str, List[Order]]] = {}  # company_id -> {'buy': [...], 'sell': [...]}
transactions: List[Transaction] = []

# API endpoints
@app.post('/shareholders')
async def create_shareholder(name: str, initial_cash: float):
    """Create a new shareholder with initial cash."""
    shareholder_id = str(uuid.uuid4())
    shareholder = Shareholder(id=shareholder_id, name=name, cash=initial_cash)
    shareholders[shareholder_id] = shareholder
    portfolios[shareholder_id] = Portfolio(shareholder_id=shareholder_id, holdings={})
    return shareholder

@app.post('/companies')
async def create_company(name: str, initial_stock_price: float, initial_shares: int, founder_id: str):
    """Create a new company with initial shares owned by the founder."""
    if founder_id not in shareholders:
        raise HTTPException(status_code=404, detail="Founder not found")
    
    company_id = str(uuid.uuid4())
    company = Company(id=company_id, name=name, stock_price=initial_stock_price, outstanding_shares=initial_shares)
    companies[company_id] = company
    
    portfolios[founder_id].holdings[company_id] = initial_shares
    return company

@app.post('/orders')
async def create_order(shareholder_id: str, company_id: str, order_type: OrderType, order_subtype: OrderSubType, shares: int, price: float = None):
    """Create a new buy or sell order (limit or market) and attempt to match it."""
    if shareholder_id not in shareholders or company_id not in companies:
        raise HTTPException(status_code=404, detail="Shareholder or company not found")
    
    shareholder = shareholders[shareholder_id]
    portfolio = portfolios[shareholder_id]
    company = companies[company_id]
    
    # Check for sufficient shares for sell orders
    if order_type == OrderType.SELL and portfolio.holdings.get(company_id, 0) < shares:
        raise HTTPException(status_code=400, detail="Insufficient shares")
    
    # Check for price for limit orders
    if order_subtype == OrderSubType.LIMIT and price is None:
        raise HTTPException(status_code=400, detail="Price is required for limit orders")
    
    # Check total shares in existing orders
    existing_order_shares = sum(order.shares for order in order_book.get(company_id, {}).get(order_type.value, [])
                                if order.shareholder_id == shareholder_id)
    
    # Check for exceeding company's outstanding shares
    if order_type == OrderType.BUY and existing_order_shares + shares > company.outstanding_shares:
        raise HTTPException(status_code=400, detail="Total buy orders exceed company's outstanding shares")
    
    # Check for sufficient funds
    if order_type == OrderType.BUY:
        order_price = price if order_subtype == OrderSubType.LIMIT else company.stock_price
        total_cost = sum(order.shares * (order.price or company.stock_price) for order in order_book.get(company_id, {}).get('buy', [])
                         if order.shareholder_id == shareholder_id)
        if shareholder.cash < total_cost + (shares * order_price):
            raise HTTPException(status_code=400, detail="Insufficient funds for order")
    
    # Check for exceeding owned shares for sell orders
    if order_type == OrderType.SELL and existing_order_shares + shares > portfolio.holdings.get(company_id, 0):
        raise HTTPException(status_code=400, detail="Total sell orders exceed owned shares")

    # Create and add the order
    order = Order(id=str(uuid.uuid4()), shareholder_id=shareholder_id, company_id=company_id, 
                  order_type=order_type, order_subtype=order_subtype, shares=shares, price=price)
    
    if company_id not in order_book:
        order_book[company_id] = {'buy': [], 'sell': []}
    order_book[company_id][order_type].append(order)
    
    # For market orders, execute immediately
    if order_subtype == OrderSubType.MARKET:
        return execute_market_order(shareholder_id, company_id, order_type, shares)
    
    # For limit orders, attempt to match
    match_orders(company_id)
    return order

def match_orders(company_id: str):
    """Match limit buy and sell orders for a specific company."""
    buy_orders = sorted([o for o in order_book[company_id]['buy'] if o.order_subtype == OrderSubType.LIMIT], 
                        key=lambda x: x.price, reverse=True)
    sell_orders = sorted([o for o in order_book[company_id]['sell'] if o.order_subtype == OrderSubType.LIMIT], 
                         key=lambda x: x.price)
    
    company = companies[company_id]  # Add this line
    
    while buy_orders and sell_orders and buy_orders[0].price >= sell_orders[0].price:
        buy_order, sell_order = buy_orders[0], sell_orders[0]
        transaction_shares = min(buy_order.shares, sell_order.shares)
        
        # Check if buyer would own all shares
        buyer_current_shares = portfolios[buy_order.shareholder_id].holdings.get(company_id, 0)
        if buyer_current_shares + transaction_shares >= company.outstanding_shares:
            order_book[company_id]['buy'].remove(buy_order)
            buy_orders.pop(0)
            continue

        transaction = Transaction(
            id=str(uuid.uuid4()),
            buyer_id=buy_order.shareholder_id,
            seller_id=sell_order.shareholder_id,
            company_id=company_id,
            shares=transaction_shares,
            price_per_share=sell_order.price  # Execute at the sell order's price
        )
        
        execute_transaction(transaction)
        
        buy_order.shares -= transaction_shares
        sell_order.shares -= transaction_shares
        
        if buy_order.shares == 0:
            order_book[company_id]['buy'].remove(buy_order)
            buy_orders.pop(0)
        else:
            # Partial fill, update the order in the order book
            for i, order in enumerate(order_book[company_id]['buy']):
                if order.id == buy_order.id:
                    order_book[company_id]['buy'][i] = buy_order
                    break
        
        if sell_order.shares == 0:
            order_book[company_id]['sell'].remove(sell_order)
            sell_orders.pop(0)
        else:
            # Partial fill, update the order in the order book
            for i, order in enumerate(order_book[company_id]['sell']):
                if order.id == sell_order.id:
                    order_book[company_id]['sell'][i] = sell_order
                    break

def execute_market_order(shareholder_id: str, company_id: str, order_type: OrderType, shares: int):
    """Execute a market order immediately at the best available price."""
    if company_id not in order_book or not order_book[company_id]['buy'] + order_book[company_id]['sell']:
        raise HTTPException(status_code=400, detail="No orders available for this company")
    
    matching_orders = sorted(order_book[company_id]['sell' if order_type == OrderType.BUY else 'buy'], 
                             key=lambda x: x.price or 0, reverse=(order_type == OrderType.SELL))
    
    executed_shares = 0
    transactions = []
    
    for matching_order in matching_orders:
        if executed_shares >= shares:
            break
        
        transaction_shares = min(matching_order.shares, shares - executed_shares)
        transaction_price = matching_order.price or companies[company_id].stock_price

        transaction = Transaction(
            id=str(uuid.uuid4()),
            buyer_id=shareholder_id if order_type == OrderType.BUY else matching_order.shareholder_id,
            seller_id=matching_order.shareholder_id if order_type == OrderType.BUY else shareholder_id,
            company_id=company_id,
            shares=transaction_shares,
            price_per_share=transaction_price
        )
        
        execute_transaction(transaction)
        transactions.append(transaction)
        executed_shares += transaction_shares
        matching_order.shares -= transaction_shares
        
        if matching_order.shares == 0:
            order_book[company_id]['sell' if order_type == OrderType.BUY else 'buy'].remove(matching_order)
        else:
            # Update the partially filled order in the order book
            for i, order in enumerate(order_book[company_id]['sell' if order_type == OrderType.BUY else 'buy']):
                if order.id == matching_order.id:
                    order_book[company_id]['sell' if order_type == OrderType.BUY else 'buy'][i] = matching_order
                    break

    if executed_shares < shares:
        # Remove the unfilled market order
        order_book[company_id][order_type].pop()
        
    return {
        "message": f"Market order executed: {executed_shares}/{shares} shares",
        "transactions": transactions
    }


def clean_up_orders(company_id: str):
    company = companies[company_id]
    for order_type in ['buy', 'sell']:
        order_book[company_id][order_type] = [
            order for order in order_book[company_id][order_type]
            if (order_type == 'buy' and 
                shareholders[order.shareholder_id].cash >= order.shares * (order.price or company.stock_price)) or
               (order_type == 'sell' and 
                portfolios[order.shareholder_id].holdings.get(company_id, 0) >= order.shares)
        ]

def update_company_shares(company_id: str):
    company = companies[company_id]
    total_shares = sum(portfolio.holdings.get(company_id, 0) for portfolio in portfolios.values())
    company.outstanding_shares = total_shares

def execute_transaction(transaction: Transaction):
    """Execute a transaction, updating shareholder portfolios and cash."""
    buyer, seller = shareholders[transaction.buyer_id], shareholders[transaction.seller_id]
    buyer_portfolio, seller_portfolio = portfolios[transaction.buyer_id], portfolios[transaction.seller_id]
    company = companies[transaction.company_id]
    
    total_price = transaction.shares * transaction.price_per_share
    
    buyer.cash -= total_price
    seller.cash += total_price
    
    buyer_portfolio.holdings[transaction.company_id] = buyer_portfolio.holdings.get(transaction.company_id, 0) + transaction.shares
    seller_portfolio.holdings[transaction.company_id] -= transaction.shares
    
    company.stock_price = transaction.price_per_share
    
    # Clean up empty holdings
    if seller_portfolio.holdings[transaction.company_id] == 0:
        del seller_portfolio.holdings[transaction.company_id]

    update_company_shares(transaction.company_id)
    clean_up_orders(transaction.company_id)

    transactions.append(transaction)
    
    logger.info(f"Transaction: {transaction.shares} shares of {transaction.company_id} "
                f"from {transaction.seller_id} to {transaction.buyer_id} at ${transaction.price_per_share:.2f}/share")

@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str):
    """Cancel an existing order."""
    for company_id, orders in order_book.items():
        for order_type in ['buy', 'sell']:
            for order in orders[order_type]:
                if order.id == order_id:
                    orders[order_type].remove(order)
                    return {"message": f"Order {order_id} cancelled successfully"}
    raise HTTPException(status_code=404, detail="Order not found")

@app.get('/shareholders/{shareholder_id}/orders')
async def get_shareholder_orders(shareholder_id: str):
    """Retrieve all open orders for a specific shareholder."""
    if shareholder_id not in shareholders:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    
    shareholder_orders = []
    for company_id, orders in order_book.items():
        for order_type in ['buy', 'sell']:
            for order in orders[order_type]:
                if order.shareholder_id == shareholder_id:
                    shareholder_orders.append(order)
    
    return shareholder_orders

# Simplified GET endpoints
@app.get('/shareholders/{shareholder_id}')
async def get_shareholder(shareholder_id: str):
    """Retrieve a specific shareholder by ID."""
    if shareholder_id not in shareholders:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    return shareholders[shareholder_id]

@app.get('/shareholders')
async def get_all_shareholders():
    """Retrieve all shareholders and their IDs."""
    return [{"id": s.id, "name": s.name} for s in shareholders.values()]

@app.get('/companies/{company_id}')
async def get_company(company_id: str):
    """Retrieve a specific company by ID."""
    if company_id not in companies:
        raise HTTPException(status_code=404, detail="Company not found")
    return companies[company_id]

@app.get('/companies')
async def get_all_companies():
    """Retrieve all companies and their IDs."""
    return [{"id": c.id, "name": c.name} for c in companies.values()]

@app.get('/portfolios/{shareholder_id}')
async def get_portfolio(shareholder_id: str):
    """Retrieve a specific portfolio by shareholder ID."""
    if shareholder_id not in portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolios[shareholder_id]

@app.get('/order_book/{company_id}')
async def get_order_book(company_id: str):
    """Retrieve the order book for a specific company."""
    if company_id not in companies:
        raise HTTPException(status_code=404, detail="Company not found")
    return order_book.get(company_id, {'buy': [], 'sell': []})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)