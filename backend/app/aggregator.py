"""
Market Data Aggregator - 시장 데이터 집계기

Market Data Service와 Liquidation Service의 데이터를 통합하여 제공합니다.
"""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketDataAggregator:
    """시장 데이터 집계기 클래스"""
    
    def __init__(self, market_service_url: str, liquidation_service_url: str):
        self.market_service_url = market_service_url
        self.liquidation_service_url = liquidation_service_url
        
        # 캐시 설정
        self.cache = {}
        self.cache_ttl = 5  # 5초 캐시
        
    async def get_combined_market_data(self) -> List[Dict[str, Any]]:
        """Market Data Service에서 통합된 시장 데이터를 가져옵니다."""
        cache_key = "combined_market_data"
        
        # 캐시 확인
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.market_service_url}/api/market/combined"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success", True):
                            data = result.get("data", [])
                            
                            # 캐시 저장
                            self.cache[cache_key] = {
                                "data": data,
                                "timestamp": datetime.now().timestamp()
                            }
                            
                            logger.info(f"✅ Market Data Service에서 {len(data)}개 코인 데이터 수신")
                            return data
                    else:
                        logger.warning(f"Market Data Service 응답 오류: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("Market Data Service 타임아웃")
        except Exception as e:
            logger.error(f"Market Data Service 연결 오류: {e}")
        
        # 실패 시 빈 배열 반환
        return []
    
    async def get_market_prices(self) -> List[Dict[str, Any]]:
        """가격 데이터만 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.market_service_url}/api/market/prices"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("data", [])
        except Exception as e:
            logger.error(f"Market prices 조회 오류: {e}")
        
        return []
    
    async def get_market_volumes(self) -> List[Dict[str, Any]]:
        """거래량 데이터만 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.market_service_url}/api/market/volumes"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("data", [])
        except Exception as e:
            logger.error(f"Market volumes 조회 오류: {e}")
        
        return []
    
    async def get_market_premiums(self) -> List[Dict[str, Any]]:
        """김치 프리미엄 데이터만 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.market_service_url}/api/market/premiums"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("data", [])
        except Exception as e:
            logger.error(f"Market premiums 조회 오류: {e}")
        
        return []
    
    async def get_exchange_rates(self) -> Dict[str, Any]:
        """환율 정보 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.market_service_url}/api/market/exchange-rate"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("data", {})
        except Exception as e:
            logger.error(f"Exchange rates 조회 오류: {e}")
        
        return {}
    
    async def get_liquidation_data(self, limit: int = 60) -> List[Dict[str, Any]]:
        """청산 데이터 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.liquidation_service_url}/api/liquidations/aggregated?limit={limit}"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            logger.error(f"Liquidation data 조회 오류: {e}")
        
        return []
    
    async def get_fear_greed_index(self) -> Dict[str, Any]:
        """공포탐욕지수 가져오기 (기존 서비스 유지 또는 외부 API 직접 호출)"""
        try:
            # Alternative.me API 직접 호출
            async with aiohttp.ClientSession() as session:
                url = "https://api.alternative.me/fng/"
                params = {"limit": 1, "format": "json"}
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and data['data']:
                            latest_data = data['data'][0]
                            return {
                                "value": int(latest_data['value']),
                                "value_classification": latest_data['value_classification'],
                                "timestamp": latest_data['timestamp']
                            }
        except Exception as e:
            logger.error(f"공포탐욕지수 조회 오류: {e}")
        
        return {"error": "데이터를 가져올 수 없습니다"}
    
    async def get_service_health(self) -> Dict[str, Any]:
        """연결된 서비스들의 상태 확인"""
        health_status = {
            "market_service": {"status": "unknown", "url": self.market_service_url},
            "liquidation_service": {"status": "unknown", "url": self.liquidation_service_url}
        }
        
        # Market Data Service 상태 확인
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.market_service_url}/health"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        health_status["market_service"]["status"] = "healthy"
                        health_status["market_service"]["details"] = health_data
                    else:
                        health_status["market_service"]["status"] = "unhealthy"
        except Exception as e:
            health_status["market_service"]["status"] = "error"
            health_status["market_service"]["error"] = str(e)
        
        # Liquidation Service 상태 확인
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.liquidation_service_url}/health"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        health_status["liquidation_service"]["status"] = "healthy"
                        health_status["liquidation_service"]["details"] = health_data
                    else:
                        health_status["liquidation_service"]["status"] = "unhealthy"
        except Exception as e:
            health_status["liquidation_service"]["status"] = "error"
            health_status["liquidation_service"]["error"] = str(e)
        
        return health_status
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 확인"""
        if cache_key not in self.cache:
            return False
        
        cache_age = datetime.now().timestamp() - self.cache[cache_key]["timestamp"]
        return cache_age < self.cache_ttl
    
    def clear_cache(self):
        """캐시 초기화"""
        self.cache.clear()
        logger.info("집계기 캐시가 초기화되었습니다.")