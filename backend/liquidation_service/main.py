"""Market Sentiment & Liquidation Service

롱숏 비율과 청산 데이터를 실시간으로 수집하고 제공하는 FastAPI 서비스
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models.data_schemas import (
    APIResponse, HealthCheck, LongShortRatio, LiquidationSummary,
    MarketSentiment, Exchange
)
from collectors.long_short_collector import LongShortCollector
from collectors.liquidation_websocket import LiquidationWebSocketCollector
from analyzers.liquidation_estimator import LiquidationEstimator
from analyzers.sentiment_analyzer import SentimentAnalyzer
from utils.redis_cache import RedisCache

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SERVICE_VERSION = "2.0.0"

# 전역 객체들
redis_cache: Optional[RedisCache] = None
long_short_collector: Optional[LongShortCollector] = None
liquidation_collector: Optional[LiquidationWebSocketCollector] = None
liquidation_estimator: Optional[LiquidationEstimator] = None
sentiment_analyzer: Optional[SentimentAnalyzer] = None

# 백그라운드 작업들
background_tasks: List[asyncio.Task] = []
websocket_connections: List[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 생명주기 관리"""
    # 시작 시 초기화
    await startup_event()
    
    try:
        yield
    finally:
        # 종료 시 정리
        await shutdown_event()


