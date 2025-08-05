"""Liquidation Data WebSocket Collector

바이낸스 청산 웹소켓 스트림에서 실시간 청산 데이터를 수집하고 집계
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import websockets.client
import websockets.exceptions
from collections import defaultdict, deque

from models.data_schemas import (
    LiquidationEvent, LiquidationSummary, Exchange, PositionSide
)
from utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class LiquidationWebSocketCollector:
    """바이낸스 청산 웹소켓 데이터 수집기"""
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.redis_cache = redis_cache
        self.websocket = None
        self.is_running = False
        
        # 웹소켓 설정
        self.websocket_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
        self.reconnect_delay = 5  # 재연결 대기 시간 (초)
        self.max_reconnect_attempts = 10
        
        # 데이터 저장소 (메모리 기반)
        self.liquidation_events: deque = deque(maxlen=10000)  # 최근 10,000개 이벤트
        self.hourly_summaries: Dict[str, Dict[str, LiquidationSummary]] = defaultdict(dict)  # symbol -> hour -> summary
        
        # 추적할 심볼 목록
        self.tracked_symbols: Set[str] = {
            "BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOGEUSDT",
            "LINKUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT",
            "UNIUSDT", "FILUSDT", "TRXUSDT", "ATOMUSDT", "NEARUSDT"
        }
        
        # 통계 카운터
        self.stats = {
            "total_events": 0,
            "events_per_symbol": defaultdict(int),
            "connection_errors": 0,
            "last_event_time": None
        }
        
        # 데이터 복구 완료 플래그
        self.data_recovery_completed = False
    
    async def recover_data_from_redis(self):
        """Redis에서 기존 청산 데이터 복구"""
        if not self.redis_cache or self.data_recovery_completed:
            return
            
        try:
            logger.info("🔄 Redis에서 청산 데이터 복구 시작...")
            recovered_events = 0
            
            for symbol in self.tracked_symbols:
                # Redis에서 최근 이벤트 데이터 복구
                recent_key = f"liquidation_recent:{symbol}"
                try:
                    cached_events = await self.redis_cache.lrange(recent_key, 0, 999)
                    
                    for event_json in reversed(cached_events):  # 시간순으로 복구
                        try:
                            event_data = json.loads(event_json)
                            # 24시간 이내 데이터만 복구
                            event_time = datetime.fromisoformat(event_data['timestamp'].replace('Z', '+00:00'))
                            if datetime.now() - event_time <= timedelta(hours=24):
                                # LiquidationEvent 객체 재생성
                                recovered_event = LiquidationEvent(
                                    exchange=Exchange(event_data['exchange']),
                                    symbol=event_data['symbol'],
                                    timestamp=event_time,
                                    side=PositionSide(event_data['side']),
                                    price=float(event_data['price']),
                                    quantity=float(event_data['quantity']),
                                    value_usd=float(event_data['value_usd']),
                                    order_id=event_data.get('order_id'),
                                    leverage=float(event_data.get('leverage', 1))
                                )
                                self.liquidation_events.append(recovered_event)
                                recovered_events += 1
                                
                        except Exception as e:
                            logger.debug(f"이벤트 복구 실패: {e}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"{symbol} 데이터 복구 실패: {e}")
                    continue
            
            self.data_recovery_completed = True
            logger.info(f"✅ 청산 데이터 복구 완료: {recovered_events}개 이벤트")
            
        except Exception as e:
            logger.error(f"❌ 데이터 복구 중 오류: {e}")

    async def start_collection(self):
        """청산 데이터 수집 시작"""
        self.is_running = True
        
        # 서비스 시작 시 기존 데이터 복구
        await self.recover_data_from_redis()
        
        reconnect_count = 0
        
        while self.is_running and reconnect_count < self.max_reconnect_attempts:
            try:
                logger.info(f"Connecting to Binance liquidation WebSocket...")
                
                async with websockets.client.connect(
                    self.websocket_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    logger.info("Connected to Binance liquidation WebSocket")
                    reconnect_count = 0  # 연결 성공 시 재연결 카운터 리셋
                    
                    # 메시지 수신 루프
                    async for message in websocket:
                        try:
                            await self._process_liquidation_message(message)
                        except Exception as e:
                            logger.error(f"Error processing liquidation message: {e}")
                            continue
                            
            except websockets.exceptions.ConnectionClosedError:
                logger.warning("WebSocket connection closed. Attempting to reconnect...")
                reconnect_count += 1
                self.stats["connection_errors"] += 1
                
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                reconnect_count += 1
                self.stats["connection_errors"] += 1
            
            if self.is_running and reconnect_count < self.max_reconnect_attempts:
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds... (attempt {reconnect_count})")
                await asyncio.sleep(self.reconnect_delay)
        
        if reconnect_count >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Stopping collection.")
            self.is_running = False
    
    async def stop_collection(self):
        """청산 데이터 수집 중지"""
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed")
    
    async def _process_liquidation_message(self, message: str | bytes):
        """청산 메시지 처리"""
        try:
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            
            data = json.loads(message)
            
            # 바이낸스 청산 이벤트 구조 확인
            if "o" in data:  # 청산 주문 데이터
                order_data = data["o"]
                
                symbol = order_data.get("s", "")
                if symbol not in self.tracked_symbols:
                    return  # 추적하지 않는 심볼은 무시
                
                # 청산 이벤트 객체 생성
                liquidation_event = LiquidationEvent(
                    exchange=Exchange.BINANCE,
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(order_data.get("T", 0) / 1000),
                    side=PositionSide.LONG if order_data.get("S") == "SELL" else PositionSide.SHORT,
                    price=float(order_data.get("p", 0)),
                    quantity=float(order_data.get("q", 0)),
                    value_usd=float(order_data.get("p", 0)) * float(order_data.get("q", 0)),
                    order_id=str(order_data.get("i", "")),
                    leverage=float(order_data.get("l", 1))
                )
                
                # 이벤트 저장
                self.liquidation_events.append(liquidation_event)
                
                # 통계 업데이트
                self.stats["total_events"] += 1
                self.stats["events_per_symbol"][symbol] += 1
                self.stats["last_event_time"] = liquidation_event.timestamp
                
                # 시간별 요약 업데이트
                await self._update_hourly_summary(liquidation_event)
                
                # Redis에 실시간 데이터 저장
                if self.redis_cache:
                    await self._cache_liquidation_event(liquidation_event)
                
                logger.debug(f"Processed liquidation: {symbol} {liquidation_event.side.value} "
                           f"${liquidation_event.value_usd:.2f}")
                
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON message")
        except Exception as e:
            logger.error(f"Error processing liquidation message: {e}")
    
    async def _update_hourly_summary(self, event: LiquidationEvent):
        """시간별 청산 요약 업데이트"""
        hour_key = event.timestamp.strftime("%Y-%m-%d-%H")
        symbol = event.symbol
        
        if hour_key not in self.hourly_summaries[symbol]:
            # 새로운 시간대 요약 생성
            self.hourly_summaries[symbol][hour_key] = LiquidationSummary(
                symbol=symbol,
                timeframe="1h",
                timestamp=event.timestamp.replace(minute=0, second=0, microsecond=0),
                total_liquidation_usd=0,
                long_liquidation_usd=0,
                short_liquidation_usd=0,
                long_percentage=0,
                short_percentage=0,
                total_events=0,
                long_events=0,
                short_events=0,
                exchange_breakdown={Exchange.BINANCE: 0}
            )
        
        summary = self.hourly_summaries[symbol][hour_key]
        
        # 요약 데이터 업데이트
        summary.total_liquidation_usd += event.value_usd
        summary.total_events += 1
        summary.exchange_breakdown[Exchange.BINANCE] += event.value_usd
        
        if event.side == PositionSide.LONG:
            summary.long_liquidation_usd += event.value_usd
            summary.long_events += 1
        else:
            summary.short_liquidation_usd += event.value_usd
            summary.short_events += 1
        
        # 비율 재계산
        if summary.total_liquidation_usd > 0:
            summary.long_percentage = (summary.long_liquidation_usd / summary.total_liquidation_usd) * 100
            summary.short_percentage = (summary.short_liquidation_usd / summary.total_liquidation_usd) * 100
    
    async def get_24h_liquidation_summary(self, symbol: str) -> Optional[LiquidationSummary]:
        """24시간 청산 요약 데이터 조회"""
        now = datetime.now()
        start_time = now - timedelta(hours=24)
        
        total_usd = 0
        long_usd = 0
        short_usd = 0
        total_events = 0
        long_events = 0
        short_events = 0
        
        # 지난 24시간의 이벤트 집계
        for event in self.liquidation_events:
            if (event.symbol == symbol and 
                event.timestamp >= start_time and 
                event.timestamp <= now):
                
                total_usd += event.value_usd
                total_events += 1
                
                if event.side == PositionSide.LONG:
                    long_usd += event.value_usd
                    long_events += 1
                else:
                    short_usd += event.value_usd
                    short_events += 1
        
        if total_events == 0:
            return None
        
        return LiquidationSummary(
            symbol=symbol,
            timeframe="24h",
            timestamp=now,
            total_liquidation_usd=total_usd,
            long_liquidation_usd=long_usd,
            short_liquidation_usd=short_usd,
            long_percentage=(long_usd / total_usd * 100) if total_usd > 0 else 0,
            short_percentage=(short_usd / total_usd * 100) if total_usd > 0 else 0,
            total_events=total_events,
            long_events=long_events,
            short_events=short_events,
            exchange_breakdown={Exchange.BINANCE: total_usd}
        )
    
    async def get_all_24h_summaries(self) -> Dict[str, LiquidationSummary]:
        """모든 추적 심볼의 24시간 청산 요약"""
        summaries = {}
        
        for symbol in self.tracked_symbols:
            summary = await self.get_24h_liquidation_summary(symbol)
            if summary:
                summaries[symbol] = summary
        
        return summaries
    
    async def get_recent_liquidation_events(self, symbol: str, limit: int = 100) -> List[LiquidationEvent]:
        """최근 청산 이벤트 조회"""
        events = []
        count = 0
        
        # deque를 역순으로 순회 (최신 이벤트부터)
        for event in reversed(self.liquidation_events):
            if event.symbol == symbol:
                events.append(event)
                count += 1
                if count >= limit:
                    break
        
        return events
    
    async def _cache_liquidation_event(self, event: LiquidationEvent):
        """청산 이벤트를 Redis에 캐싱"""
        if not self.redis_cache:
            return
        
        try:
            # 최근 이벤트 리스트 업데이트 (최근 1000개 유지)
            recent_key = f"liquidation_recent:{event.symbol}"
            event_data = event.model_dump()
            
            # Redis에 리스트로 저장 (LPUSH + LTRIM으로 최근 1000개 유지)
            await self.redis_cache.lpush(recent_key, json.dumps(event_data, default=str))
            await self.redis_cache.ltrim(recent_key, 0, 999)  # 최근 1000개만 유지
            await self.redis_cache.expire(recent_key, 86400)  # 24시간 TTL
            
            # 실시간 통계도 업데이트
            stats_key = f"liquidation_stats:{event.symbol}"
            current_stats = await self.redis_cache.get(stats_key)
            
            if current_stats:
                stats = json.loads(current_stats)
            else:
                stats = {"total_usd": 0.0, "long_usd": 0.0, "short_usd": 0.0, "count": 0}
            
            stats["total_usd"] += float(event.value_usd)
            stats["count"] += 1
            
            if event.side == PositionSide.LONG:
                stats["long_usd"] += float(event.value_usd)
            else:
                stats["short_usd"] += float(event.value_usd)
            
            await self.redis_cache.set(stats_key, json.dumps(stats), ttl=90000)  # 25시간 TTL
            
        except Exception as e:
            logger.error(f"Error caching liquidation event: {e}")
    
    def get_collection_stats(self) -> Dict:
        """수집 통계 반환"""
        return {
            **self.stats,
            "is_running": self.is_running,
            "tracked_symbols": list(self.tracked_symbols),
            "events_in_memory": len(self.liquidation_events),
            "hourly_summaries_count": sum(len(summaries) for summaries in self.hourly_summaries.values())
        }


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)
    
    collector = LiquidationWebSocketCollector()
    
    # 백그라운드에서 데이터 수집 시작
    collection_task = asyncio.create_task(collector.start_collection())
    
    try:
        # 10초 동안 데이터 수집
        await asyncio.sleep(10)
        
        # 통계 출력
        stats = collector.get_collection_stats()
        print(f"Collection Stats: {stats}")
        
        # BTC 24시간 요약 조회
        btc_summary = await collector.get_24h_liquidation_summary("BTCUSDT")
        if btc_summary:
            print(f"BTC 24h Liquidations: ${btc_summary.total_liquidation_usd:.2f}")
            print(f"  Long: ${btc_summary.long_liquidation_usd:.2f} ({btc_summary.long_percentage:.1f}%)")
            print(f"  Short: ${btc_summary.short_liquidation_usd:.2f} ({btc_summary.short_percentage:.1f}%)")
    
    finally:
        await collector.stop_collection()
        collection_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())