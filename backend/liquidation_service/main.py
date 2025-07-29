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
    liquidation_stats_data,
    get_liquidation_data
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Liquidation Statistics Service", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """FastAPI 애플리케이션 시작 시 청산 통계 수집 태스크를 시작합니다.

    이 함수는 애플리케이션이 시작될 때 비동기적으로 `start_liquidation_stats_collection` 함수를 실행하여
    청산 데이터를 지속적으로 수집하도록 합니다.
    """
    logger.info("청산 통계 수집 서비스를 시작합니다...")
    asyncio.create_task(start_liquidation_stats_collection())


@app.get("/health")
def health_check():
    """서비스의 상태를 확인하기 위한 헬스 체크 엔드포인트입니다.

    서비스가 정상적으로 실행 중인지 여부와 데이터 수집 상태를 반환합니다.

    Returns:
        dict: 서비스 상태를 나타내는 딕셔너리.
    """
    from datetime import datetime
    
    # 데이터 수집 상태 확인
    total_data_points = sum(len(data) for data in liquidation_stats_data.values())
    active_exchanges = [exchange for exchange, data in liquidation_stats_data.items() if len(data) > 0]
    
    return {
        "status": "healthy", 
        "service": "liquidation-service",
        "timestamp": datetime.now().isoformat(),
        "data_status": {
            "total_exchanges": len(liquidation_stats_data),
            "active_exchanges": active_exchanges,
            "total_data_points": total_data_points
        }
    }


@app.get("/api/liquidations/aggregated")
async def get_aggregated_liquidations(limit: int = 60):
    """집계된 청산 데이터를 조회하고 반환합니다.

    지정된 `limit`에 따라 최근 청산 데이터를 가져옵니다.
    이 데이터는 주로 메인 백엔드 서비스나 프론트엔드에서 사용됩니다.

    Args:
        limit (int, optional): 가져올 청산 데이터의 최대 개수. 기본값은 60입니다.

    Returns:
        dict: 집계된 청산 데이터를 포함하는 딕셔너리.
    """
    return get_aggregated_liquidation_data(limit=limit)


@app.get("/api/liquidations/debug")
async def debug_liquidation_data():
    """통합된 청산 데이터의 디버그 정보를 반환합니다.

    각 거래소별로 저장된 청산 데이터의 총 버킷 수와 최근 5개의 버킷 데이터를 제공합니다.
    이 엔드포인트는 주로 개발 및 디버깅 목적으로 사용됩니다.

    Returns:
        dict: 각 거래소별 청산 데이터의 디버그 정보를 포함하는 딕셔너리.
    """
    debug_info = {}
    for exchange, data_deque in liquidation_stats_data.items():
        recent_buckets = list(data_deque)[-5:]  # 최근 5개
        debug_info[exchange] = {
            "total_buckets": len(data_deque),
            "recent_buckets": recent_buckets
        }
    
    return debug_info

@app.get("/api/liquidations/raw")
async def get_raw_liquidations(exchange: str = None, limit: int = 60):
    """원시 청산 데이터를 반환합니다.
    
    Args:
        exchange (str, optional): 특정 거래소 필터링
        limit (int): 반환할 데이터 개수 제한
        
    Returns:
        List[Dict]: 원시 청산 데이터 목록
    """
    return get_liquidation_data(exchange=exchange, limit=limit)


@app.get("/api/exchanges/stats")
async def get_exchange_stats():
    """각 거래소별 최신 청산 통계 요약을 반환합니다.

    각 거래소의 가장 최근 청산 데이터 버킷에서 총 청산 볼륨, 롱/숏 볼륨,
    그리고 마지막 업데이트 시간을 추출하여 요약 정보를 제공합니다.

    Returns:
        dict: 각 거래소의 요약된 청산 통계를 담은 딕셔너리.
              각 거래소 키는 'total_volume_24h', 'long_volume', 'short_volume', 'last_update'를 포함합니다.
    """
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

@app.get("/api/liquidations/summary")
async def get_liquidation_summary():
    """청산 데이터 요약 정보를 반환합니다.
    
    Returns:
        dict: 거래소별 청산 요약 정보
    """
    summary = {
        "total_exchanges": len(liquidation_stats_data),
        "active_exchanges": [exchange for exchange, data in liquidation_stats_data.items() if len(data) > 0],
        "total_data_points": sum(len(data) for data in liquidation_stats_data.values()),
        "last_update": max([list(data)[-1].get('timestamp', 0) for data in liquidation_stats_data.values() if len(data) > 0], default=0)
    }
    return summary