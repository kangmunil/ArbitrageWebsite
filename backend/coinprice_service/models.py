
from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, DATETIME, ForeignKey
from sqlalchemy.orm import relationship

# Reuse the Base from the database module so all models share the same metadata
from database import Base

class Exchange(Base):
    """거래소 정보를 저장하는 모델.
    
    국내외 암호화폐 거래소의 기본 정보를 저장합니다.
    Upbit, Bithumb(국내)와 Binance, Bybit(해외) 등을 포함합니다.
    
    Attributes:
        id (int): 기본 키
        exchange_id (str): 거래소 고유 ID
        name (str): 거래소 명
        country (str): 국가
        is_korean (bool): 한국 거래소 여부
        site_url (str): 거래소 웹사이트 URL
        api_url (str): API 기본 URL
        logo_url (str): 로고 이미지 URL
        is_active (bool): 활성 상태
    """
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
    """암호화폐 정보를 저장하는 모델.
    
    지원되는 암호화폐의 메타데이터를 저장합니다.
    BTC, ETH, XRP 등의 기본 정보를 포함합니다.
    
    Attributes:
        id (int): 기본 키
        crypto_id (str): 암호화폐 고유 ID
        symbol (str): 심볼 (예: BTC, ETH)
        name_ko (str): 한글 명칭
        name_en (str): 영문 명칭
        logo_url (str): 로고 이미지 URL
        is_active (bool): 활성 상태
    """
    __tablename__ = 'cryptocurrencies'
    id = Column(Integer, primary_key=True, autoincrement=True)
    crypto_id = Column(String(255), unique=True, nullable=False)
    symbol = Column(String(255), nullable=False)
    name_ko = Column(String(255))
    name_en = Column(String(255))
    logo_url = Column(String(255))
    is_active = Column(Boolean, default=True)

class CoinPrice(Base):
    """코인 가격 정보를 저장하는 모델.
    
    특정 시점의 암호화폐 가격을 거래소별로 저장합니다.
    KRW와 USD 가격을 모두 추적합니다.
    
    Attributes:
        id (int): 기본 키
        crypto_id (int): 암호화폐 ID (외래키)
        exchange_id (int): 거래소 ID (외래키)
        price_krw (Decimal): KRW 가격
        price_usd (Decimal): USD 가격
        last_updated (datetime): 마지막 업데이트 시간
        cryptocurrency: 암호화폐 객체 참조
        exchange: 거래소 객체 참조
    """
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
    """프리미엄 이력을 저장하는 모델.
    
    김치 프리미엄 계산 이력과 관련 정보를 저장합니다.
    한국 거래소와 해외 거래소 간의 가격차를 추적합니다.
    
    Attributes:
        id (int): 기본 키
        crypto_id (int): 암호화폐 ID (외래키)
        premium (Decimal): 프리미엄 비율 (%)
        gap (Decimal): 절대 가격차 금액
        korean_price (Decimal): 한국 거래소 가격
        foreign_price (Decimal): 해외 거래소 가격
        reference_exchange_kor (int): 기준 한국 거래소 ID
        reference_exchange_for (int): 기준 해외 거래소 ID
        timestamp (datetime): 기록 시간
        cryptocurrency: 암호화폐 객체 참조
        kor_exchange: 한국 거래소 객체 참조
        for_exchange: 해외 거래소 객체 참조
    """
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
