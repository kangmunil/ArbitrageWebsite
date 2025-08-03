#!/usr/bin/env python3
"""
SQLAlchemy 모델 정의
새로운 테이블 구조에 맞는 ORM 모델들
"""

from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal

from sqlalchemy import Column, String, Integer, Boolean, TIMESTAMP, DECIMAL, TEXT, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

class CoinMaster(Base):
    """글로벌 코인 마스터 (CoinGecko 기준)"""
    __tablename__ = "coin_master"
    
    coingecko_id = Column(String(50), primary_key=True, comment="CoinGecko 고유 ID")
    symbol = Column(String(20), nullable=False, comment="대표 심볼")
    name_en = Column(String(100), comment="영문명")
    name_ko = Column(String(100), comment="한글명")
    image_url = Column(String(255), comment="아이콘 URL")
    market_cap_rank = Column(Integer, comment="시가총액 순위")
    description = Column(TEXT, comment="코인 설명")
    homepage_url = Column(String(255), comment="공식 홈페이지")
    is_active = Column(Boolean, default=True, comment="활성 상태")
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_symbol', 'symbol'),
        Index('idx_rank', 'market_cap_rank'),
        Index('idx_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<CoinMaster(id={self.coingecko_id}, symbol={self.symbol})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "coingecko_id": self.coingecko_id,
            "symbol": self.symbol,
            "name_en": self.name_en,
            "name_ko": self.name_ko,
            "image_url": self.image_url,
            "market_cap_rank": self.market_cap_rank,
            "description": self.description,
            "homepage_url": self.homepage_url,
            "is_active": self.is_active,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class UpbitListing(Base):
    """업비트 상장 코인 (API 한글명 포함)"""
    __tablename__ = "upbit_listings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String(20), nullable=False, unique=True, comment="마켓 코드")
    symbol = Column(String(20), nullable=False, comment="심볼")
    korean_name = Column(String(100), nullable=False, comment="한글명")
    english_name = Column(String(100), comment="영문명")
    coingecko_id = Column(String(50), comment="CoinGecko ID")
    is_active = Column(Boolean, default=True, comment="거래 활성 상태")
    last_updated = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_symbol', 'symbol'),
        Index('idx_korean_name', 'korean_name'),
        Index('idx_coingecko', 'coingecko_id'),
    )
    
    def __repr__(self):
        return f"<UpbitListing(market={self.market}, symbol={self.symbol}, korean_name={self.korean_name})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "market": self.market,
            "symbol": self.symbol,
            "korean_name": self.korean_name,
            "english_name": self.english_name,
            "coingecko_id": self.coingecko_id,
            "is_active": self.is_active,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }

class BithumbListing(Base):
    """빗썸 상장 코인 (CoinGecko 한글명 매핑)"""
    __tablename__ = "bithumb_listings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True, comment="심볼")
    korean_name = Column(String(100), comment="한글명")
    coingecko_id = Column(String(50), comment="CoinGecko ID")
    # trading_pair는 GENERATED ALWAYS AS로 정의됨 (MySQL에서 처리)
    is_active = Column(Boolean, default=True, comment="거래 활성 상태")
    last_updated = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_symbol', 'symbol'),
        Index('idx_korean_name', 'korean_name'),
        Index('idx_coingecko', 'coingecko_id'),
    )
    
    def __repr__(self):
        return f"<BithumbListing(symbol={self.symbol}, korean_name={self.korean_name})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "korean_name": self.korean_name,
            "coingecko_id": self.coingecko_id,
            "trading_pair": f"KRW-{self.symbol}",  # 계산된 거래쌍
            "is_active": self.is_active,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }

class ExchangeRegistry(Base):
    """거래소 등록 정보"""
    __tablename__ = "exchange_registry"
    
    exchange_id = Column(String(20), primary_key=True, comment="거래소 ID")
    exchange_name = Column(String(50), nullable=False, comment="거래소 명")
    region = Column(String(10), nullable=False, comment="지역")
    base_currency = Column(String(10), comment="기본 통화")
    api_enabled = Column(Boolean, default=True, comment="API 활성화")
    rate_limit_per_minute = Column(Integer, default=1200, comment="분당 요청 제한")
    priority_order = Column(Integer, default=999, comment="우선순위")
    ccxt_id = Column(String(20), comment="CCXT ID")
    is_active = Column(Boolean, default=True, comment="활성 상태")
    created_at = Column(TIMESTAMP, default=func.now())
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_region', 'region'),
        Index('idx_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<ExchangeRegistry(id={self.exchange_id}, name={self.exchange_name})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange_id": self.exchange_id,
            "exchange_name": self.exchange_name,
            "region": self.region,
            "base_currency": self.base_currency,
            "api_enabled": self.api_enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "priority_order": self.priority_order,
            "ccxt_id": self.ccxt_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class PriceSnapshot(Base):
    """실시간 가격 데이터"""
    __tablename__ = "price_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    coingecko_id = Column(String(50), nullable=False, comment="CoinGecko ID")
    exchange_id = Column(String(20), nullable=False, comment="거래소 ID")
    symbol = Column(String(20), nullable=False, comment="심볼")
    trading_pair = Column(String(20), nullable=False, comment="거래쌍")
    price = Column(DECIMAL(20, 8), nullable=False, comment="현재가")
    volume_24h = Column(DECIMAL(20, 8), comment="24시간 거래량")
    price_change_24h = Column(DECIMAL(10, 4), comment="24시간 가격 변화율")
    collected_at = Column(TIMESTAMP, default=func.now(), comment="수집 시간")
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_coin_exchange', 'coingecko_id', 'exchange_id'),
        Index('idx_symbol_time', 'symbol', 'collected_at'),
        Index('idx_collected_at', 'collected_at'),
    )
    
    def __repr__(self):
        return f"<PriceSnapshot(coin={self.coingecko_id}, exchange={self.exchange_id}, price={self.price})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "coingecko_id": self.coingecko_id,
            "exchange_id": self.exchange_id,
            "symbol": self.symbol,
            "trading_pair": self.trading_pair,
            "price": float(self.price) if self.price else None,
            "volume_24h": float(self.volume_24h) if self.volume_24h else None,
            "price_change_24h": float(self.price_change_24h) if self.price_change_24h else None,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None
        }

