from typing import Dict, List, Optional
import requests
import aiohttp
import asyncio
import json
import logging
import uuid
from websockets import connect as websockets_connect  # type: ignore
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# --- Shared Data Store ---
# 이 변수는 모든 실시간 데이터를 중앙에서 관리합니다.
# 각 WebSocket 클라이언트는 이 변수를 업데이트하고,
# price_aggregator는 이 변수를 읽어 최종 데이터를 만듭니다.
shared_data = {
    "upbit_tickers": {},  # Upbit 실시간 시세
    "bithumb_tickers": {}, # Bithumb 실시간 시세
    "binance_tickers": {}, # Binance 실시간 시세
    "bybit_tickers": {},   # Bybit 실시간 시세
    "exchange_rate": None, # USD/KRW 환율
    "usdt_krw_rate": None, # USDT/KRW 환율
}

# --- WebSocket Clients ---

from .enhanced_websocket import EnhancedWebSocketClient # Add this import

async def upbit_websocket_client():
    """
    Upbit WebSocket에 연결하여 모든 KRW 마켓의 실시간 시세를 수신하고
    shared_data를 업데이트합니다. EnhancedWebSocketClient 사용.
    """
    uri = "wss://api.upbit.com/websocket/v1"
    client = EnhancedWebSocketClient(uri=uri, name="Upbit", ping_interval=20, ping_timeout=10)

    async def on_connect():
        logger.info("Upbit WebSocket에 연결되었습니다.")
        krw_markets = get_upbit_krw_markets()
        if not krw_markets:
            logger.error("Upbit KRW 마켓 목록을 가져올 수 없습니다. 재시도합니다.")
            # Consider raising an exception or handling this more robustly if markets are critical
            return

        subscribe_message = [
            {"ticket": str(uuid.uuid4())},
            {"type": "ticker", "codes": [f"KRW-{symbol}" for symbol in krw_markets]}
        ]
        await client.websocket.send(json.dumps(subscribe_message))
        logger.info(f"Upbit WebSocket에 {len(krw_markets)}개 마켓을 구독했습니다.")

    async def on_message(data):
        try:
            # EnhancedWebSocketClient handles JSON parsing, so 'data' is already a dict/list
            symbol = data['code'].replace('KRW-', '')
            
            shared_data["upbit_tickers"][symbol] = {
                "price": data['trade_price'],
                "volume": data['acc_trade_price_24h'],  # 거래대금 (KRW) 사용
                "change_percent": data['signed_change_rate'] * 100
            }
            if symbol == 'BTC':
                logger.info(f"📈 Upbit BTC 실시간 수신: {data['trade_price']:.1f} KRW (정확한 값: {data['trade_price']})")
            if symbol == 'AMO': # AMO 코인 데이터 수신 시 로그 추가
                logger.info(f"🔍 Upbit AMO 수신: {data}")
        except Exception as parse_error:
            logger.error(f"Upbit 메시지 처리 오류: {parse_error}, 메시지: {data}")

    client.on_connect = on_connect
    client.on_message = on_message
    await client.run_with_retry()

async def binance_websocket_client():
    """
    Binance WebSocket에 연결하여 모든 USDT 페어의 24시간 티커 정보를 수신하고
    shared_data를 업데이트합니다. EnhancedWebSocketClient 사용.
    """
    uri = "wss://stream.binance.com:9443/ws/!ticker@arr"
    client = EnhancedWebSocketClient(uri=uri, name="Binance", ping_interval=20, ping_timeout=10)

    async def on_connect():
        logger.info("Binance WebSocket에 연결되었습니다.")
        # Binance All Ticker Stream doesn't require a subscription message after connection

    async def on_message(data):
        try:
            # EnhancedWebSocketClient handles JSON parsing, so 'data' is already a dict/list
            for ticker in data:
                if ticker['s'].endswith('USDT'):
                    symbol = ticker['s'].replace('USDT', '')
                    shared_data["binance_tickers"][symbol] = {
                        "price": float(ticker['c']),
                        "volume": float(ticker['q']),  # q = quote asset volume (USDT 거래대금)
                        "change_percent": float(ticker['P'])
                    }
                    if symbol == 'BTC':
                        logger.info(f"📊 Binance BTC 실시간 수신: {ticker['c']} USDT")
        except Exception as parse_error:
            logger.error(f"Binance 메시지 처리 오류: {parse_error}, 메시지: {data}")

    client.on_connect = on_connect
    client.on_message = on_message
    await client.run_with_retry()

