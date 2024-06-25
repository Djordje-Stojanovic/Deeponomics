from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from sqlalchemy import func, DateTime
from pydantic import BaseModel
from typing import List, Optional
import uuid
import logging
from enum import Enum
from sqlalchemy.orm import relationship
from database import Base, engine, get_db, redis_client
from sqlalchemy import Column, String, Float, Integer, ForeignKey, Enum as SQLAlchemyEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Database models
class DBShareholder(Base):
    __tablename__ = "shareholders"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    cash = Column(Float)

class DBStock(Base):
    __tablename__ = "stocks"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"))
    current_price = Column(Float)
    last_updated = Column(DateTime, default=func.now())

    company = relationship("DBCompany", back_populates="stock")

class DBCompany(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    stock_price = Column(Float)
    outstanding_shares = Column(Integer)

    stock = relationship("DBStock", back_populates="company", uselist=False)
    portfolios = relationship("DBPortfolio", back_populates="company")

class DBPortfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, index=True)
    shareholder_id = Column(String, ForeignKey("shareholders.id"))
    company_id = Column(String, ForeignKey("companies.id"))
    shares = Column(Integer)

    shareholder = relationship("DBShareholder", back_populates="portfolios")
    company = relationship("DBCompany", back_populates="portfolios")

DBShareholder.portfolios = relationship("DBPortfolio", back_populates="shareholder")

def create_tables():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    logger.info(f"Tables in the database: {table_names}")
    
    if not table_names:
        logger.warning("No tables were created in the database.")
    else:
        logger.info("Database tables created successfully.")

create_tables()

app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Pydantic models (for API)
class Shareholder(BaseModel):
    id: str
    name: str
    cash: float

class Company(BaseModel):
    id: str
    name: str
    stock_price: float
    outstanding_shares: int

class Portfolio(BaseModel):
    shareholder_id: str
    company_id: str
    shares: int

class OrderType(str, Enum):
    BUY = 'buy'
    SELL = 'sell'

class OrderSubType(str, Enum):
    LIMIT = 'limit'
    MARKET = 'market'

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    shareholder_id = Column(String, ForeignKey("shareholders.id"))
    company_id = Column(String, ForeignKey("companies.id"))
    order_type = Column(SQLAlchemyEnum(OrderType))
    order_subtype = Column(SQLAlchemyEnum(OrderSubType))
    shares = Column(Integer)
    price = Column(Float, nullable=True)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    buyer_id = Column(String, ForeignKey("shareholders.id"))
    seller_id = Column(String, ForeignKey("shareholders.id"))
    company_id = Column(String, ForeignKey("companies.id"))
    shares = Column(Integer)
    price_per_share = Column(Float)

class OrderCreate(BaseModel):
    shareholder_id: str
    company_id: str
    order_type: OrderType
    order_subtype: OrderSubType
    shares: int
    price: Optional[float] = None

class OrderResponse(BaseModel):
    id: str
    shareholder_id: str
    company_id: str
    order_type: OrderType
    order_subtype: OrderSubType
    shares: int
    price: Optional[float]

    class Config:
        orm_mode = True

class TransactionResponse(BaseModel):
    id: str
    buyer_id: str
    seller_id: str
    company_id: str
    shares: int
    price_per_share: float

    class Config:
        orm_mode = True

# API endpoints
@app.post('/shareholders', response_model=Shareholder)
async def create_shareholder(name: str, initial_cash: float, db: Session = Depends(get_db)):
    shareholder_id = str(uuid.uuid4())
    db_shareholder = DBShareholder(id=shareholder_id, name=name, cash=initial_cash)
    db.add(db_shareholder)
    db.commit()
    db.refresh(db_shareholder)
    return db_shareholder

@app.post('/companies', response_model=Company)
async def create_company(name: str, initial_stock_price: float, initial_shares: int, founder_id: str, db: Session = Depends(get_db)):
    founder = db.query(DBShareholder).filter(DBShareholder.id == founder_id).first()
    if not founder:
        raise HTTPException(status_code=404, detail="Founder not found")
    
    company_id = str(uuid.uuid4())
    db_company = DBCompany(id=company_id, name=name, stock_price=initial_stock_price, outstanding_shares=initial_shares)
    db.add(db_company)
    
    db_portfolio = DBPortfolio(shareholder_id=founder_id, company_id=company_id, shares=initial_shares)
    db.add(db_portfolio)
    
    db.commit()
    db.refresh(db_company)
    return db_company

