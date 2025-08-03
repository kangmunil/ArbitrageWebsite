#!/usr/bin/env python3
"""
Core 모듈
데이터베이스, 설정, 모델 등 핵심 기능들
"""

from .config import settings, DB_URL, REDIS_URL, KOREAN_EXCHANGES, GLOBAL_EXCHANGES
from .database import (
    db_manager, 
    get_db, 
    get_batch_db, 
    execute_sql, 
    test_db_connection,
    get_db_info,
    health_check,
    cleanup_database
)
from .models import (
    Base,
    CoinMaster,
    UpbitListing,
    BithumbListing,
    ExchangeRegistry,
    PriceSnapshot,
    KimchiPremium,
    ExchangeRate,
    get_model_by_name,
    get_all_models
)

__version__ = "1.0.0"
__all__ = [
    # Config
    "settings",
    "DB_URL", 
    "REDIS_URL",
    "KOREAN_EXCHANGES",
    "GLOBAL_EXCHANGES",
    
    # Database
    "db_manager",
    "get_db",
    "get_batch_db", 
    "execute_sql",
    "test_db_connection",
    "get_db_info",
    "health_check",
    "cleanup_database",
    
    # Models
    "Base",
    "CoinMaster",
    "UpbitListing", 
    "BithumbListing",
    "ExchangeRegistry",
    "PriceSnapshot",
    "KimchiPremium",
    "ExchangeRate",
    "get_model_by_name",
    "get_all_models"
]