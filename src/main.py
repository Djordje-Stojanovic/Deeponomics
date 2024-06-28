# main.py
import asyncio
from contextlib import asynccontextmanager
from crud import run_company_ticks
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base
from schemas import Shareholder, Company, Portfolio, OrderCreate, OrderResponse, TransactionResponse, OrderType, OrderSubType, MarketOrderResponse
from typing import List, Union
import crud
import logging
from services.order_matching import match_orders, execute_market_order

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_tables():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")

create_tables()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    company_ticks_task = asyncio.create_task(run_company_ticks())
    yield
    # Shutdown
    company_ticks_task.cancel()
    try:
        await company_ticks_task
    except asyncio.CancelledError:
        logger.info("Company ticks task cancelled")

app = FastAPI(lifespan=lifespan)

async def background_order_matching():
    logger.info("Background order matching task started")
    while True:
        logger.info("Running background order matching cycle")
        db = SessionLocal()
        try:
            companies = crud.get_all_companies(db)
            logger.info(f"Found {len(companies)} companies to process")
            for company in companies:
                logger.info(f"Processing orders for company: {company.name}")
                match_orders(company.id, db)
        except Exception as e:
            logger.error(f"Error in background order matching: {str(e)}")
        finally:
            db.close()
        await asyncio.sleep(1)  # Run every second

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_order_matching())

@app.post('/shareholders', response_model=Shareholder)
async def create_shareholder(name: str, initial_cash: float, db: Session = Depends(get_db)):
    return crud.create_shareholder(db, name, initial_cash)

@app.get('/shareholders/{shareholder_id}', response_model=Shareholder)
async def get_shareholder(shareholder_id: str, db: Session = Depends(get_db)):
    shareholder = crud.get_shareholder(db, shareholder_id)
    if not shareholder:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    return shareholder

@app.get('/shareholders', response_model=List[Shareholder])
async def get_all_shareholders(db: Session = Depends(get_db)):
    return crud.get_all_shareholders(db)

@app.post('/companies', response_model=Company)
async def create_company(name: str, initial_stock_price: float, initial_shares: int, founder_id: str, db: Session = Depends(get_db)):
    company = crud.create_company(db, name, initial_stock_price, initial_shares, founder_id)
    if not company:
        raise HTTPException(status_code=400, detail="Failed to create company. Please check the founder ID and try again.")
    return company

@app.get('/companies/{company_id}', response_model=Company)
async def get_company(company_id: str, db: Session = Depends(get_db)):
    company = crud.get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@app.get('/companies', response_model=List[Company])
async def get_all_companies(db: Session = Depends(get_db)):
    return crud.get_all_companies(db)

@app.post('/orders', response_model=Union[OrderResponse, MarketOrderResponse])
async def create_order(order: OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_order = crud.create_order(db, order)
    if not db_order:
        raise HTTPException(status_code=400, detail="Order creation failed. Please check your inputs and try again.")
    
    if order.order_subtype == OrderSubType.MARKET:
        try:
            transactions = execute_market_order(db_order, db)
            return MarketOrderResponse(
                message=f"Market order executed: {len(transactions)} transactions",
                transactions=[TransactionResponse.from_orm(t) for t in transactions]
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        background_tasks.add_task(match_orders, order.company_id, db)
        return OrderResponse.from_orm(db_order)

@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str, db: Session = Depends(get_db)):
    success = crud.cancel_order(db, order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": f"Order {order_id} cancelled successfully"}

@app.get('/shareholders/{shareholder_id}/orders', response_model=List[OrderResponse])
async def get_shareholder_orders(shareholder_id: str, db: Session = Depends(get_db)):
    shareholder = crud.get_shareholder(db, shareholder_id)
    if not shareholder:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    orders = crud.get_shareholder_orders(db, shareholder_id)
    return [OrderResponse.from_orm(order) for order in orders]

@app.get('/shareholders/{shareholder_id}/portfolio', response_model=List[Portfolio])
async def get_portfolio(shareholder_id: str, db: Session = Depends(get_db)):
    portfolios = crud.get_shareholder_portfolio(db, shareholder_id)
    if not portfolios:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return [Portfolio(shareholder_id=p.shareholder_id, company_id=p.company_id, shares=p.shares) for p in portfolios]

@app.get('/order_book/{company_id}')
async def get_order_book(company_id: str, db: Session = Depends(get_db)):
    company = crud.get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return crud.get_order_book(db, company_id)

@app.get('/transactions', response_model=List[TransactionResponse])
async def get_transactions(company_id: str = None, shareholder_id: str = None, db: Session = Depends(get_db)):
    transactions = crud.get_transaction_history(db, company_id, shareholder_id)
    return [TransactionResponse.from_orm(t) for t in transactions]

@app.get('/companies/{company_id}/performance')
async def get_company_performance(company_id: str, db: Session = Depends(get_db)):
    company = crud.get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return {
        "id": company.id,
        "name": company.name,
        "stock_price": company.stock_price,
        "revenue": company.revenue,
        "costs": company.costs,
        "profit": company.profit,
        "total_profit": company.total_profit,
        "days_active": company.days_active,
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)