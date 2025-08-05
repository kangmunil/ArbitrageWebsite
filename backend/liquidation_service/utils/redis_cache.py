"""Redis Cache Management

데이터 캐싱 및 실시간 데이터 관리를 위한 Redis 클래스
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
import redis.asyncio as redis
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RedisCache:
    """비동기 Redis 캐시 관리자"""
    
    def __init__(
        self, 
        host: str = "redis",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
        max_connections: int = 10
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.decode_responses = decode_responses
        
        # Connection pool 설정
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses,
            max_connections=max_connections,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={}
        )
        
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self):
        """Redis 연결"""
        try:
            self.redis_client = redis.Redis(connection_pool=self.pool)
            # 연결 테스트
            await self.redis_client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise
    
    async def disconnect(self):
        """Redis 연결 해제"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("Disconnected from Redis")
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.disconnect()
    
    def _ensure_connected(self):
        """Redis 연결 상태 확인"""
        if not self._connected or not self.redis_client:
            raise RuntimeError("Redis client is not connected. Call connect() first.")
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """키-값 저장"""
        self._ensure_connected()
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            
            result = await self.redis_client.set(key, value)
            
            if ttl:
                await self.redis_client.expire(key, ttl)
            
            return bool(result)
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[str]:
        """키로 값 조회"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
    
    async def get_json(self, key: str) -> Optional[Union[Dict, List]]:
        """JSON 형태의 값 조회"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for key {key}")
                return None
        return None
    
    async def delete(self, *keys: str) -> int:
        """키 삭제"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Error deleting keys {keys}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        self._ensure_connected()
        
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Error checking existence of key {key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """키에 TTL 설정"""
        self._ensure_connected()
        
        try:
            return bool(await self.redis_client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Error setting TTL for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """키의 남은 TTL 조회"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {e}")
            return -2  # Key does not exist
    
    # List operations
    async def lpush(self, key: str, *values: Any) -> int:
        """리스트 앞쪽에 값 추가"""
        self._ensure_connected()
        
        try:
            # JSON 직렬화가 필요한 값들 처리
            processed_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    processed_values.append(json.dumps(value, default=str))
                else:
                    processed_values.append(value)
            
            return await self.redis_client.lpush(key, *processed_values)
        except Exception as e:
            logger.error(f"Error lpush to key {key}: {e}")
            return 0
    
    async def rpush(self, key: str, *values: Any) -> int:
        """리스트 뒤쪽에 값 추가"""
        self._ensure_connected()
        
        try:
            processed_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    processed_values.append(json.dumps(value, default=str))
                else:
                    processed_values.append(value)
            
            return await self.redis_client.rpush(key, *processed_values)
        except Exception as e:
            logger.error(f"Error rpush to key {key}: {e}")
            return 0
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """리스트 범위 조회"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.lrange(key, start, end)
        except Exception as e:
            logger.error(f"Error lrange for key {key}: {e}")
            return []
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """리스트 크기 제한"""
        self._ensure_connected()
        
        try:
            result = await self.redis_client.ltrim(key, start, end)
            return result == "OK"
        except Exception as e:
            logger.error(f"Error ltrim for key {key}: {e}")
            return False
    
    async def llen(self, key: str) -> int:
        """리스트 길이 조회"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.llen(key)
        except Exception as e:
            logger.error(f"Error llen for key {key}: {e}")
            return 0
    
    # Hash operations
    async def hset(self, key: str, field: str, value: Any) -> int:
        """해시 필드 설정"""
        self._ensure_connected()
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            
            return await self.redis_client.hset(key, field, value)
        except Exception as e:
            logger.error(f"Error hset for key {key}, field {field}: {e}")
            return 0
    
    async def hget(self, key: str, field: str) -> Optional[str]:
        """해시 필드 조회"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.hget(key, field)
        except Exception as e:
            logger.error(f"Error hget for key {key}, field {field}: {e}")
            return None
    
    async def hgetall(self, key: str) -> Dict[str, str]:
        """해시 전체 조회"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.hgetall(key)
        except Exception as e:
            logger.error(f"Error hgetall for key {key}: {e}")
            return {}
    
    async def hdel(self, key: str, *fields: str) -> int:
        """해시 필드 삭제"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.hdel(key, *fields)
        except Exception as e:
            logger.error(f"Error hdel for key {key}, fields {fields}: {e}")
            return 0
    
    # Utility methods
    async def keys(self, pattern: str = "*") -> List[str]:
        """패턴으로 키 검색"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.keys(pattern)
        except Exception as e:
            logger.error(f"Error getting keys with pattern {pattern}: {e}")
            return []
    
    async def flushdb(self) -> bool:
        """현재 DB의 모든 키 삭제"""
        self._ensure_connected()
        
        try:
            result = await self.redis_client.flushdb()
            return result == "OK"
        except Exception as e:
            logger.error(f"Error flushing database: {e}")
            return False
    
    async def info(self, section: Optional[str] = None) -> Dict:
        """Redis 서버 정보"""
        self._ensure_connected()
        
        try:
            return await self.redis_client.info(section)
        except Exception as e:
            logger.error(f"Error getting Redis info: {e}")
            return {}
    
    # Cache-specific methods
    async def cache_with_ttl(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """TTL과 함께 캐싱"""
        return await self.set(key, value, ttl)
    
    async def get_or_set(self, key: str, factory_func, ttl: int = 3600) -> Any:
        """캐시에서 조회하거나 없으면 생성 후 캐싱"""
        value = await self.get(key)
        
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        
        # 캐시에 없으면 새로 생성
        if asyncio.iscoroutinefunction(factory_func):
            new_value = await factory_func()
        else:
            new_value = factory_func()
        
        await self.set(key, new_value, ttl)
        return new_value
    
    async def increment_counter(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """카운터 증가"""
        self._ensure_connected()
        
        try:
            result = await self.redis_client.incr(key, amount)
            
            if ttl and result == amount:  # 새로 생성된 키인 경우
                await self.redis_client.expire(key, ttl)
            
            return result
        except Exception as e:
            logger.error(f"Error incrementing counter {key}: {e}")
            return 0
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Redis 연결 상태 및 기본 통계"""
        try:
            if not self._connected:
                return {"status": "disconnected", "error": "Not connected to Redis"}
            
            # Ping 테스트
            ping_result = await self.redis_client.ping()
            if not ping_result:
                return {"status": "error", "error": "Ping failed"}
            
            # 기본 정보 수집
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "connected": True,
                "version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0)
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "connected": False}


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)
    
    async with RedisCache(host="localhost") as cache:
        # 기본 캐시 테스트
        await cache.set("test_key", "test_value", ttl=10)
        value = await cache.get("test_key")
        print(f"Cached value: {value}")
        
        # JSON 캐시 테스트
        test_data = {"symbol": "BTCUSDT", "price": 50000, "timestamp": datetime.now()}
        await cache.set("test_json", test_data, ttl=10)
        json_value = await cache.get_json("test_json")
        print(f"JSON value: {json_value}")
        
        # 리스트 테스트
        await cache.lpush("test_list", "item1", "item2")
        list_items = await cache.lrange("test_list", 0, -1)
        print(f"List items: {list_items}")
        
        # 상태 확인
        health = await cache.get_health_status()
        print(f"Redis health: {health}")


if __name__ == "__main__":
    asyncio.run(main())