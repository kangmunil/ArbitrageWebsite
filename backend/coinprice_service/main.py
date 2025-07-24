"""
코인 가격 수집 전용 FastAPI 서비스.

이 서비스는 여러 거래소에서 실시간 코인 가격을 수집하고
김치 프리미엄을 계산하여 WebSocket을 통해 클라이언트에게 브로드캐스트합니다.
"""

import asyncio
import json
import os
from fastapi import FastAPI, Depends, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import engine, Base, get_db
from models import Exchange, Cryptocurrency
from schemas import Exchange as ExchangeSchema, Cryptocurrency as CryptocurrencySchema
import price_services

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CoinPrice Service", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 환경에서는 모든 오리진 허용
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- WebSocket Connection Manager ---
class ConnectionManager:
    """WebSocket 연결을 관리하는 클래스."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """새로운 WebSocket 연결을 수락하고 관리 리스트에 추가합니다."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결을 관리 리스트에서 제거합니다."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """모든 연결된 클라이언트에게 메시지를 브로드캐스트합니다."""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# 전역 변수들
current_exchange_rate = None

async def exchange_rate_updater():
    """환율 업데이트 전용 태스크 - 독립적으로 실행되어 성능 향상."""
    global current_exchange_rate
    logger.info("Starting exchange_rate_updater task...")
    
    while True:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                new_rate = await price_services.async_get_naver_exchange_rate(session)
                if new_rate is not None:
                    current_exchange_rate = new_rate
                    logger.info(f"Exchange rate updated: {current_exchange_rate}")
                else:
                    logger.info("Failed to fetch Naver exchange rate.")
        except Exception as e:
            logger.error(f"Error in exchange_rate_updater: {e}")
        
        await asyncio.sleep(10)  # 10초마다 환율 업데이트

