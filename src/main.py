from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import uuid
import logging

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

class Order(BaseModel):
    id: str
    shareholder_id: str
    company_id: str
    order_type: str  # 'buy' or 'sell'
    shares: int
    price: float

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
async def create_order(shareholder_id: str, company_id: str, order_type: str, shares: int, price: float):
    """Create a new buy or sell order and attempt to match it."""
    if shareholder_id not in shareholders or company_id not in companies:
        raise HTTPException(status_code=404, detail="Shareholder or company not found")
    
    shareholder = shareholders[shareholder_id]
    portfolio = portfolios[shareholder_id]
    
    if order_type == 'buy' and shareholder.cash < shares * price:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    elif order_type == 'sell' and portfolio.holdings.get(company_id, 0) < shares:
        raise HTTPException(status_code=400, detail="Insufficient shares")
    elif order_type not in ['buy', 'sell']:
        raise HTTPException(status_code=400, detail="Invalid order type")
    
    order = Order(id=str(uuid.uuid4()), shareholder_id=shareholder_id, company_id=company_id, 
                  order_type=order_type, shares=shares, price=price)
    
    if company_id not in order_book:
        order_book[company_id] = {'buy': [], 'sell': []}
    order_book[company_id][order_type].append(order)
    
    match_orders(company_id)
    return order

def match_orders(company_id: str):
    """Match buy and sell orders for a specific company."""
    buy_orders = sorted(order_book[company_id]['buy'], key=lambda x: x.price, reverse=True)
    sell_orders = sorted(order_book[company_id]['sell'], key=lambda x: x.price)
    
    while buy_orders and sell_orders and buy_orders[0].price >= sell_orders[0].price:
        buy_order, sell_order = buy_orders[0], sell_orders[0]
        transaction = Transaction(
            id=str(uuid.uuid4()),
            buyer_id=buy_order.shareholder_id,
            seller_id=sell_order.shareholder_id,
            company_id=company_id,
            shares=min(buy_order.shares, sell_order.shares),
            price_per_share=sell_order.price  # Execute at the sell order's price
        )
        
        execute_transaction(transaction)
        
        buy_order.shares -= transaction.shares
        sell_order.shares -= transaction.shares
        
        if buy_order.shares == 0:
            order_book[company_id]['buy'].remove(buy_order)
            buy_orders.pop(0)
        if sell_order.shares == 0:
            order_book[company_id]['sell'].remove(sell_order)
            sell_orders.pop(0)

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
    
    transactions.append(transaction)
    
    logger.info(f"Transaction: {transaction.shares} shares of {transaction.company_id} "
                f"from {transaction.seller_id} to {transaction.buyer_id} at ${transaction.price_per_share:.2f}/share")

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