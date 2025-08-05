"""
Simplified API Gateway for Arbitrage Monitor
Clean, minimal implementation focusing on core functionality
"""
import asyncio
import logging
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Core imports
from core import get_db, CoinMaster
from services.premium_service import MarketDataAggregator
from shared.websocket_manager import create_websocket_manager, WebSocketEndpoint
from shared.health_checker import create_api_gateway_health_checker
from shared.redis_manager import initialize_redis_for_service

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs
MARKET_SERVICE_URL = os.getenv("MARKET_SERVICE_URL", "http://market-service:8001")
LIQUIDATION_SERVICE_URL = os.getenv("LIQUIDATION_SERVICE_URL", "http://liquidation-service:8002")

# FastAPI app initialization
app = FastAPI(title="Arbitrage Monitor API Gateway", version="1.0.0")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Managers
price_manager = create_websocket_manager("api-gateway-prices")
liquidation_manager = create_websocket_manager("api-gateway-liquidations")

# Data aggregator instance
aggregator = MarketDataAggregator(MARKET_SERVICE_URL, LIQUIDATION_SERVICE_URL)

# Health checker instance
health_checker = None

# Redis manager for Pub/Sub
redis_manager = None


# === FastAPI Events ===
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    global health_checker, redis_manager
    
    logger.info("🚀 API Gateway starting up...")
    
    # Initialize Redis for Pub/Sub
    redis_manager = await initialize_redis_for_service("api-gateway")
    
    # Initialize health checker
    health_checker = create_api_gateway_health_checker(
        aggregator, 
        price_manager, 
        liquidation_manager
    )
    
    # Start Redis subscriber task (replaces old polling)
    if redis_manager:
        logger.info("📻 Starting Redis subscriber for real-time data")
        asyncio.create_task(redis_subscriber())
    else:
        # Fallback to polling if Redis is not available
        logger.warning("⚠️ Redis unavailable, falling back to polling")
        asyncio.create_task(price_aggregator())
    
    logger.info("✅ API Gateway startup complete")


async def redis_subscriber():
    """Redis Pub/Sub subscriber for real-time market data"""
    if not redis_manager:
        logger.error("Redis manager not available for subscription")
        return
    
    # Channel to subscribe to
    channel = "market-data-updates"
    
    # Market data cache for aggregation
    market_data_cache = {}
    last_broadcast = None
    
    async def handle_message(message):
        """Handle incoming Redis Pub/Sub messages"""
        nonlocal last_broadcast
        try:
            data = message['data']
            message_type = data.get('type')
            
            if message_type == 'price_update':
                # Update cache with new price data
                exchange = data.get('exchange')
                symbol = data.get('symbol')
                price_data = data.get('data')
                
                if not market_data_cache.get(symbol):
                    market_data_cache[symbol] = {}
                market_data_cache[symbol][exchange] = price_data
                
                # Broadcast aggregated data (throttled to prevent overwhelming)
                import time
                current_time = time.time()
                if last_broadcast is None or current_time - last_broadcast > 0.1:  # 100ms throttle
                    await broadcast_aggregated_data()
                    last_broadcast = current_time
                    
            elif message_type == 'exchange_rate_update':
                # Handle exchange rate updates
                logger.debug(f"📈 Exchange rate update: {data.get('rate_type')} = {data.get('rate')}")
                
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")
    
    async def broadcast_aggregated_data():
        """Aggregate cached data and broadcast to WebSocket clients"""
        try:
            # Get complete data from aggregator (includes premiums calculation)
            all_coins_data = await aggregator.get_combined_market_data()
            if all_coins_data:
                await price_manager.broadcast_json(all_coins_data, "price_update")
                logger.debug(f"📡 Broadcasted aggregated data for {len(all_coins_data)} coins")
        except Exception as e:
            logger.error(f"Error broadcasting aggregated data: {e}")
    
    # Start subscription with automatic retry
    await redis_manager.subscribe_with_handler(channel, handle_message)


async def price_aggregator():
    """Fallback: Simple price data aggregation and broadcast (polling)"""
    logger.info("📊 Starting fallback polling mode")
    while True:
        await asyncio.sleep(1.0)  # 1초마다 데이터 집계
        
        try:
            # Get data from Market Data Service
            all_coins_data = await aggregator.get_combined_market_data()
            if all_coins_data:
                # Broadcast to connected WebSocket clients
                await price_manager.broadcast_json(all_coins_data, "price_update")
                logger.debug(f"📡 Broadcasted data for {len(all_coins_data)} coins")
        except Exception as e:
            logger.error(f"Price aggregation error: {e}")


# === WebSocket Endpoints ===
@app.websocket("/ws/prices")
async def websocket_prices_endpoint(websocket: WebSocket):
    """Real-time price data WebSocket endpoint"""
    
    async def get_initial_data():
        """Initial data provider"""
        return await aggregator.get_combined_market_data()
    
    endpoint = WebSocketEndpoint(price_manager, get_initial_data)
    await endpoint.handle_connection(websocket, send_initial=True)