async def bybit_websocket_client():
    """
    Bybit REST API를 주기적으로 호출하여 실시간 시세를 수신하고
    shared_data를 업데이트합니다.
    (WebSocket API가 불안정하므로 REST API 사용)
    """
    while True:
        try:
            # Bybit 지원 심볼 목록 가져오기 (주요 코인만)
            major_symbols = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT', 'UNIUSDT']
            
            # Bybit API에서 24시간 티커 정보 가져오기
            url = "https://api.bybit.com/v5/market/tickers"
            params = {"category": "spot"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('retCode') == 0 and data.get('result') and data['result'].get('list'):
                            ticker_list = data['result']['list']
                            
                            # 주요 USDT 페어만 처리
                            for ticker_data in ticker_list:
                                symbol = ticker_data.get('symbol', '')
                                if symbol in major_symbols:
                                    try:
                                        base_symbol = symbol.replace('USDT', '')
                                        shared_data["bybit_tickers"][base_symbol] = {
                                            "price": float(ticker_data['lastPrice']),
                                            "volume": float(ticker_data['turnover24h']),  # 24시간 거래대금 (USDT)
                                            "change_percent": float(ticker_data['price24hPcnt']) * 100
                                        }
                                    except (ValueError, KeyError) as e:
                                        logger.warning(f"Bybit 데이터 파싱 오류 ({symbol}): {e}")
                                        continue
                            
                            updated_count = len([s for s in major_symbols if s.replace('USDT', '') in shared_data['bybit_tickers']])
                            if updated_count > 0:
                                logger.info(f"Bybit REST API에서 {updated_count}개 코인 데이터를 업데이트했습니다.")
                            else:
                                logger.warning("Bybit API에서 데이터를 받았지만 유효한 코인이 없습니다.")
                    else:
                        logger.warning(f"Bybit API 응답 오류: {response.status}")
                        
            # 5초마다 업데이트
            await asyncio.sleep(5)
                        
        except Exception as e:
            logger.error(f"Bybit REST API 오류: {e}. 10초 후 재시도합니다.")
            await asyncio.sleep(10)

async def bithumb_rest_client():
    """
    Bithumb REST API를 주기적으로 호출하여 실시간 시세를 수신하고
    shared_data를 업데이트합니다.
    """
    while True:
        try:
            # Bithumb 지원 심볼 목록 가져오기
            supported_symbols = get_bithumb_supported_symbols()
            if not supported_symbols:
                logger.error("Bithumb 지원 심볼 목록을 가져올 수 없습니다. 10초 후 재시도합니다.")
                await asyncio.sleep(10)
                continue

            # Bithumb API에서 전체 시세 정보 가져오기
            url = "https://api.bithumb.com/public/ticker/ALL_KRW"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['status'] == '0000':  # 성공
                            ticker_data = data['data']
                            
                            # 각 코인별로 데이터 처리
                            for symbol, coin_data in ticker_data.items():
                                if symbol in supported_symbols and symbol != 'date':
                                    try:
                                        shared_data["bithumb_tickers"][symbol] = {
                                            "price": float(coin_data['closing_price']),
                                            "volume": float(coin_data['acc_trade_value_24H']),  # KRW 거래대금
                                            "change_percent": float(coin_data['fluctate_rate_24H'])
                                        }
                                    except (ValueError, KeyError) as e:
                                        logger.warning(f"Bithumb 데이터 파싱 오류 ({symbol}): {e}")
                                        continue
                            
                            logger.info(f"Bithumb REST API에서 {len([s for s in ticker_data.keys() if s in supported_symbols])}개 코인 데이터를 업데이트했습니다.")
                    else:
                        logger.warning(f"Bithumb API 응답 오류: {response.status}")
                        
            # 3초마다 업데이트
            await asyncio.sleep(3)
                        
        except Exception as e:
            logger.error(f"Bithumb REST API 오류: {e}. 10초 후 재시도합니다.")
            await asyncio.sleep(10)

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
    """Bybit에서 지원하는 주요 USDT 페어 심볼 목록을 반환합니다."""
    # 주요 코인만 하드코딩으로 반환 (API 호출 실패 방지)
    return {
        'BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'ADAUSDT', 
        'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT', 'UNIUSDT'
    }

def get_bithumb_supported_symbols() -> set:
    """Bithumb에서 지원하는 KRW 페어 심볼 목록을 가져옵니다."""
    try:
        response = requests.get("https://api.bithumb.com/public/ticker/ALL_KRW")
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == '0000' and data.get('data'):
            # 'date' 필드를 제외한 모든 심볼 반환
            symbols = {symbol for symbol in data['data'].keys() if symbol != 'date'}
            return symbols
        return set()
    except requests.exceptions.RequestException as e:
        logger.error(f"Bithumb 지원 심볼 조회 오류: {e}")
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