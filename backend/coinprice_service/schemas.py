
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ExchangeBase(BaseModel):
    """거래소 기본 스키마.
    
    거래소 생성/수정 시 사용되는 기본 필드들을 정의합니다.
    
    Attributes:
        exchange_id (str): 거래소 고유 ID
        name (str): 거래소 명
        country (str): 국가
        is_korean (bool): 한국 거래소 여부
        site_url (Optional[str]): 거래소 웹사이트 URL
        api_url (Optional[str]): API 기본 URL
        logo_url (Optional[str]): 로고 이미지 URL
        is_active (bool): 활성 상태
    """
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
    """거래소 응답 스키마.
    
    API 응답에서 사용되는 거래소 정보입니다.
    ExchangeBase에 id 필드가 추가된 형태입니다.
    
    Attributes:
        id (int): 데이터베이스 기본 키
    """
    id: int

class CryptocurrencyBase(BaseModel):
    """암호화폐 기본 스키마.
    
    암호화폐 생성/수정 시 사용되는 기본 필드들을 정의합니다.
    
    Attributes:
        crypto_id (str): 암호화폐 고유 ID
        symbol (str): 심볼 (예: BTC, ETH)
        name_ko (Optional[str]): 한글 명칭
        name_en (Optional[str]): 영문 명칭
        logo_url (Optional[str]): 로고 이미지 URL
        is_active (bool): 활성 상태
    """
    crypto_id: str
    symbol: str
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool

    class Config:
        orm_mode = True

class Cryptocurrency(CryptocurrencyBase):
    """암호화폐 응답 스키마.
    
    API 응답에서 사용되는 암호화폐 정보입니다.
    CryptocurrencyBase에 id 필드가 추가된 형태입니다.
    
    Attributes:
        id (int): 데이터베이스 기본 키
    """
    id: int

class CoinPriceBase(BaseModel):
    """코인 가격 기본 스키마.
    
    코인 가격 데이터 생성/수정 시 사용되는 기본 필드들을 정의합니다.
    
    Attributes:
        crypto_id (int): 암호화폐 ID
        exchange_id (int): 거래소 ID
        price_krw (float): KRW 가격
        price_usd (float): USD 가격
        last_updated (datetime): 마지막 업데이트 시간
    """
    crypto_id: int
    exchange_id: int
    price_krw: float
    price_usd: float
    last_updated: datetime

    class Config:
        orm_mode = True

class CoinPrice(CoinPriceBase):
    """코인 가격 응답 스키마.
    
    API 응답에서 사용되는 코인 가격 정보입니다.
    
    Attributes:
        id (int): 데이터베이스 기본 키
    """
    id: int

class PremiumHistoryBase(BaseModel):
    """프리미엄 이력 기본 스키마.
    
    프리미엄 이력 데이터 생성/수정 시 사용되는 기본 필드들을 정의합니다.
    
    Attributes:
        crypto_id (int): 암호화폐 ID
        premium (float): 프리미엄 비율 (%)
        gap (float): 절대 가격차 금액
        korean_price (float): 한국 거래소 가격
        foreign_price (float): 해외 거래소 가격
        reference_exchange_kor (int): 기준 한국 거래소 ID
        reference_exchange_for (int): 기준 해외 거래소 ID
        timestamp (datetime): 기록 시간
    """
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
    """프리미엄 이력 응답 스키마.
    
    API 응답에서 사용되는 프리미엄 이력 정보입니다.
    
    Attributes:
        id (int): 데이터베이스 기본 키
    """
    id: int
