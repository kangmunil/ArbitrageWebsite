
import os
import asyncio
import json
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from .database import engine, Base, get_db
from .models import Exchange, Cryptocurrency
from .schemas import Exchange as ExchangeSchema, Cryptocurrency as CryptocurrencySchema
from . import services
from . import liquidation_services

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # 프론트엔드 주소 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """모든 연결된 클라이언트에게 메시지를 브로드캐스트합니다.
        
        Args:
            message (str): 브로드캐스트할 JSON 형태의 메시지
        """
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- Background Task for Price Fetching ---
async def price_updater():
    """백그라운드에서 실행되는 가격 업데이터.
    
    1초마다 다양한 거래소에서 암호화폐 가격을 가져와서
    김치 프리미엄을 계산하고 WebSocket을 통해 모든 클라이언트에게 브로드캐스트합니다.
    
    처리하는 데이터:
    - Upbit, Bithumb (한국 거래소)
    - Binance, Bybit (해외 거래소)
    - Naver Finance (USD/KRW 환율)
    """
    """Periodically fetches prices and broadcasts them to all connected clients."""
    print("Starting price_updater task...")
    exchange_rate = None
    update_interval = 10 # seconds, fetch exchange rate more frequently
    last_exchange_rate_update_time = 0
    
    # Initial fetch of KRW markets
    krw_symbols = ["BTC", "ETH", "XRP"] # 테스트를 위해 심볼 제한
    print(f"Fetched KRW markets: {krw_symbols}")

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
    except Exception as e:
        print(f"Error fetching Binance supported symbols: {e}")
    try:
        supported_symbols_cache["bybit"] = services.get_bybit_supported_symbols()
    except Exception as e:
        print(f"Error fetching Bybit supported symbols: {e}")
    try:
        supported_symbols_cache["okx"] = services.get_okx_supported_symbols()
    except Exception as e:
        print(f"Error fetching OKX supported symbols: {e}")
    try:
        supported_symbols_cache["gateio"] = services.get_gateio_supported_symbols()
    except Exception as e:
        print(f"Error fetching Gate.io supported symbols: {e}")
    try:
        supported_symbols_cache["mexc"] = services.get_mexc_supported_symbols()
    except Exception as e:
        print(f"Error fetching MEXC supported symbols: {e}")
    print("Finished fetching supported symbols.")

    while True:
        print("Inside price_updater loop...")
        current_time = asyncio.get_event_loop().time()

        # Fetch exchange rate periodically
        if current_time - last_exchange_rate_update_time >= update_interval:
            print("Fetching Naver exchange rate...")
            new_rate = services.get_naver_exchange_rate()
            if new_rate is not None:
                exchange_rate = new_rate
                last_exchange_rate_update_time = current_time
                print(f"Exchange rate updated: {exchange_rate}")
            else:
                print("Failed to fetch Naver exchange rate.")

        all_coins_data = []

        if exchange_rate is not None:
            for symbol in krw_symbols:
                coin_data = {"symbol": symbol}
                
                # Fetch Upbit ticker
                upbit_ticker = services.get_upbit_ticker(symbol)
                coin_data["upbit_price"] = upbit_ticker["price"] if upbit_ticker else None
                coin_data["upbit_volume"] = upbit_ticker["volume"] if upbit_ticker else None
                coin_data["upbit_change_percent"] = upbit_ticker["change_percent"] if upbit_ticker else None
                
                if upbit_ticker:
                    print(f"Successfully fetched {symbol} from Upbit: {upbit_ticker['price']} KRW")
                else:
                    print(f"Failed to fetch {symbol} from Upbit")

                # Fetch Binance ticker
                binance_symbol = f"{symbol}USDT"
                if binance_symbol in supported_symbols_cache["binance"]:
                    binance_ticker = services.get_binance_ticker(symbol)
                    coin_data["binance_price"] = binance_ticker["price"] if binance_ticker else None
                    coin_data["binance_volume"] = binance_ticker["volume"] if binance_ticker else None
                    coin_data["binance_change_percent"] = binance_ticker["change_percent"] if binance_ticker else None
                    
                    if binance_ticker:
                        print(f"Successfully fetched {symbol} from Binance: {binance_ticker['price']} USDT")
                    else:
                        print(f"Failed to fetch {symbol} from Binance")
                else:
                    print(f"Binance does not support {binance_symbol}. Skipping.")
                    coin_data["binance_price"] = None
                    coin_data["binance_volume"] = None
                    coin_data["binance_change_percent"] = None

                # Fetch Bithumb price (no 24hr data available via public API easily)
                bithumb_ticker = services.get_bithumb_ticker(symbol)
                coin_data["bithumb_price"] = bithumb_ticker["price"] if bithumb_ticker else None
                # Bithumb API는 24시간 거래량 및 변동률을 쉽게 제공하지 않으므로 None으로 설정
                coin_data["bithumb_volume"] = None
                coin_data["bithumb_change_percent"] = None

                # Fetch Bybit ticker
                bybit_symbol = f"{symbol.upper()}USDT"
                if bybit_symbol in supported_symbols_cache["bybit"]:
                    bybit_ticker = services.get_bybit_ticker(symbol)
                    coin_data["bybit_price"] = bybit_ticker["price"] if bybit_ticker else None
                    coin_data["bybit_volume"] = bybit_ticker["volume"] if bybit_ticker else None
                    coin_data["bybit_change_percent"] = bybit_ticker["change_percent"] if bybit_ticker else None
                else:
                    print(f"Bybit does not support {bybit_symbol}. Skipping.")
                    coin_data["bybit_price"] = None
                    coin_data["bybit_volume"] = None
                    coin_data["bybit_change_percent"] = None

                # Fetch OKX ticker
                # okx_symbol = f"{symbol.upper()}-USDT"
                # if okx_symbol in supported_symbols_cache["okx"]:
                #     okx_ticker = services.get_okx_ticker(symbol)
                #     coin_data["okx_price"] = okx_ticker["price"] if okx_ticker else None
                #     coin_data["okx_volume"] = okx_ticker["volume"] if okx_ticker else None
                #     coin_data["okx_change_percent"] = okx_ticker["change_percent"] if okx_ticker else None
                # else:
                #     print(f"OKX does not support {okx_symbol}. Skipping.")
                #     coin_data["okx_price"] = None
                #     coin_data["okx_volume"] = None
                #     coin_data["okx_change_percent"] = None

                # Fetch Gate.io ticker
                # gateio_symbol = f"{symbol.upper()}_USDT"
                # if gateio_symbol in supported_symbols_cache["gateio"]:
                #     gateio_ticker = services.get_gateio_ticker(symbol)
                #     coin_data["gateio_price"] = gateio_ticker["price"] if gateio_ticker else None
                #     coin_data["gateio_volume"] = gateio_ticker["volume"] if gateio_ticker else None
                #     coin_data["gateio_change_percent"] = gateio_ticker["change_percent"] if gateio_ticker else None
                # else:
                #     print(f"Gate.io does not support {gateio_symbol}. Skipping.")
                #     coin_data["gateio_price"] = None
                #     coin_data["gateio_volume"] = None
                #     coin_data["gateio_change_percent"] = None

                # Fetch MEXC ticker
                # mexc_symbol = f"{symbol.upper()}USDT"
                # if mexc_symbol in supported_symbols_cache["mexc"]:
                #     mexc_ticker = services.get_mexc_ticker(symbol)
                #     coin_data["mexc_price"] = mexc_ticker["price"] if mexc_ticker else None
                #     coin_data["mexc_volume"] = mexc_ticker["volume"] if mexc_ticker else None
                #     coin_data["mexc_change_percent"] = mexc_ticker["change_percent"] if mexc_ticker else None
                # else:
                #     print(f"MEXC does not support {mexc_symbol}. Skipping.")
                #     coin_data["mexc_price"] = None
                #     coin_data["mexc_volume"] = None
                #     coin_data["mexc_change_percent"] = None

                # Calculate Kimchi Premium if all necessary data is available and binance_price_krw is not zero
                upbit_price = coin_data["upbit_price"]
                binance_price = coin_data["binance_price"]

                if upbit_price is not None and binance_price is not None and exchange_rate is not None:
                    binance_price_krw = binance_price * exchange_rate
                    if binance_price_krw != 0:
                        premium = ((upbit_price - binance_price_krw) / binance_price_krw) * 100
                        coin_data["premium"] = round(premium, 2)
                        print(f"{symbol} Kimchi Premium calculated: {premium:.2f}% (Upbit: {upbit_price} KRW, Binance: {binance_price} USDT, Rate: {exchange_rate})")
                    else:
                        coin_data["premium"] = None # Avoid ZeroDivisionError
                        print(f"{symbol} Premium calculation failed: binance_price_krw is 0")
                else:
                    coin_data["premium"] = None # Or some other indicator
                    print(f"{symbol} Premium calculation failed: upbit_price={upbit_price}, binance_price={binance_price}, exchange_rate={exchange_rate}")

                usdt_krw_ticker = services.get_upbit_ticker("USDT")
                coin_data["usdt_krw_rate"] = usdt_krw_ticker["price"] if usdt_krw_ticker else None
                if coin_data["usdt_krw_rate"] is not None:
                    coin_data["usdt_krw_rate"] = round(coin_data["usdt_krw_rate"], 2)
                
                coin_data["exchange_rate"] = round(exchange_rate, 2)
                
                all_coins_data.append(coin_data)
            
            print(f"Broadcasting {len(all_coins_data)} coins data: {all_coins_data}")
            await manager.broadcast(json.dumps(all_coins_data))
        else:
            print("Waiting for exchange rate to be available...")
        
        await asyncio.sleep(1) # Update every 1 second

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행되는 이벤트 핸들러.
    
    백그라운드 가격 업데이터 태스크를 시작합니다.
    """
    """Start the background tasks when the app starts."""
    # No Upbit WebSocket connection needed now
    asyncio.create_task(price_updater())
    # 청산 데이터 수집 시작
    asyncio.create_task(liquidation_services.start_liquidation_collection())
    # 청산 데이터용 WebSocket 관리자 설정
    liquidation_services.set_websocket_manager(manager)

# --- WebSocket Endpoints ---
@app.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트 - 실시간 가격 스트리밍.
    
    클라이언트가 연결되면 실시간 가격 업데이트를 받을 수 있습니다.
    연결이 끊어지면 자동으로 정리됩니다.
    
    Args:
        websocket (WebSocket): 클라이언트 WebSocket 연결
    """
    await manager.connect(websocket)
    try:
        while True:
            # We are broadcasting, so we don't need to handle incoming messages
            # This part keeps the connection alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client disconnected")

@app.websocket("/ws/liquidations")
async def liquidation_websocket_endpoint(websocket: WebSocket):
    """청산 데이터 WebSocket 엔드포인트.
    
    청산 데이터 실시간 업데이트를 WebSocket으로 전송합니다.
    
    Args:
        websocket (WebSocket): 클라이언트 WebSocket 연결
    """
    await manager.connect(websocket)
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
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Liquidation WebSocket client disconnected")

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
