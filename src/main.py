from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import uuid

app = FastAPI()

class Shareholder(BaseModel):
    """Represents a shareholder in the simulation."""
    id: str
    name: str
    cash: float

class Portfolio(BaseModel):
    """Represents a shareholder's portfolio."""
    shareholder_id: str
    holdings: Dict[str, int]  # company_id: number of shares

class Company(BaseModel):
    """Represents a company in the simulation."""
    id: str
    name: str
    stock_price: float
    outstanding_shares: int

class Order(BaseModel):
    """Represents a buy or sell order in the simulation."""
    id: str
    shareholder_id: str
    company_id: str
    order_type: str  # 'buy' or 'sell'
    shares: int
    price: float

class Transaction(BaseModel):
    """Represents a completed transaction in the simulation."""
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
orders: List[Order] = []
transactions: List[Transaction] = []

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
    
    # Assign initial shares to the founder
    portfolio = portfolios[founder_id]
    portfolio.holdings[company_id] = initial_shares
    
    return company

@app.post('/orders')
async def create_order(shareholder_id: str, company_id: str, order_type: str, shares: int, price: float):
    """Create a new buy or sell order."""
    if shareholder_id not in shareholders:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    if company_id not in companies:
        raise HTTPException(status_code=404, detail="Company not found")
    
    shareholder = shareholders[shareholder_id]
    portfolio = portfolios[shareholder_id]
    company = companies[company_id]
    
    if order_type == 'buy':
        if shareholder.cash < shares * price:
            raise HTTPException(status_code=400, detail="Insufficient funds")
    elif order_type == 'sell':
        if portfolio.holdings.get(company_id, 0) < shares:
            raise HTTPException(status_code=400, detail="Insufficient shares")
    else:
        raise HTTPException(status_code=400, detail="Invalid order type")
    
    order_id = str(uuid.uuid4())
    order = Order(id=order_id, shareholder_id=shareholder_id, company_id=company_id, 
                  order_type=order_type, shares=shares, price=price)
    orders.append(order)
    
    # Try to match the order
    match_order(order)
    
    return order

def match_order(new_order: Order):
    """Attempt to match a new order with existing orders."""
    for existing_order in orders:
        if (existing_order.company_id == new_order.company_id and
            existing_order.order_type != new_order.order_type and
            existing_order.price == new_order.price):
            
            # Match found, create transaction
            if new_order.order_type == 'buy':
                buyer_id, seller_id = new_order.shareholder_id, existing_order.shareholder_id
            else:
                buyer_id, seller_id = existing_order.shareholder_id, new_order.shareholder_id
            
            transaction = Transaction(
                id=str(uuid.uuid4()),
                buyer_id=buyer_id,
                seller_id=seller_id,
                company_id=new_order.company_id,
                shares=min(new_order.shares, existing_order.shares),
                price_per_share=new_order.price
            )
            
            execute_transaction(transaction)
            
            # Update or remove orders
            new_order.shares -= transaction.shares
            existing_order.shares -= transaction.shares
            if existing_order.shares == 0:
                orders.remove(existing_order)
            if new_order.shares == 0:
                orders.remove(new_order)
            
            return transaction
    
    return None

def execute_transaction(transaction: Transaction):
    """Execute a transaction, updating shareholder portfolios and cash."""
    buyer = shareholders[transaction.buyer_id]
    seller = shareholders[transaction.seller_id]
    buyer_portfolio = portfolios[transaction.buyer_id]
    seller_portfolio = portfolios[transaction.seller_id]
    company = companies[transaction.company_id]
    
    total_price = transaction.shares * transaction.price_per_share
    
    # Update cash
    buyer.cash -= total_price
    seller.cash += total_price
    
    # Update portfolios
    buyer_portfolio.holdings[transaction.company_id] = buyer_portfolio.holdings.get(transaction.company_id, 0) + transaction.shares
    seller_portfolio.holdings[transaction.company_id] -= transaction.shares
    
    # Update company stock price
    company.stock_price = transaction.price_per_share
    
    transactions.append(transaction)

@app.get('/shareholders')
async def get_shareholders():
    """Retrieve all shareholders in the simulation."""
    return list(shareholders.values())

@app.get('/shareholders/{shareholder_id}')
async def get_shareholder(shareholder_id: str):
    """Retrieve a specific shareholder by ID."""
    if shareholder_id not in shareholders:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    return shareholders[shareholder_id]

@app.get('/companies')
async def get_companies():
    """Retrieve all companies in the simulation."""
    return list(companies.values())

@app.get('/companies/{company_id}')
async def get_company(company_id: str):
    """Retrieve a specific company by ID."""
    if company_id not in companies:
        raise HTTPException(status_code=404, detail="Company not found")
    return companies[company_id]

@app.get('/portfolios')
async def get_portfolios():
    """Retrieve all portfolios in the simulation."""
    return list(portfolios.values())

@app.get('/portfolios/{shareholder_id}')
async def get_portfolio(shareholder_id: str):
    """Retrieve a specific portfolio by shareholder ID."""
    if shareholder_id not in portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolios[shareholder_id]

@app.get('/orders')
async def get_orders():
    """Retrieve all orders in the simulation."""
    return orders

@app.get('/orders/{order_id}')
async def get_order(order_id: str):
    """Retrieve a specific order by ID."""
    order = next((order for order in orders if order.id == order_id), None)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get('/transactions')
async def get_transactions():
    """Retrieve all transactions in the simulation."""
    return transactions

@app.get('/transactions/{transaction_id}')
async def get_transaction(transaction_id: str):
    """Retrieve a specific transaction by ID."""
    transaction = next((t for t in transactions if t.id == transaction_id), None)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)