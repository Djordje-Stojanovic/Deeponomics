from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
import uuid

app = FastAPI()

class Company(BaseModel):
    """Represents a company in the simulation."""
    id: str
    name: str
    stock_price: float
    available_shares: int

class Stock(BaseModel):
    """Represents a stock in the simulation."""
    company_id: str
    price: float

class Transaction(BaseModel):
    """Represents a stock transaction in the simulation."""
    id: str
    buyer_id: str
    seller_id: str
    company_id: str
    shares: int
    price_per_share: float

# In-memory storage (we'll replace this with a database later)
companies: Dict[str, Company] = {}
transactions: List[Transaction] = []

@app.get('/')
async def root():
    """Root endpoint to check if the API is running."""
    return {'message': 'Welcome to Deeponomics!'}

@app.post('/companies')
async def create_company(name: str, initial_stock_price: float, initial_shares: int):
    """
    Create a new company in the simulation.
    
    Args:
    name (str): The name of the company.
    initial_stock_price (float): The initial price of the company's stock.
    initial_shares (int): The initial number of available shares.

    Returns:
    Company: The created company object.
    """
    company_id = str(uuid.uuid4())
    company = Company(id=company_id, name=name, stock_price=initial_stock_price, available_shares=initial_shares)
    companies[company_id] = company
    return company

@app.get('/companies')
async def get_companies():
    """
    Retrieve all companies in the simulation.

    Returns:
    List[Company]: A list of all company objects.
    """
    return list(companies.values())

@app.post('/transactions')
async def create_transaction(buyer_id: str, seller_id: str, company_id: str, shares: int):
    """
    Create a new stock transaction in the simulation.

    Args:
    buyer_id (str): The ID of the buyer.
    seller_id (str): The ID of the seller.
    company_id (str): The ID of the company whose stock is being traded.
    shares (int): The number of shares being traded.

    Returns:
    Transaction: The created transaction object.
    Dict: An error message if the transaction couldn't be completed.
    """
    if company_id not in companies:
        return {"error": "Company not found"}
    
    company = companies[company_id]
    if company.available_shares < shares:
        return {"error": "Not enough shares available"}
    
    transaction_id = str(uuid.uuid4())
    transaction = Transaction(
        id=transaction_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        company_id=company_id,
        shares=shares,
        price_per_share=company.stock_price
    )
    
    # Update company shares
    company.available_shares -= shares
    
    transactions.append(transaction)
    return transaction

@app.get('/transactions')
async def get_transactions():
    """
    Retrieve all transactions in the simulation.

    Returns:
    List[Transaction]: A list of all transaction objects.
    """
    return transactions

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)