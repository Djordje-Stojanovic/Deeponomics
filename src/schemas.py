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

class Sector(str, Enum):
    ENERGY = "Energy"
    MATERIALS = "Materials"
    INDUSTRIALS = "Industrials"
    CONSUMER_DISCRETIONARY = "Consumer Discretionary"
    CONSUMER_STAPLES = "Consumer Staples"
    HEALTH_CARE = "Health Care"
    FINANCIALS = "Financials"
    INFORMATION_TECHNOLOGY = "Information Technology"
    COMMUNICATION_SERVICES = "Communication Services"
    UTILITIES = "Utilities"
    REAL_ESTATE = "Real Estate"

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

class ShareholderType(str, Enum):
    INDIVIDUAL = "Individual"
    MUTUAL_FUND = "Mutual Fund"
    PENSION_FUND = "Pension Fund"
    ETF = "ETF"
    HEDGE_FUND = "Hedge Fund"
    INSURANCE_COMPANY = "Insurance Company"
    BANK = "Bank"
    GOVERNMENT_FUND = "Government Fund"

class IndividualInvestorType(str, Enum):
    PASSIVE = "Passive"
    VALUE = "Value"
    GROWTH = "Growth"
    INCOME = "Income"
    MOMENTUM = "Momentum"
    SWING = "Swing"
    TECHNICAL = "Technical"
    FUNDAMENTAL = "Fundamental"
    CONTRARIAN = "Contrarian"
    SECTOR_SPECIFIC = "Sector Specific"
    POSITION = "Position"
    NEWS_BASED = "News-based"
    PENNY_STOCK = "Penny Stock"

class Shareholder(BaseModel):
    id: str
    name: str
    cash: float
    type: ShareholderType

    model_config = ConfigDict(from_attributes=True)

class IndividualInvestor(Shareholder):
    subtype: IndividualInvestorType

    model_config = ConfigDict(from_attributes=True)

class Company(BaseModel):
    id: str
    name: str
    stock_price: float
    outstanding_shares: int
    sector: Sector  # Add the sector field here

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