from typing import Dict, List, Optional
import requests
import aiohttp
import asyncio
import json
import logging
import uuid
import websockets
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# --- Shared Data Store ---
# 이 변수는 모든 실시간 데이터를 중앙에서 관리합니다.
# 각 WebSocket 클라이언트는 이 변수를 업데이트하고,
# price_aggregator는 이 변수를 읽어 최종 데이터를 만듭니다.
shared_data = {
    "upbit_tickers": {},  # Upbit 실시간 시세
    "binance_tickers": {}, # Binance 실시간 시세
    "bybit_tickers": {},   # Bybit 실시간 시세
    "exchange_rate": None, # USD/KRW 환율
    "usdt_krw_rate": None, # USDT/KRW 환율
}

# --- WebSocket Clients ---

async def upbit_websocket_client():
    """
    Upbit WebSocket에 연결하여 모든 KRW 마켓의 실시간 시세를 수신하고
    shared_data를 업데이트합니다.
    """
    uri = "wss://api.upbit.com/websocket/v1"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("Upbit WebSocket에 연결되었습니다.")
                
                # 구독할 KRW 마켓 목록 가져오기
                krw_markets = get_upbit_krw_markets()
                if not krw_markets:
                    logger.error("Upbit KRW 마켓 목록을 가져올 수 없습니다. 5초 후 재시도합니다.")
                    await asyncio.sleep(5)
                    continue

                # 구독 메시지 생성
                subscribe_message = [
                    {"ticket": str(uuid.uuid4())},
                    {"type": "ticker", "codes": [f"KRW-{symbol}" for symbol in krw_markets]}
                ]
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"Upbit WebSocket에 {len(krw_markets)}개 마켓을 구독했습니다.")

                # 데이터 수신 및 처리
                async for message in websocket:
                    data = json.loads(message)
                    symbol = data['code'].replace('KRW-', '')
                    
                    
                    shared_data["upbit_tickers"][symbol] = {
                        "price": data['trade_price'],
                        "volume": data['acc_trade_price_24h'],  # 거래대금 (KRW) 사용
                        "change_percent": data['signed_change_rate'] * 100
                    }
                    # logger.debug(f"Upbit 수신: {symbol} = {data['trade_price']}")

        except Exception as e:
            logger.error(f"Upbit WebSocket 오류: {e}. 5초 후 재연결합니다.")
            await asyncio.sleep(5)

async def binance_websocket_client():
    """
    Binance WebSocket에 연결하여 모든 USDT 페어의 24시간 티커 정보를 수신하고
    shared_data를 업데이트합니다.
    """
    uri = "wss://stream.binance.com:9443/ws/!ticker@arr"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("Binance WebSocket에 연결되었습니다.")
                async for message in websocket:
                    data = json.loads(message)
                    for ticker in data:
                        if ticker['s'].endswith('USDT'):
                            symbol = ticker['s'].replace('USDT', '')
                            shared_data["binance_tickers"][symbol] = {
                                "price": float(ticker['c']),
                                "volume": float(ticker['q']),  # q = quote asset volume (USDT 거래대금)
                                "change_percent": float(ticker['P'])
                            }
                            # logger.debug(f"Binance 수신: {symbol} = {ticker['c']}")
        except Exception as e:
            logger.error(f"Binance WebSocket 오류: {e}. 5초 후 재연결합니다.")
            await asyncio.sleep(5)

async def bybit_websocket_client():
    """
    Bybit WebSocket에 연결하여 모든 USDT 페어의 실시간 시세를 수신하고
    shared_data를 업데이트합니다.
    """
    uri = "wss://stream.bybit.com/v5/public/spot"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("Bybit WebSocket에 연결되었습니다.")
                
                # 구독할 USDT 마켓 목록 가져오기
                supported_symbols = get_bybit_supported_symbols()
                if not supported_symbols:
                    logger.error("Bybit 지원 심볼 목록을 가져올 수 없습니다. 5초 후 재시도합니다.")
                    await asyncio.sleep(5)
                    continue

                # 구독 메시지 생성
                args = [f"tickers.{symbol}" for symbol in supported_symbols]
                subscribe_message = {"op": "subscribe", "args": args}
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"Bybit WebSocket에 {len(supported_symbols)}개 마켓을 구독했습니다.")

                # 데이터 수신 및 처리
                async for message in websocket:
                    data = json.loads(message)
                    if data.get("topic", "").startswith("tickers"):
                        ticker_data = data['data']
                        symbol = ticker_data['symbol'].replace('USDT', '')
                        shared_data["bybit_tickers"][symbol] = {
                            "price": float(ticker_data['lastPrice']),
                            "volume": float(ticker_data['volume24h']),
                            "change_percent": float(ticker_data['price24hPcnt']) * 100
                        }
                        # logger.debug(f"Bybit 수신: {symbol} = {ticker_data['lastPrice']}")
        except Exception as e:
            logger.error(f"Bybit WebSocket 오류: {e}. 5초 후 재연결합니다.")
            await asyncio.sleep(5)