async def price_updater():
    """백그라운드에서 실행되는 최적화된 가격 업데이터."""
    logger.info("Starting optimized price_updater task...")
    
    # Fetch KRW markets once at startup
    try:
        krw_symbols = price_services.get_upbit_krw_markets()
        logger.info(f"Target KRW markets: {len(krw_symbols)} symbols")
    except Exception as e:
        logger.error(f"Error fetching Upbit KRW markets: {e}")
        krw_symbols = ["BTC", "ETH", "XRP", "SOL"]  # Fallback to default

    # Cache for supported symbols on global exchanges
    supported_symbols_cache = {
        "binance": set(),
        "bybit": set(),
        "okx": set(),
        "gateio": set(),
        "mexc": set()
    }
    
    # Fetch supported symbols once at startup
    logger.info("Fetching supported symbols from global exchanges...")
    try:
        supported_symbols_cache["binance"] = price_services.get_binance_supported_symbols()
        logger.info(f"Binance supported symbols: {len(supported_symbols_cache['binance'])}")
    except Exception as e:
        logger.error(f"Error fetching Binance supported symbols: {e}")
    try:
        supported_symbols_cache["bybit"] = price_services.get_bybit_supported_symbols()
        logger.info(f"Bybit supported symbols: {len(supported_symbols_cache['bybit'])}")
    except Exception as e:
        logger.error(f"Error fetching Bybit supported symbols: {e}")
    logger.info("Finished fetching supported symbols.")

    while True:
        try:
            logger.info("Inside optimized price_updater loop...")
            
            # 환율이 준비될 때까지 대기
            if current_exchange_rate is None:
                logger.info("Waiting for exchange rate to be available...")
                await asyncio.sleep(2)
                continue

            # Rate limiting 방지를 위해 순차적으로 데이터 가져오기
            logger.info(f"Fetching data for {len(krw_symbols)} symbols sequentially...")
            start_time = asyncio.get_event_loop().time()
            
            # 각 심볼에 대해 순차적으로 처리 (Rate limiting 방지)
            filtered_coins_data = []
            for i, symbol in enumerate(krw_symbols):
                try:
                    logger.info(f"Processing symbol {i+1}/{len(krw_symbols)}: {symbol}")
                    coin_data = await price_services.fetch_all_tickers_for_symbol(symbol, supported_symbols_cache, current_exchange_rate)
                    if coin_data:
                        filtered_coins_data.append(coin_data)
                    
                    # 심볼 간 지연 (Rate limiting 방지)
                    if i < len(krw_symbols) - 1:  # 마지막 심볼이 아닌 경우에만
                        await asyncio.sleep(0.1)  # 100ms 지연
                        
                except Exception as e:
                    logger.error(f"Error fetching data for symbol {symbol}: {e}")
                    continue

            # USDT KRW rate를 한 번만 가져와서 모든 코인에 적용
            try:
                usdt_krw_ticker = price_services.get_upbit_ticker("USDT")
                usdt_price = usdt_krw_ticker.get("price") if usdt_krw_ticker else None
                usdt_krw_rate = round(usdt_price, 2) if usdt_price is not None else None
            except Exception as e:
                logger.error(f"Error fetching USDT KRW rate: {e}")
                usdt_krw_rate = None
            
            # Apply USDT KRW rate to all coins
            for coin_data in filtered_coins_data:
                coin_data["usdt_krw_rate"] = usdt_krw_rate
            
            end_time = asyncio.get_event_loop().time()
            fetch_duration = end_time - start_time
            
            logger.info(f"✅ Sequential fetch completed in {fetch_duration:.2f}s for {len(filtered_coins_data)} symbols")
            logger.info(f"Broadcasting {len(filtered_coins_data)} coins data to {len(manager.active_connections)} clients")
            
            if manager.active_connections:
                await manager.broadcast(json.dumps(filtered_coins_data))
            else:
                logger.info("No active WebSocket connections to broadcast to")
        
        except Exception as e:
            logger.error(f"Error in price_updater: {e}")
            import traceback
            traceback.print_exc()
        
        await asyncio.sleep(5)  # Rate limiting 방지를 위해 5초로 증가

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행되는 이벤트 핸들러."""
    logger.info("🚀 Starting CoinPrice Service...")
    
    # 환율 업데이터 태스크 시작 (독립적으로 실행)
    logger.info("📈 Starting exchange rate updater...")
    asyncio.create_task(exchange_rate_updater())
    
    # 최적화된 가격 업데이터 시작 (순차 처리)
    logger.info("💰 Starting optimized price updater...")
    asyncio.create_task(price_updater())
    
    logger.info("✅ CoinPrice Service startup complete")

# --- REST API Endpoints ---
@app.get("/")
def read_root():
    """루트 엔드포인트 - 코인 가격 서비스 상태 확인."""
    return {"message": "CoinPrice Service is running!", "service": "coinprice"}

@app.get("/exchanges", response_model=List[ExchangeSchema])
def get_exchanges(db: Session = Depends(get_db)):
    """모든 거래소 정보를 조회합니다."""
    exchanges = db.query(Exchange).all()
    return exchanges

@app.get("/cryptocurrencies", response_model=List[CryptocurrencySchema])
def get_cryptocurrencies(db: Session = Depends(get_db)):
    """모든 암호화폐 정보를 조회합니다."""
    cryptocurrencies = db.query(Cryptocurrency).all()
    return cryptocurrencies

@app.get("/api/historical_prices/{symbol}")
async def get_historical_prices(symbol: str, interval: str = "1d", limit: int = 30):
    """특정 암호화폐의 과거 시세 데이터를 조회합니다."""
    historical_data = price_services.get_binance_historical_prices(symbol.upper(), interval, limit)
    if not historical_data:
        raise HTTPException(status_code=404, detail=f"Could not fetch historical data for {symbol}")
    return historical_data

@app.get("/api/fear_greed_index")
async def get_fear_greed_index_data():
    """공포/탐욕 지수 데이터를 조회합니다."""
    fng_data = price_services.get_fear_greed_index()
    if not fng_data:
        raise HTTPException(status_code=404, detail="Could not fetch Fear & Greed Index data")
    return fng_data

@app.get("/api/prices/{symbol}")
def get_prices(symbol: str):
    """특정 암호화폐의 현재 가격과 김치 프리미엄을 조회합니다."""
    upbit_price = price_services.get_upbit_price(symbol.upper())
    binance_price = price_services.get_binance_price(symbol.upper())

    if upbit_price is None or binance_price is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")

    # Now using the real-time USDT-KRW rate from Upbit REST API
    usdt_krw_rate = price_services.get_upbit_price("USDT")
    if usdt_krw_rate is None:
        raise HTTPException(status_code=503, detail="USDT-KRW rate not available yet from Upbit REST API")

    binance_price_krw = binance_price * usdt_krw_rate
    premium = ((upbit_price - binance_price_krw) / binance_price_krw) * 100

    return {
        "symbol": symbol,
        "upbit_price": upbit_price,
        "binance_price": binance_price,
        "premium": round(premium, 2),
        "usdt_krw_rate": round(usdt_krw_rate, 2)
    }

@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트."""
    return {
        "status": "healthy",
        "service": "coinprice",
        "active_connections": len(manager.active_connections),
        "exchange_rate": current_exchange_rate
    }

# --- WebSocket Endpoints ---
@app.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트 - 실시간 가격 스트리밍."""
    logger.info("Price WebSocket connection attempt")
    await manager.connect(websocket)
    logger.info(f"Price WebSocket connected! Total connections: {len(manager.active_connections)}")
    try:
        # 즉시 연결 확인 메시지 전송
        await websocket.send_text('{"message": "Connected to price updates"}')
        
        # 연결 유지
        while True:
            await asyncio.sleep(1)
                
    except Exception as e:
        logger.error(f"Price WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
        logger.info(f"Price WebSocket client disconnected. Remaining: {len(manager.active_connections)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)