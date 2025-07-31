"""
공통 헬스체크 유틸리티

모든 마이크로서비스에서 사용할 수 있는 표준화된 헬스체크 로직을 제공합니다.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
import aiohttp
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class HealthStatus:
    """헬스 상태 정의"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ServiceHealthChecker:
    """서비스 헬스체크 관리자"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.start_time = datetime.now()
        self.health_checks: Dict[str, Callable] = {}
        self.last_check_results: Dict[str, Dict[str, Any]] = {}
    
    def add_check(self, name: str, check_func: Callable) -> None:
        """헬스체크 함수 추가"""
        self.health_checks[name] = check_func
    
    async def run_check(self, name: str) -> Dict[str, Any]:
        """개별 헬스체크 실행"""
        if name not in self.health_checks:
            return {
                "status": HealthStatus.UNKNOWN,
                "error": f"Unknown health check: {name}"
            }
        
        try:
            start_time = datetime.now()
            result = await self.health_checks[name]()
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds() * 1000  # ms
            
            if isinstance(result, dict):
                result["response_time_ms"] = response_time
                result["timestamp"] = end_time.isoformat()
                return result
            else:
                return {
                    "status": HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    "response_time_ms": response_time,
                    "timestamp": end_time.isoformat()
                }
                
        except Exception as e:
            logger.error(f"헬스체크 실행 실패 ({name}): {e}")
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """모든 헬스체크 실행"""
        results = {}
        
        for name in self.health_checks:
            results[name] = await self.run_check(name)
            self.last_check_results[name] = results[name]
        
        # 전체 상태 계산
        overall_status = self._calculate_overall_status(results)
        
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "service": self.service_name,
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": uptime_seconds,
            "checks": results
        }
    
    def _calculate_overall_status(self, results: Dict[str, Dict[str, Any]]) -> str:
        """전체 상태 계산"""
        if not results:
            return HealthStatus.UNKNOWN
        
        statuses = [check.get("status", HealthStatus.UNKNOWN) for check in results.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN
    
    def get_last_results(self) -> Dict[str, Any]:
        """마지막 헬스체크 결과 반환"""
        return {
            "service": self.service_name,
            "last_checks": self.last_check_results.copy(),
            "timestamp": datetime.now().isoformat()
        }


class CommonHealthChecks:
    """공통 헬스체크 함수들"""
    
    @staticmethod
    async def check_redis_connection(redis_client: Optional[redis.Redis]) -> Dict[str, Any]:
        """Redis 연결 상태 확인"""
        if not redis_client:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "Redis client not initialized"
            }
        
        try:
            await redis_client.ping()
            info = await redis_client.info()
            
            return {
                "status": HealthStatus.HEALTHY,
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown")
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"Redis connection failed: {e}"
            }
    
    @staticmethod
    async def check_database_connection(db_session_factory) -> Dict[str, Any]:
        """데이터베이스 연결 상태 확인"""
        try:
            with db_session_factory() as session:
                # 간단한 쿼리 실행
                result = session.execute("SELECT 1")
                result.fetchone()
                
                return {
                    "status": HealthStatus.HEALTHY,
                    "database": "connected"
                }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"Database connection failed: {e}"
            }
    
    @staticmethod
    async def check_external_service(service_url: str, timeout: float = 5.0) -> Dict[str, Any]:
        """외부 서비스 연결 상태 확인"""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.get(f"{service_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": HealthStatus.HEALTHY,
                            "service_url": service_url,
                            "response_status": response.status,
                            "service_status": data.get("status", "unknown")
                        }
                    else:
                        return {
                            "status": HealthStatus.UNHEALTHY,
                            "service_url": service_url,
                            "response_status": response.status
                        }
        except asyncio.TimeoutError:
            return {
                "status": HealthStatus.UNHEALTHY,
                "service_url": service_url,
                "error": "Request timeout"
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "service_url": service_url,
                "error": str(e)
            }
    
    @staticmethod
    async def check_websocket_connections(ws_manager) -> Dict[str, Any]:
        """WebSocket 연결 상태 확인"""
        try:
            stats = ws_manager.get_connection_stats()
            
            return {
                "status": HealthStatus.HEALTHY,
                "active_connections": len(ws_manager.active_connections),
                "connection_stats": stats["stats"]
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"WebSocket check failed: {e}"
            }
    
    @staticmethod
    async def check_data_collection(data_collector, min_data_points: int = 1) -> Dict[str, Any]:
        """데이터 수집 상태 확인"""
        try:
            stats = data_collector.get_all_stats() if hasattr(data_collector, 'get_all_stats') else {}
            
            total_data_points = 0
            active_sources = 0
            
            for source, source_stats in stats.items():
                if isinstance(source_stats, dict):
                    data_count = source_stats.get('data_count', 0)
                    if data_count > 0:
                        active_sources += 1
                        total_data_points += data_count
            
            status = HealthStatus.HEALTHY if total_data_points >= min_data_points else HealthStatus.DEGRADED
            
            return {
                "status": status,
                "total_data_points": total_data_points,
                "active_sources": active_sources,
                "source_stats": stats
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"Data collection check failed: {e}"
            }


def create_health_checker(service_name: str) -> ServiceHealthChecker:
    """표준 헬스체커 생성"""
    return ServiceHealthChecker(service_name)


def create_api_gateway_health_checker(
    aggregator, 
    price_manager, 
    liquidation_manager
) -> ServiceHealthChecker:
    """API Gateway용 헬스체커 생성"""
    checker = create_health_checker("api-gateway")
    
    # 외부 서비스 연결 확인
    async def check_market_service():
        return await CommonHealthChecks.check_external_service(
            aggregator.market_service_url
        )
    
    async def check_liquidation_service():
        return await CommonHealthChecks.check_external_service(
            aggregator.liquidation_service_url
        )
    
    # WebSocket 연결 확인
    async def check_websockets():
        price_stats = await CommonHealthChecks.check_websocket_connections(price_manager)
        liquidation_stats = await CommonHealthChecks.check_websocket_connections(liquidation_manager)
        
        return {
            "status": HealthStatus.HEALTHY,
            "price_websockets": price_stats,
            "liquidation_websockets": liquidation_stats
        }
    
    checker.add_check("market_service", check_market_service)
    checker.add_check("liquidation_service", check_liquidation_service)
    checker.add_check("websockets", check_websockets)
    
    return checker


def create_market_service_health_checker(
    redis_client,
    market_collector,
    ws_manager
) -> ServiceHealthChecker:
    """Market Data Service용 헬스체커 생성"""
    checker = create_health_checker("market-data-service")
    
    # Redis 연결 확인
    async def check_redis():
        return await CommonHealthChecks.check_redis_connection(redis_client)
    
    # 데이터 수집 확인
    async def check_data_collection():
        return await CommonHealthChecks.check_data_collection(market_collector, min_data_points=10)
    
    # WebSocket 연결 확인
    async def check_websockets():
        return await CommonHealthChecks.check_websocket_connections(ws_manager)
    
    checker.add_check("redis", check_redis)
    checker.add_check("data_collection", check_data_collection)
    checker.add_check("websockets", check_websockets)
    
    return checker


def create_liquidation_service_health_checker(
    redis_client,
    liquidation_stats_data
) -> ServiceHealthChecker:
    """Liquidation Service용 헬스체커 생성"""
    checker = create_health_checker("liquidation-service")
    
    # Redis 연결 확인
    async def check_redis():
        return await CommonHealthChecks.check_redis_connection(redis_client)
    
    # 청산 데이터 수집 확인
    async def check_liquidation_data():
        try:
            total_data_points = sum(len(data) for data in liquidation_stats_data.values())
            active_exchanges = [exchange for exchange, data in liquidation_stats_data.items() if len(data) > 0]
            
            status = HealthStatus.HEALTHY if total_data_points > 0 else HealthStatus.DEGRADED
            
            return {
                "status": status,
                "total_data_points": total_data_points,
                "active_exchanges": active_exchanges,
                "total_exchanges": len(liquidation_stats_data)
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"Liquidation data check failed: {e}"
            }
    
    checker.add_check("redis", check_redis)
    checker.add_check("liquidation_data", check_liquidation_data)
    
    return checker