"""
API 장애 감지 및 페일오버 시스템

주요 기능:
1. 실시간 API 상태 모니터링
2. 장애 감지 및 자동 페일오버
3. 백업 엔드포인트 관리
4. 서비스 복구 감지
5. 장애 알림 시스템
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set, Callable, Any, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import aiohttp

from .exchange_specifications import get_exchange_spec, EXCHANGE_SPECS
from .specialized_clients import ExchangeClient, create_exchange_client

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """서비스 상태"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # 부분적 장애
    UNHEALTHY = "unhealthy"  # 완전 장애
    UNKNOWN = "unknown"  # 상태 불명

class FailoverTrigger(Enum):
    """페일오버 트리거 유형"""
    CONNECTION_FAILED = "connection_failed"
    RATE_LIMITED = "rate_limited"
    DATA_QUALITY = "data_quality"
    TIMEOUT = "timeout"
    MANUAL = "manual"

@dataclass
class HealthCheckResult:
    """헬스체크 결과"""
    exchange: str
    endpoint: str
    status: ServiceStatus
    response_time: float
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

@dataclass
class FailoverEvent:
    """페일오버 이벤트"""
    exchange: str
    trigger: FailoverTrigger
    primary_endpoint: Optional[str]
    backup_endpoint: Optional[str]
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

