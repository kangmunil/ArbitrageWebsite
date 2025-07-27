"""
청산 통계 수집 서비스 메인 모듈

독립적인 청산 통계 수집 서비스를 위한 FastAPI 애플리케이션
"""

from fastapi import FastAPI
from typing import Dict, List
import asyncio
import logging
from liquidation_stats_collector import (
    start_liquidation_stats_collection, 
    get_aggregated_liquidation_data,
    liquidation_stats_data
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Liquidation Statistics Service", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """청산 통계 수집 서비스 시작"""
    logger.info("청산 통계 수집 서비스를 시작합니다...")
    asyncio.create_task(start_liquidation_stats_collection())


@app.get("/health")
def health_check():
    """서비스 상태 확인"""
    return {"status": "healthy", "service": "liquidation_stats"}


@app.get("/api/liquidations/aggregated")
async def get_aggregated_liquidations(limit: int = 60):
    """집계된 청산 데이터를 조회합니다."""
    return get_aggregated_liquidation_data(limit=limit)


@app.get("/api/liquidations/debug")
async def debug_liquidation_data():
    """메모리에 저장된 청산 데이터 디버깅."""
    debug_info = {}
    for exchange, data_deque in liquidation_stats_data.items():
        recent_buckets = list(data_deque)[-5:]  # 최근 5개
        debug_info[exchange] = {
            "total_buckets": len(data_deque),
            "recent_buckets": recent_buckets
        }
    
    return debug_info


@app.get("/api/exchanges/stats")
async def get_exchange_stats():
    """거래소별 최신 통계 요약"""
    result = {}
    for exchange, data_deque in liquidation_stats_data.items():
        if data_deque:
            latest = list(data_deque)[-1]
            result[exchange] = {
                "total_volume_24h": latest.get("long_volume", 0) + latest.get("short_volume", 0),
                "long_volume": latest.get("long_volume", 0),
                "short_volume": latest.get("short_volume", 0),
                "last_update": latest.get("timestamp")
            }
    
    return result