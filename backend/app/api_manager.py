"""
API 호출 관리 시스템

기능:
1. Rate Limiting (속도 제한)
2. 회로 차단기 (Circuit Breaker) 패턴
3. API 응답 데이터 유효성 검사
4. 재시도 로직 (Exponential Backoff)
5. API 사용량 모니터링
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import aiohttp
import requests

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """회로 차단기 상태"""
    CLOSED = "closed"      # 정상 동작
    OPEN = "open"          # 차단 상태
    HALF_OPEN = "half_open"  # 복구 시도 중

@dataclass
class RateLimitConfig:
    """Rate Limit 설정"""
    requests_per_second: float = 1.0
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 5  # 순간 허용 요청 수

@dataclass
class CircuitBreakerConfig:
    """회로 차단기 설정"""
    failure_threshold: int = 5      # 실패 임계값
    recovery_timeout: float = 60.0  # 복구 시도 간격 (초)
    success_threshold: int = 3      # 복구 성공 임계값

@dataclass 
class APIStats:
    """API 사용 통계"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    circuit_breaker_blocks: int = 0
    last_request_time: Optional[float] = None
    avg_response_time: float = 0.0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))

class TokenBucket:
    """토큰 버킷 알고리즘 구현"""
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # 토큰 생성 속도 (per second)
        self.capacity = capacity  # 버킷 용량
        self.tokens = capacity  # 현재 토큰 수
        self.last_update = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """토큰 소비 시도"""
        now = time.time()
        
        # 시간 경과에 따른 토큰 추가
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        # 토큰 소비 가능 여부 확인
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

class CircuitBreaker:
    """회로 차단기 패턴 구현"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.recent_failures: deque = deque(maxlen=config.failure_threshold * 2)
    
    def can_execute(self) -> bool:
        """실행 가능 여부 확인"""
        now = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # 복구 시간이 지났는지 확인
            if now - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit Breaker: HALF_OPEN 상태로 전환")
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """성공 기록"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.recent_failures.clear()
                logger.info("Circuit Breaker: CLOSED 상태로 복구")
        elif self.state == CircuitState.CLOSED:
            # 성공 시 실패 카운트 감소
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """실패 기록"""
        now = time.time()
        self.recent_failures.append(now)
        self.failure_count += 1
        self.last_failure_time = now
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit Breaker: OPEN 상태로 전환 (연속 실패 {self.failure_count}회)")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit Breaker: HALF_OPEN에서 OPEN으로 전환")