# --- Helper Functions for other data ---

def get_upbit_krw_markets() -> List[str]:
    """
    Upbit에서 거래 가능한 모든 KRW 마켓의 심볼 목록을 가져옵니다.
    """
    url = "https://api.upbit.com/v1/market/all"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        krw_markets = [item['market'] for item in data if item['market'].startswith('KRW-')]
        return [market.split('-')[1] for market in krw_markets if market != 'KRW-USDT']
    except requests.exceptions.RequestException as e:
        logger.error(f"Upbit KRW 마켓 목록 조회 오류: {e}")
        return []

async def fetch_exchange_rate_periodically():
    """
    네이버 금융에서 USD/KRW 환율을 주기적으로 가져와 shared_data를 업데이트합니다.
    """
    url = "https://finance.naver.com/marketindex/"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    rate_element = soup.select_one("#exchangeList > li.on > a.head.usd > div > span.value")
                    if rate_element:
                        shared_data["exchange_rate"] = float(rate_element.text.replace(',', ''))
                        logger.info(f"환율 업데이트: {shared_data['exchange_rate']} KRW/USD")
                    else:
                        logger.warning("네이버 금융에서 환율 정보를 찾을 수 없습니다.")
        except Exception as e:
            logger.error(f"환율 조회 중 오류 발생: {e}")
        
        await asyncio.sleep(60) # 1분에 한 번씩 업데이트

async def fetch_usdt_krw_rate_periodically():
    """
    업비트에서 USDT/KRW 가격을 주기적으로 가져와 shared_data를 업데이트합니다.
    """
    url = "https://api.upbit.com/v1/ticker?markets=KRW-USDT"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        shared_data["usdt_krw_rate"] = data[0]['trade_price']
                        logger.info(f"USDT/KRW 업데이트: {shared_data['usdt_krw_rate']}")
        except Exception as e:
            logger.error(f"USDT/KRW 조회 중 오류 발생: {e}")

        await asyncio.sleep(10) # 10초에 한 번씩 업데이트

# --- Legacy Functions (보조용) ---
# 기존의 다른 거래소 Ticker 함수들은 필요시 여기에 유지하거나 수정할 수 있습니다.
# 지금은 WebSocket으로 대체되었으므로 대부분 제거합니다.

def get_binance_supported_symbols() -> set:
    """바이낸스에서 지원하는 USDT 페어 심볼 목록을 가져옵니다."""
    try:
        response = requests.get("https://api.binance.com/api/v3/exchangeInfo")
        response.raise_for_status()
        data = response.json()
        return {item['symbol'] for item in data.get('symbols', []) if item['quoteAsset'] == 'USDT' and item['status'] == 'TRADING'}
    except requests.exceptions.RequestException as e:
        logger.error(f"바이낸스 지원 심볼 조회 오류: {e}")
        return set()

def get_bybit_supported_symbols() -> set:
    """Bybit에서 지원하는 USDT 페어 심볼 목록을 가져옵니다."""
    try:
        params = {"category": "spot"}
        response = requests.get("https://api.bybit.com/v5/market/instruments-info", params=params)
        response.raise_for_status()
        data = response.json()
        symbols = set()
        if data.get('retCode') == 0 and data.get('result') and data['result'].get('list'):
            for item in data['result']['list']:
                if item.get('quoteCoin') == 'USDT' and item.get('status') == 'Trading':
                    symbols.add(item['symbol'])
        return symbols
    except requests.exceptions.RequestException as e:
        logger.error(f"Bybit 지원 심볼 조회 오류: {e}")
        return set()

# 공포/탐욕 지수, 과거 데이터 조회 등 다른 서비스 함수들은 그대로 유지합니다.
FNG_API_URL = "https://api.alternative.me/fng/"

def get_fear_greed_index() -> Optional[Dict]:
    """Alternative.me에서 공포/탐욕 지수를 조회합니다."""
    try:
        params = {"limit": 1, "format": "json"}
        response = requests.get(FNG_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data and data['data']:
            latest_data = data['data'][0]
            return {
                "value": int(latest_data['value']),
                "value_classification": latest_data['value_classification'],
                "timestamp": latest_data['timestamp']
            }
        return None
    except Exception as e:
        logger.error(f"공포/탐욕 지수 조회 오류: {e}")
        return None