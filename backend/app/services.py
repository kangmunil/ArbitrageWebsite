import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup
import json

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

def get_upbit_ticker(symbol: str) -> dict:
    """Upbit에서 특정 암호화폐의 티커 정보를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH')
        
    Returns:
        dict: 티커 정보 (price, volume, change_percent) 또는 None
        - price (float): 현재 가격 (KRW)
        - volume (float): 24시간 거래대금 (KRW)
        - change_percent (float): 24시간 변동률 (%)
    """
    """Upbit에서 특정 암호화폐의 티커 정보를 조회합니다."""
    try:
        response = requests.get(UPBIT_API_URL, params={"markets": f"KRW-{symbol}"})
        response.raise_for_status()  # 오류 발생 시 예외 처리
        data = response.json()
        if data and data[0]:
            ticker_data = data[0]
            return {
                "price": float(ticker_data['trade_price']),
                "volume": float(ticker_data['acc_trade_price_24h']),
                "change_percent": float(ticker_data['signed_change_rate']) * 100
            }
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Upbit: {e}")
        return None

def get_binance_ticker(symbol: str) -> dict:
    """Binance에서 특정 암호화폐의 티커 정보를 조회합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH') - USDT 페어로 조회
        
    Returns:
        dict: 티커 정보 (price, volume, change_percent) 또는 None
        - price (float): 현재 가격 (USDT)
        - volume (float): 24시간 거래량
        - change_percent (float): 24시간 변동률 (%)
    """
    """Binance에서 특정 암호화폐의 티커 정보를 조회합니다."""
    try:
        response = requests.get(BINANCE_API_URL, params={"symbol": f"{symbol}USDT"})
        response.raise_for_status()
        data = response.json()
        if data:
            return {
                "price": float(data['lastPrice']),
                "volume": float(data['volume']),
                "change_percent": float(data['priceChangePercent'])
            }
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Binance: {e}")
        return None

BITHUMB_API_URL = "https://api.bithumb.com/public/ticker/"

def get_bithumb_ticker(symbol: str) -> dict:
    """Bithumb에서 특정 암호화폐의 티커 정보를 조회합니다.
    
    Note: Bithumb API는 24시간 거래량 및 변동률을 쉽게 제공하지 않아 None으로 설정됩니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH')
        
    Returns:
        dict: 티커 정보 (price만 제공, volume과 change_percent는 None) 또는 None
        - price (float): 현재 가격 (KRW)
        - volume: None (API 제한)
        - change_percent: None (API 제한)
    """
    """Bithumb에서 특정 암호화폐의 티커 정보를 조회합니다."""
    try:
        # 빗썸 API는 심볼_KRW 형식으로 요청해야 함
        response = requests.get(f"{BITHUMB_API_URL}{symbol.upper()}_KRW")
        response.raise_for_status()
        data = response.json()
        
        # 응답 구조 확인: data['data']['closing_price']
        if data and data['status'] == '0000' and 'closing_price' in data['data']:
            return {
                "price": float(data['data']['closing_price']),
                "volume": None, # 24hr volume not easily available from this API
                "change_percent": None # 24hr change percent not easily available from this API
            }
        
        print(f"Bithumb data not found or invalid for {symbol}: {data}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Bithumb: {e}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error parsing Bithumb data: {e}")
        return None

BYBIT_API_URL = "https://api.bybit.com/v5/market/tickers"

def get_bybit_ticker(symbol: str) -> dict:
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

def get_okx_ticker(symbol: str) -> dict:
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

def get_gateio_ticker(symbol: str) -> dict:
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

def get_mexc_ticker(symbol: str) -> dict:
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

def get_naver_exchange_rate() -> float:
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

def get_fear_greed_index() -> dict:
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


def get_upbit_price(symbol: str) -> float:
    """Upbit에서 특정 암호화폐의 현재 가격을 조회합니다 (레거시 호환 함수).
    
    이 함수는 하위 호환성을 위해 유지되며, get_upbit_ticker() 사용을 권장합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH')
        
    Returns:
        float: 현재 가격 (KRW) 또는 None
    """
    ticker = get_upbit_ticker(symbol)
    return ticker["price"] if ticker else None


def get_binance_price(symbol: str) -> float:
    """Binance에서 특정 암호화폐의 현재 가격을 조회합니다 (레거시 호환 함수).
    
    이 함수는 하위 호환성을 위해 유지되며, get_binance_ticker() 사용을 권장합니다.
    
    Args:
        symbol (str): 암호화폐 심볼 (예: 'BTC', 'ETH') - USDT 페어로 조회
        
    Returns:
        float: 현재 가격 (USDT) 또는 None
    """
    ticker = get_binance_ticker(symbol)
    return ticker["price"] if ticker else None