@app.post('/orders', response_model=OrderResponse)
async def create_order(order: OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    shareholder = db.query(DBShareholder).filter(DBShareholder.id == order.shareholder_id).first()
    company = db.query(DBCompany).filter(DBCompany.id == order.company_id).first()
    if not shareholder or not company:
        raise HTTPException(status_code=404, detail="Shareholder or company not found")
    
    portfolio = db.query(DBPortfolio).filter(DBPortfolio.shareholder_id == order.shareholder_id, DBPortfolio.company_id == order.company_id).first()
    
    if order.order_type == OrderType.SELL and (not portfolio or portfolio.shares < order.shares):
        raise HTTPException(status_code=400, detail="Insufficient shares")
    
    if order.order_subtype == OrderSubType.LIMIT and order.price is None:
        raise HTTPException(status_code=400, detail="Price is required for limit orders")
    
    existing_order_shares = db.query(func.sum(Order.shares)).filter(
        Order.shareholder_id == order.shareholder_id,
        Order.company_id == order.company_id,
        Order.order_type == order.order_type
    ).scalar() or 0
    
    if order.order_type == OrderType.BUY and existing_order_shares + order.shares > company.outstanding_shares:
        raise HTTPException(status_code=400, detail="Total buy orders exceed company's outstanding shares")
    
    if order.order_type == OrderType.BUY:
        order_price = order.price if order.order_subtype == OrderSubType.LIMIT else company.stock_price
        total_cost = (existing_order_shares * order_price) + (order.shares * order_price)
        if shareholder.cash < total_cost:
            raise HTTPException(status_code=400, detail="Insufficient funds for order")
    
    if order.order_type == OrderType.SELL and existing_order_shares + order.shares > (portfolio.shares if portfolio else 0):
        raise HTTPException(status_code=400, detail="Total sell orders exceed owned shares")

    db_order = Order(id=str(uuid.uuid4()), shareholder_id=order.shareholder_id, company_id=order.company_id, 
                     order_type=order.order_type, order_subtype=order.order_subtype, shares=order.shares, price=order.price)
    
    if order.order_subtype == OrderSubType.MARKET:
        try:
            return execute_market_order(db_order, db)
        except HTTPException as e:
            raise e
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    background_tasks.add_task(match_orders, order.company_id, db)
    
    return OrderResponse.from_orm(db_order)

@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
    return {"message": f"Order {order_id} cancelled successfully"}

@app.get('/shareholders/{shareholder_id}/orders', response_model=List[OrderResponse])
async def get_shareholder_orders(shareholder_id: str, db: Session = Depends(get_db)):
    shareholder = db.query(DBShareholder).filter(DBShareholder.id == shareholder_id).first()
    if not shareholder:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    
    orders = db.query(Order).filter(Order.shareholder_id == shareholder_id).all()
    return [OrderResponse.from_orm(order) for order in orders]

@app.get('/shareholders/{shareholder_id}', response_model=Shareholder)
async def get_shareholder(shareholder_id: str, db: Session = Depends(get_db)):
    shareholder = db.query(DBShareholder).filter(DBShareholder.id == shareholder_id).first()
    if not shareholder:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    return shareholder

@app.get('/shareholders', response_model=List[Shareholder])
async def get_all_shareholders(db: Session = Depends(get_db)):
    shareholders = db.query(DBShareholder).all()
    return shareholders

@app.get('/companies/{company_id}', response_model=Company)
async def get_company(company_id: str, db: Session = Depends(get_db)):
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@app.get('/companies', response_model=List[Company])
async def get_all_companies(db: Session = Depends(get_db)):
    companies = db.query(DBCompany).all()
    return companies

@app.post("/buy", response_model=OrderResponse)
async def buy_stock(company_id: str, shares: int, price: float, trader_id: str, db: Session = Depends(get_db)):
    order = OrderCreate(
        shareholder_id=trader_id,
        company_id=company_id,
        order_type=OrderType.BUY,
        order_subtype=OrderSubType.LIMIT,
        shares=shares,
        price=price
    )
    return await create_order(order, BackgroundTasks(), db)

@app.post("/sell", response_model=OrderResponse)
async def sell_stock(company_id: str, shares: int, price: float, trader_id: str, db: Session = Depends(get_db)):
    order = OrderCreate(
        shareholder_id=trader_id,
        company_id=company_id,
        order_type=OrderType.SELL,
        order_subtype=OrderSubType.LIMIT,
        shares=shares,
        price=price
    )
    return await create_order(order, BackgroundTasks(), db)

@app.get("/portfolio/{trader_id}", response_model=List[Portfolio])
async def get_portfolio(trader_id: str, db: Session = Depends(get_db)):
    portfolios = db.query(DBPortfolio).filter(DBPortfolio.shareholder_id == trader_id).all()
    if not portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return [Portfolio(shareholder_id=p.shareholder_id, company_id=p.company_id, shares=p.shares) for p in portfolios]

@app.get('/order_book/{company_id}')
async def get_order_book(company_id: str, db: Session = Depends(get_db)):
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    buy_orders = db.query(Order).filter(Order.company_id == company_id, Order.order_type == OrderType.BUY).all()
    sell_orders = db.query(Order).filter(Order.company_id == company_id, Order.order_type == OrderType.SELL).all()
    
    return {'buy': [OrderResponse.from_orm(order) for order in buy_orders], 
            'sell': [OrderResponse.from_orm(order) for order in sell_orders]}

def add_to_order_book(company_id: str, order: Order):
    key = f"order_book:{company_id}:{order.order_type.value}"
    redis_client.zadd(key, {order.id: order.price})

def get_order_book(company_id: str, order_type: OrderType):
    key = f"order_book:{company_id}:{order_type.value}"
    return redis_client.zrange(key, 0, -1, withscores=True)
def match_orders(company_id: str, db: Session):
    buy_orders = get_order_book(company_id, OrderType.BUY)
    sell_orders = get_order_book(company_id, OrderType.SELL)
    
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    
    for buy_order_id, buy_price in buy_orders:
        for sell_order_id, sell_price in sell_orders:
            if buy_price >= sell_price:
                buy_order = db.query(Order).filter(Order.id == buy_order_id).first()
                sell_order = db.query(Order).filter(Order.id == sell_order_id).first()
                
                if buy_order and sell_order:
                    transaction_shares = min(buy_order.shares, sell_order.shares)
                    
                    transaction = Transaction(
                        id=str(uuid.uuid4()),
                        buyer_id=buy_order.shareholder_id,
                        seller_id=sell_order.shareholder_id,
                        company_id=company_id,
                        shares=transaction_shares,
                        price_per_share=sell_price
                    )
                    
                    execute_transaction(transaction, db)
                    
                    buy_order.shares -= transaction_shares
                    sell_order.shares -= transaction_shares
                    
                    if buy_order.shares == 0:
                        db.delete(buy_order)
                        redis_client.zrem(f"order_book:{company_id}:{OrderType.BUY.value}", buy_order_id)
                    else:
                        db.add(buy_order)
                    
                    if sell_order.shares == 0:
                        db.delete(sell_order)
                        redis_client.zrem(f"order_book:{company_id}:{OrderType.SELL.value}", sell_order_id)
                    else:
                        db.add(sell_order)
                    
                    db.commit()
                    
                    if buy_order.shares > 0:
                        add_to_order_book(company_id, buy_order)
                    if sell_order.shares > 0:
                        add_to_order_book(company_id, sell_order)

def execute_market_order(order: Order, db: Session):
    company = db.query(DBCompany).filter(DBCompany.id == order.company_id).first()
    shareholder = db.query(DBShareholder).filter(DBShareholder.id == order.shareholder_id).first()

    matching_orders = db.query(Order).filter(
        Order.company_id == order.company_id,
        Order.order_type == (OrderType.SELL if order.order_type == OrderType.BUY else OrderType.BUY)
    ).order_by(Order.price.asc() if order.order_type == OrderType.BUY else Order.price.desc()).all()
    
    if not matching_orders:
        raise HTTPException(status_code=400, detail="No orders available for this company")
    
    executed_shares = 0
    transactions = []
    total_cost = 0
    
    for matching_order in matching_orders:
        if executed_shares >= order.shares:
            break
        
        transaction_shares = min(matching_order.shares, order.shares - executed_shares)
        transaction_price = matching_order.price or company.stock_price
        transaction_cost = transaction_shares * transaction_price

        if order.order_type == OrderType.BUY:
            if shareholder.cash < total_cost + transaction_cost:
                if executed_shares == 0:
                    raise HTTPException(status_code=400, detail="Insufficient funds for market order")
                break

        transaction = Transaction(
            id=str(uuid.uuid4()),
            buyer_id=order.shareholder_id if order.order_type == OrderType.BUY else matching_order.shareholder_id,
            seller_id=matching_order.shareholder_id if order.order_type == OrderType.BUY else order.shareholder_id,
            company_id=order.company_id,
            shares=transaction_shares,
            price_per_share=transaction_price
        )
        
        execute_transaction(transaction, db)
        transactions.append(transaction)
        executed_shares += transaction_shares
        total_cost += transaction_cost
        matching_order.shares -= transaction_shares
        
        if matching_order.shares == 0:
            db.delete(matching_order)
        else:
            db.add(matching_order)

    db.commit()

    if executed_shares == 0:
        raise HTTPException(status_code=400, detail="Could not execute market order")

    return {
        "message": f"Market order executed: {executed_shares}/{order.shares} shares",
        "transactions": [TransactionResponse.from_orm(t) for t in transactions]
    }

def clean_up_orders(company_id: str, db: Session):
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    for order_type in [OrderType.BUY, OrderType.SELL]:
        orders = db.query(Order).filter(
            Order.company_id == company_id,
            Order.order_type == order_type
        ).all()
        for order in orders:
            shareholder = db.query(DBShareholder).filter(DBShareholder.id == order.shareholder_id).first()
            portfolio = db.query(DBPortfolio).filter(
                DBPortfolio.shareholder_id == order.shareholder_id,
                DBPortfolio.company_id == company_id
            ).first()
            if (order_type == OrderType.BUY and 
                shareholder.cash < order.shares * (order.price or company.stock_price)) or \
               (order_type == OrderType.SELL and 
                (not portfolio or portfolio.shares < order.shares)):
                db.delete(order)
    db.commit()

def update_company_shares(company_id: str, db: Session):
    company = db.query(DBCompany).filter(DBCompany.id == company_id).first()
    total_shares = db.query(func.sum(DBPortfolio.shares)).filter(
        DBPortfolio.company_id == company_id
    ).scalar() or 0
    company.outstanding_shares = total_shares
    db.commit()

def execute_transaction(transaction: Transaction, db: Session):
    try:
        buyer = db.query(DBShareholder).filter(DBShareholder.id == transaction.buyer_id).first()
        seller = db.query(DBShareholder).filter(DBShareholder.id == transaction.seller_id).first()
        company = db.query(DBCompany).filter(DBCompany.id == transaction.company_id).first()
        
        buyer_portfolio = db.query(DBPortfolio).filter(
            DBPortfolio.shareholder_id == transaction.buyer_id,
            DBPortfolio.company_id == transaction.company_id
        ).first()
        
        seller_portfolio = db.query(DBPortfolio).filter(
            DBPortfolio.shareholder_id == transaction.seller_id,
            DBPortfolio.company_id == transaction.company_id
        ).first()
        
        total_price = transaction.shares * transaction.price_per_share
        
        buyer.cash -= total_price
        seller.cash += total_price
        
        if buyer_portfolio:
            buyer_portfolio.shares += transaction.shares
        else:
            buyer_portfolio = DBPortfolio(shareholder_id=transaction.buyer_id, company_id=transaction.company_id, shares=transaction.shares)
            db.add(buyer_portfolio)
        
        seller_portfolio.shares -= transaction.shares
        
        company.stock_price = transaction.price_per_share
        
        if seller_portfolio.shares == 0:
            db.delete(seller_portfolio)

        db.add(transaction)
        db.commit()
        
        logger.info(f"Transaction: {transaction.shares} shares of {transaction.company_id} "
                    f"from {transaction.seller_id} to {transaction.buyer_id} at ${transaction.price_per_share:.2f}/share")
        
        clean_up_orders(transaction.company_id, db)
        update_company_shares(transaction.company_id, db)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error executing transaction: {str(e)}")
        raise HTTPException(status_code=500, detail="Error executing transaction")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)