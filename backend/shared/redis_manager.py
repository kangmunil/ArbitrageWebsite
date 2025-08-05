"""
공통 Redis 클라이언트 관리자

모든 마이크로서비스에서 사용할 수 있는 표준화된 Redis 연결 및 작업 관리를 제공합니다.
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, AsyncGenerator
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
            if self.client is None:
                return False
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            result = await self.client.set(key, serialized_value)
            
            if expire and self.client is not None:
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
            if self.client is None:
                return default
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
            if self.client is None:
                return 0
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
            
            if self.client is None:
                return False
            result = await self.client.hset(name, mapping=serialized_mapping)  # type: ignore
            
            if expire and self.client is not None:
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
            if self.client is None:
                return False
            result = await self.client.hset(name, field, serialized_value)  # type: ignore
            
            if expire and self.client is not None:
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
            if self.client is None:
                return default
            value = await self.client.hget(name, field)  # type: ignore
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
            if self.client is None:
                return {}
            hash_data = await self.client.hgetall(name)  # type: ignore
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
            
            if self.client is None:
                return 0
            return await self.client.lpush(name, *serialized_values)  # type: ignore
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis LPUSH 오류 ({name}): {e}")
            return 0
    
    async def lrange(self, name: str, start: int = 0, end: int = -1) -> List[Any]:
        """리스트 범위 조회"""
        if not await self.ensure_connection():
            return []
        
        try:
            if self.client is None:
                return []
            values = await self.client.lrange(name, start, end)  # type: ignore
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
            if self.client is None:
                return 0
            return await self.client.exists(*keys)
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis EXISTS 오류: {e}")
            return 0
    
    async def expire(self, name: str, time: int) -> bool:
        """키 만료 시간 설정"""
        if not await self.ensure_connection():
            return False
        
        try:
            if self.client is None:
                return False
            return await self.client.expire(name, time)
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis EXPIRE 오류 ({name}): {e}")
            return False
    
    async def ping(self) -> bool:
        """연결 상태 확인"""
        if not await self.ensure_connection():
            return False
        
        try:
            if self.client is None:
                return False
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def info(self) -> Dict[str, Any]:
        """Redis 서버 정보 조회"""
        if not await self.ensure_connection():
            return {}
        
        try:
            if self.client is None:
                return {}
            return await self.client.info()
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis INFO 오류: {e}")
            return {}
    
    # === Pub/Sub Operations ===
    
    async def publish(self, channel: str, message: Any) -> int:
        """Redis 채널에 메시지 발행"""
        if not await self.ensure_connection():
            return 0
        
        try:
            if self.client is None:
                return 0
            
            # 메시지를 JSON으로 직렬화
            serialized_message = json.dumps(message, default=str) if not isinstance(message, str) else message
            
            # 메시지 발행
            result = await self.client.publish(channel, serialized_message)
            logger.debug(f"📡 [{self.service_name}] Published to {channel}: {len(str(serialized_message))} bytes to {result} subscribers")
            return result
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis PUBLISH 오류 ({channel}): {e}")
            return 0
    
    async def subscribe(self, *channels: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Redis 채널 구독 (비동기 제너레이터)"""
        if not await self.ensure_connection():
            logger.error(f"❌ [{self.service_name}] Redis 연결 실패, 구독 불가")
            return
        
        try:
            if self.client is None:
                logger.error(f"❌ [{self.service_name}] Redis 클라이언트가 없음")
                return
            
            # PubSub 객체 생성
            pubsub = self.client.pubsub()
            await pubsub.subscribe(*channels)
            
            logger.info(f"📻 [{self.service_name}] Subscribed to channels: {', '.join(channels)}")
            
            try:
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            # JSON 파싱 시도
                            data = json.loads(message['data'])
                            yield {
                                'channel': message['channel'],
                                'data': data,
                                'type': message['type']
                            }
                        except (json.JSONDecodeError, TypeError):
                            # JSON이 아닌 경우 원본 데이터 반환
                            yield {
                                'channel': message['channel'],
                                'data': message['data'],
                                'type': message['type']
                            }
                    elif message['type'] in ('subscribe', 'unsubscribe'):
                        logger.debug(f"📻 [{self.service_name}] {message['type']}: {message['channel']}")
            except asyncio.CancelledError:
                logger.info(f"📻 [{self.service_name}] Subscription cancelled")
                raise
            except Exception as e:
                logger.error(f"❌ [{self.service_name}] Subscription error: {e}")
                raise
            finally:
                await pubsub.unsubscribe(*channels)
                await pubsub.close()
                logger.info(f"📻 [{self.service_name}] Unsubscribed from channels: {', '.join(channels)}")
                
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] Redis SUBSCRIBE 오류: {e}")
            return
    
    async def subscribe_with_handler(self, channel: str, handler_func, max_retries: int = 5):
        """Redis 채널 구독 및 메시지 핸들러 실행 (재연결 포함)"""
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"📻 [{self.service_name}] Starting subscription to {channel} (attempt {retry_count + 1})")
                
                async for message in self.subscribe(channel):
                    try:
                        await handler_func(message)
                    except Exception as e:
                        logger.error(f"❌ [{self.service_name}] Handler error for {channel}: {e}")
                        continue
                
                # 정상 종료
                break
                
            except asyncio.CancelledError:
                logger.info(f"📻 [{self.service_name}] Subscription to {channel} cancelled")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ [{self.service_name}] Subscription error (attempt {retry_count}/{max_retries}): {e}")
                
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)  # 지수 백오프 (최대 30초)
                    logger.info(f"⏳ [{self.service_name}] Retrying subscription in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ [{self.service_name}] Max retries exceeded for {channel}")
                    break
    
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
    
    async def get_exchange_data(self, exchange: str, symbol: Optional[str] = None) -> Union[Dict[str, Any], Any]:
        """거래소 데이터 조회"""
        hash_key = f"market:{exchange}"
        
        if symbol:
            return await self.redis.hget(hash_key, symbol or "", {})
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
            if await self.redis.ensure_connection() and self.redis.client is not None:
                await self.redis.client.ltrim(list_key, 0, 999)  # type: ignore
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