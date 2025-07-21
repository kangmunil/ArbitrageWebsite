
from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, DATETIME, ForeignKey
from sqlalchemy.orm import relationship

# Reuse the Base from the database module so all models share the same metadata
from .database import Base

class Exchange(Base):
    __tablename__ = 'exchanges'
    id = Column(Integer, primary_key=True, autoincrement=True)
    exchange_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    country = Column(String(255))
    is_korean = Column(Boolean)
    site_url = Column(String(255))
    api_url = Column(String(255))
    logo_url = Column(String(255))
    is_active = Column(Boolean, default=True)

class Cryptocurrency(Base):
    __tablename__ = 'cryptocurrencies'
    id = Column(Integer, primary_key=True, autoincrement=True)
    crypto_id = Column(String(255), unique=True, nullable=False)
    symbol = Column(String(255), nullable=False)
    name_ko = Column(String(255))
    name_en = Column(String(255))
    logo_url = Column(String(255))
    is_active = Column(Boolean, default=True)

class CoinPrice(Base):
    __tablename__ = 'coin_prices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    crypto_id = Column(Integer, ForeignKey('cryptocurrencies.id'))
    exchange_id = Column(Integer, ForeignKey('exchanges.id'))
    price_krw = Column(DECIMAL(20, 8))
    price_usd = Column(DECIMAL(20, 8))
    last_updated = Column(DATETIME)
    cryptocurrency = relationship("Cryptocurrency")
    exchange = relationship("Exchange")

class PremiumHistory(Base):
    __tablename__ = 'premium_histories'
    id = Column(Integer, primary_key=True, autoincrement=True)
    crypto_id = Column(Integer, ForeignKey('cryptocurrencies.id'))
    premium = Column(DECIMAL(10, 4))
    gap = Column(DECIMAL(20, 8))
    korean_price = Column(DECIMAL(20, 8))
    foreign_price = Column(DECIMAL(20, 8))
    reference_exchange_kor = Column(Integer, ForeignKey('exchanges.id'))
    reference_exchange_for = Column(Integer, ForeignKey('exchanges.id'))
    timestamp = Column(DATETIME)
    cryptocurrency = relationship("Cryptocurrency")
    kor_exchange = relationship("Exchange", foreign_keys=[reference_exchange_kor])
    for_exchange = relationship("Exchange", foreign_keys=[reference_exchange_for])
