
import os
import asyncio
import json
from fastapi import FastAPI, Depends, HTTPException, WebSocket, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from .database import engine, Base, get_db
from .models import Exchange, Cryptocurrency
from .schemas import Exchange as ExchangeSchema, Cryptocurrency as CryptocurrencySchema
from . import services
from . import liquidation_services

app = FastAPI()

# WebSocket CORS 처리를 위한 커스텀 미들웨어
class WebSocketCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # WebSocket 요청은 CORS 체크를 우회
        if request.url.path.startswith("/ws"):
            return await call_next(request)
        
        # 일반 HTTP 요청은 정상적으로 처리
        response = await call_next(request)
        
        # Firefox 호환성을 위한 추가 헤더
        if request.headers.get("origin"):
            origin = request.headers.get("origin")
            if origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response

app.add_middleware(WebSocketCORSMiddleware)

# CORS 설정 - Firefox 호환성을 위해 확장
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:3000/",  # 끝 슬래시 포함
        "http://127.0.0.1:3000/"   # 끝 슬래시 포함
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# --- WebSocket Connection Manager ---
class ConnectionManager:
    """WebSocket 연결을 관리하는 클래스.
    
    다수의 클라이언트 WebSocket 연결을 관리하고,
    모든 연결된 클라이언트에게 실시간 데이터를 브로드캐스트합니다.
    """
    def __init__(self):
        """ConnectionManager 초기화.
        
        빈 연결 리스트를 생성합니다.
        """
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """새로운 WebSocket 연결을 수락하고 관리 리스트에 추가합니다.
        
        Args:
            websocket (WebSocket): 새로운 WebSocket 연결
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결을 관리 리스트에서 제거합니다.
        
        Args:
            websocket (WebSocket): 제거할 WebSocket 연결
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """모든 연결된 클라이언트에게 메시지를 브로드캐스트합니다.
        
        Args:
            message (str): 브로드캐스트할 JSON 형태의 메시지
        """
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections[:]:  # Create copy to avoid modification during iteration
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Failed to send message to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# --- Background Tasks for Optimized Data Fetching ---
async def exchange_rate_updater():
    """환율 업데이트 전용 태스크 - 독립적으로 실행되어 성능 향상."""
    exchange_rate = None
    print("Starting exchange_rate_updater task...")
    
    while True:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                new_rate = await services.async_get_naver_exchange_rate(session)
                if new_rate is not None:
                    global current_exchange_rate
                    current_exchange_rate = new_rate
                    print(f"Exchange rate updated: {current_exchange_rate}")
                else:
                    print("Failed to fetch Naver exchange rate.")
        except Exception as e:
            print(f"Error in exchange_rate_updater: {e}")
        
        await asyncio.sleep(10)  # 10초마다 환율 업데이트

# 전역 변수들
current_exchange_rate = None
current_usdt_krw_rate = None

async def price_updater():
    """백그라운드에서 실행되는 최적화된 가격 업데이터.
    
    병렬 처리를 통해 모든 거래소 API를 동시에 호출하여 성능을 크게 향상시킵니다.
    각 심볼에 대해 모든 거래소 데이터를 병렬로 가져오고,
    여러 심볼도 동시에 처리합니다.
    
    성능 개선 사항:
    - 순차 API 호출 → 병렬 API 호출
    - 환율 업데이트를 독립 태스크로 분리
    - aiohttp 세션 재사용으로 연결 오버헤드 감소
    """
    print("Starting optimized price_updater task...")
    
    # Fetch KRW markets once at startup
    try:
        krw_symbols = services.get_upbit_krw_markets()
        print(f"Target KRW markets: {len(krw_symbols)} symbols")
    except Exception as e:
        print(f"Error fetching Upbit KRW markets: {e}")
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
    print("Fetching supported symbols from global exchanges...")
    try:
        supported_symbols_cache["binance"] = services.get_binance_supported_symbols()
        print(f"Binance supported symbols: {len(supported_symbols_cache['binance'])}")
    except Exception as e:
        print(f"Error fetching Binance supported symbols: {e}")
    try:
        supported_symbols_cache["bybit"] = services.get_bybit_supported_symbols()
        print(f"Bybit supported symbols: {len(supported_symbols_cache['bybit'])}")
    except Exception as e:
        print(f"Error fetching Bybit supported symbols: {e}")
    print("Finished fetching supported symbols.")

    while True:
        try:
            print("Inside optimized price_updater loop...")
            
            # 환율이 준비될 때까지 대기
            if current_exchange_rate is None:
                print("Waiting for exchange rate to be available...")
                await asyncio.sleep(2)
                continue

            # Rate limiting 방지를 위해 순차적으로 데이터 가져오기
            print(f"Fetching data for {len(krw_symbols)} symbols sequentially...")
            start_time = asyncio.get_event_loop().time()
            
            # 각 심볼에 대해 순차적으로 처리 (Rate limiting 방지)
            filtered_coins_data = []
            for i, symbol in enumerate(krw_symbols):
                try:
                    print(f"Processing symbol {i+1}/{len(krw_symbols)}: {symbol}")
                    coin_data = await services.fetch_all_tickers_for_symbol(symbol, supported_symbols_cache, current_exchange_rate)
                    if coin_data:
                        filtered_coins_data.append(coin_data)
                    
                    # 심볼 간 지연 (Rate limiting 방지)
                    if i < len(krw_symbols) - 1:  # 마지막 심볼이 아닌 경우에만
                        await asyncio.sleep(0.1)  # 100ms 지연
                        
                except Exception as e:
                    print(f"Error fetching data for symbol {symbol}: {e}")
                    continue

            # USDT KRW rate를 한 번만 가져와서 모든 코인에 적용
            try:
                usdt_krw_ticker = services.get_upbit_ticker("USDT")
                usdt_price = usdt_krw_ticker.get("price") if usdt_krw_ticker else None
                usdt_krw_rate = round(usdt_price, 2) if usdt_price is not None else None
            except Exception as e:
                print(f"Error fetching USDT KRW rate: {e}")
                usdt_krw_rate = None
            
            # Apply USDT KRW rate to all coins
            for coin_data in filtered_coins_data:
                coin_data["usdt_krw_rate"] = usdt_krw_rate
            
            end_time = asyncio.get_event_loop().time()
            fetch_duration = end_time - start_time
            
            print(f"✅ Parallel fetch completed in {fetch_duration:.2f}s for {len(filtered_coins_data)} symbols")
            print(f"Broadcasting {len(filtered_coins_data)} coins data to {len(manager.active_connections)} clients")
            
            if manager.active_connections:
                await manager.broadcast(json.dumps(filtered_coins_data))
            else:
                print("No active WebSocket connections to broadcast to")
        
        except Exception as e:
            print(f"Error in price_updater: {e}")
            import traceback
            traceback.print_exc()
        
        await asyncio.sleep(5)  # Rate limiting 방지를 위해 5초로 증가

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행되는 이벤트 핸들러.
    
    성능 최적화된 백그라운드 태스크들을 시작합니다:
    - 환율 업데이터 (독립 태스크)
    - 가격 업데이터 (병렬 처리 최적화)
    - 청산 데이터 수집기
    """
    print("🚀 Starting optimized background tasks...")
    
    # 환율 업데이터 태스크 시작 (독립적으로 실행)
    print("📈 Starting exchange rate updater...")
    asyncio.create_task(exchange_rate_updater())
    
    # 최적화된 가격 업데이터 시작 (병렬 처리)
    print("💰 Starting optimized price updater...")
    asyncio.create_task(price_updater())
    
    # 청산 데이터 수집 시작
    print("⚡ Starting liquidation collection...")
    try:
        liquidation_task = asyncio.ensure_future(liquidation_services.start_liquidation_collection())
        print("Liquidation collection task created successfully")
        print(f"Liquidation task: {liquidation_task}")
    except Exception as e:
        print(f"Error starting liquidation collection: {e}")
        import traceback
        traceback.print_exc()
    
    # 청산 데이터용 WebSocket 관리자 설정
    print("🔗 Setting WebSocket manager for liquidations...")
    liquidation_services.set_websocket_manager(manager)
    
    print("✅ Startup complete - all optimized background tasks started")
    print("🎯 Performance improvements:")
    print("   - Sequential API calls → Parallel API calls")
    print("   - Single thread → Multiple independent tasks")  
    print("   - Exchange rate updates separated from price updates")
    print("   - aiohttp sessions for better connection management")

