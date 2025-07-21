
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ExchangeBase(BaseModel):
    exchange_id: str
    name: str
    country: str
    is_korean: bool
    site_url: Optional[str] = None
    api_url: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool

    class Config:
        orm_mode = True

class Exchange(ExchangeBase):
    id: int

class CryptocurrencyBase(BaseModel):
    crypto_id: str
    symbol: str
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool

    class Config:
        orm_mode = True

class Cryptocurrency(CryptocurrencyBase):
    id: int

class CoinPriceBase(BaseModel):
    crypto_id: int
    exchange_id: int
    price_krw: float
    price_usd: float
    last_updated: datetime

    class Config:
        orm_mode = True

class CoinPrice(CoinPriceBase):
    id: int

class PremiumHistoryBase(BaseModel):
    crypto_id: int
    premium: float
    gap: float
    korean_price: float
    foreign_price: float
    reference_exchange_kor: int
    reference_exchange_for: int
    timestamp: datetime

    class Config:
        orm_mode = True

class PremiumHistory(PremiumHistoryBase):
    id: int
