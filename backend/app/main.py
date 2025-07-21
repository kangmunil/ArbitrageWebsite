
import os
import asyncio
import json
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .database import engine, Base, get_db
from .models import Exchange, Cryptocurrency
from .schemas import Exchange as ExchangeSchema, Cryptocurrency as CryptocurrencySchema
from . import services

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
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- Background Task for Price Fetching ---
async def price_updater():
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

                # Fetch Binance ticker
                binance_symbol = f"{symbol}USDT"
                if binance_symbol in supported_symbols_cache["binance"]:
                    binance_ticker = services.get_binance_ticker(symbol)
                    coin_data["binance_price"] = binance_ticker["price"] if binance_ticker else None
                    coin_data["binance_volume"] = binance_ticker["volume"] if binance_ticker else None
                    coin_data["binance_change_percent"] = binance_ticker["change_percent"] if binance_ticker else None
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
                    else:
                        coin_data["premium"] = None # Avoid ZeroDivisionError
                else:
                    coin_data["premium"] = None # Or some other indicator

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
    """Start the background tasks when the app starts."""
    # No Upbit WebSocket connection needed now
    asyncio.create_task(price_updater())

# --- WebSocket Endpoint ---
@app.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We are broadcasting, so we don't need to handle incoming messages
            # This part keeps the connection alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client disconnected")

# --- REST API Endpoints (can be kept for other purposes or removed) ---
@app.get("/")
def read_root():
    return {"message": "KimchiScan API is running!"}

@app.get("/exchanges", response_model=List[ExchangeSchema])
def get_exchanges(db: Session = Depends(get_db)):
    exchanges = db.query(Exchange).all()
    return exchanges

@app.get("/cryptocurrencies", response_model=List[CryptocurrencySchema])
def get_cryptocurrencies(db: Session = Depends(get_db)):
    cryptocurrencies = db.query(Cryptocurrency).all()
    return cryptocurrencies

@app.get("/api/historical_prices/{symbol}")
async def get_historical_prices(symbol: str, interval: str = "1d", limit: int = 30):
    """과거 시세 데이터를 조회합니다."""
    historical_data = services.get_binance_historical_prices(symbol.upper(), interval, limit)
    if not historical_data:
        raise HTTPException(status_code=404, detail=f"Could not fetch historical data for {symbol}")
    return historical_data

@app.get("/api/fear_greed_index")
async def get_fear_greed_index_data():
    """공포/탐욕 지수 데이터를 조회합니다."""
    fng_data = services.get_fear_greed_index()
    if not fng_data:
        raise HTTPException(status_code=404, detail="Could not fetch Fear & Greed Index data")
    return fng_data

# The old polling endpoint is no longer the primary method, but can be kept for testing.
@app.get("/api/prices/{symbol}")
def get_prices(symbol: str):
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