class HealthChecker:
    """API 엔드포인트 헬스체크"""
    
    def __init__(self):
        self.check_interval = 30  # 30초마다 체크
        self.timeout = 10
        self.max_retries = 3
        
    async def check_exchange_health(self, exchange_name: str) -> HealthCheckResult:
        """거래소 API 상태 확인"""
        spec = get_exchange_spec(exchange_name)
        if not spec:
            return HealthCheckResult(
                exchange=exchange_name,
                endpoint="unknown",
                status=ServiceStatus.UNKNOWN,
                response_time=0,
                error_message="Unknown exchange"
            )
        
        # REST API 헬스체크
        start_time = time.time()
        url = ""
        
        try:
            # 거래소별 간단한 헬스체크 엔드포인트
            health_endpoints = {
                "upbit": "/v1/market/all",
                "binance": "/api/v3/ping",
                "bybit": "/v5/market/time",
                "bithumb": "/public/ticker/ALL_KRW"
            }
            
            endpoint = health_endpoints.get(exchange_name, "/")
            url = f"{spec.base_url}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        # 응답 내용 간단 검증
                        try:
                            data = await response.json()
                            if self._validate_health_response(exchange_name, data):
                                status = ServiceStatus.HEALTHY
                                error_msg = None
                            else:
                                status = ServiceStatus.DEGRADED
                                error_msg = "Invalid response format"
                        except:
                            status = ServiceStatus.DEGRADED
                            error_msg = "Invalid JSON response"
                    else:
                        status = ServiceStatus.UNHEALTHY
                        error_msg = f"HTTP {response.status}"
                    
                    return HealthCheckResult(
                        exchange=exchange_name,
                        endpoint=url,
                        status=status,
                        response_time=response_time,
                        error_message=error_msg
                    )
        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                exchange=exchange_name,
                endpoint=url,
                status=ServiceStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error_message="Timeout"
            )
        except Exception as e:
            return HealthCheckResult(
                exchange=exchange_name,
                endpoint=url,
                status=ServiceStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def _validate_health_response(self, exchange_name: str, data: Any) -> bool:
        """헬스체크 응답 검증"""
        if exchange_name == "upbit":
            return isinstance(data, list) and len(data) > 0
        elif exchange_name == "binance":
            return isinstance(data, dict)  # ping 응답은 빈 객체
        elif exchange_name == "bybit":
            return isinstance(data, dict) and "result" in data
        elif exchange_name == "bithumb":
            return isinstance(data, dict) and "status" in data
        return True

class FailoverManager:
    """페일오버 관리자"""
    
    def __init__(self):
        self.health_checker = HealthChecker()
        self.service_status: Dict[str, ServiceStatus] = {}
        self.active_endpoints: Dict[str, str] = {}  # exchange -> active endpoint
        self.backup_endpoints: Dict[str, List[str]] = {}
        self.failover_history: deque = deque(maxlen=100)
        
        # 이벤트 콜백
        self.on_failover: Optional[Callable[[FailoverEvent], Awaitable[None]]] = None
        self.on_recovery: Optional[Callable[[str], Awaitable[None]]] = None
        
        # 설정
        self.failover_threshold = 3  # 연속 실패 횟수
        self.recovery_threshold = 2  # 연속 성공 횟수
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.success_counts: Dict[str, int] = defaultdict(int)
        
        # 헬스체크 이력
        self.health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        
        self._initialize_endpoints()
    
    def _initialize_endpoints(self):
        """초기 엔드포인트 설정"""
        for exchange_name, spec in EXCHANGE_SPECS.items():
            self.active_endpoints[exchange_name] = spec.base_url
            self.backup_endpoints[exchange_name] = spec.backup_endpoints.copy()
            self.service_status[exchange_name] = ServiceStatus.UNKNOWN
    
    async def start_monitoring(self):
        """헬스 모니터링 시작"""
        logger.info("API 헬스 모니터링 시작")
        
        while True:
            try:
                # 모든 거래소 헬스체크 실행
                tasks = [
                    self.health_checker.check_exchange_health(exchange)
                    for exchange in EXCHANGE_SPECS.keys()
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, HealthCheckResult):
                        await self._process_health_result(result)
                    else:
                        logger.error(f"헬스체크 오류: {result}")
                
                await asyncio.sleep(self.health_checker.check_interval)
                
            except Exception as e:
                logger.error(f"헬스 모니터링 오류: {e}")
                await asyncio.sleep(10)
    
    async def _process_health_result(self, result: HealthCheckResult):
        """헬스체크 결과 처리"""
        exchange = result.exchange
        
        # 이력 저장
        self.health_history[exchange].append(result)
        
        # 상태 업데이트
        previous_status = self.service_status.get(exchange, ServiceStatus.UNKNOWN)
        current_status = result.status
        
        if current_status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]:
            self.success_counts[exchange] += 1
            self.failure_counts[exchange] = 0
            
            # 복구 감지
            if (previous_status == ServiceStatus.UNHEALTHY and 
                self.success_counts[exchange] >= self.recovery_threshold):
                await self._handle_recovery(exchange)
                
        else:  # UNHEALTHY
            self.failure_counts[exchange] += 1
            self.success_counts[exchange] = 0
            
            # 장애 감지 및 페일오버
            if (previous_status != ServiceStatus.UNHEALTHY and 
                self.failure_counts[exchange] >= self.failover_threshold):
                await self._handle_failover(exchange, FailoverTrigger.CONNECTION_FAILED)
        
        self.service_status[exchange] = current_status
        
        # 상태 변경 로그
        if previous_status != current_status:
            logger.info(f"{exchange} 상태 변경: {previous_status.value} -> {current_status.value}")
    
    async def _handle_failover(self, exchange: str, trigger: FailoverTrigger):
        """페일오버 처리"""
        current_endpoint = self.active_endpoints.get(exchange)
        backup_endpoints = self.backup_endpoints.get(exchange, [])
        
        if not backup_endpoints:
            logger.warning(f"{exchange}: 백업 엔드포인트가 없습니다")
            event = FailoverEvent(
                exchange=exchange,
                trigger=trigger,
                primary_endpoint=current_endpoint,
                backup_endpoint=None,
                details={"reason": "No backup endpoints available"}
            )
        else:
            # 첫 번째 백업 엔드포인트로 전환
            backup_endpoint = backup_endpoints[0]
            self.active_endpoints[exchange] = backup_endpoint
            
            # 현재 엔드포인트를 백업 목록 끝으로 이동
            if current_endpoint:
                backup_endpoints.append(current_endpoint)
                backup_endpoints.remove(backup_endpoint)
            
            logger.warning(f"{exchange} 페일오버: {current_endpoint} -> {backup_endpoint}")
            
            event = FailoverEvent(
                exchange=exchange,
                trigger=trigger,
                primary_endpoint=current_endpoint,
                backup_endpoint=backup_endpoint,
                details={"available_backups": len(backup_endpoints)}
            )
        
        self.failover_history.append(event)
        
        if self.on_failover:
            callback = self.on_failover
            await callback(event)
    
    async def _handle_recovery(self, exchange: str):
        """서비스 복구 처리"""
        logger.info(f"{exchange} 서비스 복구됨")
        
        if self.on_recovery:
            callback = self.on_recovery
            await callback(exchange)
    
    def get_service_status(self, exchange: str) -> ServiceStatus:
        """서비스 상태 반환"""
        return self.service_status.get(exchange, ServiceStatus.UNKNOWN)
    
    def get_active_endpoint(self, exchange: str) -> Optional[str]:
        """현재 활성 엔드포인트 반환"""
        return self.active_endpoints.get(exchange)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """전체 헬스 상태 요약"""
        summary = {}
        
        for exchange in EXCHANGE_SPECS.keys():
            recent_results = list(self.health_history[exchange])[-5:]  # 최근 5회
            
            if recent_results:
                avg_response_time = sum(r.response_time for r in recent_results) / len(recent_results)
                success_rate = sum(1 for r in recent_results if r.status == ServiceStatus.HEALTHY) / len(recent_results) * 100
            else:
                avg_response_time = 0
                success_rate = 0
            
            summary[exchange] = {
                "status": self.service_status.get(exchange, ServiceStatus.UNKNOWN).value,
                "active_endpoint": self.active_endpoints.get(exchange),
                "avg_response_time": round(avg_response_time, 3),
                "success_rate": round(success_rate, 1),
                "failure_count": self.failure_counts[exchange],
                "last_check": recent_results[-1].timestamp if recent_results else None
            }
        
        return {
            "exchanges": summary,
            "total_failovers": len(self.failover_history),
            "recent_failovers": [
                {
                    "exchange": event.exchange,
                    "trigger": event.trigger.value,
                    "timestamp": event.timestamp
                }
                for event in list(self.failover_history)[-5:]
            ]
        }
    
    def force_failover(self, exchange: str, reason: str = "Manual failover"):
        """수동 페일오버 실행"""
        asyncio.create_task(self._handle_failover(exchange, FailoverTrigger.MANUAL))
        logger.info(f"{exchange} 수동 페일오버 실행: {reason}")

