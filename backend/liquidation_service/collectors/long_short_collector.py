"""Long/Short Ratio Data Collector

바이낸스, 비트겟 등 거래소 API에서 롱숏 비율 데이터를 수집
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import json

from models.data_schemas import LongShortRatio, Exchange, TimeInterval
from utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class LongShortCollector:
    """롱숏 비율 데이터 수집기"""
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.redis_cache = redis_cache
        self.session: Optional[aiohttp.ClientSession] = None
        
        # API 엔드포인트 설정
        self.api_endpoints = {
            Exchange.BINANCE: {
                "base_url": "https://fapi.binance.com",
                "endpoints": {
                    "longShortRatio": "/futures/data/globalLongShortAccountRatio",
                    "topLongShortAccountRatio": "/futures/data/topLongShortAccountRatio", 
                    "topLongShortPositionRatio": "/futures/data/topLongShortPositionRatio"
                }
            },
            Exchange.BITGET: {
                "base_url": "https://api.bitget.com",
                "endpoints": {
                    "longShortRatio": "/api/v2/mix/market/long-short"
                }
            }
        }
        
        # 지원되는 심볼 목록 (주요 암호화폐)
        self.symbols = [
            "BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOGEUSDT",
            "LINKUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT"
        ]
        
        # 요청 제한 관리
        self.request_limits = {
            Exchange.BINANCE: {"requests_per_minute": 1200, "weight_per_minute": 6000},
            Exchange.BITGET: {"requests_per_minute": 600, "weight_per_minute": 3000}
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "ArbitrageWebsite/2.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def collect_binance_long_short_ratio(
        self, 
        symbol: str,
        period: str = "1d",
        limit: int = 30
    ) -> List[LongShortRatio]:
        """바이낸스 롱숏 비율 수집"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        results = []
        base_url = self.api_endpoints[Exchange.BINANCE]["base_url"]
        
        # 일반 계정 기반 롱숏 비율
        try:
            endpoint = self.api_endpoints[Exchange.BINANCE]["endpoints"]["longShortRatio"]
            params = {
                "symbol": symbol,
                "period": period,
                "limit": limit
            }
            
            url = f"{base_url}{endpoint}"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for item in data:
                        ratio_data = LongShortRatio(
                            exchange=Exchange.BINANCE,
                            symbol=symbol,
                            timestamp=datetime.fromtimestamp(int(item["timestamp"]) / 1000),
                            interval=self._convert_period_to_interval(period),
                            long_ratio=float(item["longAccount"]) / (float(item["longAccount"]) + float(item["shortAccount"])),
                            short_ratio=float(item["shortAccount"]) / (float(item["longAccount"]) + float(item["shortAccount"])),
                            long_short_ratio=float(item["longShortRatio"]),
                            account_based=True,
                            top_traders_only=False,
                            total_accounts=None,
                            total_position_value=None
                        )
                        results.append(ratio_data)
                else:
                    logger.error(f"Binance API error for {symbol}: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error collecting Binance long/short ratio for {symbol}: {e}")
        
        # 상위 트레이더 계정 기반 비율
        try:
            endpoint = self.api_endpoints[Exchange.BINANCE]["endpoints"]["topLongShortAccountRatio"]
            params = {
                "symbol": symbol,
                "period": period,
                "limit": limit
            }
            
            url = f"{base_url}{endpoint}"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for item in data:
                        ratio_data = LongShortRatio(
                            exchange=Exchange.BINANCE,
                            symbol=symbol,
                            timestamp=datetime.fromtimestamp(int(item["timestamp"]) / 1000),
                            interval=self._convert_period_to_interval(period),
                            long_ratio=float(item["longAccount"]) / (float(item["longAccount"]) + float(item["shortAccount"])),
                            short_ratio=float(item["shortAccount"]) / (float(item["longAccount"]) + float(item["shortAccount"])),
                            long_short_ratio=float(item["longShortRatio"]),
                            account_based=True,
                            top_traders_only=True,
                            total_accounts=None,
                            total_position_value=None
                        )
                        results.append(ratio_data)
                        
        except Exception as e:
            logger.error(f"Error collecting Binance top traders ratio for {symbol}: {e}")
        
        return results
    
    async def collect_bitget_long_short_ratio(
        self,
        symbol: str,
        period: str = "1D",
        limit: int = 30
    ) -> List[LongShortRatio]:
        """비트겟 롱숏 비율 수집"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        results = []
        base_url = self.api_endpoints[Exchange.BITGET]["base_url"]
        endpoint = self.api_endpoints[Exchange.BITGET]["endpoints"]["longShortRatio"]
        
        try:
            params = {
                "symbol": symbol,
                "granularity": period,
                "limit": limit
            }
            
            url = f"{base_url}{endpoint}"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()
                    
                    if response_data.get("code") == "00000" and "data" in response_data:
                        for item in response_data["data"]:
                            # Bitget 응답 구조에 맞게 파싱
                            long_ratio = float(item.get("longRatio", 0))
                            short_ratio = float(item.get("shortRatio", 0))
                            
                            if long_ratio + short_ratio > 0:
                                ratio_data = LongShortRatio(
                                    exchange=Exchange.BITGET,
                                    symbol=symbol,
                                    timestamp=datetime.fromtimestamp(int(item["timestamp"]) / 1000),
                                    interval=self._convert_period_to_interval(period),
                                    long_ratio=long_ratio / (long_ratio + short_ratio),
                                    short_ratio=short_ratio / (long_ratio + short_ratio),
                                    long_short_ratio=long_ratio / short_ratio if short_ratio > 0 else 0,
                                    account_based=True,
                                    top_traders_only=False,
                                    total_accounts=None,
                                    total_position_value=None
                                )
                                results.append(ratio_data)
                else:
                    logger.error(f"Bitget API error for {symbol}: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error collecting Bitget long/short ratio for {symbol}: {e}")
        
        return results
    
    async def collect_all_long_short_ratios(
        self,
        symbols: Optional[List[str]] = None,
        period: str = "1d"
    ) -> Dict[str, List[LongShortRatio]]:
        """모든 거래소에서 롱숏 비율 수집"""
        if symbols is None:
            symbols = self.symbols
        
        all_results = {}
        
        # 바이낸스에서 수집
        for symbol in symbols:
            try:
                binance_data = await self.collect_binance_long_short_ratio(symbol, period)
                if symbol not in all_results:
                    all_results[symbol] = []
                all_results[symbol].extend(binance_data)
                
                # API 레이트 리미트 준수
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error collecting Binance data for {symbol}: {e}")
        
        # 비트겟에서 수집 (기간 형식 변환 필요)
        bitget_period = "1D" if period == "1d" else period.upper()
        for symbol in symbols:
            try:
                bitget_data = await self.collect_bitget_long_short_ratio(symbol, bitget_period)
                if symbol not in all_results:
                    all_results[symbol] = []
                all_results[symbol].extend(bitget_data)
                
                # API 레이트 리미트 준수
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error collecting Bitget data for {symbol}: {e}")
        
        # Redis에 캐싱
        if self.redis_cache:
            try:
                await self._cache_results(all_results)
            except Exception as e:
                logger.error(f"Error caching results: {e}")
        
        return all_results
    
    async def get_latest_long_short_ratio(self, symbol: str) -> Optional[Dict[Exchange, LongShortRatio]]:
        """특정 심볼의 최신 롱숏 비율 조회"""
        # 먼저 캐시에서 확인
        if self.redis_cache:
            try:
                cached_data = await self.redis_cache.get(f"long_short_latest:{symbol}")
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logger.error(f"Error reading from cache: {e}")
        
        # 캐시에 없으면 실시간 수집
        results = await self.collect_all_long_short_ratios([symbol], "5m")
        if symbol in results and results[symbol]:
            latest_by_exchange = {}
            for ratio in results[symbol]:
                if ratio.exchange not in latest_by_exchange or ratio.timestamp > latest_by_exchange[ratio.exchange].timestamp:
                    latest_by_exchange[ratio.exchange] = ratio
            
            return latest_by_exchange
        
        return None
    
    def _convert_period_to_interval(self, period: str) -> TimeInterval:
        """기간 문자열을 TimeInterval enum으로 변환"""
        period_mapping = {
            "5m": TimeInterval.FIVE_MIN,
            "15m": TimeInterval.FIFTEEN_MIN,
            "30m": TimeInterval.THIRTY_MIN,
            "1h": TimeInterval.ONE_HOUR,
            "4h": TimeInterval.FOUR_HOUR,
            "1d": TimeInterval.ONE_DAY,
            "1D": TimeInterval.ONE_DAY,
        }
        return period_mapping.get(period, TimeInterval.ONE_DAY)
    
    async def _cache_results(self, results: Dict[str, List[LongShortRatio]]):
        """결과를 Redis에 캐싱"""
        if not self.redis_cache:
            return
        
        for symbol, ratios in results.items():
            if ratios:
                # 최신 데이터만 별도 캐싱
                latest_by_exchange = {}
                for ratio in ratios:
                    if ratio.exchange not in latest_by_exchange or ratio.timestamp > latest_by_exchange[ratio.exchange].timestamp:
                        latest_by_exchange[ratio.exchange] = ratio
                
                # 최신 데이터 캐싱 (5분 TTL)
                cache_key = f"long_short_latest:{symbol}"
                cache_data = {
                    exchange.value: ratio.dict() 
                    for exchange, ratio in latest_by_exchange.items()
                }
                await self.redis_cache.set(cache_key, json.dumps(cache_data, default=str), ttl=300)
                
                # 전체 히스토리 캐싱 (1시간 TTL)
                history_key = f"long_short_history:{symbol}"
                history_data = [ratio.dict() for ratio in ratios]
                await self.redis_cache.set(history_key, json.dumps(history_data, default=str), ttl=3600)


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)
    
    async with LongShortCollector() as collector:
        # BTC 롱숏 비율 수집 테스트
        results = await collector.collect_all_long_short_ratios(["BTCUSDT"], "1d")
        
        for symbol, ratios in results.items():
            print(f"\\n{symbol} Long/Short Ratios:")
            for ratio in ratios[:3]:  # 최신 3개만 출력
                print(f"  {ratio.exchange.value}: {ratio.long_short_ratio:.4f} "
                      f"(Long: {ratio.long_ratio:.2%}, Short: {ratio.short_ratio:.2%}) "
                      f"at {ratio.timestamp}")


if __name__ == "__main__":
    asyncio.run(main())