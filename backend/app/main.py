import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
from sqlalchemy.orm import Session

from . import services
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from liquidation_service.liquidation_stats_collector import start_liquidation_stats_collection, set_websocket_manager, get_aggregated_liquidation_data
from .database import get_db
from .models import Cryptocurrency

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 웹소켓 클라이언트 로그 레벨을 WARNING으로 설정하여 DEBUG 메시지 차단
logging.getLogger('websockets.client').setLevel(logging.WARNING)
logging.getLogger('websockets.server').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)

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

price_manager = ConnectionManager()
liquidation_manager = ConnectionManager()

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
        bithumb_tickers = services.shared_data["bithumb_tickers"]
        binance_tickers = services.shared_data["binance_tickers"]
        bybit_tickers = services.shared_data["bybit_tickers"]
        exchange_rate = services.shared_data["exchange_rate"]
        usdt_krw_rate = services.shared_data["usdt_krw_rate"]

        if not (upbit_tickers or bithumb_tickers) or not exchange_rate:
            logger.warning(f"Missing data - upbit: {len(upbit_tickers)}, bithumb: {len(bithumb_tickers)}, binance: {len(binance_tickers)}, exchange_rate: {exchange_rate}, usdt_krw: {usdt_krw_rate}")
            continue

        # 모든 거래소에서 사용 가능한 심볼들을 수집
        all_symbols = set()
        all_symbols.update(upbit_tickers.keys())
        all_symbols.update(bithumb_tickers.keys())
        all_symbols.update(binance_tickers.keys())
        all_symbols.update(bybit_tickers.keys())

        for symbol in all_symbols:
            upbit_ticker = upbit_tickers.get(symbol, {})
            bithumb_ticker = bithumb_tickers.get(symbol, {})
            binance_ticker = binance_tickers.get(symbol, {})
            bybit_ticker = bybit_tickers.get(symbol, {})

            upbit_price = upbit_ticker.get("price")
            bithumb_price = bithumb_ticker.get("price")
            binance_price = binance_ticker.get("price")

            # 김프 계산 (국내 거래소 기준으로)
            premium = None
            domestic_price = upbit_price or bithumb_price  # 업비트 우선, 없으면 빗썸
            if domestic_price and binance_price and exchange_rate:
                binance_price_krw = binance_price * exchange_rate
                if binance_price_krw > 0:
                    premium = ((domestic_price - binance_price_krw) / binance_price_krw) * 100

            # Binance volume (원본 USDT와 KRW 변환 모두 제공)
            binance_volume_usd = binance_ticker.get("volume")  # USDT 거래대금
            binance_volume_krw = None
            if binance_volume_usd is not None and usdt_krw_rate is not None:
                binance_volume_krw = binance_volume_usd * usdt_krw_rate

            # Bybit volume (원본 USDT와 KRW 변환 모두 제공)
            bybit_volume_usd = bybit_ticker.get("volume")  # USDT 거래대금
            bybit_volume_krw = None
            if bybit_volume_usd is not None and usdt_krw_rate is not None:
                bybit_volume_krw = bybit_volume_usd * usdt_krw_rate

            coin_data = {
                "symbol": symbol,
                "upbit_price": upbit_price,
                "upbit_volume": upbit_ticker.get("volume"),
                "upbit_change_percent": upbit_ticker.get("change_percent"),
                "bithumb_price": bithumb_price,
                "bithumb_volume": bithumb_ticker.get("volume"),
                "bithumb_change_percent": bithumb_ticker.get("change_percent"),
                "binance_price": binance_price,
                "binance_volume": binance_volume_krw, # KRW 변환된 거래량
                "binance_volume_usd": binance_volume_usd, # 원본 USDT 거래량
                "binance_change_percent": binance_ticker.get("change_percent"),
                "bybit_price": bybit_ticker.get("price"),
                "bybit_volume": bybit_volume_krw, # KRW 변환된 거래량
                "bybit_volume_usd": bybit_volume_usd, # 원본 USDT 거래량
                "bybit_change_percent": bybit_ticker.get("change_percent"),
                "premium": round(premium, 2) if premium is not None else None,
                "exchange_rate": exchange_rate,
                "usdt_krw_rate": usdt_krw_rate,
            }
            
            all_coins_data.append(coin_data)


        if all_coins_data:
            # 실시간 데이터 브로드캐스팅 (연결된 클라이언트 수 관계없이 1초마다 실행됨)
            await price_manager.broadcast(json.dumps(all_coins_data))
            
            # 연결된 클라이언트가 있을 때만 로그 출력
            if len(price_manager.active_connections) > 0:
                logger.info(f"📡 실시간 브로드캐스팅: {len(all_coins_data)}개 코인 → {len(price_manager.active_connections)}명 클라이언트")
        else:
            logger.warning(f"No coin data to broadcast - upbit: {len(upbit_tickers)}, binance: {len(binance_tickers)}, exchange_rate: {exchange_rate}")