class APIManager:
    """통합 API 관리자"""
    
    def __init__(self, name: str, base_url: str = ""):
        self.name = name
        self.base_url = base_url
        
        # 기본 설정
        self.rate_limit_config = RateLimitConfig()
        self.circuit_breaker_config = CircuitBreakerConfig()
        
        # 구성 요소 초기화
        self.token_bucket = TokenBucket(
            self.rate_limit_config.requests_per_second,
            self.rate_limit_config.burst_size
        )
        self.circuit_breaker = CircuitBreaker(self.circuit_breaker_config)
        self.stats = APIStats()
        
        # 요청 기록 (분/시간별 카운팅)
        self.minute_requests: deque = deque(maxlen=60)
        self.hour_requests: deque = deque(maxlen=3600)
        
        # 데이터 검증 함수
        self.validators: List[Callable[[Any], bool]] = []
    
    def configure_rate_limits(self, config: RateLimitConfig):
        """Rate Limit 설정"""
        self.rate_limit_config = config
        self.token_bucket = TokenBucket(config.requests_per_second, config.burst_size)
    
    def configure_circuit_breaker(self, config: CircuitBreakerConfig):
        """Circuit Breaker 설정"""
        self.circuit_breaker_config = config
        self.circuit_breaker = CircuitBreaker(config)
    
    def add_validator(self, validator: Callable[[Any], bool]):
        """데이터 검증 함수 추가"""
        self.validators.append(validator)
    
    def _check_rate_limits(self) -> bool:
        """속도 제한 확인"""
        now = time.time()
        
        # 토큰 버킷 확인
        if not self.token_bucket.consume():
            return False
        
        # 분당 요청 수 확인
        minute_cutoff = now - 60
        self.minute_requests = deque(
            [t for t in self.minute_requests if t > minute_cutoff],
            maxlen=60
        )
        if len(self.minute_requests) >= self.rate_limit_config.requests_per_minute:
            return False
        
        # 시간당 요청 수 확인
        hour_cutoff = now - 3600
        self.hour_requests = deque(
            [t for t in self.hour_requests if t > hour_cutoff],
            maxlen=3600
        )
        if len(self.hour_requests) >= self.rate_limit_config.requests_per_hour:
            return False
        
        return True
    
    def _record_request(self):
        """요청 기록"""
        now = time.time()
        self.minute_requests.append(now)
        self.hour_requests.append(now)
        self.stats.total_requests += 1
        self.stats.last_request_time = now
    
    def _validate_response_data(self, data: Any) -> bool:
        """응답 데이터 유효성 검사"""
        if not self.validators:
            return True
        
        for validator in self.validators:
            try:
                if not validator(data):
                    return False
            except Exception as e:
                logger.warning(f"{self.name}: 데이터 검증 중 오류 - {e}")
                return False
        
        return True
    
    async def make_request(
        self,
        method: str,
        url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Any]:
        """HTTP 요청 실행"""
        
        # Circuit Breaker 확인
        if not self.circuit_breaker.can_execute():
            self.stats.circuit_breaker_blocks += 1
            logger.warning(f"{self.name}: Circuit Breaker에 의해 요청 차단")
            return None
        
        # Rate Limiting 확인
        if not self._check_rate_limits():
            self.stats.rate_limited_requests += 1
            logger.warning(f"{self.name}: Rate Limit에 의해 요청 차단")
            return None
        
        # 요청 기록
        self._record_request()
        
        # 재시도 로직
        for attempt in range(max_retries + 1):
            start_time = time.time()
            
            try:
                full_url = f"{self.base_url}{url}" if self.base_url else url
                
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method, full_url, timeout=aiohttp.ClientTimeout(total=timeout), **kwargs
                    ) as response:
                        
                        response_time = time.time() - start_time
                        self.stats.response_times.append(response_time)
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            # 데이터 유효성 검사
                            if self._validate_response_data(data):
                                self.circuit_breaker.record_success()
                                self.stats.successful_requests += 1
                                
                                # 평균 응답시간 업데이트
                                if self.stats.response_times:
                                    self.stats.avg_response_time = sum(self.stats.response_times) / len(self.stats.response_times)
                                
                                return data
                            else:
                                logger.warning(f"{self.name}: 데이터 유효성 검사 실패")
                        else:
                            logger.warning(f"{self.name}: HTTP {response.status} 오류")
                
            except asyncio.TimeoutError:
                logger.warning(f"{self.name}: 요청 타임아웃 (시도 {attempt + 1}/{max_retries + 1})")
            except Exception as e:
                logger.error(f"{self.name}: 요청 오류 - {e} (시도 {attempt + 1}/{max_retries + 1})")
            
            # 재시도 대기 (Exponential Backoff)
            if attempt < max_retries:
                wait_time = (2 ** attempt) * 1.0  # 1, 2, 4초
                await asyncio.sleep(wait_time)
        
        # 모든 재시도 실패
        self.circuit_breaker.record_failure()
        self.stats.failed_requests += 1
        return None
    
    def make_sync_request(
        self,
        method: str,
        url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Any]:
        """동기식 HTTP 요청 실행"""
        
        # Circuit Breaker 확인
        if not self.circuit_breaker.can_execute():
            self.stats.circuit_breaker_blocks += 1
            logger.warning(f"{self.name}: Circuit Breaker에 의해 요청 차단")
            return None
        
        # Rate Limiting 확인
        if not self._check_rate_limits():
            self.stats.rate_limited_requests += 1
            logger.warning(f"{self.name}: Rate Limit에 의해 요청 차단")
            return None
        
        # 요청 기록
        self._record_request()
        
        # 재시도 로직
        for attempt in range(max_retries + 1):
            start_time = time.time()
            
            try:
                full_url = f"{self.base_url}{url}" if self.base_url else url
                
                response = requests.request(
                    method, full_url, timeout=timeout, **kwargs
                )
                
                response_time = time.time() - start_time
                self.stats.response_times.append(response_time)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 데이터 유효성 검사
                    if self._validate_response_data(data):
                        self.circuit_breaker.record_success()
                        self.stats.successful_requests += 1
                        
                        # 평균 응답시간 업데이트
                        if self.stats.response_times:
                            self.stats.avg_response_time = sum(self.stats.response_times) / len(self.stats.response_times)
                        
                        return data
                    else:
                        logger.warning(f"{self.name}: 데이터 유효성 검사 실패")
                else:
                    logger.warning(f"{self.name}: HTTP {response.status_code} 오류")
                
            except requests.exceptions.Timeout:
                logger.warning(f"{self.name}: 요청 타임아웃 (시도 {attempt + 1}/{max_retries + 1})")
            except Exception as e:
                logger.error(f"{self.name}: 요청 오류 - {e} (시도 {attempt + 1}/{max_retries + 1})")
            
            # 재시도 대기
            if attempt < max_retries:
                wait_time = (2 ** attempt) * 1.0
                time.sleep(wait_time)
        
        # 모든 재시도 실패
        self.circuit_breaker.record_failure()
        self.stats.failed_requests += 1
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """API 관리자 통계 반환"""
        now = time.time()
        
        # 현재 Rate Limit 상태
        minute_requests = len([t for t in self.minute_requests if now - t <= 60])
        hour_requests = len([t for t in self.hour_requests if now - t <= 3600])
        
        return {
            "name": self.name,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "rate_limited_requests": self.stats.rate_limited_requests,
                "circuit_breaker_blocks": self.stats.circuit_breaker_blocks,
                "success_rate": (
                    self.stats.successful_requests / self.stats.total_requests * 100
                    if self.stats.total_requests > 0 else 0
                ),
                "avg_response_time": round(self.stats.avg_response_time, 3),
                "last_request_time": self.stats.last_request_time
            },
            "rate_limits": {
                "requests_per_minute": f"{minute_requests}/{self.rate_limit_config.requests_per_minute}",
                "requests_per_hour": f"{hour_requests}/{self.rate_limit_config.requests_per_hour}",
                "tokens_available": round(self.token_bucket.tokens, 2)
            }
        }