# --- WebSocket Endpoints ---
@app.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트 - 실시간 가격 스트리밍.
    
    클라이언트가 연결되면 실시간 가격 업데이트를 받을 수 있습니다.
    연결이 끊어지면 자동으로 정리됩니다.
    
    Args:
        websocket (WebSocket): 클라이언트 WebSocket 연결
    """
    print(f"Price WebSocket connection attempt")
    await manager.connect(websocket)
    print(f"Price WebSocket connected! Total connections: {len(manager.active_connections)}")
    try:
        # 즉시 연결 확인 메시지 전송
        await websocket.send_text('{"message": "Connected to price updates"}')
        
        # 연결 유지
        while True:
            await asyncio.sleep(1)
                
    except Exception as e:
        print(f"Price WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
        print(f"Price WebSocket client disconnected. Remaining: {len(manager.active_connections)}")

@app.websocket("/ws/liquidations")
async def liquidation_websocket_endpoint(websocket: WebSocket):
    """청산 데이터 WebSocket 엔드포인트.
    
    청산 데이터 실시간 업데이트를 WebSocket으로 전송합니다.
    
    Args:
        websocket (WebSocket): 클라이언트 WebSocket 연결
    """
    print(f"Liquidation WebSocket connection attempt")
    await manager.connect(websocket)
    print(f"Liquidation WebSocket connected! Total connections: {len(manager.active_connections)}")
    try:
        # 연결 시 최근 청산 데이터 전송
        recent_data = liquidation_services.get_aggregated_liquidation_data(limit=60)
        if recent_data:
            initial_message = json.dumps({
                'type': 'liquidation_initial',
                'data': recent_data
            })
            await websocket.send_text(initial_message)
        
        # 연결 유지
        while True:
            await asyncio.sleep(1)
                
    except Exception as e:
        print(f"Liquidation WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
        print(f"Liquidation WebSocket client disconnected. Remaining: {len(manager.active_connections)}")

# --- REST API Endpoints (can be kept for other purposes or removed) ---
@app.get("/")
def read_root():
    """루트 엔드포인트 - API 상태 확인.
    
    Returns:
        dict: API 실행 상태 메시지
    """
    return {"message": "KimchiScan API is running!"}

@app.get("/exchanges", response_model=List[ExchangeSchema])
def get_exchanges(db: Session = Depends(get_db)):
    """모든 거래소 정보를 조회합니다.
    
    Args:
        db (Session): 데이터베이스 세션
        
    Returns:
        List[ExchangeSchema]: 거래소 리스트
    """
    exchanges = db.query(Exchange).all()
    return exchanges

@app.get("/cryptocurrencies", response_model=List[CryptocurrencySchema])
def get_cryptocurrencies(db: Session = Depends(get_db)):
    """모든 암호화폐 정보를 조회합니다.
    
    Args:
        db (Session): 데이터베이스 세션
        
    Returns:
        List[CryptocurrencySchema]: 암호화폐 리스트
    """
    cryptocurrencies = db.query(Cryptocurrency).all()
    return cryptocurrencies

@app.get("/api/historical_prices/{symbol}")
async def get_historical_prices(symbol: str, interval: str = "1d", limit: int = 30):
    """특정 암호화폐의 과거 시세 데이터를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: BTC, ETH)
        interval (str): 시간 간격 (기본값: "1d")
        limit (int): 조회할 데이터 개수 (기본값: 30)
        
    Returns:
        list: 과거 시세 데이터 리스트
        
    Raises:
        HTTPException: 데이터 조회 실패 시 404 에러
    """
    """과거 시세 데이터를 조회합니다."""
    historical_data = services.get_binance_historical_prices(symbol.upper(), interval, limit)
    if not historical_data:
        raise HTTPException(status_code=404, detail=f"Could not fetch historical data for {symbol}")
    return historical_data

@app.get("/api/fear_greed_index")
async def get_fear_greed_index_data():
    """공포/탐욕 지수 데이터를 조회합니다.
    
    Returns:
        dict: 공포/탐욕 지수 데이터
        
    Raises:
        HTTPException: 데이터 조회 실패 시 404 에러
    """
    """공포/탐욕 지수 데이터를 조회합니다."""
    fng_data = services.get_fear_greed_index()
    if not fng_data:
        raise HTTPException(status_code=404, detail="Could not fetch Fear & Greed Index data")
    return fng_data

# The old polling endpoint is no longer the primary method, but can be kept for testing.
@app.get("/api/prices/{symbol}")
def get_prices(symbol: str):
    """특정 암호화폐의 현재 가격과 김치 프리미엄을 조회합니다.
    
    이 엔드포인트는 테스트 목적으로 유지되는 레거시 방식입니다.
    실시간 데이터는 WebSocket을 통해 제공됩니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: BTC, ETH)
        
    Returns:
        dict: 가격 정보와 김치 프리미엄
        
    Raises:
        HTTPException: 가격 조회 실패 시 404 또는 503 에러
    """
    upbit_price = services.get_upbit_price(symbol.upper())
    binance_price = services.get_binance_price(symbol.upper())

    if upbit_price is None or binance_price is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")

    # Now using the real-time USDT-KRW rate from Upbit REST API
    usdt_krw_rate = services.get_upbit_price("USDT")
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

@app.get("/api/liquidations")
def get_liquidations(exchange: Optional[str] = None, limit: int = 60):
    """청산 데이터를 조회합니다.
    
    Args:
        exchange (str, optional): 특정 거래소 데이터만 조회
        limit (int): 반환할 데이터 포인트 수 (기본값: 60분)
        
    Returns:
        list: 청산 데이터 리스트
    """
    return liquidation_services.get_liquidation_data(exchange, limit)

@app.get("/api/liquidations/aggregated")
def get_aggregated_liquidations(limit: int = 60):
    """집계된 청산 데이터를 조회합니다.
    
    모든 거래소의 청산 데이터를 시간별로 집계하여 반환합니다.
    
    Args:
        limit (int): 반환할 시간 포인트 수 (기본값: 60분)
        
    Returns:
        list: 시간별로 집계된 청산 데이터
    """
    return liquidation_services.get_aggregated_liquidation_data(limit)