# --- FastAPI Events ---
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 백그라운드 태스크를 실행합니다."""
    logger.info("백그라운드 데이터 수집 태스크를 시작합니다.")
    # 각 거래소 WebSocket 클라이언트 및 기타 데이터 수집기 실행
    asyncio.create_task(services.upbit_websocket_client())
    asyncio.create_task(services.bithumb_rest_client())
    asyncio.create_task(services.binance_websocket_client())
    asyncio.create_task(services.bybit_websocket_client())
    asyncio.create_task(services.fetch_exchange_rate_periodically())
    asyncio.create_task(services.fetch_usdt_krw_rate_periodically())

    # 가격 집계 및 브로드캐스트 태스크 시작
    logger.info("가격 집계 태스크를 시작합니다.")
    asyncio.create_task(price_aggregator())

    # 청산 통계 수집 시작
    logger.info("청산 통계 수집을 시작합니다.")
    set_websocket_manager(liquidation_manager) # liquidation_stats_collector 시스템 사용
    asyncio.create_task(start_liquidation_stats_collection())


# --- WebSocket Endpoint ---
@app.websocket("/ws/prices")
async def websocket_prices_endpoint(websocket: WebSocket):
    """실시간 가격 데이터를 위한 WebSocket 엔드포인트."""
    await price_manager.connect(websocket)
    logger.info(f"클라이언트 연결: {websocket.client}. 총 연결: {len(price_manager.active_connections)}")
    try:
        while True:
            # 클라이언트로부터 메시지를 받을 필요는 없지만, 연결 유지를 위해 필요
            await websocket.receive_text()
    except Exception:
        logger.info(f"클라이언트 연결 해제: {websocket.client}")
    finally:
        price_manager.disconnect(websocket)

@app.websocket("/ws/liquidations")
async def websocket_liquidations_endpoint(websocket: WebSocket):
    """실시간 청산 데이터를 위한 WebSocket 엔드포인트."""
    await liquidation_manager.connect(websocket)
    logger.info(f"청산 클라이언트 연결: {websocket.client}. 총 연결: {len(liquidation_manager.active_connections)}")
    try:
        # 초기 데이터 전송
        initial_data = get_aggregated_liquidation_data(limit=60)
        await websocket.send_text(json.dumps({"type": "liquidation_initial", "data": initial_data}))
        while True:
            await websocket.receive_text()
    except Exception:
        logger.info(f"청산 클라이언트 연결 해제: {websocket.client}")
    finally:
        liquidation_manager.disconnect(websocket)

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

@app.get("/api/liquidations/debug")
async def debug_liquidation_data():
    """메모리에 저장된 청산 데이터 디버깅."""
    from liquidation_service.liquidation_stats_collector import liquidation_stats_data
    
    debug_info = {}
    for exchange, data_deque in liquidation_stats_data.items():
        recent_buckets = list(data_deque)[-5:]  # 최근 5개
        debug_info[exchange] = {
            "total_buckets": len(data_deque),
            "recent_buckets": recent_buckets
        }
    
    return debug_info

@app.get("/api/coins/latest")
async def get_latest_coin_data():
    """
    현재 집계된 최신 코인 데이터를 반환합니다.
    (price_aggregator의 로직과 유사)
    """
    all_coins_data = []
    upbit_tickers = services.shared_data["upbit_tickers"]
    binance_tickers = services.shared_data["binance_tickers"]
    bybit_tickers = services.shared_data["bybit_tickers"]
    exchange_rate = services.shared_data["exchange_rate"]
    usdt_krw_rate = services.shared_data["usdt_krw_rate"]

    if not upbit_tickers or not exchange_rate:
        return {"count": 0, "data": []}

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

        binance_volume_krw = None
        if binance_ticker.get("volume") is not None and usdt_krw_rate is not None:
            usdt_volume = binance_ticker["volume"]
            binance_volume_krw = usdt_volume * usdt_krw_rate

        # Binance volume (원본 USDT와 KRW 변환 모두 제공)
        binance_volume_usd = binance_ticker.get("volume")  # USDT 거래대금
        
        # Bybit volume (원본 USDT와 KRW 변환 모두 제공)  
        bybit_volume_usd = bybit_ticker.get("volume")  # USDT 거래대금
        bybit_volume_krw = None
        if bybit_volume_usd is not None and usdt_krw_rate is not None:
            bybit_volume_krw = bybit_volume_usd * usdt_krw_rate

        coin_data = {
            "symbol": symbol,
            "upbit_price": upbit_price,
            "upbit_volume": upbit_ticker.get("volume"),
            "upbit_change_percent": upbit_ticker.get("change_percent"),
            "binance_price": binance_price,
            "binance_volume": binance_volume_krw, # KRW 변환된 거래량
            "binance_volume_usd": binance_volume_usd, # 원본 USDT 거래량
            "binance_change_percent": binance_ticker.get("change_percent"),
            "bybit_price": bybit_ticker.get("price"),
            "bybit_volume": bybit_volume_krw, # KRW 변환된 거래량
            "bybit_volume_usd": bybit_volume_usd, # 원본 USDT 거래량
            "bybit_change_percent": bybit_ticker.get("change_percent"),
            "premium": round(premium, 2) if premium is not None else None,
            "exchange_rate": exchange_rate,
            "usdt_krw_rate": usdt_krw_rate,
        }
        all_coins_data.append(coin_data)

    return {"count": len(all_coins_data), "data": all_coins_data}


@app.get("/api/coin-names")
async def get_coin_names(db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    모든 코인의 심볼 -> 한글명 매핑을 반환합니다.
    
    Returns:
        Dict[str, str]: 심볼 -> 한글명 매핑 딕셔너리
    """
    try:
        # 데이터베이스에서 모든 코인 정보 조회
        cryptocurrencies = db.query(Cryptocurrency).filter(
            Cryptocurrency.is_active == True
        ).all()
        
        # 심볼 -> 한글명 매핑 딕셔너리 생성
        coin_names = {}
        for crypto in cryptocurrencies:
            coin_names[crypto.symbol] = crypto.name_ko or crypto.symbol
        
        logger.info(f"코인 한글명 {len(coin_names)}개 반환")
        return coin_names
        
    except Exception as e:
        logger.error(f"코인 한글명 조회 오류: {e}")
        # 오류 시 빈 딕셔너리 반환
        return {}
