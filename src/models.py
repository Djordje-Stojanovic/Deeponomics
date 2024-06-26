import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from sqlalchemy import func, DateTime
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