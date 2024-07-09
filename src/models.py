# models.py
import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, Enum as SQLAlchemyEnum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy import func
from database import Base
from enum import Enum
from datetime import datetime
import random

class GlobalSettings(Base):
    __tablename__ = "global_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String)
    last_updated = Column(DateTime)    

class OrderType(str, Enum):
    BUY = 'buy'
    SELL = 'sell'

class OrderSubType(str, Enum):
    LIMIT = 'limit'
    MARKET = 'market'

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

class DBShareholder(Base):
    __tablename__ = "shareholders"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    cash = Column(Float)
    type = Column(SQLAlchemyEnum(ShareholderType))
    portfolios = relationship("DBPortfolio", back_populates="shareholder")
    founded_companies = relationship("DBCompany", back_populates="founder")

    __mapper_args__ = {
        'polymorphic_identity': 'shareholder',
        'polymorphic_on': type
    }

class DBIndividualInvestor(DBShareholder):
    __tablename__ = "individual_investors"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)
    subtype = Column(SQLAlchemyEnum(IndividualInvestorType))

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.INDIVIDUAL
    }

class DBMutualFund(DBShareholder):
    __tablename__ = "mutual_funds"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.MUTUAL_FUND
    }

class DBPensionFund(DBShareholder):
    __tablename__ = "pension_funds"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.PENSION_FUND
    }

class DBETF(DBShareholder):
    __tablename__ = "etfs"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.ETF
    }

class DBHedgeFund(DBShareholder):
    __tablename__ = "hedge_funds"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.HEDGE_FUND
    }

class DBInsuranceCompany(DBShareholder):
    __tablename__ = "insurance_companies"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.INSURANCE_COMPANY
    }

class DBBank(DBShareholder):
    __tablename__ = "banks"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.BANK
    }

class DBGovernmentFund(DBShareholder):
    __tablename__ = "government_funds"

    id = Column(String, ForeignKey('shareholders.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': ShareholderType.GOVERNMENT_FUND
    }

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

class CEO(Base):
    __tablename__ = "ceos"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    capex_allocation = Column(Float)
    dividend_allocation = Column(Float)
    cash_investment_allocation = Column(Float)
    company_id = Column(String, ForeignKey("companies.id"), unique=True)
    
    company = relationship("DBCompany", back_populates="ceo", foreign_keys=[company_id])

    @classmethod
    def generate_random_ceo(cls):
        return cls(
            id=str(uuid.uuid4()),
            name=f"{random.choice(['John', 'Jane', 'Mike', 'Sarah', 'David', 'Emily'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis'])}",
            capex_allocation=random.uniform(0, 1),
            dividend_allocation=random.uniform(0, 1),
            cash_investment_allocation=random.uniform(0, 1)
        )

class DBCompany(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    stock_price = Column(Float)
    outstanding_shares = Column(Integer)
    
    # Founder ID
    founder_id = Column(String, ForeignKey("shareholders.id"))

    # CEO relationship
    ceo = relationship("CEO", back_populates="company", uselist=False, foreign_keys=[CEO.company_id])

    # Sector
    sector = Column(SQLAlchemyEnum(Sector))

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

    # New fields for cash flow statement
    capex = Column(Float, default=0)
    gain_loss_investments = Column(Float, default=0)
    acquisitions = Column(Float, default=0)
    marketable_securities_investment = Column(Float, default=0)
    debt_issued = Column(Float, default=0)
    debt_repaid = Column(Float, default=0)
    stock_issued = Column(Float, default=0)
    stock_buyback = Column(Float, default=0)
    dividends_paid = Column(Float, default=0)
    special_dividends = Column(Float, default=0)
    change_in_nwc = Column(Float, default=0)
    interest_income = Column(Float, default=0)

    # New attributes for CEO decision-making
    capex_percentage = Column(Float, default=0.5)  # Default to 50%
    dividend_payout_percentage = Column(Float, default=0) # Default to 0%
    cash_allocation = Column(Float, default=0.5)  # Default to 50% cash, 50% investments
    dividend_account = Column(Float, default=0)
    last_dividend_payout_date = Column(DateTime, default=func.now())

    # Relationships
    portfolios = relationship("DBPortfolio", back_populates="company")
    founder = relationship("DBShareholder", back_populates="founded_companies")

    @property
    def total_assets(self):
        return self.cash + self.short_term_investments + self.business_assets + self.working_capital + self.marketable_securities

    @property
    def total_liabilities(self):
        return self.issued_bonds + self.issued_debt

    @property
    def total_equity(self):
        return self.total_assets - self.total_liabilities
    
    @property
    def cfo(self):
        net_income = self.annual_revenue * (1 - self.cost_of_revenue_percentage) * (1 - 0.21)  # Assuming 21% tax rate
        return net_income + self.gain_loss_investments + self.interest_income - self.change_in_nwc    
    
    @property
    def annual_capex(self):
        annualcapex = self.capex * 365
        return annualcapex

    @property
    def fcf(self):
        return self.cfo - self.annual_capex

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