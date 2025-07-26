"""
거래소별 API 명세 및 특성 분석

각 거래소의 API 제한사항, 데이터 형식, 오류 처리 방식을 정의합니다.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import time

class ExchangeType(Enum):
    """거래소 유형"""
    DOMESTIC = "domestic"    # 국내 거래소
    GLOBAL = "global"       # 해외 거래소

class APIEndpointType(Enum):
    """API 엔드포인트 유형"""
    REST = "rest"
    WEBSOCKET = "websocket"

@dataclass
class RateLimitSpec:
    """Rate Limit 명세"""
    requests_per_second: float
    requests_per_minute: int
    requests_per_hour: int
    burst_capacity: int
    weight_per_request: int = 1  # 가중치 기반 제한 (Binance)
    
@dataclass
class WebSocketSpec:
    """WebSocket 명세"""
    url: str
    max_connections: int
    max_subscriptions: int
    heartbeat_interval: Optional[int] = None
    reconnect_limit: int = 10
    message_size_limit: int = 1024 * 1024  # 1MB

@dataclass
class ErrorHandlingSpec:
    """오류 처리 명세"""
    retry_codes: List[int]  # 재시도 가능한 HTTP 상태 코드
    fatal_codes: List[int]  # 재시도 불가능한 코드
    rate_limit_codes: List[int]  # Rate limit 관련 코드
    maintenance_patterns: List[str]  # 점검 관련 에러 메시지 패턴

@dataclass
class DataFormat:
    """데이터 형식 명세"""
    price_field: str
    volume_field: str
    change_percent_field: str
    symbol_format: str  # 심볼 형식 (예: "BTC-KRW", "BTCUSDT")
    decimal_places: int = 8
    volume_unit: str = "quote"  # "base" or "quote"

@dataclass
class ExchangeSpec:
    """거래소 API 명세"""
    name: str
    type: ExchangeType
    base_url: str
    websocket_url: str
    
    # API 제한사항
    rest_rate_limits: RateLimitSpec
    websocket_spec: WebSocketSpec
    error_handling: ErrorHandlingSpec
    data_format: DataFormat
    
    # 기능 지원 여부
    supports_all_tickers: bool = True
    supports_individual_ticker: bool = True
    supports_market_data: bool = True
    supports_kline_data: bool = True
    
    # 추가 설정
    timezone: str = "UTC"
    maintenance_window: Optional[str] = None  # 정기 점검 시간
    backup_endpoints: List[str] = field(default_factory=list)

# === 거래소별 명세 정의 ===

# Upbit 명세
UPBIT_SPEC = ExchangeSpec(
    name="upbit",
    type=ExchangeType.DOMESTIC,
    base_url="https://api.upbit.com",
    websocket_url="wss://api.upbit.com/websocket/v1",
    
    rest_rate_limits=RateLimitSpec(
        requests_per_second=10.0,
        requests_per_minute=600,
        requests_per_hour=10000,
        burst_capacity=20
    ),
    
    websocket_spec=WebSocketSpec(
        url="wss://api.upbit.com/websocket/v1",
        max_connections=5,
        max_subscriptions=1000,
        heartbeat_interval=None,
        reconnect_limit=10
    ),
    
    error_handling=ErrorHandlingSpec(
        retry_codes=[500, 502, 503, 504, 429],
        fatal_codes=[400, 401, 403, 404],
        rate_limit_codes=[429],
        maintenance_patterns=["maintenance", "점검", "서비스 중단"]
    ),
    
    data_format=DataFormat(
        price_field="trade_price",
        volume_field="acc_trade_price_24h",  # KRW 거래대금
        change_percent_field="signed_change_rate",
        symbol_format="KRW-{symbol}",
        decimal_places=8,
        volume_unit="quote"
    ),
    
    timezone="Asia/Seoul",
    maintenance_window="05:00-05:30 KST",  # 일반적인 점검 시간
    backup_endpoints=[]
)

# Binance 명세
BINANCE_SPEC = ExchangeSpec(
    name="binance",
    type=ExchangeType.GLOBAL,
    base_url="https://api.binance.com",
    websocket_url="wss://stream.binance.com:9443",
    
    rest_rate_limits=RateLimitSpec(
        requests_per_second=20.0,
        requests_per_minute=1200,
        requests_per_hour=20000,
        burst_capacity=50,
        weight_per_request=1  # 가중치 기반
    ),
    
    websocket_spec=WebSocketSpec(
        url="wss://stream.binance.com:9443/ws/!ticker@arr",
        max_connections=1024,
        max_subscriptions=200,
        heartbeat_interval=60,
        reconnect_limit=5
    ),
    
    error_handling=ErrorHandlingSpec(
        retry_codes=[500, 502, 503, 504, 429, 418],  # 418: I'm a teapot (IP ban)
        fatal_codes=[400, 401, 403, 404, 451],
        rate_limit_codes=[429, 418],
        maintenance_patterns=["maintenance", "system upgrade", "temporarily unavailable"]
    ),
    
    data_format=DataFormat(
        price_field="c",  # close price
        volume_field="q",  # quote asset volume (USDT)
        change_percent_field="P",  # price change percent
        symbol_format="{symbol}USDT",
        decimal_places=8,
        volume_unit="quote"
    ),
    
    timezone="UTC",
    maintenance_window="08:00-09:00 UTC",  # 일반적인 점검 시간
    backup_endpoints=[
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com"
    ]
)

# Bybit 명세
BYBIT_SPEC = ExchangeSpec(
    name="bybit",
    type=ExchangeType.GLOBAL,
    base_url="https://api.bybit.com",
    websocket_url="wss://stream.bybit.com/v5/public/spot",
    
    rest_rate_limits=RateLimitSpec(
        requests_per_second=5.0,
        requests_per_minute=300,
        requests_per_hour=2000,
        burst_capacity=10
    ),
    
    websocket_spec=WebSocketSpec(
        url="wss://stream.bybit.com/v5/public/spot",
        max_connections=10,
        max_subscriptions=100,
        heartbeat_interval=30,
        reconnect_limit=10
    ),
    
    error_handling=ErrorHandlingSpec(
        retry_codes=[500, 502, 503, 504, 429],
        fatal_codes=[400, 401, 403, 404, 10001],  # 10001: Invalid parameter
        rate_limit_codes=[429, 10006],  # 10006: Too many requests
        maintenance_patterns=["maintenance", "upgrade", "temporarily unavailable"]
    ),
    
    data_format=DataFormat(
        price_field="lastPrice",
        volume_field="turnover24h",  # 24h turnover in USDT
        change_percent_field="price24hPcnt",
        symbol_format="{symbol}USDT",
        decimal_places=8,
        volume_unit="quote"
    ),
    
    timezone="UTC",
    maintenance_window="02:00-04:00 UTC",
    backup_endpoints=[
        "https://api-testnet.bybit.com"  # 테스트넷 (백업용도로 제한적 사용)
    ]
)

# Bithumb 명세 (국내 거래소)
BITHUMB_SPEC = ExchangeSpec(
    name="bithumb",
    type=ExchangeType.DOMESTIC,
    base_url="https://api.bithumb.com",
    websocket_url="wss://pubwss.bithumb.com/pub/ws",
    
    rest_rate_limits=RateLimitSpec(
        requests_per_second=20.0,  # 관대한 편
        requests_per_minute=900,
        requests_per_hour=15000,
        burst_capacity=30
    ),
    
    websocket_spec=WebSocketSpec(
        url="wss://pubwss.bithumb.com/pub/ws",
        max_connections=5,
        max_subscriptions=100,
        heartbeat_interval=60,
        reconnect_limit=10
    ),
    
    error_handling=ErrorHandlingSpec(
        retry_codes=[500, 502, 503, 504],
        fatal_codes=[400, 401, 403, 404],
        rate_limit_codes=[429],
        maintenance_patterns=["점검", "maintenance", "서비스 일시 중단"]
    ),
    
    data_format=DataFormat(
        price_field="closing_price",
        volume_field="acc_trade_value_24H",  # KRW 거래대금
        change_percent_field="fluctate_rate_24H",
        symbol_format="{symbol}_KRW",
        decimal_places=4,  # Bithumb은 소수점 자리가 적음
        volume_unit="quote"
    ),
    
    timezone="Asia/Seoul",
    maintenance_window="05:30-06:00 KST",
    backup_endpoints=[]
)

# 전체 거래소 명세 딕셔너리
EXCHANGE_SPECS: Dict[str, ExchangeSpec] = {
    "upbit": UPBIT_SPEC,
    "binance": BINANCE_SPEC,
    "bybit": BYBIT_SPEC,
    "bithumb": BITHUMB_SPEC,
}

# === 유틸리티 함수들 ===

def get_exchange_spec(exchange_name: str) -> Optional[ExchangeSpec]:
    """거래소 명세 반환"""
    return EXCHANGE_SPECS.get(exchange_name.lower())

def get_all_exchange_names() -> List[str]:
    """모든 거래소 이름 반환"""
    return list(EXCHANGE_SPECS.keys())

def get_domestic_exchanges() -> List[str]:
    """국내 거래소 목록 반환"""
    return [
        name for name, spec in EXCHANGE_SPECS.items()
        if spec.type == ExchangeType.DOMESTIC
    ]

def get_global_exchanges() -> List[str]:
    """해외 거래소 목록 반환"""
    return [
        name for name, spec in EXCHANGE_SPECS.items()
        if spec.type == ExchangeType.GLOBAL
    ]

def is_retriable_error(exchange_name: str, status_code: int, error_message: str = "") -> bool:
    """재시도 가능한 오류인지 판단"""
    spec = get_exchange_spec(exchange_name)
    if not spec:
        return False
    
    # HTTP 상태 코드 확인
    if status_code in spec.error_handling.fatal_codes:
        return False
    
    if status_code in spec.error_handling.retry_codes:
        return True
    
    # 점검 관련 메시지 확인
    if error_message:
        message_lower = error_message.lower()
        for pattern in spec.error_handling.maintenance_patterns:
            if pattern.lower() in message_lower:
                return True
    
    return False

def is_rate_limited(exchange_name: str, status_code: int, error_message: str = "") -> bool:
    """Rate limit 오류인지 판단"""
    spec = get_exchange_spec(exchange_name)
    if not spec:
        return False
    
    return status_code in spec.error_handling.rate_limit_codes

def get_symbol_format(exchange_name: str, base_symbol: str) -> str:
    """거래소별 심볼 형식 생성"""
    spec = get_exchange_spec(exchange_name)
    if not spec:
        return base_symbol
    
    return spec.data_format.symbol_format.format(symbol=base_symbol)

def normalize_ticker_data(exchange_name: str, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """거래소별 티커 데이터 정규화"""
    spec = get_exchange_spec(exchange_name)
    if not spec:
        return None
    
    try:
        normalized = {
            "exchange": exchange_name,
            "timestamp": time.time(),
            "price": float(raw_data.get(spec.data_format.price_field, 0)),
            "volume": float(raw_data.get(spec.data_format.volume_field, 0)),
            "change_percent": float(raw_data.get(spec.data_format.change_percent_field, 0)),
            "raw_data": raw_data  # 원본 데이터 보존
        }
        
        # 거래소별 추가 처리
        if exchange_name == "upbit":
            # Upbit은 change_percent가 비율(0.05 = 5%)
            normalized["change_percent"] *= 100
            
        elif exchange_name == "binance":
            # Binance는 이미 퍼센트 단위
            pass
            
        elif exchange_name == "bybit":
            # Bybit은 문자열로 올 수 있음
            if isinstance(raw_data.get(spec.data_format.change_percent_field), str):
                change_str = raw_data.get(spec.data_format.change_percent_field, "0")
                normalized["change_percent"] = float(change_str) * 100
        
        # 데이터 유효성 검사
        if normalized["price"] <= 0:
            return None
            
        return normalized
        
    except (ValueError, TypeError, KeyError) as e:
        return None

def get_maintenance_info(exchange_name: str) -> Dict[str, Any]:
    """거래소 점검 정보 반환"""
    spec = get_exchange_spec(exchange_name)
    if not spec:
        return {}
    
    return {
        "exchange": exchange_name,
        "timezone": spec.timezone,
        "maintenance_window": spec.maintenance_window,
        "backup_endpoints": spec.backup_endpoints
    }