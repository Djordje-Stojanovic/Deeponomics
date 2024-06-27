# schemas.py
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from enum import Enum

class OrderType(str, Enum):
    BUY = 'buy'
    SELL = 'sell'

class OrderSubType(str, Enum):
    LIMIT = 'limit'
    MARKET = 'market'

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

    model_config = ConfigDict(from_attributes=True)

# Update other models similarly
class Shareholder(BaseModel):
    id: str
    name: str
    cash: float

    model_config = ConfigDict(from_attributes=True)

class Company(BaseModel):
    id: str
    name: str
    stock_price: float
    outstanding_shares: int

    model_config = ConfigDict(from_attributes=True)

class Portfolio(BaseModel):
    shareholder_id: str
    company_id: str
    shares: int

    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    id: str
    buyer_id: str
    seller_id: str
    company_id: str
    shares: int
    price_per_share: float

    model_config = ConfigDict(from_attributes=True)

class MarketOrderResponse(BaseModel):
    message: str
    transactions: List[TransactionResponse]

    model_config = ConfigDict(from_attributes=True)