class ResilientExchangeManager:
    """복원력 있는 거래소 관리자"""
    
    def __init__(self):
        self.failover_manager = FailoverManager()
        self.exchange_clients: Dict[str, ExchangeClient] = {}
        self.data_quality_monitor = DataQualityMonitor()
        
        # 페일오버 이벤트 핸들러 설정
        self.failover_manager.on_failover = self._on_failover_event
        self.failover_manager.on_recovery = self._on_recovery_event
        
        self.is_running = False
        
    async def start(self):
        """시스템 시작"""
        logger.info("복원력 있는 거래소 관리자 시작")
        
        # 거래소 클라이언트 초기화
        for exchange_name in EXCHANGE_SPECS.keys():
            client = create_exchange_client(exchange_name)
            if client:
                self.exchange_clients[exchange_name] = client
                # 클라이언트 오류 콜백 설정
                if client.on_error:
                    client.on_error = lambda e, ex=exchange_name: self._on_client_error(ex, e)
        
        # 백그라운드 태스크 시작
        self.is_running = True
        asyncio.create_task(self.failover_manager.start_monitoring())
        asyncio.create_task(self.data_quality_monitor.start_monitoring())
        
        logger.info("모든 백그라운드 서비스 시작 완료")
    
    async def stop(self):
        """시스템 종료"""
        logger.info("복원력 있는 거래소 관리자 종료")
        self.is_running = False
        
        # 모든 클라이언트 연결 종료
        for client in self.exchange_clients.values():
            await client.disconnect()
    
    async def _on_failover_event(self, event: FailoverEvent):
        """페일오버 이벤트 발생 시 호출되는 콜백 함수입니다.

        해당 거래소의 클라이언트를 재시작하여 새로운 엔드포인트로 연결을 시도합니다.

        Args:
            event (FailoverEvent): 발생한 페일오버 이벤트 객체.
        """
        exchange = event.exchange
        
        # 해당 거래소 클라이언트 재시작
        if exchange in self.exchange_clients:
            client = self.exchange_clients[exchange]
            try:
                await client.disconnect()
                await asyncio.sleep(5)  # 잠시 대기
                
                # 새 엔드포인트로 재연결 시도
                success = await client.connect()
                if success:
                    logger.info(f"{exchange} 클라이언트 재연결 성공")
                else:
                    logger.error(f"{exchange} 클라이언트 재연결 실패")
                    
            except Exception as e:
                logger.error(f"{exchange} 페일오버 처리 중 오류: {e}")
    
    async def _on_recovery_event(self, exchange: str):
        """서비스 복구 이벤트 발생 시 호출되는 콜백 함수입니다.

        서비스 복구 상태를 로깅하고, 필요 시 알림을 전송합니다.

        Args:
            exchange (str): 복구된 서비스의 거래소 이름.
        """
        logger.info(f"{exchange} 서비스 복구 완료")
        
        if self.on_recovery:
            callback = self.on_recovery
            await callback(exchange)
    
    async def _on_client_error(self, exchange: str, error: Exception):
        """거래소 클라이언트에서 오류 발생 시 호출되는 콜백 함수입니다.

        오류 유형을 분석하여 타임아웃 또는 Rate Limit과 같은 특정 오류에 대해
        페일오버를 트리거합니다.

        Args:
            exchange (str): 오류가 발생한 거래소 이름.
            error (Exception): 발생한 예외 객체.
        """
        logger.warning(f"{exchange} 클라이언트 오류: {error}")
        
        # 오류 유형에 따른 페일오버 트리거
        if "timeout" in str(error).lower():
            await self.failover_manager._handle_failover(exchange, FailoverTrigger.TIMEOUT)
        elif "rate limit" in str(error).lower():
            await self.failover_manager._handle_failover(exchange, FailoverTrigger.RATE_LIMITED)
    
    def get_system_status(self) -> Dict[str, Any]:
        """전체 시스템의 현재 상태를 종합하여 반환합니다.

        페일오버 관리자, 거래소 클라이언트, 데이터 품질 모니터의 상태 정보를
        포함하는 딕셔너리를 생성하여 반환합니다.

        Returns:
            Dict[str, Any]: 시스템의 종합 상태 정보.
        """
        return {
            "failover_manager": self.failover_manager.get_health_summary(),
            "exchange_clients": {
                name: client.get_stats() 
                for name, client in self.exchange_clients.items()
            },
            "data_quality": self.data_quality_monitor.get_stats(),
            "system_uptime": time.time(),
            "is_running": self.is_running
        }

