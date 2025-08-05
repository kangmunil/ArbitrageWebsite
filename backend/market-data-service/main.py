"""
Market Data Service - 시세 데이터 전담 서비스

거래소별 가격, 거래량, 변화율 데이터와 환율 정보를 수집하고 제공합니다.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from market_collector import MarketDataCollector
from shared_data import SharedMarketData
from shared.websocket_manager import create_websocket_manager, WebSocketEndpoint
from shared.health_checker import create_market_service_health_checker
from shared.redis_manager import initialize_redis_for_service

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Market-Data-Service:%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="Market Data Service", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 인스턴스
shared_data = SharedMarketData()
market_collector = MarketDataCollector()
market_collector.shared_data = shared_data  # 같은 인스턴스 공유

# Redis 매니저
redis_manager = None

# WebSocket 매니저
ws_manager = create_websocket_manager("market-data-service")

# 헬스체커
health_checker = None

@app.on_event("startup")
async def startup_event():
    """
    서비스 시작 시 초기화 작업을 수행합니다.

    Redis 매니저, 헬스체커를 초기화하고 시장 데이터 수집을 시작합니다.
    """
    global redis_manager, health_checker
    
    logger.info("🚀 Market Data Service 시작")
    
    # Redis 매니저 초기화
    redis_manager = await initialize_redis_for_service("market-data-service")
    
    # 헬스체커 초기화
    health_checker = create_market_service_health_checker(
        redis_manager,
        market_collector,
        ws_manager
    )
    
    # 시장 데이터 수집 시작
    shared_data.set_redis_manager(redis_manager)
    market_collector.set_redis_client(redis_manager.client if redis_manager else None)
    asyncio.create_task(market_collector.start_collection())
    
    logger.info("📊 시장 데이터 수집 시작")

@app.on_event("shutdown")
async def shutdown_event():
    """
    서비스 종료 시 정리 작업을 수행합니다.

    데이터 수집을 중지하고 Redis 연결을 종료합니다.
    """
    logger.info("🛑 Market Data Service 종료")
    await market_collector.stop_collection()
    if redis_manager:
        await redis_manager.disconnect()

# === Health Check ===
@app.get("/health")
async def health_check():
    """
    서비스의 상태를 확인합니다.

    Returns:
        dict: 서비스의 헬스 체크 결과.
    """
    global health_checker
    
    if health_checker:
        return await health_checker.run_all_checks()
    else:
        # 백업 헬스체크
        return {
            "service": "market-data-service",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "basic": {
                    "status": "healthy",
                    "message": "Market Data Service is running"
                }
            }
        }

# === Market Data APIs ===
@app.get("/api/market/prices")
async def get_market_prices():
    """
    모든 코인의 가격 데이터를 반환합니다.

    Returns:
        dict: 가격 데이터 목록.
    """
    try:
        prices_data = await shared_data.get_all_prices()
        return {
            "success": True,
            "count": len(prices_data),
            "data": prices_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"가격 데이터 조회 오류: {e}")
        return {"success": False, "error": str(e), "data": []}

@app.get("/api/market/volumes")
async def get_market_volumes():
    """
    모든 코인의 거래량 데이터를 반환합니다.

    Returns:
        dict: 거래량 데이터 목록.
    """
    try:
        volumes_data = await shared_data.get_all_volumes()
        return {
            "success": True,
            "count": len(volumes_data),
            "data": volumes_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"거래량 데이터 조회 오류: {e}")
        return {"success": False, "error": str(e), "data": []}

@app.get("/api/market/premiums")
async def get_market_premiums():
    """
    김치 프리미엄 데이터를 반환합니다.

    Returns:
        dict: 프리미엄 데이터 목록.
    """
    try:
        premiums_data = await shared_data.get_all_premiums()
        return {
            "success": True,
            "count": len(premiums_data),
            "data": premiums_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"프리미엄 데이터 조회 오류: {e}")
        return {"success": False, "error": str(e), "data": []}

@app.get("/api/market/exchange-rate")
async def get_exchange_rate():
    """
    환율 정보를 반환합니다.

    Returns:
        dict: 환율 데이터.
    """
    try:
        exchange_data = await shared_data.get_exchange_rates()
        return {
            "success": True,
            "data": exchange_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"환율 데이터 조회 오류: {e}")
        return {"success": False, "error": str(e), "data": {}}

@app.get("/api/market/combined")
async def get_combined_market_data():
    """
    통합된 시장 데이터를 반환합니다. (API Gateway에서 사용)

    Returns:
        dict: 통합된 시장 데이터 목록.
    """
    try:
        combined_data = await shared_data.get_combined_data()
        return {
            "success": True,
            "count": len(combined_data),
            "data": combined_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"통합 데이터 조회 오류: {e}")
        return {"success": False, "error": str(e), "data": []}

# === WebSocket Endpoint ===
@app.websocket("/ws/market")
async def websocket_market_endpoint(websocket: WebSocket):
    """
    실시간 시장 데이터를 위한 WebSocket 엔드포인트입니다.

    Args:
        websocket (WebSocket): 클라이언트 WebSocket 연결.
    """
    
    async def get_initial_data():
        """초기 시장 데이터 제공자"""
        return await shared_data.get_combined_data()
    
    endpoint = WebSocketEndpoint(ws_manager, get_initial_data)
    await endpoint.handle_connection(websocket, send_initial=True, streaming_interval=0.2)

# === Debug Endpoints ===
@app.get("/api/debug/collectors")
async def debug_collectors():
    """
    데이터 수집기의 상태를 디버깅합니다.

    Returns:
        dict: 수집기 및 공유 데이터의 통계 정보.
    """
    return {
        "collectors": market_collector.get_all_stats(),
        "shared_data_stats": await shared_data.get_stats(),
        "redis_status": redis_manager is not None and redis_manager.client is not None
    }

@app.get("/api/debug/raw-data/{exchange}")
async def debug_raw_data(exchange: str):
    """
    특정 거래소의 원시 데이터를 확인합니다.

    Args:
        exchange (str): 거래소 이름.

    Returns:
        dict: 해당 거래소의 원시 데이터.
    """
    try:
        raw_data = await shared_data.get_exchange_raw_data(exchange)
        return {
            "exchange": exchange,
            "data": raw_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "exchange": exchange}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
