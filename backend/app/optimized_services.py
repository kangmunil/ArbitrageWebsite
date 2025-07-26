"""
최적화된 데이터 수집 서비스

개선사항:
1. 향상된 WebSocket 클라이언트 사용
2. Thread-safe shared_data 구조
3. 데이터 유효성 검사 강화
4. 메모리 효율적인 데이터 관리
"""

import asyncio
import json
import logging
import time
import uuid
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
import requests
import aiohttp
from bs4 import BeautifulSoup

from .enhanced_websocket import EnhancedWebSocketClient, ConnectionState

logger = logging.getLogger(__name__)

# --- Thread-Safe Shared Data Structure ---

@dataclass
class TickerData:
    """티커 데이터 구조"""
    symbol: str
    price: float
    volume: float
    change_percent: float
    timestamp: float = field(default_factory=time.time)
    
    def is_valid(self) -> bool:
        """데이터 유효성 검사"""
        return (
            self.price > 0 and
            self.volume >= 0 and
            abs(self.change_percent) <= 100 and  # 100% 이상 변동은 비정상
            time.time() - self.timestamp < 300  # 5분 이내 데이터만 유효
        )

@dataclass 
class ExchangeRateData:
    """환율 데이터 구조"""
    usd_krw: Optional[float] = None
    usdt_krw: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    
    def is_valid(self) -> bool:
        """데이터 유효성 검사"""
        return (
            (self.usd_krw is None or 1000 <= self.usd_krw <= 2000) and  # 합리적인 환율 범위
            (self.usdt_krw is None or 1000 <= self.usdt_krw <= 2000) and
            time.time() - self.timestamp < 600  # 10분 이내 데이터만 유효
        )

class ThreadSafeSharedData:
    """Thread-safe한 공유 데이터 저장소"""
    
    def __init__(self, max_history: int = 100):
        self._lock = threading.RLock()
        self.max_history = max_history
        
        # 거래소별 티커 데이터
        self._upbit_tickers: Dict[str, TickerData] = {}
        self._binance_tickers: Dict[str, TickerData] = {}
        self._bybit_tickers: Dict[str, TickerData] = {}
        
        # 환율 데이터
        self._exchange_rates = ExchangeRateData()
        
        # 통계 정보
        self._stats = {
            "upbit_updates": 0,
            "binance_updates": 0,
            "bybit_updates": 0,
            "exchange_rate_updates": 0,
            "last_update": time.time()
        }
        
        # 성능 모니터링
        self._update_history: deque = deque(maxlen=max_history)
        
    def update_upbit_ticker(self, symbol: str, ticker: TickerData) -> bool:
        """Upbit 티커 데이터 업데이트"""
        if not ticker.is_valid():
            logger.warning(f"유효하지 않은 Upbit 티커 데이터: {symbol}")
            return False
            
        with self._lock:
            self._upbit_tickers[symbol] = ticker
            self._stats["upbit_updates"] += 1
            self._stats["last_update"] = time.time()
            self._update_history.append(("upbit", symbol, time.time()))
            return True
    
    def update_binance_ticker(self, symbol: str, ticker: TickerData) -> bool:
        """Binance 티커 데이터 업데이트"""
        if not ticker.is_valid():
            logger.warning(f"유효하지 않은 Binance 티커 데이터: {symbol}")
            return False
            
        with self._lock:
            self._binance_tickers[symbol] = ticker
            self._stats["binance_updates"] += 1
            self._stats["last_update"] = time.time()
            self._update_history.append(("binance", symbol, time.time()))
            return True
    
    def update_bybit_ticker(self, symbol: str, ticker: TickerData) -> bool:
        """Bybit 티커 데이터 업데이트"""
        if not ticker.is_valid():
            logger.warning(f"유효하지 않은 Bybit 티커 데이터: {symbol}")
            return False
            
        with self._lock:
            self._bybit_tickers[symbol] = ticker
            self._stats["bybit_updates"] += 1
            self._stats["last_update"] = time.time()
            self._update_history.append(("bybit", symbol, time.time()))
            return True
    
    def update_exchange_rates(self, rates: ExchangeRateData) -> bool:
        """환율 데이터 업데이트"""
        if not rates.is_valid():
            logger.warning("유효하지 않은 환율 데이터")
            return False
            
        with self._lock:
            self._exchange_rates = rates
            self._stats["exchange_rate_updates"] += 1
            self._stats["last_update"] = time.time()
            return True
    
    def get_all_data(self) -> Dict:
        """모든 데이터를 안전하게 복사해서 반환"""
        with self._lock:
            return {
                "upbit_tickers": dict(self._upbit_tickers),
                "binance_tickers": dict(self._binance_tickers),
                "bybit_tickers": dict(self._bybit_tickers),
                "exchange_rates": self._exchange_rates,
                "stats": dict(self._stats)
            }
    
    def cleanup_expired_data(self, max_age: float = 300) -> int:
        """만료된 데이터 정리 (5분 이상 된 데이터)"""
        current_time = time.time()
        removed_count = 0
        
        with self._lock:
            # Upbit 데이터 정리
            expired_symbols = [
                symbol for symbol, ticker in self._upbit_tickers.items()
                if current_time - ticker.timestamp > max_age
            ]
            for symbol in expired_symbols:
                del self._upbit_tickers[symbol]
                removed_count += 1
                
            # Binance 데이터 정리
            expired_symbols = [
                symbol for symbol, ticker in self._binance_tickers.items()
                if current_time - ticker.timestamp > max_age
            ]
            for symbol in expired_symbols:
                del self._binance_tickers[symbol]
                removed_count += 1
                
            # Bybit 데이터 정리
            expired_symbols = [
                symbol for symbol, ticker in self._bybit_tickers.items()
                if current_time - ticker.timestamp > max_age
            ]
            for symbol in expired_symbols:
                del self._bybit_tickers[symbol]
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"만료된 데이터 {removed_count}개 정리 완료")
            
        return removed_count
    
    def get_stats(self) -> Dict:
        """통계 정보 반환"""
        with self._lock:
            current_time = time.time()
            
            # 최근 1분간 업데이트 횟수 계산
            recent_updates = sum(
                1 for _, _, timestamp in self._update_history
                if current_time - timestamp <= 60
            )
            
            return {
                **self._stats,
                "upbit_tickers_count": len(self._upbit_tickers),
                "binance_tickers_count": len(self._binance_tickers),
                "bybit_tickers_count": len(self._bybit_tickers),
                "recent_updates_per_minute": recent_updates,
                "data_age_seconds": current_time - self._stats["last_update"]
            }

