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


# === FastAPI Events ===
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    global health_checker
    
    logger.info("🚀 API Gateway starting up...")
    
    # Initialize health checker
    health_checker = create_api_gateway_health_checker(
        aggregator, 
        price_manager, 
        liquidation_manager
    )
    
    # Start price aggregation task
    logger.info("📊 Starting price aggregation task")
    asyncio.create_task(price_aggregator())
    
    logger.info("✅ API Gateway startup complete")


async def price_aggregator():
    """Simple price data aggregation and broadcast"""
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
    """Get coin symbol to Korean name mapping"""
    try:
        # Query all active coins
        coins = db.query(CoinMaster).all()
        
        # Create symbol -> Korean name mapping
        coin_names = {}
        for coin in coins:
            if hasattr(coin, 'name_ko') and coin.name_ko:
                coin_names[coin.symbol] = coin.name_ko
            else:
                coin_names[coin.symbol] = coin.symbol
        
        logger.info(f"Returned {len(coin_names)} coin names")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)