class KimchiPremium(Base):
    """김치프리미엄 계산 결과"""
    __tablename__ = "kimchi_premium"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    coingecko_id = Column(String(50), nullable=False, comment="CoinGecko ID")
    symbol = Column(String(20), nullable=False, comment="심볼")
    
    # 국내 가격 정보
    upbit_price = Column(DECIMAL(20, 8), comment="업비트 가격")
    bithumb_price = Column(DECIMAL(20, 8), comment="빗썸 가격")
    korean_avg_price = Column(DECIMAL(20, 8), comment="국내 평균가")
    
    # 해외 가격 정보
    global_avg_price = Column(DECIMAL(20, 8), comment="해외 평균가")
    global_avg_price_krw = Column(DECIMAL(20, 8), comment="해외 평균가 KRW")
    
    # 김치프리미엄 계산
    usd_krw_rate = Column(DECIMAL(10, 4), nullable=False, comment="달러-원 환율")
    kimchi_premium = Column(DECIMAL(10, 4), comment="김치 프리미엄")
    calculated_at = Column(TIMESTAMP, default=func.now(), comment="계산 시간")
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_symbol_calc', 'symbol', 'calculated_at'),
        Index('idx_premium', 'kimchi_premium'),
        Index('idx_calc_time', 'calculated_at'),
    )
    
    def __repr__(self):
        return f"<KimchiPremium(symbol={self.symbol}, premium={self.kimchi_premium}%)>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "coingecko_id": self.coingecko_id,
            "symbol": self.symbol,
            "upbit_price": float(self.upbit_price) if self.upbit_price else None,
            "bithumb_price": float(self.bithumb_price) if self.bithumb_price else None,
            "korean_avg_price": float(self.korean_avg_price) if self.korean_avg_price else None,
            "global_avg_price": float(self.global_avg_price) if self.global_avg_price else None,
            "global_avg_price_krw": float(self.global_avg_price_krw) if self.global_avg_price_krw else None,
            "usd_krw_rate": float(self.usd_krw_rate) if self.usd_krw_rate else None,
            "kimchi_premium": float(self.kimchi_premium) if self.kimchi_premium else None,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None
        }

class ExchangeRate(Base):
    """환율 정보"""
    __tablename__ = "exchange_rates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    currency_pair = Column(String(10), nullable=False, unique=True, comment="통화쌍")
    rate = Column(DECIMAL(10, 4), nullable=False, comment="환율")
    source = Column(String(50), nullable=False, comment="환율 소스")
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_updated', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<ExchangeRate(pair={self.currency_pair}, rate={self.rate})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "currency_pair": self.currency_pair,
            "rate": float(self.rate) if self.rate else None,
            "source": self.source,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# 편의 함수들
def get_model_by_name(model_name: str):
    """모델명으로 모델 클래스 반환"""
    models = {
        "coin_master": CoinMaster,
        "upbit_listings": UpbitListing,
        "bithumb_listings": BithumbListing,
        "exchange_registry": ExchangeRegistry,
        "price_snapshots": PriceSnapshot,
        "kimchi_premium": KimchiPremium,
        "exchange_rates": ExchangeRate
    }
    return models.get(model_name.lower())

def get_all_models():
    """모든 모델 반환"""
    return [
        CoinMaster,
        UpbitListing,
        BithumbListing,
        ExchangeRegistry,
        PriceSnapshot,
        KimchiPremium,
        ExchangeRate
    ]

# 테이블 생성 함수 (개발용)
def create_tables(engine):
    """모든 테이블 생성 (주의: 기존 데이터 삭제됨)"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # 간단한 테스트
    print("📋 정의된 모델들:")
    for model in get_all_models():
        print(f"   - {model.__tablename__}: {model.__doc__ or 'No description'}")