class DataQualityMonitor:
    """데이터 품질 모니터링"""
    
    def __init__(self):
        self.data_samples: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.quality_scores: Dict[str, float] = {}
        self.anomaly_threshold = 0.8  # 품질 점수 임계값
        
    async def start_monitoring(self):
        """데이터 품질 모니터링을 주기적으로 실행하는 태스크를 시작합니다.

        무한 루프를 돌며 주기적으로 모든 거래소의 데이터 품질을 분석하고,
        품질 저하가 감지되면 경고를 로깅합니다.
        """
        while True:
            try:
                # 주기적으로 데이터 품질 분석
                for exchange in EXCHANGE_SPECS.keys():
                    score = self._calculate_quality_score(exchange)
                    self.quality_scores[exchange] = score
                    
                    if score < self.anomaly_threshold:
                        logger.warning(f"{exchange} 데이터 품질 저하: {score:.2f}")
                
                await asyncio.sleep(60)  # 1분마다 분석
                
            except Exception as e:
                logger.error(f"데이터 품질 모니터링 오류: {e}")
                await asyncio.sleep(10)
    
    def record_data_sample(self, exchange: str, data: Dict[str, Any]):
        """수신된 데이터 샘플을 기록하고 유효성을 검사합니다.

        데이터의 유효성을 검사한 후, 타임스탬프와 함께 샘플을 내부 기록에 추가합니다.

        Args:
            exchange (str): 데이터가 수신된 거래소 이름.
            data (Dict[str, Any]): 수신된 데이터 샘플.
        """
        sample = {
            "timestamp": time.time(),
            "price": data.get("price", 0),
            "volume": data.get("volume", 0),
            "change_percent": data.get("change_percent", 0),
            "is_valid": self._validate_data(data)
        }
        
        self.data_samples[exchange].append(sample)
    
    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """데이터의 기본적인 유효성을 검사합니다.

        가격이 0 이하이거나, 거래량이 음수이거나, 변동률이 비정상적으로 큰 경우
        유효하지 않은 데이터로 판단합니다.

        Args:
            data (Dict[str, Any]): 검사할 데이터.

        Returns:
            bool: 데이터가 유효하면 True, 그렇지 않으면 False.
        """
        try:
            price = float(data.get("price", 0))
            volume = float(data.get("volume", 0))
            change = float(data.get("change_percent", 0))
            
            # 기본적인 유효성 검사
            if price <= 0:
                return False
            if volume < 0:
                return False
            if abs(change) > 50:  # 50% 이상 변동은 비정상
                return False
                
            return True
            
        except (ValueError, TypeError):
            return False
    
    def _calculate_quality_score(self, exchange: str) -> float:
        """특정 거래소의 데이터 품질 점수를 계산합니다.

        기록된 데이터 샘플을 기반으로 유효 데이터 비율과 데이터 신선도를
        종합하여 0.0에서 1.0 사이의 점수를 반환합니다.

        Args:
            exchange (str): 품질 점수를 계산할 거래소 이름.

        Returns:
            float: 계산된 데이터 품질 점수. 샘플이 없으면 0.0을 반환합니다.
        """
        samples = list(self.data_samples[exchange])
        if not samples:
            return 0.0
        
        # 유효 데이터 비율
        valid_ratio = sum(1 for s in samples if s["is_valid"]) / len(samples)
        
        # 데이터 신선도 (최근 데이터 비율)
        current_time = time.time()
        fresh_samples = [s for s in samples if current_time - s["timestamp"] < 300]  # 5분 이내
        freshness_ratio = len(fresh_samples) / len(samples) if samples else 0
        
        # 종합 점수
        quality_score = (valid_ratio * 0.7) + (freshness_ratio * 0.3)
        
        return quality_score
    
    def get_stats(self) -> Dict[str, Any]:
        """현재 데이터 품질 모니터링 통계를 반환합니다.

        각 거래소별 품질 점수, 샘플 수, 그리고 전체적인 품질 점수를 포함하는
        딕셔너리를 반환합니다.

        Returns:
            Dict[str, Any]: 데이터 품질 통계.
        """
        return {
            "quality_scores": self.quality_scores,
            "sample_counts": {
                exchange: len(samples) 
                for exchange, samples in self.data_samples.items()
            },
            "overall_quality": sum(self.quality_scores.values()) / len(self.quality_scores) if self.quality_scores else 0
        }