# --- 사전 정의된 API 관리자들 ---

# Upbit API 관리자
upbit_api = APIManager("Upbit", "https://api.upbit.com")
upbit_api.configure_rate_limits(RateLimitConfig(
    requests_per_second=10.0,
    requests_per_minute=600,
    requests_per_hour=1000,
    burst_size=20
))

# Binance API 관리자  
binance_api = APIManager("Binance", "https://api.binance.com")
binance_api.configure_rate_limits(RateLimitConfig(
    requests_per_second=20.0,
    requests_per_minute=1200,
    requests_per_hour=10000,
    burst_size=50
))

# Bybit API 관리자
bybit_api = APIManager("Bybit", "https://api.bybit.com")
bybit_api.configure_rate_limits(RateLimitConfig(
    requests_per_second=5.0,
    requests_per_minute=300,
    requests_per_hour=1000,
    burst_size=10
))

# 네이버 금융 API 관리자
naver_api = APIManager("Naver", "https://finance.naver.com")
naver_api.configure_rate_limits(RateLimitConfig(
    requests_per_second=0.5,  # 보수적으로 설정
    requests_per_minute=10,
    requests_per_hour=100,
    burst_size=2
))

def get_all_api_stats() -> Dict[str, Any]:
    """모든 API 관리자 통계 반환"""
    return {
        "upbit": upbit_api.get_stats(),
        "binance": binance_api.get_stats(), 
        "bybit": bybit_api.get_stats(),
        "naver": naver_api.get_stats()
    }