# FastAPI 앱 초기화
app = FastAPI(
    title="Market Sentiment & Liquidation Service",
    description="롱숏 비율과 청산 데이터를 실시간으로 수집하고 분석하는 서비스",
    version=SERVICE_VERSION,
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def startup_event():
    """서비스 시작 이벤트"""
    global redis_cache, long_short_collector, liquidation_collector
    global liquidation_estimator, sentiment_analyzer, background_tasks
    
    logger.info("Starting Market Sentiment & Liquidation Service...")
    
    try:
        # Redis 연결
        redis_cache = RedisCache(host=REDIS_HOST, port=REDIS_PORT)
        await redis_cache.connect()
        logger.info("Connected to Redis")
        
        # 수집기들 초기화
        long_short_collector = LongShortCollector(redis_cache)
        liquidation_collector = LiquidationWebSocketCollector(redis_cache)
        
        # 분석기들 초기화 (나중에 구현)
        # liquidation_estimator = LiquidationEstimator(redis_cache)
        # sentiment_analyzer = SentimentAnalyzer(redis_cache)
        
        # 백그라운드 작업 시작
        # 1. 롱숏 비율 정기 수집 (5분마다)
        long_short_task = asyncio.create_task(periodic_long_short_collection())
        background_tasks.append(long_short_task)
        
        # 2. 청산 데이터 실시간 수집
        liquidation_task = asyncio.create_task(liquidation_collector.start_collection())
        background_tasks.append(liquidation_task)
        
        # 3. 웹소켓 브로드캐스트 (1초마다)
        websocket_task = asyncio.create_task(websocket_broadcast_loop())
        background_tasks.append(websocket_task)
        
        logger.info("All background tasks started successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


async def shutdown_event():
    """서비스 종료 이벤트"""
    global background_tasks, redis_cache, liquidation_collector
    
    logger.info("Shutting down Market Sentiment & Liquidation Service...")
    
    # 백그라운드 작업 중지
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    # 웹소켓 연결 정리
    for ws in websocket_connections[:]:
        try:
            await ws.close()
        except Exception:
            pass
    
    # 청산 수집기 중지
    if liquidation_collector:
        await liquidation_collector.stop_collection()
    
    # Redis 연결 해제
    if redis_cache:
        await redis_cache.disconnect()
    
    logger.info("Service shutdown completed")


async def periodic_long_short_collection():
    """정기적인 롱숏 비율 수집"""
    while True:
        try:
            if long_short_collector:
                logger.info("Starting periodic long/short ratio collection...")
                
                async with long_short_collector:
                    # 주요 심볼들의 롱숏 비율 수집
                    symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOGEUSDT"]
                    results = await long_short_collector.collect_all_long_short_ratios(symbols, "5m")
                    
                    logger.info(f"Collected long/short ratios for {len(results)} symbols")
                    
                    # 수집 통계를 Redis에 저장
                    stats = {
                        "last_collection": datetime.now().isoformat(),
                        "symbols_collected": len(results),
                        "total_ratios": sum(len(ratios) for ratios in results.values())
                    }
                    if redis_cache:
                        await redis_cache.set("long_short_collection_stats", json.dumps(stats), ttl=3600)
        
        except Exception as e:
            logger.error(f"Error in periodic long/short collection: {e}")
        
        # 5분 대기
        await asyncio.sleep(300)


async def websocket_broadcast_loop():
    """웹소켓으로 실시간 데이터 브로드캐스트"""
    while True:
        try:
            if websocket_connections and liquidation_collector:
                # 최신 청산 데이터 가져오기
                summaries = await liquidation_collector.get_all_24h_summaries()
                
                if summaries:
                    # 웹소켓으로 브로드캐스트
                    message = {
                        "type": "liquidation_update",
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            symbol: {
                                "total_usd": summary.total_liquidation_usd,
                                "long_usd": summary.long_liquidation_usd,
                                "short_usd": summary.short_liquidation_usd,
                                "long_percentage": summary.long_percentage,
                                "short_percentage": summary.short_percentage,
                                "total_events": summary.total_events
                            }
                            for symbol, summary in summaries.items()
                        }
                    }
                    
                    # 연결이 끊어진 웹소켓 정리
                    disconnected = []
                    sent_count = 0
                    for ws in websocket_connections:
                        try:
                            await ws.send_text(json.dumps(message, default=str))
                            sent_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to send WebSocket message: {e}")
                            disconnected.append(ws)
                    
                    # 끊어진 연결 제거
                    for ws in disconnected:
                        websocket_connections.remove(ws)
                    
                    if sent_count > 0:
                        logger.debug(f"Broadcasted liquidation data to {sent_count} WebSocket connections")
                else:
                    logger.debug("No liquidation summaries available for broadcast")
        
        except Exception as e:
            logger.error(f"Error in websocket broadcast: {e}")
        
        # 3초 대기 (더 자주 업데이트)
        await asyncio.sleep(3)


# === API 엔드포인트들 ===

@app.get("/", response_model=APIResponse)
async def root():
    """루트 엔드포인트"""
    return APIResponse(
        message="Market Sentiment & Liquidation Service is running",
        data={"version": SERVICE_VERSION, "timestamp": datetime.now()}
    )


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """서비스 상태 체크"""
    try:
        # Redis 상태 확인
        redis_status = "unknown"
        if redis_cache:
            health_info = await redis_cache.get_health_status()
            redis_status = health_info.get("status", "unknown")
        
        # 수집기 상태 확인
        collectors_status = {}
        
        if liquidation_collector:
            liq_stats = liquidation_collector.get_collection_stats()
            collectors_status["liquidation"] = "running" if liq_stats["is_running"] else "stopped"
        
        if long_short_collector:
            collectors_status["long_short"] = "available"
        
        # 마지막 업데이트 시간
        last_update = None
        if redis_cache:
            stats = await redis_cache.get_json("long_short_collection_stats")
            if isinstance(stats, dict) and "last_collection" in stats:
                last_update = datetime.fromisoformat(stats["last_collection"])
        
        return HealthCheck(
            status="healthy",
            collectors_status=collectors_status,
            redis_status=redis_status,
            websocket_connections=len(websocket_connections),
            last_update=last_update,
            total_symbols_tracked=15,
            active_websockets=len(websocket_connections)
        )
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthCheck(
            status="unhealthy",
            collectors_status={"error": str(e)},
            redis_status="error"
        )


@app.get("/api/long-short/{symbol}", response_model=APIResponse)
async def get_long_short_ratio(symbol: str):
    """특정 심볼의 최신 롱숏 비율 조회"""
    try:
        if not long_short_collector:
            raise HTTPException(status_code=503, detail="Long/Short collector not available")
        
        symbol = symbol.upper()
        
        # Redis 캐시에서 먼저 확인
        cache_key = f"long_short_latest:{symbol}"
        cached_data = await redis_cache.get_json(cache_key) if redis_cache else None
        
        if cached_data:
            return APIResponse(
                message=f"Long/Short ratio for {symbol} (cached)",
                data=cached_data
            )
        
        # 캐시에 없으면 실시간 수집
        async with long_short_collector:
            latest_ratios = await long_short_collector.get_latest_long_short_ratio(symbol)
            
            if not latest_ratios:
                raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol}")
            
            # 응답 데이터 준비
            response_data = {}
            for exchange, ratio in latest_ratios.items():
                response_data[exchange.value] = {
                    "long_ratio": ratio.long_ratio,
                    "short_ratio": ratio.short_ratio,
                    "long_short_ratio": ratio.long_short_ratio,
                    "timestamp": ratio.timestamp.isoformat(),
                    "account_based": ratio.account_based,
                    "top_traders_only": ratio.top_traders_only
                }
            
            return APIResponse(
                message=f"Long/Short ratio for {symbol}",
                data=response_data
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting long/short ratio for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/long-short/all", response_model=APIResponse)
async def get_all_long_short_ratios():
    """모든 심볼의 최신 롱숏 비율 조회"""
    try:
        if not redis_cache:
            raise HTTPException(status_code=503, detail="Cache not available")
        
        # 캐시된 모든 롱숏 비율 데이터 조회
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOGEUSDT"]
        all_ratios = {}
        
        for symbol in symbols:
            cache_key = f"long_short_latest:{symbol}"
            cached_data = await redis_cache.get_json(cache_key)
            if cached_data:
                all_ratios[symbol] = cached_data
        
        return APIResponse(
            message="All long/short ratios",
            data=all_ratios
        )
    
    except Exception as e:
        logger.error(f"Error getting all long/short ratios: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/liquidations/24h", response_model=APIResponse)
async def get_24h_liquidations():
    """24시간 청산 데이터 조회"""
    try:
        if not liquidation_collector:
            raise HTTPException(status_code=503, detail="Liquidation collector not available")
        
        summaries = await liquidation_collector.get_all_24h_summaries()
        
        if not summaries:
            return APIResponse(
                message="No liquidation data available",
                data={}
            )
        
        # 응답 데이터 준비
        response_data = {}
        for symbol, summary in summaries.items():
            response_data[symbol] = {
                "total_liquidation_usd": summary.total_liquidation_usd,
                "long_liquidation_usd": summary.long_liquidation_usd,
                "short_liquidation_usd": summary.short_liquidation_usd,
                "long_percentage": summary.long_percentage,
                "short_percentage": summary.short_percentage,
                "total_events": summary.total_events,
                "long_events": summary.long_events,
                "short_events": summary.short_events,
                "timestamp": summary.timestamp.isoformat()
            }
        
        return APIResponse(
            message="24h liquidation data",
            data=response_data
        )
    
    except Exception as e:
        logger.error(f"Error getting 24h liquidations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/liquidations/aggregated", response_model=APIResponse)
async def get_aggregated_liquidations(limit: int = 20):
    """집계된 청산 데이터 조회 (API Gateway 호환)"""
    try:
        if not liquidation_collector:
            raise HTTPException(status_code=503, detail="Liquidation collector not available")
        
        summaries = await liquidation_collector.get_all_24h_summaries()
        
        if not summaries:
            return APIResponse(
                message="No aggregated liquidation data available",
                data=[]
            )
        
        # 응답 데이터 준비 (API Gateway 호환 형식)
        response_data = []
        for symbol, summary in list(summaries.items())[:limit]:
            response_data.append({
                "symbol": symbol,
                "total_usd": summary.total_liquidation_usd,
                "long_usd": summary.long_liquidation_usd,
                "short_usd": summary.short_liquidation_usd,
                "long_percentage": summary.long_percentage,
                "short_percentage": summary.short_percentage,
                "total_events": summary.total_events,
                "long_events": summary.long_events,
                "short_events": summary.short_events,
                "timestamp": summary.timestamp.isoformat()
            })
        
        return APIResponse(
            message="Aggregated liquidation data",
            data=response_data
        )
    
    except Exception as e:
        logger.error(f"Error getting aggregated liquidations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/liquidations/{symbol}/recent", response_model=APIResponse)
async def get_recent_liquidations(symbol: str, limit: int = 50):
    """특정 심볼의 최근 청산 이벤트 조회"""
    try:
        if not liquidation_collector:
            raise HTTPException(status_code=503, detail="Liquidation collector not available")
        
        symbol = symbol.upper()
        events = await liquidation_collector.get_recent_liquidation_events(symbol, limit)
        
        if not events:
            return APIResponse(
                message=f"No recent liquidation events for {symbol}",
                data=[]
            )
        
        # 응답 데이터 준비
        response_data = []
        for event in events:
            response_data.append({
                "timestamp": event.timestamp.isoformat(),
                "side": event.side.value,
                "price": event.price,
                "quantity": event.quantity,
                "value_usd": event.value_usd,
                "order_id": event.order_id
            })
        
        return APIResponse(
            message=f"Recent liquidation events for {symbol}",
            data=response_data
        )
    
    except Exception as e:
        logger.error(f"Error getting recent liquidations for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/stats", response_model=APIResponse)
async def get_service_stats():
    """서비스 통계 조회"""
    try:
        stats = {}
        
        # 청산 수집기 통계
        if liquidation_collector:
            liq_stats = liquidation_collector.get_collection_stats()
            stats["liquidation_collector"] = liq_stats
        
        # 롱숏 비율 수집 통계
        if redis_cache:
            long_short_stats = await redis_cache.get_json("long_short_collection_stats")
            if long_short_stats:
                stats["long_short_collector"] = long_short_stats
        
        # 웹소켓 통계
        stats["websockets"] = {
            "active_connections": len(websocket_connections)
        }
        
        # Redis 통계
        if redis_cache:
            redis_health = await redis_cache.get_health_status()
            stats["redis"] = redis_health
        
        return APIResponse(
            message="Service statistics",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"Error getting service stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.websocket("/ws/liquidations")
async def websocket_liquidation_stream(websocket: WebSocket):
    """실시간 청산 데이터 웹소켓 스트림"""
    await websocket.accept()
    websocket_connections.append(websocket)
    logger.info(f"WebSocket connected. Total connections: {len(websocket_connections)}")
    
    try:
        # 연결 직후 즉시 최신 데이터 전송
        if liquidation_collector:
            summaries = await liquidation_collector.get_all_24h_summaries()
            if summaries:
                initial_message = {
                    "type": "liquidation_update",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        symbol: {
                            "total_usd": summary.total_liquidation_usd,
                            "long_usd": summary.long_liquidation_usd,
                            "short_usd": summary.short_liquidation_usd,
                            "long_percentage": summary.long_percentage,
                            "short_percentage": summary.short_percentage,
                            "total_events": summary.total_events
                        }
                        for symbol, summary in summaries.items()
                    }
                }
                await websocket.send_text(json.dumps(initial_message, default=str))
                logger.info(f"Sent initial liquidation data to WebSocket: {len(summaries)} symbols")
        
        while True:
            # 클라이언트로부터 메시지를 기다림 (연결 유지용)
            try:
                message = await websocket.receive_text()
                logger.debug(f"Received WebSocket message: {message}")
            except Exception:
                break
    
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(websocket_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level="info"
    )