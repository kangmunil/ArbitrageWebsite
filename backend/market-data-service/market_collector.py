"""
Market Data Collector - 시장 데이터 수집기

거래소별 가격, 거래량, 변화율 데이터를 수집합니다.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional, Set
import aiohttp
import redis.asyncio as redis
from bs4 import BeautifulSoup
try:
    import websockets.legacy.client as websockets_client
    websockets_connect = websockets_client.connect
except ImportError:
    try:
        from websockets import connect as websockets_connect  # type: ignore
    except ImportError:
        # websockets 라이브러리가 설치되지 않은 경우
        websockets_connect = None

from shared_data import SharedMarketData

logger = logging.getLogger(__name__)

class MarketDataCollector:
    """시장 데이터 수집기 클래스"""
    
    def __init__(self):
        self.is_running = False
        self.redis_client: Optional[redis.Redis] = None
        self.shared_data = SharedMarketData()
        
        # 연결 상태 추적
        self.connection_status = {
            "upbit": False,
            "binance": False,
            "bybit": False,
            "bithumb": False
        }
        
        # 수집 통계
        self.stats = {
            "upbit": {"messages": 0, "errors": 0, "last_update": None},
            "binance": {"messages": 0, "errors": 0, "last_update": None},
            "bybit": {"messages": 0, "errors": 0, "last_update": None},
            "bithumb": {"messages": 0, "errors": 0, "last_update": None}
        }
    
    def set_redis_client(self, redis_client: Optional[redis.Redis]):
        """Redis 클라이언트 설정"""
        self.redis_client = redis_client
        self.shared_data.set_redis_client(redis_client)
    
    async def start_collection(self):
        """데이터 수집 시작"""
        if self.is_running:
            logger.warning("데이터 수집이 이미 실행 중입니다.")
            return
        
        self.is_running = True
        logger.info("📊 시장 데이터 수집 시작")
        
        # 모든 수집 태스크 병렬 실행
        tasks = [
            self.collect_upbit_data(),
            self.collect_binance_data(),
            self.collect_bybit_data(),
            self.collect_bithumb_data(),
            self.collect_exchange_rates(),
        ]
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"데이터 수집 중 오류: {e}")
    
    async def stop_collection(self):
        """데이터 수집 중지"""
        self.is_running = False
        logger.info("⏹️ 시장 데이터 수집 중지")
    
    # === Upbit WebSocket ===
    async def collect_upbit_data(self):
        """업비트 WebSocket 데이터 수집"""
        while self.is_running:
            try:
                if websockets_connect is None:
                    logger.error("websockets 라이브러리가 설치되지 않았습니다.")
                    await asyncio.sleep(30)
                    continue
                    
                logger.info("🟡 업비트 WebSocket 연결 시도")
                
                # KRW 마켓 목록 가져오기
                krw_markets = await self.get_upbit_krw_markets()
                if not krw_markets:
                    logger.error("업비트 KRW 마켓 목록을 가져올 수 없습니다.")
                    await asyncio.sleep(10)
                    continue
                
                uri = "wss://api.upbit.com/websocket/v1"
                async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    # 구독 메시지 전송
                    subscribe_message = [
                        {"ticket": str(uuid.uuid4())},
                        {"type": "ticker", "codes": [f"KRW-{symbol}" for symbol in krw_markets]}
                    ]
                    await websocket.send(json.dumps(subscribe_message))
                    
                    self.connection_status["upbit"] = True
                    logger.info(f"✅ 업비트 WebSocket 연결 성공 ({len(krw_markets)}개 마켓)")
                    
                    async for message in websocket:
                        if not self.is_running:
                            break
                        
                        try:
                            data = json.loads(message)
                            await self.process_upbit_message(data)
                            
                        except Exception as e:
                            self.stats["upbit"]["errors"] += 1
                            logger.error(f"업비트 메시지 처리 오류: {e}")
                            
            except Exception as e:
                self.connection_status["upbit"] = False
                logger.error(f"업비트 WebSocket 오류: {e}")
                await asyncio.sleep(5)
    
    async def process_upbit_message(self, data: dict):
        """업비트 메시지 처리"""
        try:
            symbol = data['code'].replace('KRW-', '')
            
            ticker_data = {
                "price": data['trade_price'],
                "volume": data['acc_trade_price_24h'],  # KRW 거래대금
                "change_percent": data['signed_change_rate'] * 100
            }
            
            await self.shared_data.update_upbit_data(symbol, ticker_data)
            
            self.stats["upbit"]["messages"] += 1
            self.stats["upbit"]["last_update"] = datetime.now().isoformat()
            
            if symbol == 'BTC':
                logger.info(f"📈 업비트 BTC: {ticker_data['price']:,.0f} KRW")
                
        except Exception as e:
            logger.error(f"업비트 메시지 처리 오류: {e}, 데이터: {data}")
    
    async def get_upbit_krw_markets(self) -> Set[str]:
        """업비트 KRW 마켓 목록 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.upbit.com/v1/market/all") as response:
                    if response.status == 200:
                        data = await response.json()
                        krw_markets = {
                            item['market'].replace('KRW-', '') 
                            for item in data 
                            if item['market'].startswith('KRW-') and item['market'] != 'KRW-USDT'
                        }
                        return krw_markets
        except Exception as e:
            logger.error(f"업비트 마켓 목록 조회 오류: {e}")
        return set()
    
    # === Binance WebSocket ===
    async def collect_binance_data(self):
        """바이낸스 WebSocket 데이터 수집"""
        while self.is_running:
            try:
                if websockets_connect is None:
                    logger.error("websockets 라이브러리가 설치되지 않았습니다.")
                    await asyncio.sleep(30)
                    continue
                    
                logger.info("🟡 바이낸스 WebSocket 연결 시도")
                
                uri = "wss://stream.binance.com:9443/ws/!ticker@arr"
                async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    self.connection_status["binance"] = True
                    logger.info("✅ 바이낸스 WebSocket 연결 성공")
                    
                    async for message in websocket:
                        if not self.is_running:
                            break
                        
                        try:
                            data = json.loads(message)
                            await self.process_binance_message(data)
                            
                        except Exception as e:
                            self.stats["binance"]["errors"] += 1
                            logger.error(f"바이낸스 메시지 처리 오류: {e}")
                            
            except Exception as e:
                self.connection_status["binance"] = False
                logger.error(f"바이낸스 WebSocket 오류: {e}")
                await asyncio.sleep(5)
    
    async def process_binance_message(self, data: list):
        """바이낸스 메시지 처리"""
        try:
            for ticker in data:
                if ticker['s'].endswith('USDT'):
                    symbol = ticker['s'].replace('USDT', '')
                    
                    ticker_data = {
                        "price": float(ticker['c']),
                        "volume": float(ticker['q']),  # USDT 거래대금
                        "change_percent": float(ticker['P'])
                    }
                    
                    await self.shared_data.update_binance_data(symbol, ticker_data)
                    
                    if symbol == 'BTC':
                        logger.info(f"📊 바이낸스 BTC: ${ticker_data['price']:,.2f}")
            
            self.stats["binance"]["messages"] += 1
            self.stats["binance"]["last_update"] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"바이낸스 메시지 처리 오류: {e}")
    
    # === Bybit REST API ===
    async def collect_bybit_data(self):
        """바이비트 REST API 데이터 수집"""
        while self.is_running:
            try:
                url = "https://api.bybit.com/v5/market/tickers"
                params = {"category": "spot"}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            await self.process_bybit_message(data)
                            self.connection_status["bybit"] = True
                        else:
                            self.connection_status["bybit"] = False
                            logger.warning(f"바이비트 API 응답 오류: {response.status}")
                
                await asyncio.sleep(5)  # 5초마다 업데이트
                
            except Exception as e:
                self.connection_status["bybit"] = False
                self.stats["bybit"]["errors"] += 1
                logger.error(f"바이비트 REST API 오류: {e}")
                await asyncio.sleep(10)
    
    async def process_bybit_message(self, data: dict):
        """바이비트 메시지 처리"""
        try:
            if data.get('retCode') == 0 and data.get('result') and data['result'].get('list'):
                ticker_list = data['result']['list']
                
                # 주요 USDT 페어만 처리
                major_symbols = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'ADAUSDT', 
                               'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT', 'UNIUSDT']
                
                for ticker_data in ticker_list:
                    symbol_full = ticker_data.get('symbol', '')
                    if symbol_full in major_symbols:
                        symbol = symbol_full.replace('USDT', '')
                        
                        ticker_info = {
                            "price": float(ticker_data['lastPrice']),
                            "volume": float(ticker_data['turnover24h']),  # USDT 거래대금
                            "change_percent": float(ticker_data['price24hPcnt']) * 100
                        }
                        
                        await self.shared_data.update_bybit_data(symbol, ticker_info)
                
                # 실제 업데이트된 코인 수 계산
                updated_symbols = []
                for ticker_data in ticker_list:
                    symbol_full = ticker_data.get('symbol', '')
                    if symbol_full in major_symbols:
                        updated_symbols.append(symbol_full.replace('USDT', ''))
                
                self.stats["bybit"]["messages"] += 1
                self.stats["bybit"]["last_update"] = datetime.now().isoformat()
                logger.info(f"📊 바이비트 데이터 업데이트: {len(updated_symbols)}개 코인 - {', '.join(updated_symbols[:5])}")
                
        except Exception as e:
            logger.error(f"바이비트 메시지 처리 오류: {e}")
    
    # === Bithumb REST API ===
    async def collect_bithumb_data(self):
        """빗썸 REST API 데이터 수집"""
        while self.is_running:
            try:
                url = "https://api.bithumb.com/public/ticker/ALL_KRW"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            await self.process_bithumb_message(data)
                            self.connection_status["bithumb"] = True
                        else:
                            self.connection_status["bithumb"] = False
                            logger.warning(f"빗썸 API 응답 오류: {response.status}")
                
                await asyncio.sleep(3)  # 3초마다 업데이트
                
            except Exception as e:
                self.connection_status["bithumb"] = False
                self.stats["bithumb"]["errors"] += 1
                logger.error(f"빗썸 REST API 오류: {e}")
                await asyncio.sleep(10)
    
    async def process_bithumb_message(self, data: dict):
        """빗썸 메시지 처리"""
        try:
            if data['status'] == '0000':  # 성공
                ticker_data = data['data']
                
                # 각 코인별로 데이터 처리
                processed_count = 0
                for symbol, coin_data in ticker_data.items():
                    if symbol != 'date':
                        try:
                            ticker_info = {
                                "price": float(coin_data['closing_price']),
                                "volume": float(coin_data['acc_trade_value_24H']),  # KRW 거래대금
                                "change_percent": float(coin_data['fluctate_rate_24H'])
                            }
                            
                            await self.shared_data.update_bithumb_data(symbol, ticker_info)
                            processed_count += 1
                            
                        except (ValueError, KeyError) as e:
                            logger.warning(f"빗썸 데이터 파싱 오류 ({symbol}): {e}")
                            continue
                
                self.stats["bithumb"]["messages"] += 1
                self.stats["bithumb"]["last_update"] = datetime.now().isoformat()
                logger.info(f"📊 빗썸 데이터 업데이트: {processed_count}개 코인")
                
        except Exception as e:
            logger.error(f"빗썸 메시지 처리 오류: {e}")
    
    # === Exchange Rates ===
    async def collect_exchange_rates(self):
        """환율 정보 수집"""
        while self.is_running:
            try:
                # USD/KRW 환율 (네이버 금융)
                await self.fetch_usd_krw_rate()
                
                # USDT/KRW 환율 (업비트)
                await self.fetch_usdt_krw_rate()
                
                await asyncio.sleep(60)  # 1분마다 환율 업데이트
                
            except Exception as e:
                logger.error(f"환율 수집 오류: {e}")
                await asyncio.sleep(30)
    
    async def fetch_usd_krw_rate(self):
        """USD/KRW 환율 수집"""
        try:
            url = "https://finance.naver.com/marketindex/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'lxml')
                        rate_element = soup.select_one("#exchangeList > li.on > a.head.usd > div > span.value")
                        if rate_element:
                            usd_krw_rate = float(rate_element.text.replace(',', ''))
                            await self.shared_data.update_exchange_rate("USD_KRW", usd_krw_rate)
                            logger.info(f"💱 USD/KRW 환율: {usd_krw_rate:,.2f}")
                        else:
                            logger.warning("USD/KRW 환율 정보를 찾을 수 없습니다.")
        except Exception as e:
            logger.error(f"USD/KRW 환율 수집 오류: {e}")
    
    async def fetch_usdt_krw_rate(self):
        """USDT/KRW 환율 수집"""
        try:
            url = "https://api.upbit.com/v1/ticker?markets=KRW-USDT"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            usdt_krw_rate = data[0]['trade_price']
                            await self.shared_data.update_exchange_rate("USDT_KRW", usdt_krw_rate)
                            logger.info(f"💱 USDT/KRW 환율: {usdt_krw_rate:,.2f}")
        except Exception as e:
            logger.error(f"USDT/KRW 환율 수집 오류: {e}")
    
    # === Utility Methods ===
    def get_connection_status(self, exchange: str) -> bool:
        """거래소 연결 상태 조회"""
        return self.connection_status.get(exchange, False)
    
    def get_all_stats(self) -> Dict:
        """모든 수집기 통계 조회"""
        return {
            "connection_status": self.connection_status,
            "stats": self.stats,
            "is_running": self.is_running
        }