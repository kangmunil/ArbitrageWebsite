"""Data Schemas for Market Sentiment & Liquidation Service

Pydantic 모델을 사용한 데이터 구조 정의
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from enum import Enum
from pydantic import BaseModel, Field


class Exchange(str, Enum):
    """거래소 목록"""
    BINANCE = "binance"
    BITGET = "bitget"
    OKX = "okx"
    BYBIT = "bybit"


class TimeInterval(str, Enum):
    """시간 간격"""
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    THIRTY_MIN = "30m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"


class PositionSide(str, Enum):
    """포지션 방향"""
    LONG = "long"
    SHORT = "short"


class LongShortRatio(BaseModel):
    """롱숏 비율 데이터 모델"""
    exchange: Exchange
    symbol: str
    timestamp: datetime
    interval: TimeInterval
    
    # 비율 데이터
    long_ratio: float = Field(..., ge=0, le=1, description="롱 포지션 비율 (0-1)")
    short_ratio: float = Field(..., ge=0, le=1, description="숏 포지션 비율 (0-1)")
    long_short_ratio: float = Field(..., gt=0, description="롱/숏 비율 (long/short)")
    
    # 계정 기반 vs 포지션 기반
    account_based: bool = Field(True, description="계정 기반 비율 여부")
    top_traders_only: bool = Field(False, description="상위 트레이더만 포함 여부")
    
    # 메타데이터
    total_accounts: Optional[int] = Field(None, description="총 계정 수")
    total_position_value: Optional[float] = Field(None, description="총 포지션 가치 (USDT)")


class LiquidationEvent(BaseModel):
    """개별 청산 이벤트"""
    exchange: Exchange
    symbol: str
    timestamp: datetime
    
    # 청산 정보
    side: PositionSide
    price: float = Field(..., gt=0, description="청산 가격")
    quantity: float = Field(..., gt=0, description="청산 수량")
    value_usd: float = Field(..., gt=0, description="청산 가치 (USD)")
    
    # 추가 정보
    order_id: Optional[str] = None
    leverage: Optional[float] = Field(None, gt=0, description="레버리지")


class LiquidationSummary(BaseModel):
    """청산 요약 데이터"""
    symbol: str
    timeframe: str  # "24h", "1h", "5m" 등
    timestamp: datetime
    
    # 총계
    total_liquidation_usd: float = Field(..., ge=0)
    long_liquidation_usd: float = Field(..., ge=0)
    short_liquidation_usd: float = Field(..., ge=0)
    
    # 비율
    long_percentage: float = Field(..., ge=0, le=100)
    short_percentage: float = Field(..., ge=0, le=100)
    
    # 건수
    total_events: int = Field(..., ge=0)
    long_events: int = Field(..., ge=0)
    short_events: int = Field(..., ge=0)
    
    # 거래소별 분포
    exchange_breakdown: Dict[Exchange, float] = Field(default_factory=dict)


class MarketIndicator(BaseModel):
    """시장 지표 데이터"""
    symbol: str
    timestamp: datetime
    
    # 가격 관련
    price: float = Field(..., gt=0)
    price_change_24h: float
    price_change_percent_24h: float
    
    # 거래량 관련
    volume_24h: float = Field(..., ge=0)
    volume_change_percent_24h: float
    
    # 파생상품 지표
    open_interest: Optional[float] = Field(None, ge=0, description="미결제약정")
    open_interest_change_24h: Optional[float] = None
    funding_rate: Optional[float] = Field(None, description="펀딩비율")
    
    # 변동성 지표
    volatility_24h: Optional[float] = Field(None, ge=0, description="24시간 변동성")
    atr_14: Optional[float] = Field(None, ge=0, description="14일 ATR")


class LiquidationRisk(BaseModel):
    """청산 위험도 분석"""
    symbol: str
    timestamp: datetime
    
    # 위험도 점수 (0-100)
    risk_score: float = Field(..., ge=0, le=100, description="청산 위험도 점수")
    risk_level: str = Field(..., description="위험 수준 (low/medium/high/extreme)")
    
    # 구성 요소별 점수
    funding_rate_risk: float = Field(..., ge=0, le=100)
    volatility_risk: float = Field(..., ge=0, le=100)
    open_interest_risk: float = Field(..., ge=0, le=100)
    volume_risk: float = Field(..., ge=0, le=100)
    
    # 예상 청산 가격대
    long_liquidation_zones: List[float] = Field(default_factory=list, description="롱 포지션 청산 예상 가격대")
    short_liquidation_zones: List[float] = Field(default_factory=list, description="숏 포지션 청산 예상 가격대")


class MarketSentiment(BaseModel):
    """종합 시장 심리"""
    symbol: str
    timestamp: datetime
    
    # 종합 점수
    sentiment_score: float = Field(..., ge=-100, le=100, description="시장 심리 점수 (-100: 극도 약세, +100: 극도 강세)")
    sentiment_label: str = Field(..., description="심리 라벨 (극도약세/약세/중립/강세/극도강세)")
    
    # 구성 요소
    long_short_sentiment: float = Field(..., ge=-50, le=50, description="롱숏 비율 기반 심리")
    liquidation_sentiment: float = Field(..., ge=-50, le=50, description="청산 데이터 기반 심리")
    
    # 신뢰도
    confidence: float = Field(..., ge=0, le=1, description="분석 신뢰도")
    
    # 추가 컨텍스트
    dominant_trend: str = Field(..., description="지배적 트렌드 (bullish/bearish/neutral)")
    market_phase: str = Field(..., description="시장 단계 (accumulation/markup/distribution/markdown)")


class APIResponse(BaseModel):
    """API 응답 기본 구조"""
    success: bool = True
    message: str = "Success"
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Optional[Union[
        LongShortRatio,
        List[LongShortRatio],
        LiquidationSummary,
        List[LiquidationSummary],
        MarketSentiment,
        List,
        Dict,
        Any
    ]] = None


class HealthCheck(BaseModel):
    """서비스 상태 체크"""
    service_name: str = "Market Sentiment & Liquidation Service"
    version: str = "2.0.0"
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # 각 구성요소 상태
    collectors_status: Dict[str, str] = Field(default_factory=dict)
    redis_status: str = "unknown"
    websocket_connections: int = 0
    
    # 데이터 통계
    last_update: Optional[datetime] = None
    total_symbols_tracked: int = 0
    active_websockets: int = 0