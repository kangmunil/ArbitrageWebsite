from typing import Dict, List, Optional
import requests
import aiohttp
from aiohttp import ClientTimeout
import asyncio
from datetime import datetime, timedelta
import time
import json
import logging

logger = logging.getLogger(__name__)
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup
import json

# API 캐싱을 위한 전역 변수들
_api_cache = {}
_cache_ttl = 30  # 30초 캐시 유지

def _get_cache_key(exchange: str, symbol: str) -> str:
    """캐시 키 생성"""
    return f"{exchange}:{symbol}"

def _get_cached_data(cache_key: str) -> Optional[Dict]:
    """캐시된 데이터 조회"""
    if cache_key in _api_cache:
        cached_data, timestamp = _api_cache[cache_key]
        if time.time() - timestamp < _cache_ttl:
            print(f"Cache hit for {cache_key}")
            return cached_data
        else:
            # 만료된 캐시 삭제
            del _api_cache[cache_key]
    return None

def _set_cached_data(cache_key: str, data: Dict) -> None:
    """데이터 캐시에 저장"""
    _api_cache[cache_key] = (data, time.time())
    print(f"Cache set for {cache_key}")

def _clear_expired_cache():
    """만료된 캐시 항목들 정리"""
    current_time = time.time()
    expired_keys = []
    for key, (data, timestamp) in _api_cache.items():
        if current_time - timestamp >= _cache_ttl:
            expired_keys.append(key)
    
    for key in expired_keys:
        del _api_cache[key]
    
    if expired_keys:
        print(f"Cleared {len(expired_keys)} expired cache entries")

UPBIT_API_URL = "https://api.upbit.com/v1/ticker"
UPBIT_MARKET_API_URL = "https://api.upbit.com/v1/market/all"
BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/24hr"
NAVER_FINANCE_URL = "https://finance.naver.com/marketindex/"


def get_upbit_krw_markets():
    """Upbit에서 KRW 마켓의 모든 코인 심볼 목록을 가져옵니다.
    
    USDT는 제외하고 KRW로 거래되는 모든 암호화폐 심볼을 반환합니다.
    
    Returns:
        list: KRW 마켓의 암호화폐 심볼 리스트 (예: ['BTC', 'ETH', 'XRP'])
    """
    """Upbit에서 KRW 마켓의 모든 코인 심볼 목록을 가져옵니다."""
    try:
        response = requests.get(UPBIT_MARKET_API_URL)
        response.raise_for_status()
        data = response.json()
        krw_markets = [item['market'] for item in data if item['market'].startswith('KRW-')]
        # USDT 자체를 코인처럼 돌리는 버그 방지: USDT는 KRW 마켓에서 제외
        return [market.split('-')[1] for market in krw_markets if market != 'KRW-USDT']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Upbit market API: {e}")
        return []

def get_upbit_ticker(symbol: str) -> Optional[Dict]:
    """업비트 티커 정보를 캐싱과 함께 가져옵니다."""
    # 캐시 확인
    cache_key = _get_cache_key("upbit", symbol)
    cached_data = _get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://api.upbit.com/v1/ticker?markets=KRW-{symbol}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 429:
            print(f"⚠️  Rate limit exceeded for Upbit {symbol} - using cache if available")
            # Rate limit 시 오래된 캐시라도 사용
            if cache_key in _api_cache:
                cached_data, _ = _api_cache[cache_key]
                print(f"Using stale cache for Upbit {symbol}")
                return cached_data
            return None
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            ticker = data[0]
            result = {
                "price": ticker["trade_price"],
                "volume": ticker["acc_trade_volume_24h"],
                "change_percent": (ticker["signed_change_rate"] * 100)
            }
            # 캐시에 저장
            _set_cached_data(cache_key, result)
            return result
        return None
    except requests.exceptions.RequestException as e:
        print(f"Warning: Error fetching Upbit ticker for {symbol}: {e}")
        # 에러 시에도 캐시 사용 시도
        if cache_key in _api_cache:
            cached_data, _ = _api_cache[cache_key]
            print(f"Using stale cache for Upbit {symbol} due to error")
            return cached_data
        return None