# 전역 공유 데이터 인스턴스
shared_data = ThreadSafeSharedData()

# --- WebSocket 클라이언트 구현 ---

class UpbitWebSocketClient:
    """개선된 Upbit WebSocket 클라이언트"""
    
    def __init__(self):
        self.client = EnhancedWebSocketClient(
            uri="wss://api.upbit.com/websocket/v1",
            name="Upbit",
            max_retries=20,
            initial_retry_delay=2.0,
            max_retry_delay=120.0
        )
        self.subscribed_symbols: Set[str] = set()
        
        # 콜백 함수 설정
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_error = self._on_error
    
    async def _on_connect(self):
        """연결 성공 시 처리"""
        logger.info("Upbit WebSocket 연결 성공, 마켓 구독 시작")
        await self._subscribe_markets()
    
    async def _on_message(self, data: Dict):
        """메시지 수신 시 처리"""
        try:
            if data.get("type") == "ticker":
                symbol = data["code"].replace("KRW-", "")
                
                ticker = TickerData(
                    symbol=symbol,
                    price=float(data["trade_price"]),
                    volume=float(data.get("acc_trade_price_24h", 0)),
                    change_percent=float(data.get("signed_change_rate", 0)) * 100
                )
                
                shared_data.update_upbit_ticker(symbol, ticker)
                
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Upbit 데이터 파싱 오류: {e}")
    
    async def _on_error(self, error: Exception):
        """오류 발생 시 처리"""
        logger.error(f"Upbit WebSocket 오류: {error}")
    
    async def _subscribe_markets(self):
        """KRW 마켓 구독"""
        try:
            krw_markets = get_upbit_krw_markets()
            if not krw_markets:
                logger.error("Upbit KRW 마켓 목록을 가져올 수 없습니다")
                return
                
            subscribe_message = [
                {"ticket": str(uuid.uuid4())},
                {"type": "ticker", "codes": [f"KRW-{symbol}" for symbol in krw_markets]}
            ]
            
            success = await self.client.send_message(json.dumps(subscribe_message))
            if success:
                self.subscribed_symbols = set(krw_markets)
                logger.info(f"Upbit {len(krw_markets)}개 마켓 구독 완료")
            else:
                logger.error("Upbit 마켓 구독 실패")
                
        except Exception as e:
            logger.error(f"Upbit 마켓 구독 중 오류: {e}")
    
    async def run(self):
        """WebSocket 클라이언트 실행"""
        await self.client.run_with_retry()

