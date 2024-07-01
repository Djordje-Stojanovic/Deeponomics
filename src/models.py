# models.py
import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, Enum as SQLAlchemyEnum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy import func
from database import Base
from enum import Enum

class OrderType(str, Enum):
    BUY = 'buy'
    SELL = 'sell'

class OrderSubType(str, Enum):
    LIMIT = 'limit'
    MARKET = 'market'

class DBShareholder(Base):
    __tablename__ = "shareholders"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    cash = Column(Float)
    portfolios = relationship("DBPortfolio", back_populates="shareholder")

class DBCompany(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    stock_price = Column(Float)
    outstanding_shares = Column(Integer)
    
    # Assets
    cash = Column(Float, default=0)
    short_term_investments = Column(Float, default=0)
    business_assets = Column(Float, default=100)
    working_capital = Column(Float, default=0)
    marketable_securities = Column(Float, default=0)
    
    # Liabilities
    issued_bonds = Column(Float, default=0)
    issued_debt = Column(Float, default=0)
    
    # Other financial attributes
    annual_revenue = Column(Float, default=0)
    cost_of_revenue_percentage = Column(Float, default=0.7)
    rd_spend_percentage = Column(Float, default=0.1)
    
    last_update = Column(DateTime, default=func.now())

    # Relationships
    portfolios = relationship("DBPortfolio", back_populates="company")

    @property
    def total_assets(self):
        return self.cash + self.short_term_investments + self.business_assets + self.working_capital + self.marketable_securities

    @property
    def total_liabilities(self):
        return self.issued_bonds + self.issued_debt

    @property
    def total_equity(self):
        return self.total_assets - self.total_liabilities

class DBPortfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    shareholder_id = Column(String, ForeignKey("shareholders.id"))
    company_id = Column(String, ForeignKey("companies.id"))
    shares = Column(Integer)

    shareholder = relationship("DBShareholder", back_populates="portfolios")
    company = relationship("DBCompany", back_populates="portfolios")

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