def get_bithumb_ticker(symbol: str) -> Optional[Dict]:
    """빗썸 티커 정보를 가져옵니다."""
    url = f"https://api.bithumb.com/public/ticker/{symbol}_KRW"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data and data["status"] == "0000":
            ticker = data["data"]
            return {
                "price": float(ticker["closing_price"]),
                "volume": float(ticker["units_traded_24H"]),
                "change_percent": float(ticker["fluctate_rate_24H"])
            }
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Bithumb ticker for {symbol}: {e}")
        return None

def get_binance_ticker(symbol: str) -> Optional[Dict]:
    """바이낸스 티커 정보를 가져옵니다."""
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return {
            "price": float(data["lastPrice"]),
            "volume": float(data["volume"]),
            "change_percent": float(data["priceChangePercent"])
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Binance ticker for {symbol}: {e}")
        return None

BYBIT_API_URL = "https://api.bybit.com/v5/market/tickers"

def get_bybit_ticker(symbol: str) -> Optional[Dict]:
    """Bybit에서 특정 암호화폐의 티커 정보를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH') - USDT 페어로 조회
        
    Returns:
        dict: 티커 정보 (price, volume, change_percent) 또는 None
        - price (float): 현재 가격 (USDT)
        - volume (float): 24시간 거래량
        - change_percent (float): 24시간 변동률 (%)
    """
    """Bybit에서 특정 암호화폐의 티커 정보를 조회합니다."""
    try:
        params = {
            "category": "spot",
            "symbol": f"{symbol.upper()}USDT"
        }
        response = requests.get(BYBIT_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data and data['retCode'] == 0 and data['result'] and data['result']['list']:
            ticker_data = data['result']['list'][0]
            return {
                "price": float(ticker_data['lastPrice']),
                "volume": float(ticker_data['volume24h']),
                "change_percent": float(ticker_data['price24hPcnt']) * 100
            }
        
        print(f"Bybit data not found or invalid for {symbol}: {data}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Bybit: {e}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error parsing Bybit data: {e}")
        return None

OKX_API_URL = "https://www.okx.com/api/v5/market/ticker"

def get_okx_ticker(symbol: str) -> Optional[Dict]:
    """OKX에서 특정 암호화폐의 티커 정보를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH') - USDT 페어로 조회
        
    Returns:
        dict: 티커 정보 (price, volume, change_percent) 또는 None
        - price (float): 현재 가격 (USDT)
        - volume (float): 24시간 거래량
        - change_percent (float): 24시간 변동률 (%)
    """
    """OKX에서 특정 암호화폐의 티커 정보를 조회합니다."""
    try:
        params = {"instId": f"{symbol.upper()}-USDT"}
        response = requests.get(OKX_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data and data.get('data') and data['data'][0]:
            ticker_data = data['data'][0]
            last_price = float(ticker_data['last'])
            open_price = float(ticker_data['sodUtc8'])
            change_percent = ((last_price - open_price) / open_price) * 100 if open_price != 0 else 0
            return {
                "price": last_price,
                "volume": float(ticker_data['vol24h']),
                "change_percent": change_percent
            }
        print(f"OKX data not found or invalid for {symbol}: {data}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from OKX: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
        print(f"Error parsing OKX data: {e}")
        return None

GATEIO_API_URL = "https://api.gateio.ws/api/v4/spot/tickers"

def get_gateio_ticker(symbol: str) -> Optional[Dict]:
    """Gate.io에서 특정 암호화폐의 티커 정보를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH') - USDT 페어로 조회
        
    Returns:
        dict: 티커 정보 (price, volume, change_percent) 또는 None
        - price (float): 현재 가격 (USDT)
        - volume (float): 24시간 거래량
        - change_percent (float): 24시간 변동률 (%)
    """
    """Gate.io에서 특정 암호화폐의 티커 정보를 조회합니다."""
    try:
        params = {"currency_pair": f"{symbol.upper()}_USDT"}
        response = requests.get(GATEIO_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and data[0]:
            ticker_data = data[0]
            return {
                "price": float(ticker_data['last']),
                "volume": float(ticker_data['base_volume']),
                "change_percent": float(ticker_data['change_percentage'])
            }
        print(f"Gate.io data not found or invalid for {symbol}: {data}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Gate.io: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
        print(f"Error parsing Gate.io data: {e}")
        return None

MEXC_API_URL = "https://api.mexc.com/api/v3/ticker/24hr"

def get_mexc_ticker(symbol: str) -> Optional[Dict]:
    """MEXC에서 특정 암호화폐의 티커 정보를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH') - USDT 페어로 조회
        
    Returns:
        dict: 티커 정보 (price, volume, change_percent) 또는 None
        - price (float): 현재 가격 (USDT)
        - volume (float): 24시간 거래량
        - change_percent (float): 24시간 변동률 (%)
    """
    """MEXC에서 특정 암호화폐의 티커 정보를 조회합니다."""
    try:
        params = {"symbol": f"{symbol.upper()}USDT"}
        response = requests.get(MEXC_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        # MEXC API는 단일 심볼 조회 시 딕셔너리를 반환
        if data and data.get('lastPrice'):
            return {
                "price": float(data['lastPrice']),
                "volume": float(data['volume']),
                "change_percent": float(data['priceChangePercent'])
            }
        print(f"MEXC data not found or invalid for {symbol}: {data}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from MEXC: {e}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error parsing MEXC data: {e}")
        return None

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
BYBIT_EXCHANGE_INFO_URL = "https://api.bybit.com/v5/market/instruments-info"
OKX_EXCHANGE_INFO_URL = "https://www.okx.com/api/v5/public/instruments"
GATEIO_EXCHANGE_INFO_URL = "https://api.gateio.ws/api/v4/spot/currency_pairs"
MEXC_EXCHANGE_INFO_URL = "https://api.mexc.com/api/v3/exchangeInfo"

def get_binance_supported_symbols() -> set:
    """바이낸스에서 지원하는 USDT 페어 심볼 목록을 가져옵니다.
    
    거래 가능한 상태의 USDT 페어만 반환합니다.
    
    Returns:
        set: 지원되는 심볼 집합 (예: {'BTCUSDT', 'ETHUSDT', ...})
    """
    """바이낸스에서 지원하는 USDT 페어 심볼 목록을 가져옵니다."""
    try:
        response = requests.get(BINANCE_EXCHANGE_INFO_URL)
        response.raise_for_status()
        data = response.json()
        symbols = set()
        for item in data.get('symbols', []):
            if item['quoteAsset'] == 'USDT' and item['status'] == 'TRADING':
                symbols.add(item['symbol'])
        return symbols
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Binance exchange info: {e}")
        return set()

def get_bybit_supported_symbols() -> set:
    """Bybit에서 지원하는 USDT 페어 심볼 목록을 가져옵니다.
    
    현물 거래에서 거래 가능한 상태의 USDT 페어만 반환합니다.
    
    Returns:
        set: 지원되는 심볼 집합 (예: {'BTCUSDT', 'ETHUSDT', ...})
    """
    """Bybit에서 지원하는 USDT 페어 심볼 목록을 가져옵니다."""
    try:
        params = {"category": "spot"}
        response = requests.get(BYBIT_EXCHANGE_INFO_URL, params=params)
        response.raise_for_status()
        data = response.json()
        symbols = set()
        if data.get('retCode') == 0 and data.get('result') and data['result'].get('list'):
            for item in data['result']['list']:
                if item.get('quoteCoin') == 'USDT' and item.get('status') == 'Trading':
                    symbols.add(item['symbol'])
        return symbols
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Bybit exchange info: {e}")
        return set()

def get_okx_supported_symbols() -> set:
    """OKX에서 지원하는 USDT 페어 심볼 목록을 가져옵니다.
    
    현물 거래에서 활성 상태의 USDT 페어만 반환합니다.
    
    Returns:
        set: 지원되는 심볼 집합 (예: {'BTC-USDT', 'ETH-USDT', ...})
    """
    """OKX에서 지원하는 USDT 페어 심볼 목록을 가져옵니다."""
    try:
        params = {"instType": "SPOT"}
        response = requests.get(OKX_EXCHANGE_INFO_URL, params=params)
        response.raise_for_status()
        data = response.json()
        symbols = set()
        if data.get('code') == '0' and data.get('data'):
            for item in data['data']:
                if item['quoteCcy'] == 'USDT' and item['state'] == 'live':
                    symbols.add(item['instId'])
        return symbols
    except requests.exceptions.RequestException as e:
        print(f"Error fetching OKX exchange info: {e}")
        return set()

def get_gateio_supported_symbols() -> set:
    """Gate.io에서 지원하는 USDT 페어 심볼 목록을 가져옵니다.
    
    거래 가능한 상태의 USDT 페어만 반환합니다.
    
    Returns:
        set: 지원되는 심볼 집합 (예: {'BTC_USDT', 'ETH_USDT', ...})
    """
    """Gate.io에서 지원하는 USDT 페어 심볼 목록을 가져옵니다."""
    try:
        response = requests.get(GATEIO_EXCHANGE_INFO_URL)
        response.raise_for_status()
        data = response.json()
        symbols = set()
        for item in data:
            if item.get('quote_asset') == 'USDT' and item['trade_status'] == 'tradable':
                symbols.add(item['id']) # currency_pair, e.g., BTC_USDT
        return symbols
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Gate.io exchange info: {e}")
        return set()

def get_mexc_supported_symbols() -> set:
    """MEXC에서 지원하는 USDT 페어 심볼 목록을 가져옵니다.
    
    거래 가능한 상태의 USDT 페어만 반환합니다.
    
    Returns:
        set: 지원되는 심볼 집합 (예: {'BTCUSDT', 'ETHUSDT', ...})
    """
    """MEXC에서 지원하는 USDT 페어 심볼 목록을 가져옵니다."""
    try:
        response = requests.get(MEXC_EXCHANGE_INFO_URL)
        response.raise_for_status()
        data = response.json()
        symbols = set()
        for item in data.get('symbols', []):
            if item['quoteAsset'] == 'USDT' and item['status'] == 'TRADING':
                symbols.add(item['symbol'])
        return symbols
    except requests.exceptions.RequestException as e:
        print(f"Error fetching MEXC exchange info: {e}")
        return set()


def get_binance_historical_prices(symbol: str, interval: str = "1d", limit: int = 30) -> list:
    """Binance에서 특정 암호화폐의 과거 시세(캔들스틱) 데이터를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC') - USDT 페어로 조회
        interval (str): 시간 간격 (예: '1d', '1h', '15m'). 기본값: '1d'
        limit (int): 조회할 데이터 개수. 기본값: 30
        
    Returns:
        list: 과거 시세 데이터 리스트. 각 항목은 dict 형태:
        - timestamp (int): 타임스탬프
        - open (float): 시가
        - high (float): 고가
        - low (float): 저가
        - close (float): 종가
        - volume (float): 거래량
    """
    """Binance에서 특정 암호화폐의 과거 시세(캔들스틱) 데이터를 조회합니다."""
    try:
        params = {
            "symbol": f"{symbol}USDT",
            "interval": interval,
            "limit": limit
        }
        response = requests.get(BINANCE_KLINES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 캔들스틱 데이터 파싱 (시간, 시가, 고가, 저가, 종가, 거래량 등)
        # [0] open time, [1] open, [2] high, [3] low, [4] close, [5] volume
        historical_data = []
        for entry in data:
            historical_data.append({
                "timestamp": entry[0],
                "open": float(entry[1]),
                "high": float(entry[2]),
                "low": float(entry[3]),
                "close": float(entry[4]),
                "volume": float(entry[5])
            })
        return historical_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching historical data from Binance: {e}")
        return []
    except (json.JSONDecodeError, IndexError, ValueError) as e:
        print(f"Error parsing Binance historical data: {e}")
        return []

def get_naver_exchange_rate() -> Optional[float]:
    """네이버 금융에서 원/달러 환율을 스크래핑합니다.
    
    네이버 금융 페이지를 파싱하여 실시간 USD/KRW 환율을 가져옵니다.
    
    Returns:
        float: USD/KRW 환율 또는 None (조회 실패 시)
        
    Note:
        웹사이트 구조 변경 시 selector 업데이트가 필요할 수 있습니다.
    """
    """네이버 금융에서 원/달러 환율을 스크래핑합니다."""
    try:
        response = requests.get(NAVER_FINANCE_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        # Find the specific element containing the USD to KRW exchange rate
        # The selector might need to be updated if the website structure changes.
        exchange_rate_element = soup.select_one("#exchangeList > li.on > a.head.usd > div > span.value")
        if exchange_rate_element:
            return float(exchange_rate_element.text.replace(',', ''))
        else:
            print("Could not find the exchange rate element on Naver Finance.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Naver Finance: {e}")
        return None
    except (AttributeError, ValueError) as e:
        print(f"Error parsing Naver Finance page: {e}")
        return None

FNG_API_URL = "https://api.alternative.me/fng/"

def get_fear_greed_index() -> Optional[Dict]:
    """Alternative.me에서 공포/탐욕 지수를 조회합니다.
    
    암호화폐 시장의 감정을 나타내는 공포/탐욕 지수 데이터를 가져옵니다.
    0~100 점수로 표시되며, 0에 가까울수록 공포, 100에 가까울수록 탐욕을 의미합니다.
    
    Returns:
        dict: 공포/탐욕 지수 데이터 또는 None
        - value (int): 지수 값 (0-100)
        - value_classification (str): 감정 분류 (예: 'Extreme Fear', 'Greed')
        - timestamp (str): 데이터 타임스탬프
    """
    """Alternative.me에서 공포/탐욕 지수를 조회합니다."""
    try:
        params = {
            "limit": 1,  # 최신 데이터 1개만 가져옴
            "format": "json"
        }
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
        else:
            print("Fear & Greed Index data not found.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Fear & Greed Index: {e}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error parsing Fear & Greed Index data: {e}")
        return None


def get_upbit_price(symbol: str) -> Optional[float]:
    """Upbit에서 특정 암호화폐의 현재 가격을 조회합니다 (레거시 호환 함수).
    
    이 함수는 하위 호환성을 위해 유지되며, get_upbit_ticker() 사용을 권장합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH')
        
    Returns:
        float: 현재 가격 (KRW) 또는 None
    """
    ticker = get_upbit_ticker(symbol)
    return ticker["price"] if ticker else None


def get_binance_price(symbol: str) -> Optional[float]:
    """Binance에서 특정 암호화폐의 현재 가격을 조회합니다 (레거시 호환 함수).
    
    이 함수는 하위 호환성을 위해 유지되며, get_binance_ticker() 사용을 권장합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH') - USDT 페어로 조회
        
    Returns:
        float: 현재 가격 (USDT) 또는 None
    """
    ticker = get_binance_ticker(symbol)
    return ticker["price"] if ticker else None


# ============================================================================
# 비동기 함수들 - 성능 최적화를 위한 병렬 처리
# ============================================================================

async def async_get_upbit_ticker(session: aiohttp.ClientSession, symbol: str) -> Optional[Dict]:
    """업비트 티커 정보를 캐싱과 함께 비동기로 가져옵니다."""
    # 캐시 확인
    cache_key = _get_cache_key("upbit", symbol)
    cached_data = _get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://api.upbit.com/v1/ticker?markets=KRW-{symbol}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 404:
                print(f"Warning: Upbit does not support symbol {symbol}")
                return None
            response.raise_for_status()
            data = await response.json()
            if data and len(data) > 0:
                ticker = data[0]
                result = {
                    "price": ticker["trade_price"],
                    "volume": ticker["acc_trade_volume_24h"],
                    "change_percent": (ticker["signed_change_rate"] * 100)
                }
                # 캐시에 저장
                _set_cached_data(cache_key, result)
                return result
            else:
                print(f"Warning: Empty data received for Upbit {symbol}")
                return None
    except aiohttp.ClientTimeout:  # type: ignore
        print(f"Warning: Timeout fetching Upbit ticker for {symbol}")
        return None
    except aiohttp.ClientResponseError as e:
        if e.status == 429:
            print(f"⚠️  Rate limit exceeded for Upbit {symbol} - using cache if available")
            # Rate limit 시 오래된 캐시라도 사용
            if cache_key in _api_cache:
                cached_data, _ = _api_cache[cache_key]
                print(f"Using stale cache for Upbit {symbol}")
                return cached_data
        else:
            print(f"Warning: HTTP error {e.status} fetching Upbit ticker for {symbol}")
        return None
    except Exception as e:
        print(f"Warning: Unexpected error fetching Upbit ticker for {symbol}: {e}")
        return None

async def async_get_binance_ticker(session: aiohttp.ClientSession, symbol: str) -> Optional[Dict]:
    """바이낸스 티커 정보를 캐싱과 함께 비동기로 가져옵니다."""
    # 캐시 확인
    cache_key = _get_cache_key("binance", symbol)
    cached_data = _get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 400:
                print(f"Warning: Binance does not support symbol {symbol}USDT")
                return None
            response.raise_for_status()
            data = await response.json()
            result = {
                "price": float(data["lastPrice"]),
                "volume": float(data["volume"]),
                "change_percent": float(data["priceChangePercent"])
            }
            # 캐시에 저장
            _set_cached_data(cache_key, result)
            return result
    except aiohttp.ClientTimeout:  # type: ignore
        print(f"Warning: Timeout fetching Binance ticker for {symbol}")
        return None
    except aiohttp.ClientResponseError as e:
        if e.status == 429:
            print(f"⚠️  Rate limit exceeded for Binance {symbol} - using cache if available")
            if cache_key in _api_cache:
                cached_data, _ = _api_cache[cache_key]
                print(f"Using stale cache for Binance {symbol}")
                return cached_data
        else:
            print(f"Warning: HTTP error {e.status} fetching Binance ticker for {symbol}")
        return None
    except Exception as e:
        print(f"Warning: Unexpected error fetching Binance ticker for {symbol}: {e}")
        return None

async def async_get_bithumb_ticker(session: aiohttp.ClientSession, symbol: str) -> Optional[Dict]:
    """빗썸 티커 정보를 캐싱과 함께 비동기로 가져옵니다."""
    # 캐시 확인
    cache_key = _get_cache_key("bithumb", symbol)
    cached_data = _get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://api.bithumb.com/public/ticker/{symbol}_KRW"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status()
            data = await response.json()
            if data and data.get("status") == "0000":
                ticker = data["data"]
                result = {
                    "price": float(ticker["closing_price"]),
                    "volume": float(ticker["units_traded_24H"]),
                    "change_percent": float(ticker["fluctate_rate_24H"])
                }
                # 캐시에 저장
                _set_cached_data(cache_key, result)
                return result
            else:
                print(f"Warning: Bithumb does not support symbol {symbol} or API error")
                return None
    except aiohttp.ClientTimeout:  # type: ignore
        print(f"Warning: Timeout fetching Bithumb ticker for {symbol}")
        return None
    except aiohttp.ClientResponseError as e:
        if e.status == 429:
            print(f"⚠️  Rate limit exceeded for Bithumb {symbol} - using cache if available")
            if cache_key in _api_cache:
                cached_data, _ = _api_cache[cache_key]
                print(f"Using stale cache for Bithumb {symbol}")
                return cached_data
        else:
            print(f"Warning: HTTP error {e.status} fetching Bithumb ticker for {symbol}")
        return None
    except Exception as e:
        print(f"Warning: Unexpected error fetching Bithumb ticker for {symbol}: {e}")
        return None

async def async_get_bybit_ticker(session: aiohttp.ClientSession, symbol: str) -> Optional[Dict]:
    """바이비트 티커 정보를 캐싱과 함께 비동기로 가져옵니다."""
    # 캐시 확인
    cache_key = _get_cache_key("bybit", symbol)
    cached_data = _get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}USDT"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status()
            data = await response.json()
            if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                ticker = data["result"]["list"][0]
                result = {
                    "price": float(ticker["lastPrice"]),
                    "volume": float(ticker["volume24h"]),
                    "change_percent": float(ticker["price24hPcnt"]) * 100
                }
                # 캐시에 저장
                _set_cached_data(cache_key, result)
                return result
            else:
                print(f"Warning: Bybit does not support symbol {symbol}USDT or API error")
                return None
    except aiohttp.ClientTimeout:  # type: ignore
        print(f"Warning: Timeout fetching Bybit ticker for {symbol}")
        return None
    except aiohttp.ClientResponseError as e:
        if e.status == 429:
            print(f"⚠️  Rate limit exceeded for Bybit {symbol} - using cache if available")
            if cache_key in _api_cache:
                cached_data, _ = _api_cache[cache_key]
                print(f"Using stale cache for Bybit {symbol}")
                return cached_data
        else:
            print(f"Warning: HTTP error {e.status} fetching Bybit ticker for {symbol}")
        return None
    except Exception as e:
        print(f"Warning: Unexpected error fetching Bybit ticker for {symbol}: {e}")
        return None

async def async_get_naver_exchange_rate(session: aiohttp.ClientSession) -> Optional[float]:
    """네이버 금융에서 원/달러 환율을 비동기로 스크래핑합니다."""
    try:
        async with session.get(NAVER_FINANCE_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, 'lxml')
            exchange_rate_element = soup.select_one("#exchangeList > li.on > a.head.usd > div > span.value")
            if exchange_rate_element:
                return float(exchange_rate_element.text.replace(',', ''))
            else:
                print("Could not find the exchange rate element on Naver Finance.")
                return None
    except Exception as e:
        print(f"Error fetching from Naver Finance: {e}")
        return None

async def fetch_all_tickers_for_symbol(symbol: str, supported_symbols_cache: Dict, exchange_rate: Optional[float]) -> Dict:
    """특정 심볼에 대해 모든 거래소의 티커 데이터를 순차적으로 가져옵니다 (Rate Limiting 방지)."""
    # 주기적으로 만료된 캐시 정리
    _clear_expired_cache()
    
    async with aiohttp.ClientSession() as session:
        # Rate limiting 방지를 위해 순차적으로 API 호출
        results = {}
        
        # Upbit (항상 호출)
        print(f"Fetching {symbol} from Upbit...")
        results["upbit"] = await async_get_upbit_ticker(session, symbol)
        await asyncio.sleep(0.2)  # 200ms 지연
        
        # Binance (지원 여부 확인 후 호출)
        binance_symbol = f"{symbol}USDT"
        if binance_symbol in supported_symbols_cache["binance"]:
            print(f"Fetching {symbol} from Binance...")
            results["binance"] = await async_get_binance_ticker(session, symbol)
            await asyncio.sleep(0.2)  # 200ms 지연
        else:
            results["binance"] = None
        
        # Bithumb (항상 호출)
        print(f"Fetching {symbol} from Bithumb...")
        results["bithumb"] = await async_get_bithumb_ticker(session, symbol)
        await asyncio.sleep(0.2)  # 200ms 지연
        
        # Bybit (지원 여부 확인 후 호출)
        bybit_symbol = f"{symbol.upper()}USDT"
        if bybit_symbol in supported_symbols_cache["bybit"]:
            print(f"Fetching {symbol} from Bybit...")
            results["bybit"] = await async_get_bybit_ticker(session, symbol)
            await asyncio.sleep(0.2)  # 200ms 지연
        else:
            results["bybit"] = None
        
        # 결과 처리
        coin_data = {
            "symbol": symbol,
            "upbit_price": None,
            "upbit_volume": None,
            "upbit_change_percent": None,
            "binance_price": None,
            "binance_volume": None,
            "binance_change_percent": None,
            "bithumb_price": None,
            "bithumb_volume": None,
            "bithumb_change_percent": None,
            "bybit_price": None,
            "bybit_volume": None,
            "bybit_change_percent": None,
            "okx_price": None,
            "okx_volume": None,
            "okx_change_percent": None,
            "gateio_price": None,
            "gateio_volume": None,
            "gateio_change_percent": None,
            "mexc_price": None,
            "mexc_volume": None,
            "mexc_change_percent": None,
            "premium": None,
            "usdt_krw_rate": None,
            "exchange_rate": None,
        }
        
        # 결과를 coin_data에 매핑
        for exchange_name in ["upbit", "binance", "bithumb", "bybit"]:
            result = results.get(exchange_name)
            if result and isinstance(result, dict):
                coin_data[f"{exchange_name}_price"] = result.get("price")
                coin_data[f"{exchange_name}_volume"] = result.get("volume")
                coin_data[f"{exchange_name}_change_percent"] = result.get("change_percent")
        
        # 김치 프리미엄 계산
        upbit_price = coin_data["upbit_price"]
        binance_price = coin_data["binance_price"]
        
        if upbit_price is not None and binance_price is not None and exchange_rate is not None:
            binance_price_krw = binance_price * exchange_rate
            if binance_price_krw != 0:
                premium = ((upbit_price - binance_price_krw) / binance_price_krw) * 100
                coin_data["premium"] = round(premium, 2)
                print(f"{symbol} Kimchi Premium calculated: {premium:.2f}% (Upbit: {upbit_price} KRW, Binance: {binance_price} USDT, Rate: {exchange_rate})")
        
        # 환율 정보 추가
        if exchange_rate is not None:
            coin_data["exchange_rate"] = round(exchange_rate, 2)
        
        return coin_data