class BinanceWebSocketClient:
    """개선된 Binance WebSocket 클라이언트"""
    
    def __init__(self):
        self.client = EnhancedWebSocketClient(
            uri="wss://stream.binance.com:9443/ws/!ticker@arr",
            name="Binance",
            max_retries=20,
            initial_retry_delay=2.0,
            max_retry_delay=120.0
        )
        
        # 콜백 함수 설정
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_error = self._on_error
    
    async def _on_connect(self):
        """연결 성공 시 처리"""
        logger.info("Binance WebSocket 연결 성공")
    
    async def _on_message(self, data: List):
        """메시지 수신 시 처리"""
        try:
            if isinstance(data, list):
                for ticker_data in data:
                    symbol = ticker_data["s"].replace("USDT", "")
                    
                    # USDT 페어만 처리
                    if not ticker_data["s"].endswith("USDT"):
                        continue
                    
                    ticker = TickerData(
                        symbol=symbol,
                        price=float(ticker_data["c"]),
                        volume=float(ticker_data["q"]),  # Quote asset volume (USDT)
                        change_percent=float(ticker_data["P"])
                    )
                    
                    shared_data.update_binance_ticker(symbol, ticker)
                    
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Binance 데이터 파싱 오류: {e}")
    
    async def _on_error(self, error: Exception):
        """오류 발생 시 처리"""
        logger.error(f"Binance WebSocket 오류: {error}")
    
    async def run(self):
        """WebSocket 클라이언트 실행"""
        await self.client.run_with_retry()

# --- 환율 및 기타 데이터 수집 ---

async def fetch_exchange_rates_periodically():
    """환율 데이터 주기적 수집"""
    while True:
        try:
            # USD/KRW 환율 (네이버 금융)
            usd_krw = await _fetch_usd_krw_rate()
            
            # USDT/KRW 환율 (업비트)
            usdt_krw = await _fetch_usdt_krw_rate()
            
            rates = ExchangeRateData(
                usd_krw=usd_krw,
                usdt_krw=usdt_krw
            )
            
            if shared_data.update_exchange_rates(rates):
                logger.info(f"환율 업데이트: USD/KRW={usd_krw}, USDT/KRW={usdt_krw}")
            
        except Exception as e:
            logger.error(f"환율 조회 중 오류: {e}")
        
        await asyncio.sleep(60)  # 1분마다 업데이트

async def _fetch_usd_krw_rate() -> Optional[float]:
    """USD/KRW 환율 조회"""
    try:
        url = "https://finance.naver.com/marketindex/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                element = soup.select_one("#exchangeList > li.on > a.head.usd > div > span.value")
                if element:
                    return float(element.text.replace(',', ''))
                return None
    except Exception as e:
        logger.error(f"USD/KRW 환율 조회 오류: {e}")
        return None

async def _fetch_usdt_krw_rate() -> Optional[float]:
    """USDT/KRW 환율 조회"""
    try:
        url = "https://api.upbit.com/v1/ticker?markets=KRW-USDT"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if data:
                    return float(data[0]["trade_price"])
                return None
    except Exception as e:
        logger.error(f"USDT/KRW 환율 조회 오류: {e}")
        return None

async def cleanup_expired_data_periodically():
    """만료된 데이터 정기 정리"""
    while True:
        try:
            removed = shared_data.cleanup_expired_data()
            if removed > 0:
                logger.info(f"데이터 정리 완료: {removed}개 항목 제거")
        except Exception as e:
            logger.error(f"데이터 정리 중 오류: {e}")
        
        await asyncio.sleep(300)  # 5분마다 정리

# --- 기존 호환성을 위한 함수들 ---

def get_upbit_krw_markets() -> List[str]:
    """Upbit KRW 마켓 목록 조회"""
    try:
        url = "https://api.upbit.com/v1/market/all"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        krw_markets = [
            item['market'] for item in data 
            if item['market'].startswith('KRW-')
        ]
        return [market.split('-')[1] for market in krw_markets if market != 'KRW-USDT']
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Upbit KRW 마켓 목록 조회 오류: {e}")
        return []

def get_fear_greed_index() -> Optional[Dict]:
    """공포/탐욕 지수 조회"""
    try:
        url = "https://api.alternative.me/fng/"
        params = {"limit": 1, "format": "json"}
        response = requests.get(url, params=params, timeout=10)
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

# --- 메인 실행 함수들 ---

async def start_optimized_services():
    """최적화된 서비스 시작"""
    logger.info("최적화된 데이터 수집 서비스 시작")
    
    # WebSocket 클라이언트들 생성
    upbit_client = UpbitWebSocketClient()
    binance_client = BinanceWebSocketClient()
    
    # 백그라운드 태스크들
    tasks = [
        asyncio.create_task(upbit_client.run()),
        asyncio.create_task(binance_client.run()),
        asyncio.create_task(fetch_exchange_rates_periodically()),
        asyncio.create_task(cleanup_expired_data_periodically())
    ]
    
    logger.info("모든 백그라운드 서비스 시작 완료")
    
    # 모든 태스크가 완료될 때까지 대기
    await asyncio.gather(*tasks, return_exceptions=True)