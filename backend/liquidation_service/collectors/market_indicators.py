"""Market Indicators Collector

미결제약정, 펀딩비율, 거래량 등 간접 지표 수집 (미래 구현 예정)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp

from ..models.data_schemas import MarketIndicator, Exchange
from ..utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class MarketIndicatorCollector:
    """시장 지표 수집기 (개발 중)"""
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.redis_cache = redis_cache
        self.session: Optional[aiohttp.ClientSession] = None
        
        # API 엔드포인트 설정
        self.api_endpoints = {
            Exchange.BINANCE: {
                "base_url": "https://fapi.binance.com",
                "endpoints": {
                    "openInterest": "/fapi/v1/openInterest",
                    "fundingRate": "/fapi/v1/fundingRate",
                    "ticker24hr": "/fapi/v1/ticker/24hr",
                    "premiumIndex": "/fapi/v1/premiumIndex"
                }
            },
            Exchange.BITGET: {
                "base_url": "https://api.bitget.com",
                "endpoints": {
                    "openInterest": "/api/v2/mix/market/open-interest",
                    "fundingRate": "/api/v2/mix/market/current-fund-rate",
                    "ticker24hr": "/api/v2/mix/market/ticker"
                }
            }
        }
        
        # 추적할 심볼 목록
        self.symbols = [
            "BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOGEUSDT",
            "LINKUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT"
        ]
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "MarketIndicatorCollector/2.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def collect_binance_indicators(self, symbol: str) -> Optional[MarketIndicator]:
        """바이낸스 시장 지표 수집"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        try:
            base_url = self.api_endpoints[Exchange.BINANCE]["base_url"]
            endpoints = self.api_endpoints[Exchange.BINANCE]["endpoints"]
            
            # 24시간 통계 수집
            ticker_url = f"{base_url}{endpoints['ticker24hr']}"
            ticker_params = {"symbol": symbol}
            
            async with self.session.get(ticker_url, params=ticker_params) as response:
                if response.status != 200:
                    logger.error(f"Binance ticker API error for {symbol}: {response.status}")
                    return None
                
                ticker_data = await response.json()
                
                # 미결제약정 수집
                oi_url = f"{base_url}{endpoints['openInterest']}"
                oi_params = {"symbol": symbol}
                
                oi_data = None
                async with self.session.get(oi_url, params=oi_params) as oi_response:
                    if oi_response.status == 200:
                        oi_data = await oi_response.json()
                
                # 펀딩비율 수집
                funding_url = f"{base_url}{endpoints['fundingRate']}"
                funding_params = {"symbol": symbol, "limit": 1}
                
                funding_data = None
                async with self.session.get(funding_url, params=funding_params) as funding_response:
                    if funding_response.status == 200:
                        funding_result = await funding_response.json()
                        if funding_result:
                            funding_data = funding_result[0]
                
                # MarketIndicator 객체 생성
                return MarketIndicator(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    price=float(ticker_data.get("lastPrice", 0)),
                    price_change_24h=float(ticker_data.get("priceChange", 0)),
                    price_change_percent_24h=float(ticker_data.get("priceChangePercent", 0)),
                    volume_24h=float(ticker_data.get("quoteVolume", 0)),
                    volume_change_percent_24h=0,  # 계산 필요
                    open_interest=float(oi_data.get("openInterest", 0)) if oi_data else None,
                    open_interest_change_24h=None,  # 계산 필요
                    funding_rate=float(funding_data.get("fundingRate", 0)) if funding_data else None,
                    volatility_24h=None,  # 계산 필요
                    atr_14=None  # 계산 필요
                )
        
        except Exception as e:
            logger.error(f"Error collecting Binance indicators for {symbol}: {e}")
            return None
    
    async def collect_bitget_indicators(self, symbol: str) -> Optional[MarketIndicator]:
        """비트겟 시장 지표 수집 (기본 구현)"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        try:
            base_url = self.api_endpoints[Exchange.BITGET]["base_url"]
            endpoints = self.api_endpoints[Exchange.BITGET]["endpoints"]
            
            # 24시간 통계 수집
            ticker_url = f"{base_url}{endpoints['ticker24hr']}"
            ticker_params = {"symbol": symbol, "productType": "usdt-futures"}
            
            async with self.session.get(ticker_url, params=ticker_params) as response:
                if response.status != 200:
                    logger.error(f"Bitget ticker API error for {symbol}: {response.status}")
                    return None
                
                response_data = await response.json()
                
                if response_data.get("code") != "00000" or not response_data.get("data"):
                    logger.error(f"Bitget API response error for {symbol}")
                    return None
                
                ticker_data = response_data["data"][0] if response_data["data"] else {}
                
                # 미결제약정 수집 (별도 API 호출 필요)
                oi_url = f"{base_url}{endpoints['openInterest']}"
                oi_params = {"symbol": symbol, "productType": "usdt-futures"}
                
                oi_value = None
                async with self.session.get(oi_url, params=oi_params) as oi_response:
                    if oi_response.status == 200:
                        oi_response_data = await oi_response.json()
                        if (oi_response_data.get("code") == "00000" and 
                            oi_response_data.get("data")):
                            oi_value = float(oi_response_data["data"].get("openInterest", 0))
                
                # 펀딩비율 수집
                funding_url = f"{base_url}{endpoints['fundingRate']}"
                funding_params = {"symbol": symbol, "productType": "usdt-futures"}
                
                funding_rate = None
                async with self.session.get(funding_url, params=funding_params) as funding_response:
                    if funding_response.status == 200:
                        funding_response_data = await funding_response.json()
                        if (funding_response_data.get("code") == "00000" and 
                            funding_response_data.get("data")):
                            funding_rate = float(funding_response_data["data"].get("fundingRate", 0))
                
                # MarketIndicator 객체 생성
                return MarketIndicator(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    price=float(ticker_data.get("lastPr", 0)),
                    price_change_24h=float(ticker_data.get("change", 0)),
                    price_change_percent_24h=float(ticker_data.get("changeUtc", 0)),
                    volume_24h=float(ticker_data.get("quoteVolume", 0)),
                    volume_change_percent_24h=0,  # 계산 필요
                    open_interest=oi_value,
                    open_interest_change_24h=None,  # 계산 필요
                    funding_rate=funding_rate,
                    volatility_24h=None,  # 계산 필요
                    atr_14=None  # 계산 필요
                )
        
        except Exception as e:
            logger.error(f"Error collecting Bitget indicators for {symbol}: {e}")
            return None
    
    async def collect_all_indicators(
        self, 
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Dict[Exchange, MarketIndicator]]:
        """모든 거래소에서 시장 지표 수집"""
        if symbols is None:
            symbols = self.symbols
        
        all_indicators = {}
        
        for symbol in symbols:
            symbol_indicators = {}
            
            # 바이낸스에서 수집
            try:
                binance_data = await self.collect_binance_indicators(symbol)
                if binance_data:
                    symbol_indicators[Exchange.BINANCE] = binance_data
                await asyncio.sleep(0.1)  # API 레이트 리미트 준수
            except Exception as e:
                logger.error(f"Error collecting Binance indicators for {symbol}: {e}")
            
            # 비트겟에서 수집
            try:
                bitget_data = await self.collect_bitget_indicators(symbol)
                if bitget_data:
                    symbol_indicators[Exchange.BITGET] = bitget_data
                await asyncio.sleep(0.1)  # API 레이트 리미트 준수
            except Exception as e:
                logger.error(f"Error collecting Bitget indicators for {symbol}: {e}")
            
            if symbol_indicators:
                all_indicators[symbol] = symbol_indicators
        
        # Redis에 캐싱
        if self.redis_cache:
            await self._cache_indicators(all_indicators)
        
        return all_indicators
    
    async def get_latest_indicators(self, symbol: str) -> Optional[Dict[Exchange, MarketIndicator]]:
        """특정 심볼의 최신 시장 지표 조회"""
        # 캐시에서 먼저 확인
        if self.redis_cache:
            cache_key = f"market_indicators:{symbol}"
            cached_data = await self.redis_cache.get_json(cache_key)
            if cached_data and isinstance(cached_data, dict):
                # JSON에서 MarketIndicator 객체로 복원
                indicators = {}
                for exchange_name, data in cached_data.items():
                    try:
                        exchange = Exchange(exchange_name)
                        indicators[exchange] = MarketIndicator(**data)
                    except Exception as e:
                        logger.error(f"Error restoring indicator data: {e}")
                return indicators
        
        # 캐시에 없으면 실시간 수집
        results = await self.collect_all_indicators([symbol])
        return results.get(symbol, {})
    
    async def _cache_indicators(self, indicators: Dict[str, Dict[Exchange, MarketIndicator]]):
        """시장 지표를 Redis에 캐싱"""
        if not self.redis_cache:
            return
        
        for symbol, exchange_indicators in indicators.items():
            cache_key = f"market_indicators:{symbol}"
            cache_data = {}
            
            for exchange, indicator in exchange_indicators.items():
                cache_data[exchange.value] = indicator.dict()
            
            # 10분 TTL로 캐싱
            await self.redis_cache.set(cache_key, cache_data, ttl=600)
    
    async def calculate_volatility(self, symbol: str, periods: int = 24) -> Optional[float]:
        """변동성 계산 (미구현)"""
        # TODO: 과거 가격 데이터를 이용한 변동성 계산
        return None
    
    async def calculate_atr(self, symbol: str, periods: int = 14) -> Optional[float]:
        """ATR(Average True Range) 계산 (미구현)"""
        # TODO: ATR 계산 로직 구현
        return None
    
    async def detect_volume_spikes(self, symbol: str, threshold: float = 2.0) -> bool:
        """거래량 급증 감지 (미구현)"""
        # TODO: 거래량 급증 감지 로직
        return False
    
    async def get_funding_rate_history(
        self, 
        symbol: str, 
        hours: int = 24
    ) -> List[Dict]:
        """펀딩비율 히스토리 조회 (미구현)"""
        # TODO: 과거 펀딩비율 데이터 수집 및 분석
        return []


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)
    
    async with MarketIndicatorCollector() as collector:
        # BTC 시장 지표 수집 테스트
        indicators = await collector.collect_all_indicators(["BTCUSDT"])
        
        if isinstance(indicators, dict):
            for symbol in indicators:
                exchange_data = indicators[symbol]
                print(f"\n{symbol} Market Indicators:")
                if isinstance(exchange_data, dict):
                    for exchange in exchange_data:
                        indicator = exchange_data[exchange]
                        print(f"  {exchange.value}:")
                        print(f"    Price: ${indicator.price:,.2f}")
                        print(f"    24h Change: {indicator.price_change_percent_24h:+.2f}%")
                        print(f"    Volume: ${indicator.volume_24h:,.0f}")
                        if indicator.open_interest:
                            print(f"    Open Interest: {indicator.open_interest:,.0f}")
                        if indicator.funding_rate:
                            print(f"    Funding Rate: {indicator.funding_rate:.6f}")



if __name__ == "__main__":
    asyncio.run(main())