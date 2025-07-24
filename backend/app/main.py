import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from . import services
from . import liquidation_services # 청산 서비스도 함께 실행
from .liquidation_services import get_aggregated_liquidation_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# --- CORS 설정 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected_clients.append(connection)
        for client in disconnected_clients:
            self.disconnect(client)

manager = ConnectionManager()

# --- Data Aggregator and Broadcaster ---
async def price_aggregator():
    """
    shared_data를 주기적으로 읽어 최종 데이터를 조립하고,
    모든 WebSocket 클라이언트에게 브로드캐스트합니다.
    """
    while True:
        await asyncio.sleep(1) # 1초마다 데이터 집계 및 전송

        all_coins_data = []
        upbit_tickers = services.shared_data["upbit_tickers"]
        binance_tickers = services.shared_data["binance_tickers"]
        bybit_tickers = services.shared_data["bybit_tickers"]
        exchange_rate = services.shared_data["exchange_rate"]
        usdt_krw_rate = services.shared_data["usdt_krw_rate"]

        if not upbit_tickers or not exchange_rate:
            continue

        for symbol, upbit_ticker in upbit_tickers.items():
            binance_ticker = binance_tickers.get(symbol, {})
            bybit_ticker = bybit_tickers.get(symbol, {})

            upbit_price = upbit_ticker.get("price")
            binance_price = binance_ticker.get("price")

            premium = None
            if upbit_price and binance_price and exchange_rate:
                binance_price_krw = binance_price * exchange_rate
                if binance_price_krw > 0:
                    premium = ((upbit_price - binance_price_krw) / binance_price_krw) * 100

            # Binance volume (convert to KRW equivalent)
            binance_volume_krw = None
            if binance_ticker.get("volume") is not None and usdt_krw_rate is not None:
                # binance volume은 이제 USDT 거래대금이므로 KRW 환율만 곱함
                usdt_volume = binance_ticker["volume"]
                binance_volume_krw = usdt_volume * usdt_krw_rate
                

            # Bybit volume (convert to KRW equivalent)
            bybit_volume_krw = None
            if bybit_ticker.get("volume") is not None and bybit_ticker.get("price") is not None and usdt_krw_rate is not None:
                bybit_volume_krw = bybit_ticker["volume"] * bybit_ticker["price"] * usdt_krw_rate

            coin_data = {
                "symbol": symbol,
                "upbit_price": upbit_price,
                "upbit_volume": upbit_ticker.get("volume"),
                "upbit_change_percent": upbit_ticker.get("change_percent"),
                "binance_price": binance_price,
                "binance_volume": binance_volume_krw, # KRW 변환된 거래량 사용
                "binance_change_percent": binance_ticker.get("change_percent"),
                "bybit_price": bybit_ticker.get("price"),
                "bybit_volume": bybit_volume_krw, # KRW 변환된 거래량 사용
                "bybit_change_percent": bybit_ticker.get("change_percent"),
                "premium": round(premium, 2) if premium is not None else None,
                "exchange_rate": exchange_rate,
                "usdt_krw_rate": usdt_krw_rate,
            }
            
            all_coins_data.append(coin_data)


        if all_coins_data:
            await manager.broadcast(json.dumps(all_coins_data))


# --- FastAPI Events ---
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 백그라운드 태스크를 실행합니다."""
    logger.info("백그라운드 데이터 수집 태스크를 시작합니다.")
    # 각 거래소 WebSocket 클라이언트 및 기타 데이터 수집기 실행
    asyncio.create_task(services.upbit_websocket_client())
    asyncio.create_task(services.binance_websocket_client())
    asyncio.create_task(services.bybit_websocket_client())
    asyncio.create_task(services.fetch_exchange_rate_periodically())
    asyncio.create_task(services.fetch_usdt_krw_rate_periodically())

    # 가격 집계 및 브로드캐스트 태스크 시작
    logger.info("가격 집계 태스크를 시작합니다.")
    asyncio.create_task(price_aggregator())

    # 청산 데이터 수집 시작
    logger.info("청산 데이터 수집을 시작합니다.")
    liquidation_services.set_websocket_manager(manager) # 청산 서비스에 동일한 매니저 사용
    asyncio.create_task(liquidation_services.start_liquidation_collection())


# --- WebSocket Endpoint ---
@app.websocket("/ws/prices")
async def websocket_prices_endpoint(websocket: WebSocket):
    """실시간 가격 데이터를 위한 WebSocket 엔드포인트."""
    await manager.connect(websocket)
    logger.info(f"클라이언트 연결: {websocket.client}. 총 연결: {len(manager.active_connections)}")
    try:
        while True:
            # 클라이언트로부터 메시지를 받을 필요는 없지만, 연결 유지를 위해 필요
            await websocket.receive_text()
    except Exception:
        logger.info(f"클라이언트 연결 해제: {websocket.client}")
    finally:
        manager.disconnect(websocket)

@app.websocket("/ws/liquidations")
async def websocket_liquidations_endpoint(websocket: WebSocket):
    """실시간 청산 데이터를 위한 WebSocket 엔드포인트."""
    # 가격 매니저를 청산 데이터에서도 공유하여 사용
    await manager.connect(websocket)
    logger.info(f"청산 클라이언트 연결: {websocket.client}. 총 연결: {len(manager.active_connections)}")
    try:
        # 초기 데이터 전송
        initial_data = liquidation_services.get_aggregated_liquidation_data(limit=60)
        await websocket.send_text(json.dumps({"type": "liquidation_initial", "data": initial_data}))
        while True:
            await websocket.receive_text()
    except Exception:
        logger.info(f"청산 클라이언트 연결 해제: {websocket.client}")
    finally:
        manager.disconnect(websocket)

# --- REST API Endpoints (보조용) ---
@app.get("/")
def read_root():
    return {"message": "KimchiScan API is running!"}

@app.get("/api/fear_greed_index")
async def get_fear_greed_index_data():
    """공포/탐욕 지수 데이터를 조회합니다."""
    return services.get_fear_greed_index()

@app.get("/api/liquidations/aggregated")
async def get_aggregated_liquidations(limit: int = 60):
    """집계된 청산 데이터를 조회합니다."""
    return get_aggregated_liquidation_data(limit=limit)
