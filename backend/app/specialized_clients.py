"""
거래소별 전문 클라이언트 구현

각 거래소의 API 특성에 맞춘 최적화된 클라이언트를 제공합니다.
"""

import asyncio
import json
import logging
import time
import uuid
import hashlib
from typing import Dict, List, Optional, Set, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
import websockets
import aiohttp

from .enhanced_websocket import EnhancedWebSocketClient
from .api_manager import APIManager, RateLimitConfig, CircuitBreakerConfig
from .exchange_specifications import (
    get_exchange_spec, normalize_ticker_data, is_retriable_error, 
    is_rate_limited, get_symbol_format, EXCHANGE_SPECS
)

logger = logging.getLogger(__name__)

@dataclass
class SubscriptionRequest:
    """구독 요청 정보"""
    symbols: Set[str]
    channels: List[str] = None
    params: Dict[str, Any] = None

class ExchangeClient(ABC):
    """거래소 클라이언트 기본 클래스"""
    
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self.spec = get_exchange_spec(exchange_name)
        if not self.spec:
            raise ValueError(f"Unknown exchange: {exchange_name}")
        
        self.is_connected = False
        self.subscribed_symbols: Set[str] = set()
        self.last_heartbeat = time.time()
        self.connection_stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "messages_received": 0,
            "errors": 0,
            "last_message_time": None
        }
        
        # 콜백 함수들
        self.on_ticker_data: Optional[Callable[[str, Dict], None]] = None
        self.on_connection_change: Optional[Callable[[bool], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """거래소에 연결"""
        pass
    
    @abstractmethod
    async def subscribe(self, request: SubscriptionRequest) -> bool:
        """데이터 구독"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """연결 종료"""
        pass
    
    @abstractmethod
    def get_supported_symbols(self) -> Set[str]:
        """지원되는 심볼 목록 반환"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """클라이언트 통계 반환"""
        return {
            "exchange": self.exchange_name,
            "is_connected": self.is_connected,
            "subscribed_symbols_count": len(self.subscribed_symbols),
            "stats": self.connection_stats,
            "uptime_seconds": time.time() - self.last_heartbeat if self.is_connected else 0
        }

class UpbitClient(ExchangeClient):
    """업비트 전문 클라이언트"""
    
    def __init__(self):
        super().__init__("upbit")
        self.websocket_client = None
        self.api_manager = APIManager("Upbit", self.spec.base_url)
        
        # 업비트 특화 설정
        self.api_manager.configure_rate_limits(RateLimitConfig(
            requests_per_second=self.spec.rest_rate_limits.requests_per_second,
            requests_per_minute=self.spec.rest_rate_limits.requests_per_minute,
            requests_per_hour=self.spec.rest_rate_limits.requests_per_hour,
            burst_size=self.spec.rest_rate_limits.burst_capacity
        ))
        
        # 데이터 검증 함수 추가
        self.api_manager.add_validator(self._validate_upbit_data)
    
    def _validate_upbit_data(self, data: Any) -> bool:
        """업비트 데이터 유효성 검사"""
        if isinstance(data, list):
            return all(
                isinstance(item, dict) and 
                'market' in item and 
                'trade_price' in item
                for item in data
            )
        elif isinstance(data, dict):
            return 'market' in data and 'trade_price' in data
        return False
    
    async def connect(self) -> bool:
        """업비트 WebSocket 연결"""
        try:
            self.connection_stats["connection_attempts"] += 1
            
            self.websocket_client = EnhancedWebSocketClient(
                uri=self.spec.websocket_url,
                name=f"Upbit-{id(self)}",
                max_retries=self.spec.websocket_spec.reconnect_limit,
                timeout=30.0
            )
            
            # 콜백 설정
            self.websocket_client.on_connect = self._on_websocket_connect
            self.websocket_client.on_message = self._on_websocket_message
            self.websocket_client.on_disconnect = self._on_websocket_disconnect
            self.websocket_client.on_error = self._on_websocket_error
            
            # 연결 시도
            success = await self.websocket_client.connect()
            if success:
                self.is_connected = True
                self.connection_stats["successful_connections"] += 1
                if self.on_connection_change:
                    await self.on_connection_change(True)
                    
            return success
            
        except Exception as e:
            logger.error(f"Upbit 연결 실패: {e}")
            if self.on_error:
                await self.on_error(e)
            return False
    
    async def _on_websocket_connect(self):
        """WebSocket 연결 성공 시 처리"""
        logger.info("Upbit WebSocket 연결 성공")
        self.last_heartbeat = time.time()
    
    async def _on_websocket_message(self, data: Dict):
        """WebSocket 메시지 수신 처리"""
        try:
            self.connection_stats["messages_received"] += 1
            self.connection_stats["last_message_time"] = time.time()
            
            if data.get("type") == "ticker":
                # 티커 데이터 정규화
                normalized = normalize_ticker_data(self.exchange_name, data)
                if normalized and self.on_ticker_data:
                    symbol = data["code"].replace("KRW-", "")
                    await self.on_ticker_data(symbol, normalized)
                    
        except Exception as e:
            logger.error(f"Upbit 메시지 처리 오류: {e}")
            self.connection_stats["errors"] += 1
            if self.on_error:
                await self.on_error(e)
    
    async def _on_websocket_disconnect(self):
        """WebSocket 연결 해제 처리"""
        self.is_connected = False
        if self.on_connection_change:
            await self.on_connection_change(False)
        logger.info("Upbit WebSocket 연결 해제")
    
    async def _on_websocket_error(self, error: Exception):
        """WebSocket 오류 처리"""
        self.connection_stats["errors"] += 1
        if self.on_error:
            await self.on_error(error)
    
    async def subscribe(self, request: SubscriptionRequest) -> bool:
        """업비트 마켓 구독"""
        if not self.websocket_client or not self.is_connected:
            return False
        
        try:
            # 업비트 형식으로 심볼 변환
            upbit_codes = [f"KRW-{symbol}" for symbol in request.symbols]
            
            subscribe_message = [
                {"ticket": str(uuid.uuid4())},
                {
                    "type": "ticker",
                    "codes": upbit_codes,
                    "isOnlySnapshot": False,
                    "isOnlyRealtime": True
                }
            ]
            
            success = await self.websocket_client.send_message(subscribe_message)
            if success:
                self.subscribed_symbols.update(request.symbols)
                logger.info(f"Upbit {len(request.symbols)}개 심볼 구독 완료")
                
            return success
            
        except Exception as e:
            logger.error(f"Upbit 구독 실패: {e}")
            if self.on_error:
                await self.on_error(e)
            return False
    
    async def disconnect(self):
        """연결 종료"""
        if self.websocket_client:
            await self.websocket_client.disconnect()
        self.is_connected = False
        self.subscribed_symbols.clear()
    
    def get_supported_symbols(self) -> Set[str]:
        """업비트 지원 심볼 조회"""
        try:
            response = self.api_manager.make_sync_request(
                "GET", "/v1/market/all", timeout=10
            )
            
            if response:
                krw_markets = [
                    item['market'].replace('KRW-', '') 
                    for item in response 
                    if item['market'].startswith('KRW-')
                ]
                return set(krw_markets)
                
        except Exception as e:
            logger.error(f"Upbit 심볼 조회 실패: {e}")
            
        return set()

class BinanceClient(ExchangeClient):
    """바이낸스 전문 클라이언트"""
    
    def __init__(self):
        super().__init__("binance")
        self.websocket_client = None
        self.api_manager = APIManager("Binance", self.spec.base_url)
        
        # 바이낸스 특화 설정 (가중치 기반 Rate Limiting)
        self.api_manager.configure_rate_limits(RateLimitConfig(
            requests_per_second=self.spec.rest_rate_limits.requests_per_second,
            requests_per_minute=self.spec.rest_rate_limits.requests_per_minute,
            requests_per_hour=self.spec.rest_rate_limits.requests_per_hour,
            burst_size=self.spec.rest_rate_limits.burst_capacity
        ))
        
        self.api_manager.add_validator(self._validate_binance_data)
        
        # 바이낸스 특화 변수들
        self.listen_key = None
        self.last_ping = time.time()
        
    def _validate_binance_data(self, data: Any) -> bool:
        """바이낸스 데이터 유효성 검사"""
        if isinstance(data, list):
            return all(
                isinstance(item, dict) and 
                's' in item and  # symbol
                'c' in item      # close price
                for item in data
            )
        elif isinstance(data, dict):
            return 's' in data and 'c' in data
        return False
    
    async def connect(self) -> bool:
        """바이낸스 WebSocket 연결"""
        try:
            self.connection_stats["connection_attempts"] += 1
            
            # 바이낸스는 전체 티커 스트림 사용
            self.websocket_client = EnhancedWebSocketClient(
                uri=self.spec.websocket_spec.url,
                name=f"Binance-{id(self)}",
                max_retries=self.spec.websocket_spec.reconnect_limit,
                timeout=30.0
            )
            
            # 콜백 설정
            self.websocket_client.on_connect = self._on_websocket_connect
            self.websocket_client.on_message = self._on_websocket_message
            self.websocket_client.on_disconnect = self._on_websocket_disconnect
            self.websocket_client.on_error = self._on_websocket_error
            
            success = await self.websocket_client.connect()
            if success:
                self.is_connected = True
                self.connection_stats["successful_connections"] += 1
                if self.on_connection_change:
                    await self.on_connection_change(True)
                    
                # 하트비트 태스크 시작
                asyncio.create_task(self._heartbeat_task())
                    
            return success
            
        except Exception as e:
            logger.error(f"Binance 연결 실패: {e}")
            if self.on_error:
                await self.on_error(e)
            return False
    
    async def _heartbeat_task(self):
        """바이낸스 하트비트 관리"""
        while self.is_connected:
            try:
                current_time = time.time()
                if current_time - self.last_ping > self.spec.websocket_spec.heartbeat_interval:
                    # 바이낸스는 ping/pong 자동 처리되므로 연결 상태만 확인
                    self.last_ping = current_time
                    
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Binance 하트비트 오류: {e}")
                break
    
    async def _on_websocket_connect(self):
        """WebSocket 연결 성공 시 처리"""
        logger.info("Binance WebSocket 연결 성공")
        self.last_heartbeat = time.time()
    
    async def _on_websocket_message(self, data: List):
        """WebSocket 메시지 수신 처리 (바이낸스는 배열로 전송)"""
        try:
            self.connection_stats["messages_received"] += 1
            self.connection_stats["last_message_time"] = time.time()
            
            if isinstance(data, list):
                for ticker_data in data:
                    if ticker_data.get("s", "").endswith("USDT"):
                        symbol = ticker_data["s"].replace("USDT", "")
                        
                        # 구독 중인 심볼만 처리 (모든 심볼을 구독하지 않은 경우)
                        if self.subscribed_symbols and symbol not in self.subscribed_symbols:
                            continue
                            
                        normalized = normalize_ticker_data(self.exchange_name, ticker_data)
                        if normalized and self.on_ticker_data:
                            await self.on_ticker_data(symbol, normalized)
                            
        except Exception as e:
            logger.error(f"Binance 메시지 처리 오류: {e}")
            self.connection_stats["errors"] += 1
            if self.on_error:
                await self.on_error(e)
    
    async def _on_websocket_disconnect(self):
        """WebSocket 연결 해제 처리"""
        self.is_connected = False
        if self.on_connection_change:
            await self.on_connection_change(False)
        logger.info("Binance WebSocket 연결 해제")
    
    async def _on_websocket_error(self, error: Exception):
        """WebSocket 오류 처리"""
        self.connection_stats["errors"] += 1
        if self.on_error:
            await self.on_error(error)
    
    async def subscribe(self, request: SubscriptionRequest) -> bool:
        """바이낸스 구독 (전체 티커 스트림 사용)"""
        # 바이낸스는 !ticker@arr로 모든 티커를 받으므로 별도 구독 불필요
        self.subscribed_symbols.update(request.symbols)
        logger.info(f"Binance {len(request.symbols)}개 심볼 구독 설정 (필터링 방식)")
        return True
    
    async def disconnect(self):
        """연결 종료"""
        if self.websocket_client:
            await self.websocket_client.disconnect()
        self.is_connected = False
        self.subscribed_symbols.clear()
    
    def get_supported_symbols(self) -> Set[str]:
        """바이낸스 지원 심볼 조회"""
        try:
            response = self.api_manager.make_sync_request(
                "GET", "/api/v3/exchangeInfo", timeout=10
            )
            
            if response and "symbols" in response:
                usdt_symbols = {
                    item['symbol'].replace('USDT', '')
                    for item in response['symbols']
                    if item['symbol'].endswith('USDT') and item['status'] == 'TRADING'
                }
                return usdt_symbols
                
        except Exception as e:
            logger.error(f"Binance 심볼 조회 실패: {e}")
            
        return set()

class BybitClient(ExchangeClient):
    """바이비트 전문 클라이언트"""
    
    def __init__(self):
        super().__init__("bybit")
        self.websocket_client = None
        self.api_manager = APIManager("Bybit", self.spec.base_url)
        
        # 바이비트 특화 설정
        self.api_manager.configure_rate_limits(RateLimitConfig(
            requests_per_second=self.spec.rest_rate_limits.requests_per_second,
            requests_per_minute=self.spec.rest_rate_limits.requests_per_minute,
            requests_per_hour=self.spec.rest_rate_limits.requests_per_hour,
            burst_size=self.spec.rest_rate_limits.burst_capacity
        ))
        
        self.api_manager.add_validator(self._validate_bybit_data)
        
        # 바이비트 특화 변수들
        self.req_id = 0
        
    def _validate_bybit_data(self, data: Any) -> bool:
        """바이비트 데이터 유효성 검사"""
        if isinstance(data, dict):
            # 바이비트 WebSocket 응답 구조 확인
            return (
                'topic' in data or 
                ('data' in data and isinstance(data['data'], (dict, list)))
            )
        return False
    
    async def connect(self) -> bool:
        """바이비트 WebSocket 연결"""
        try:
            self.connection_stats["connection_attempts"] += 1
            
            self.websocket_client = EnhancedWebSocketClient(
                uri=self.spec.websocket_spec.url,
                name=f"Bybit-{id(self)}",
                max_retries=self.spec.websocket_spec.reconnect_limit,
                timeout=30.0
            )
            
            # 콜백 설정
            self.websocket_client.on_connect = self._on_websocket_connect
            self.websocket_client.on_message = self._on_websocket_message
            self.websocket_client.on_disconnect = self._on_websocket_disconnect
            self.websocket_client.on_error = self._on_websocket_error
            
            success = await self.websocket_client.connect()
            if success:
                self.is_connected = True
                self.connection_stats["successful_connections"] += 1
                if self.on_connection_change:
                    await self.on_connection_change(True)
                    
                # 하트비트 태스크 시작
                asyncio.create_task(self._heartbeat_task())
                    
            return success
            
        except Exception as e:
            logger.error(f"Bybit 연결 실패: {e}")
            if self.on_error:
                await self.on_error(e)
            return False
    
    async def _heartbeat_task(self):
        """바이비트 하트비트"""
        while self.is_connected:
            try:
                # 바이비트는 ping 메시지 전송 필요
                ping_message = {"op": "ping"}
                await self.websocket_client.send_message(ping_message)
                
                await asyncio.sleep(self.spec.websocket_spec.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Bybit ping 오류: {e}")
                break
    
    async def _on_websocket_connect(self):
        """WebSocket 연결 성공 시 처리"""
        logger.info("Bybit WebSocket 연결 성공")
        self.last_heartbeat = time.time()
    
    async def _on_websocket_message(self, data: Dict):
        """WebSocket 메시지 수신 처리"""
        try:
            self.connection_stats["messages_received"] += 1
            self.connection_stats["last_message_time"] = time.time()
            
            # Pong 메시지 처리
            if data.get("op") == "pong":
                return
            
            # 티커 데이터 처리
            if data.get("topic", "").startswith("tickers"):
                ticker_info = data.get("data", {})
                if isinstance(ticker_info, dict):
                    symbol_raw = ticker_info.get("symbol", "")
                    if symbol_raw.endswith("USDT"):
                        symbol = symbol_raw.replace("USDT", "")
                        
                        normalized = normalize_ticker_data(self.exchange_name, ticker_info)
                        if normalized and self.on_ticker_data:
                            await self.on_ticker_data(symbol, normalized)
                            
        except Exception as e:
            logger.error(f"Bybit 메시지 처리 오류: {e}")
            self.connection_stats["errors"] += 1
            if self.on_error:
                await self.on_error(e)
    
    async def _on_websocket_disconnect(self):
        """WebSocket 연결 해제 처리"""
        self.is_connected = False
        if self.on_connection_change:
            await self.on_connection_change(False)
        logger.info("Bybit WebSocket 연결 해제")
    
    async def _on_websocket_error(self, error: Exception):
        """WebSocket 오류 처리"""
        self.connection_stats["errors"] += 1
        if self.on_error:
            await self.on_error(error)
    
    async def subscribe(self, request: SubscriptionRequest) -> bool:
        """바이비트 티커 구독"""
        if not self.websocket_client or not self.is_connected:
            return False
        
        try:
            # 바이비트는 심볼별 개별 구독
            success_count = 0
            
            for symbol in request.symbols:
                self.req_id += 1
                subscribe_message = {
                    "req_id": str(self.req_id),
                    "op": "subscribe",
                    "args": [f"tickers.{symbol}USDT"]
                }
                
                if await self.websocket_client.send_message(subscribe_message):
                    success_count += 1
                    await asyncio.sleep(0.1)  # 요청 간격
            
            if success_count > 0:
                self.subscribed_symbols.update(request.symbols)
                logger.info(f"Bybit {success_count}/{len(request.symbols)}개 심볼 구독 완료")
                
            return success_count == len(request.symbols)
            
        except Exception as e:
            logger.error(f"Bybit 구독 실패: {e}")
            if self.on_error:
                await self.on_error(e)
            return False
    
    async def disconnect(self):
        """연결 종료"""
        if self.websocket_client:
            await self.websocket_client.disconnect()
        self.is_connected = False
        self.subscribed_symbols.clear()
    
    def get_supported_symbols(self) -> Set[str]:
        """바이비트 지원 심볼 조회"""
        try:
            response = self.api_manager.make_sync_request(
                "GET", "/v5/market/instruments-info", 
                params={"category": "spot"}, 
                timeout=10
            )
            
            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                if "list" in result:
                    usdt_symbols = {
                        item['symbol'].replace('USDT', '')
                        for item in result['list']
                        if item['symbol'].endswith('USDT') and item.get('status') == 'Trading'
                    }
                    return usdt_symbols
                    
        except Exception as e:
            logger.error(f"Bybit 심볼 조회 실패: {e}")
            
        return set()

# === 클라이언트 팩토리 ===

def create_exchange_client(exchange_name: str) -> Optional[ExchangeClient]:
    """거래소 클라이언트 생성"""
    clients = {
        "upbit": UpbitClient,
        "binance": BinanceClient, 
        "bybit": BybitClient
    }
    
    client_class = clients.get(exchange_name.lower())
    if client_class:
        return client_class()
    else:
        logger.error(f"지원하지 않는 거래소: {exchange_name}")
        return None

def get_all_supported_symbols() -> Dict[str, Set[str]]:
    """모든 거래소의 지원 심볼 조회"""
    results = {}
    
    for exchange_name in ["upbit", "binance", "bybit"]:
        try:
            client = create_exchange_client(exchange_name)
            if client:
                symbols = client.get_supported_symbols()
                results[exchange_name] = symbols
                logger.info(f"{exchange_name}: {len(symbols)}개 심볼 지원")
        except Exception as e:
            logger.error(f"{exchange_name} 심볼 조회 오류: {e}")
            results[exchange_name] = set()
    
    return results