@app.websocket("/ws/liquidations")
async def websocket_liquidations_endpoint(websocket: WebSocket):
    """Real-time liquidation data WebSocket endpoint"""
    
    async def get_initial_data():
        """Initial liquidation data provider"""
        try:
            # Get liquidation data from service
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=3.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{LIQUIDATION_SERVICE_URL}/api/liquidations/aggregated?limit=20") as response:
                    if response.status == 200:
                        return await response.json()
            return []
        except Exception as e:
            logger.error(f"Liquidation data fetch error: {e}")
            return []
    
    endpoint = WebSocketEndpoint(liquidation_manager, get_initial_data)
    await endpoint.handle_connection(websocket, send_initial=True)


# === REST API Endpoints ===
@app.get("/")
def read_root():
    """API root endpoint"""
    return {"message": "Arbitrage Monitor API Gateway", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Service health check"""
    global health_checker
    
    if health_checker:
        return await health_checker.run_all_checks()
    else:
        from datetime import datetime
        return {
            "service": "api-gateway",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "basic": {
                    "status": "healthy",
                    "message": "API Gateway is running"
                }
            }
        }


@app.get("/api/coins/latest")
async def get_latest_coin_data():
    """Get latest coin data from Market Data Service"""
    try:
        combined_data = await aggregator.get_combined_market_data()
        return {"count": len(combined_data), "data": combined_data}
    except Exception as e:
        logger.error(f"Market Data Service connection error: {e}")
        return {"count": 0, "data": [], "error": str(e)}


@app.get("/api/coin-names")
async def get_coin_names(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Get coin symbol to Korean name mapping from multiple sources"""
    try:
        from sqlalchemy import text
        
        coin_names = {}
        
        # 1. CoinMaster 테이블에서 기본 한글명 가져오기
        coins = db.query(CoinMaster).all()
        for coin in coins:
            korean_name = getattr(coin, 'name_ko', None)
            if korean_name and korean_name.strip():
                coin_names[coin.symbol] = korean_name
            else:
                coin_names[coin.symbol] = coin.symbol
        
        # 2. 업비트 테이블에서 한글명 가져오기 (우선순위 높음)
        try:
            upbit_result = db.execute(text("""
                SELECT symbol, korean_name 
                FROM upbit_listings 
                WHERE is_active = true 
                AND korean_name IS NOT NULL 
                AND korean_name != ''
            """)).fetchall()
            
            for symbol, korean_name in upbit_result:
                if korean_name and korean_name.strip():
                    coin_names[symbol] = korean_name.strip()
            
            logger.info(f"Added {len(upbit_result)} Upbit Korean names")
        except Exception as e:
            logger.warning(f"Failed to fetch Upbit Korean names: {e}")
        
        # 3. 빗썸 테이블에서 한글명 가져오기 (우선순위 높음)
        try:
            bithumb_result = db.execute(text("""
                SELECT symbol, korean_name 
                FROM bithumb_listings 
                WHERE is_active = true 
                AND korean_name IS NOT NULL 
                AND korean_name != ''
            """)).fetchall()
            
            for symbol, korean_name in bithumb_result:
                if korean_name and korean_name.strip():
                    coin_names[symbol] = korean_name.strip()
            
            logger.info(f"Added {len(bithumb_result)} Bithumb Korean names")
        except Exception as e:
            logger.warning(f"Failed to fetch Bithumb Korean names: {e}")
        
        logger.info(f"Total coin names returned: {len(coin_names)}")
        return coin_names
        
    except Exception as e:
        logger.error(f"Coin names query error: {e}")
        return {}


@app.get("/api/coin-images")
async def get_coin_images(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Get coin symbol to image URL mapping"""
    try:
        # Query coins with image URLs
        coins = db.query(CoinMaster).filter(
            CoinMaster.image_url.isnot(None),
            CoinMaster.image_url != ''
        ).all()
        
        # Create symbol -> image URL mapping
        coin_images = {}
        for coin in coins:
            coin_images[coin.symbol] = coin.image_url
        
        logger.info(f"Returned {len(coin_images)} coin images")
        return coin_images
        
    except Exception as e:
        logger.error(f"Coin images query error: {e}")
        return {}


@app.get("/api/liquidations/aggregated")
async def get_aggregated_liquidations(limit: int = 60):
    """Get aggregated liquidation data by proxying to liquidation service"""
    try:
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{LIQUIDATION_SERVICE_URL}/api/liquidations/aggregated?limit={limit}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise HTTPException(status_code=response.status, detail="Liquidation service error")
    except Exception as e:
        logger.error(f"Liquidation service error: {e}")
        raise HTTPException(status_code=503, detail="Liquidation service unavailable")


@app.get("/api/fear_greed_index")
async def get_fear_greed_index_data():
    """Get Fear & Greed Index data from external API"""
    try:
        return await aggregator.get_fear_greed_index()
    except Exception as e:
        logger.error(f"Fear & Greed Index error: {e}")
        raise HTTPException(status_code=503, detail="Fear & Greed Index service unavailable")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)