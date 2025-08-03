#!/usr/bin/env python3
"""
시스템 설정 관리
환경변수, 상수, 설정값들을 중앙 관리
"""

import os
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", 3306))
    user: str = os.getenv("DB_USER", "user")
    password: str = os.getenv("DB_PASSWORD", "password")
    database: str = os.getenv("DB_NAME", "kimchiscan")
    charset: str = "utf8mb4"
    pool_size: int = 10
    max_overflow: int = 20
    
    @property
    def url(self) -> str:
        """SQLAlchemy 연결 URL"""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"

@dataclass
class RedisConfig:
    """Redis 설정"""
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", 6379))
    db: int = int(os.getenv("REDIS_DB", 0))
    password: str = os.getenv("REDIS_PASSWORD", "")
    
    @property
    def url(self) -> str:
        """Redis 연결 URL"""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

@dataclass
class ExchangeConfig:
    """거래소 설정"""
    
    # 한국 거래소
    KOREAN_EXCHANGES = ["upbit", "bithumb"]
    
    # 해외 거래소 (CCXT 기반)
    GLOBAL_EXCHANGES = ["binance", "bybit", "okx", "gateio", "bitget", "mexc", "coinbasepro"]
    
    # 우선순위 (낮을수록 높은 우선순위)
    EXCHANGE_PRIORITY = {
        "upbit": 1, "bithumb": 2,
        "binance": 3, "bybit": 4, "okx": 5,
        "gateio": 6, "bitget": 7, "mexc": 8, "coinbasepro": 9
    }
    
    # 거래소별 Rate Limit (requests per minute)
    RATE_LIMITS = {
        "upbit": 600, "bithumb": 300,
        "binance": 1200, "bybit": 600, "okx": 300,
        "gateio": 300, "bitget": 300, "mexc": 300, "coinbasepro": 300
    }
    
    # 주요 거래쌍
    MAJOR_PAIRS = {
        "KR": ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"],
        "GLOBAL": ["BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT", "DOGE/USDT"]
    }

@dataclass
class CoinGeckoConfig:
    """CoinGecko API 설정"""
    base_url: str = "https://api.coingecko.com/api/v3"
    api_key: str = os.getenv("COINGECKO_API_KEY", "")
    rate_limit_delay: float = 1.5  # 초당 요청 간격
    max_retries: int = 3
    timeout: int = 30

@dataclass
class SystemConfig:
    """시스템 전반 설정"""
    
    # 데이터 수집 주기
    PRICE_COLLECTION_INTERVAL = 60  # 초
    METADATA_UPDATE_INTERVAL = 3600 * 24  # 일 1회
    KIMCHI_CALCULATION_INTERVAL = 60  # 초
    
    # 데이터 보관 기간
    PRICE_DATA_RETENTION_DAYS = 90
    LOG_RETENTION_DAYS = 30
    
    # 성능 설정
    BATCH_SIZE = 1000
    MAX_CONCURRENT_REQUESTS = 10
    REQUEST_TIMEOUT = 30
    
    # 환율 설정
    DEFAULT_USD_KRW_RATE = 1350.0
    FX_RATE_UPDATE_INTERVAL = 3600  # 1시간마다
    
    # 웹소켓 설정
    WEBSOCKET_PING_INTERVAL = 30
    WEBSOCKET_RECONNECT_DELAY = 5
    
    # 로깅 설정
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

class Settings:
    """전체 설정 클래스"""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.redis = RedisConfig()
        self.exchange = ExchangeConfig()
        self.coingecko = CoinGeckoConfig()
        self.system = SystemConfig()
        
        # 환경별 설정 오버라이드
        self._load_environment_overrides()
    
    def _load_environment_overrides(self):
        """환경변수로 설정 오버라이드"""
        
        # 개발/운영 환경 구분
        environment = os.getenv("ENVIRONMENT", "development")
        
        if environment == "production":
            # 운영 환경 설정
            self.system.LOG_LEVEL = "WARNING"
            self.system.BATCH_SIZE = 5000
            self.database.pool_size = 20
            
        elif environment == "development":
            # 개발 환경 설정
            self.system.LOG_LEVEL = "DEBUG"
            self.system.BATCH_SIZE = 100
            
        elif environment == "testing":
            # 테스트 환경 설정
            self.database.database = "kimchiscan_test"
            self.system.PRICE_COLLECTION_INTERVAL = 10
    
    def get_exchange_config(self, exchange_id: str) -> Dict:
        """특정 거래소 설정 반환"""
        return {
            "id": exchange_id,
            "priority": self.exchange.EXCHANGE_PRIORITY.get(exchange_id, 999),
            "rate_limit": self.exchange.RATE_LIMITS.get(exchange_id, 300),
            "is_korean": exchange_id in self.exchange.KOREAN_EXCHANGES,
            "is_active": True
        }
    
    def get_all_exchange_configs(self) -> List[Dict]:
        """모든 거래소 설정 반환"""
        all_exchanges = self.exchange.KOREAN_EXCHANGES + self.exchange.GLOBAL_EXCHANGES
        return [self.get_exchange_config(ex_id) for ex_id in all_exchanges]
    
    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "development") == "production"
    
    @property
    def is_development(self) -> bool:
        return os.getenv("ENVIRONMENT", "development") == "development"

# 글로벌 설정 인스턴스
settings = Settings()

# 자주 사용하는 상수들
DB_URL = settings.database.url
REDIS_URL = settings.redis.url
KOREAN_EXCHANGES = settings.exchange.KOREAN_EXCHANGES
GLOBAL_EXCHANGES = settings.exchange.GLOBAL_EXCHANGES

# 기본 환율 (fallback)
DEFAULT_EXCHANGE_RATE = settings.system.DEFAULT_USD_KRW_RATE