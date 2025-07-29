"""
공통 Redis 클라이언트 관리자

모든 마이크로서비스에서 사용할 수 있는 표준화된 Redis 연결 및 작업 관리를 제공합니다.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis 연결 및 작업 관리자"""
    
    def __init__(self, redis_url: str = "redis://redis:6379", service_name: str = "unknown"):
        self.redis_url = redis_url
        self.service_name = service_name
        self.client: Optional[redis.Redis] = None
        self.is_connected = False
        self.connection_attempts = 0
        self.max_retry_attempts = 3
    
    async def connect(self) -> bool:
        """Redis에 연결"""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            self.is_connected = True
            self.connection_attempts = 0
            logger.info(f"✅ [{self.service_name}] Redis 연결 성공: {self.redis_url}")
            return True
        except Exception as e:
            self.connection_attempts += 1
            self.is_connected = False
            if self.connection_attempts <= self.max_retry_attempts:
                logger.warning(f"⚠️ [{self.service_name}] Redis 연결 실패 (시도 {self.connection_attempts}/{self.max_retry_attempts}): {e}")
            else:
                logger.error(f"❌ [{self.service_name}] Redis 연결 최종 실패: {e}")
            return False
    
    async def disconnect(self):
        """Redis 연결 해제"""
        if self.client:
            try:
                await self.client.close()
                logger.info(f"🔌 [{self.service_name}] Redis 연결 해제")
            except Exception as e:
                logger.error(f"❌ [{self.service_name}] Redis 연결 해제 오류: {e}")
        self.is_connected = False
        self.client = None
    
    async def ensure_connection(self) -> bool:
        """연결 상태 확인 및 재연결"""
        if not self.is_connected or not self.client:
            return await self.connect()
        
        try:
            await self.client.ping()
            return True
        except Exception:
            logger.warning(f"⚠️ [{self.service_name}] Redis 연결 끊김, 재연결 시도")
            return await self.connect()
    
    # === Key-Value Operations ===
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """값 저장"""
        if not await self.ensure_connection():
            return False
        
        try:
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            result = await self.client.set(key, serialized_value)
            
            if expire:
                await self.client.expire(key, expire)
            
            return result
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis SET 오류 ({key}): {e}")
            return False
    
    async def get(self, key: str, default: Any = None) -> Any:
        """값 조회"""
        if not await self.ensure_connection():
            return default
        
        try:
            value = await self.client.get(key)
            if value is None:
                return default
            
            # JSON 디코딩 시도
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis GET 오류 ({key}): {e}")
            return default
    
    async def delete(self, *keys: str) -> int:
        """키 삭제"""
        if not await self.ensure_connection():
            return 0
        
        try:
            return await self.client.delete(*keys)
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis DELETE 오류: {e}")
            return 0
    
    # === Hash Operations ===
    
    async def hset(self, name: str, mapping: Dict[str, Any], expire: Optional[int] = None) -> bool:
        """해시 필드 설정"""
        if not await self.ensure_connection():
            return False
        
        try:
            # 값들을 JSON으로 직렬화
            serialized_mapping = {}
            for field, value in mapping.items():
                serialized_mapping[field] = json.dumps(value) if not isinstance(value, str) else value
            
            result = await self.client.hset(name, mapping=serialized_mapping)
            
            if expire:
                await self.client.expire(name, expire)
            
            return result > 0
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis HSET 오류 ({name}): {e}")
            return False
    
    async def hset_field(self, name: str, field: str, value: Any, expire: Optional[int] = None) -> bool:
        """해시 단일 필드 설정"""
        if not await self.ensure_connection():
            return False
        
        try:
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            result = await self.client.hset(name, field, serialized_value)
            
            if expire:
                await self.client.expire(name, expire)
            
            return result > 0
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis HSET 필드 오류 ({name}.{field}): {e}")
            return False
    
    async def hget(self, name: str, field: str, default: Any = None) -> Any:
        """해시 필드 조회"""
        if not await self.ensure_connection():
            return default
        
        try:
            value = await self.client.hget(name, field)
            if value is None:
                return default
            
            # JSON 디코딩 시도
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis HGET 오류 ({name}.{field}): {e}")
            return default
    
    async def hgetall(self, name: str) -> Dict[str, Any]:
        """해시 전체 조회"""
        if not await self.ensure_connection():
            return {}
        
        try:
            hash_data = await self.client.hgetall(name)
            if not hash_data:
                return {}
            
            # 모든 값에 대해 JSON 디코딩 시도
            result = {}
            for field, value in hash_data.items():
                try:
                    result[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[field] = value
            
            return result
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis HGETALL 오류 ({name}): {e}")
            return {}
    
    # === List Operations ===
    
    async def lpush(self, name: str, *values: Any) -> int:
        """리스트 앞쪽에 추가"""
        if not await self.ensure_connection():
            return 0
        
        try:
            serialized_values = []
            for value in values:
                serialized_values.append(json.dumps(value) if not isinstance(value, str) else value)
            
            return await self.client.lpush(name, *serialized_values)
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis LPUSH 오류 ({name}): {e}")
            return 0
    
    async def lrange(self, name: str, start: int = 0, end: int = -1) -> List[Any]:
        """리스트 범위 조회"""
        if not await self.ensure_connection():
            return []
        
        try:
            values = await self.client.lrange(name, start, end)
            if not values:
                return []
            
            # JSON 디코딩 시도
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    result.append(value)
            
            return result
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis LRANGE 오류 ({name}): {e}")
            return []
    
    # === Utility Methods ===
    
    async def exists(self, *keys: str) -> int:
        """키 존재 확인"""
        if not await self.ensure_connection():
            return 0
        
        try:
            return await self.client.exists(*keys)
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis EXISTS 오류: {e}")
            return 0
    
    async def expire(self, name: str, time: int) -> bool:
        """키 만료 시간 설정"""
        if not await self.ensure_connection():
            return False
        
        try:
            return await self.client.expire(name, time)
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis EXPIRE 오류 ({name}): {e}")
            return False
    
    async def ping(self) -> bool:
        """연결 상태 확인"""
        if not await self.ensure_connection():
            return False
        
        try:
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def info(self) -> Dict[str, Any]:
        """Redis 서버 정보 조회"""
        if not await self.ensure_connection():
            return {}
        
        try:
            return await self.client.info()
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis INFO 오류: {e}")
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Redis 매니저 통계 정보"""
        return {
            "service": self.service_name,
            "redis_url": self.redis_url,
            "is_connected": self.is_connected,
            "connection_attempts": self.connection_attempts,
            "client_exists": self.client is not None
        }


# === Factory Functions ===

def create_redis_manager(service_name: str, redis_url: str = "redis://redis:6379") -> RedisManager:
    """Redis 매니저 생성"""
    return RedisManager(redis_url, service_name)


async def initialize_redis_for_service(service_name: str, redis_url: str = "redis://redis:6379") -> Optional[RedisManager]:
    """서비스용 Redis 매니저 초기화"""
    redis_manager = create_redis_manager(service_name, redis_url)
    
    if await redis_manager.connect():
        return redis_manager
    else:
        logger.warning(f"⚠️ [{service_name}] Redis 초기화 실패, 로컬 메모리 사용")
        return None


# === Service-Specific Helpers ===

class MarketDataRedisHelper:
    """Market Data Service용 Redis 헬퍼"""
    
    def __init__(self, redis_manager: RedisManager):
        self.redis = redis_manager
    
    async def update_exchange_data(self, exchange: str, symbol: str, data: Dict[str, Any], ttl: int = 300):
        """거래소 데이터 업데이트"""
        hash_key = f"market:{exchange}"
        success = await self.redis.hset_field(hash_key, symbol, data, expire=ttl)
        
        # 마지막 업데이트 시간 기록
        if success:
            await self.redis.set(f"market:{exchange}:last_update", datetime.now().isoformat(), expire=ttl)
        
        return success
    
    async def get_exchange_data(self, exchange: str, symbol: str = None) -> Union[Dict[str, Any], Any]:
        """거래소 데이터 조회"""
        hash_key = f"market:{exchange}"
        
        if symbol:
            return await self.redis.hget(hash_key, symbol, {})
        else:
            return await self.redis.hgetall(hash_key)
    
    async def update_exchange_rates(self, rates: Dict[str, float], ttl: int = 300):
        """환율 정보 업데이트"""
        return await self.redis.hset("market:rates", rates, expire=ttl)
    
    async def get_exchange_rates(self) -> Dict[str, float]:
        """환율 정보 조회"""
        return await self.redis.hgetall("market:rates")


class LiquidationRedisHelper:
    """Liquidation Service용 Redis 헬퍼"""
    
    def __init__(self, redis_manager: RedisManager):
        self.redis = redis_manager
    
    async def add_liquidation_event(self, exchange: str, liquidation_data: Dict[str, Any], ttl: int = 86400):
        """청산 이벤트 추가"""
        list_key = f"liquidations:{exchange}:events"
        
        # 타임스탬프 추가
        liquidation_data["recorded_at"] = datetime.now().isoformat()
        
        # 리스트에 추가 (최대 1000개 유지)
        await self.redis.lpush(list_key, liquidation_data)
        
        # TTL 설정
        await self.redis.expire(list_key, ttl)
        
        # 리스트 크기 제한 (최대 1000개)
        try:
            if await self.ensure_connection():
                await self.redis.client.ltrim(list_key, 0, 999)
        except Exception as e:
            logger.error(f"청산 리스트 크기 제한 오류: {e}")
    
    async def get_recent_liquidations(self, exchange: str, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 청산 데이터 조회"""
        list_key = f"liquidations:{exchange}:events"
        return await self.redis.lrange(list_key, 0, limit - 1)
    
    async def update_liquidation_stats(self, exchange: str, stats: Dict[str, Any], ttl: int = 3600):
        """청산 통계 업데이트"""
        hash_key = f"liquidations:{exchange}:stats"
        return await self.redis.hset(hash_key, stats, expire=ttl)