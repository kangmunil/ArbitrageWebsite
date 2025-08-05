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
from typing import Dict, List, Optional, Set, Callable, Any, Awaitable, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
import websockets
import aiohttp

from .enhanced_websocket import EnhancedWebSocketClient
from .api_manager import APIManager, RateLimitConfig, CircuitBreakerConfig
from .exchange_specifications import (
    get_exchange_spec, normalize_ticker_data, is_retriable_error, 
    is_rate_limited, get_symbol_format, EXCHANGE_SPECS, ExchangeSpec
)

logger = logging.getLogger(__name__)

@dataclass
class SubscriptionRequest:
    """구독 요청 정보를 담는 데이터 클래스입니다.

    Attributes:
        symbols (Set[str]): 구독할 심볼(코인)들의 집합.
        channels (Optional[List[str]]): 구독할 채널 목록 (예: "ticker", "orderbook"). 기본값은 None.
        params (Optional[Dict[str, Any]]): 구독에 필요한 추가 파라미터. 기본값은 None.
    """
    symbols: Set[str]
    channels: Optional[List[str]] = None
    params: Optional[Dict[str, Any]] = None

class ExchangeClient(ABC):
    """거래소 클라이언트의 추상 기본 클래스입니다.

    모든 거래소 클라이언트는 이 클래스를 상속받아 필수 메서드들을 구현해야 합니다.
    연결 상태, 구독 심볼, 연결 통계 등을 관리합니다.
    """
    
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self.spec: Optional[ExchangeSpec] = get_exchange_spec(exchange_name)
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
        self.on_ticker_data: Optional[Callable[[str, Dict], Awaitable[None]]] = None
        self.on_connection_change: Optional[Callable[[bool], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[Exception], Awaitable[None]]] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """거래소에 비동기적으로 연결을 시도합니다.

        이 메서드는 각 거래소 클라이언트에서 반드시 구현되어야 합니다.

        Returns:
            bool: 연결 성공 여부.
        """
        pass
    
    @abstractmethod
    async def subscribe(self, request: SubscriptionRequest) -> bool:
        """지정된 구독 요청에 따라 거래소 데이터를 구독합니다.

        이 메서드는 각 거래소 클라이언트에서 반드시 구현되어야 합니다.

        Args:
            request (SubscriptionRequest): 구독할 심볼, 채널 및 기타 파라미터 정보를 담은 객체.

        Returns:
            bool: 구독 성공 여부.
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """거래소와의 연결을 종료합니다.

        이 메서드는 각 거래소 클라이언트에서 반드시 구현되어야 합니다.
        """
        pass
    
    @abstractmethod
    def get_supported_symbols(self) -> Set[str]:
        """거래소에서 지원하는 모든 심볼(코인) 목록을 반환합니다.

        이 메서드는 각 거래소 클라이언트에서 반드시 구현되어야 합니다.

        Returns:
            Set[str]: 지원되는 심볼들의 집합.
        """
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """현재 클라이언트의 연결 및 메시지 수신 통계를 반환합니다.

        Returns:
            Dict[str, Any]: 클라이언트 통계 정보를 담은 딕셔너리.
                            'exchange', 'is_connected', 'subscribed_symbols_count',
                            'stats', 'uptime_seconds' 키를 포함합니다.
        """
        return {
            "exchange": self.exchange_name,
            "is_connected": self.is_connected,
            "subscribed_symbols_count": len(self.subscribed_symbols),
            "stats": self.connection_stats,
            "uptime_seconds": time.time() - self.last_heartbeat if self.is_connected else 0
        }

class UpbitClient(ExchangeClient):
    """업비트 거래소와 상호작용하기 위한 전문 클라이언트입니다.

    ExchangeClient를 상속받아 업비트 WebSocket 및 REST API를 통해
    데이터를 수집하고 처리하는 기능을 구현합니다.
    """
    
    def __init__(self):
        super().__init__("upbit")
        self.websocket_client = None
        self.api_manager = APIManager("Upbit", self.spec.base_url if self.spec else "")
        
        # 업비트 특화 설정
        if self.spec and self.spec.rest_rate_limits:
            self.api_manager.configure_rate_limits(RateLimitConfig(
                requests_per_second=self.spec.rest_rate_limits.requests_per_second,
                requests_per_minute=self.spec.rest_rate_limits.requests_per_minute,
                requests_per_hour=self.spec.rest_rate_limits.requests_per_hour,
                burst_size=self.spec.rest_rate_limits.burst_capacity
            ))
        
        # 데이터 검증 함수 추가
        self.api_manager.add_validator(self._validate_upbit_data)
    
    def _validate_upbit_data(self, data: Any) -> bool:
        """업비트에서 수신된 데이터의 유효성을 검사합니다.

        데이터가 리스트인 경우 각 항목이 'market'과 'trade_price' 키를 포함하는 딕셔너리인지 확인하고,
        데이터가 단일 딕셔너리인 경우에도 동일한 키를 포함하는지 확인합니다.

        Args:
            data (Any): 유효성을 검사할 업비트 데이터.

        Returns:
            bool: 데이터가 유효하면 True, 그렇지 않으면 False.
        """
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
        """업비트 WebSocket 서버에 연결을 시도합니다.

        EnhancedWebSocketClient를 사용하여 연결을 설정하고,
        연결 성공/실패, 메시지 수신, 연결 해제, 오류 발생 시 호출될 콜백 함수를 설정합니다.

        Returns:
            bool: 연결 성공 여부.
        """
        try:
            self.connection_stats["connection_attempts"] += 1
            
            if self.spec and self.spec.websocket_spec:
                self.websocket_client = EnhancedWebSocketClient(
                    uri=self.spec.websocket_spec.url,
                    name=f"Upbit-{id(self)}",
                    max_retries=self.spec.websocket_spec.reconnect_limit,
                    timeout=30.0
                )
            else:
                logger.error(f"Upbit WebSocket 사양을 찾을 수 없습니다.")
                return False
            
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
                    callback = self.on_connection_change
                    await callback(True)
                    
            return success
            
        except Exception as e:
            logger.error(f"Upbit 연결 실패: {e}")
            if self.on_error:
                await self.on_error(e)
            return False
    
    async def _on_websocket_connect(self):
        """WebSocket 연결 성공 시 호출되는 콜백 함수입니다.

        연결 상태를 로깅하고 마지막 하트비트 시간을 업데이트합니다.
        """
        logger.info("Upbit WebSocket 연결 성공")
        self.last_heartbeat = time.time()
    
    async def _on_websocket_message(self, data: Union[Dict, List]):
        """WebSocket 메시지 수신 시 호출되는 콜백 함수입니다.

        수신된 메시지를 처리하고, 티커 데이터인 경우 정규화하여 `on_ticker_data` 콜백을 호출합니다.
        메시지 수신 통계를 업데이트합니다.

        Args:
            data (Union[Dict, List]): 수신된 WebSocket 메시지 데이터.
        """
        try:
            self.connection_stats["messages_received"] += 1
            self.connection_stats["last_message_time"] = time.time()

            if isinstance(data, dict): # Add this check
                if data.get("type") == "ticker":
                    # 티커 데이터 정규화
                    normalized = normalize_ticker_data(self.exchange_name, data)
                    if normalized and self.on_ticker_data:
                        symbol = data["code"].replace("KRW-", "")
                        await self.on_ticker_data(symbol, normalized)
            else:
                logger.warning(f"Upbit: Unexpected message format received: {type(data)}") # Log unexpected types
                    
        except Exception as e:
            logger.error(f"Upbit 메시지 처리 오류: {e}")
            self.connection_stats["errors"] += 1
            if self.on_error:
                await self.on_error(e)
    
    async def _on_websocket_disconnect(self):
        """WebSocket 연결 해제 시 호출되는 콜백 함수입니다.

        클라이언트의 연결 상태를 업데이트하고 `on_connection_change` 콜백을 호출합니다.
        """
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
        """업비트 마켓 데이터 구독을 요청합니다.

        WebSocket 클라이언트가 연결되어 있지 않거나 실행 중이 아니면 구독할 수 없습니다.
        요청된 심볼들을 업비트의 'KRW-' 형식으로 변환하여 구독 메시지를 생성하고 전송합니다.

        Args:
            request (SubscriptionRequest): 구독할 심볼 정보를 담은 객체.

        Returns:
            bool: 구독 요청 성공 여부.
        """
        if not self.websocket_client or not self.is_connected:
            return False
        
        try:
            # 업비트 형식으로 심볼 변환
            upbit_codes = [f"KRW-{symbol}" for symbol in request.symbols]
            
            subscribe_message = {
                "ticket": str(uuid.uuid4()),
                "type": "ticker",
                "codes": upbit_codes,
                "isOnlySnapshot": False,
                "isOnlyRealtime": True
            }
            
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
        """업비트에서 지원하는 모든 KRW 마켓 심볼(코인) 목록을 조회합니다.

        업비트 REST API를 통해 모든 마켓 정보를 가져와 KRW 마켓에 해당하는 심볼만 추출하여 반환합니다.

        Returns:
            Set[str]: 업비트에서 지원하는 KRW 마켓 심볼들의 집합.
                      API 호출 실패 시 빈 집합을 반환합니다.
        """
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
    """바이낸스 거래소와 상호작용하기 위한 전문 클라이언트입니다.

    ExchangeClient를 상속받아 바이낸스 WebSocket 및 REST API를 통해
    데이터를 수집하고 처리하는 기능을 구현합니다.
    """
    
    def __init__(self):
        super().__init__("binance")
        self.websocket_client = None
        self.api_manager = APIManager("Binance", self.spec.base_url if self.spec else "")
        
        # 바이낸스 특화 설정 (가중치 기반 Rate Limiting)
        if self.spec and self.spec.rest_rate_limits:
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
        """바이낸스에서 수신된 데이터의 유효성을 검사합니다.

        데이터가 리스트인 경우 각 항목이 's'(symbol)와 'c'(close price) 키를 포함하는 딕셔너리인지 확인하고,
        데이터가 단일 딕셔너리인 경우에도 동일한 키를 포함하는지 확인합니다.

        Args:
            data (Any): 유효성을 검사할 바이낸스 데이터.

        Returns:
            bool: 데이터가 유효하면 True, 그렇지 않으면 False.
        """
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
        """바이낸스 WebSocket 서버에 연결을 시도합니다.

        EnhancedWebSocketClient를 사용하여 연결을 설정하고,
        연결 성공/실패, 메시지 수신, 연결 해제, 오류 발생 시 호출될 콜백 함수를 설정합니다.
        연결 성공 시 하트비트 태스크를 시작합니다.

        Returns:
            bool: 연결 성공 여부.
        """
        try:
            self.connection_stats["connection_attempts"] += 1
            
            # 바이낸스는 전체 티커 스트림 사용
            if self.spec and self.spec.websocket_spec:
                self.websocket_client = EnhancedWebSocketClient(
                    uri=self.spec.websocket_spec.url,
                    name=f"Binance-{id(self)}",
                    max_retries=self.spec.websocket_spec.reconnect_limit,
                    timeout=30.0
                )
            else:
                logger.error(f"Binance WebSocket 사양을 찾을 수 없습니다.")
                return False
            
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
        """바이낸스 WebSocket 연결의 하트비트를 관리합니다.

        연결이 활성 상태인 동안 주기적으로 하트비트 간격을 확인하고,
        필요한 경우 연결 상태를 갱신합니다. 바이낸스는 ping/pong을 자동으로 처리합니다.
        """
        while self.is_connected:
            try:
                current_time = time.time()
                if self.spec and self.spec.websocket_spec and self.spec.websocket_spec.heartbeat_interval:
                    if current_time - self.last_ping > self.spec.websocket_spec.heartbeat_interval:
                        # 바이낸스는 ping/pong 자동 처리되므로 연결 상태만 확인
                        self.last_ping = current_time
                else:
                    # heartbeat_interval이 없으면 기본값 사용 또는 경고 로깅
                    if current_time - self.last_ping > 30: # 기본 30초
                        self.last_ping = current_time
                        logger.warning(f"{self.exchange_name}: heartbeat_interval이 정의되지 않아 기본값 30초 사용")
                    
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Binance 하트비트 오류: {e}")
                break
    
    async def _on_websocket_connect(self):
        """WebSocket 연결 성공 시 호출되는 콜백 함수입니다.

        연결 상태를 로깅하고 마지막 하트비트 시간을 업데이트합니다.
        """
        logger.info("Binance WebSocket 연결 성공")
        self.last_heartbeat = time.time()
    
    async def _on_websocket_message(self, data: Union[Dict, List]):
        """WebSocket 메시지 수신 시 호출되는 콜백 함수입니다.

        수신된 메시지를 처리하고, 티커 데이터인 경우 정규화하여 `on_ticker_data` 콜백을 호출합니다。
        메시지 수신 통계를 업데이트합니다. 바이낸스는 메시지를 배열 형태로 전송할 수 있습니다.

        Args:
            data (Union[Dict, List]): 수신된 WebSocket 메시지 데이터.
        """
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
        """WebSocket 연결 해제 시 호출되는 콜백 함수입니다.

        클라이언트의 연결 상태를 업데이트하고 `on_connection_change` 콜백을 호출합니다.
        """
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
        """바이낸스 마켓 데이터 구독을 요청합니다.

        바이낸스는 일반적으로 전체 티커 스트림을 제공하므로, 별도의 구독 메시지 전송 없이
        내부적으로 구독 심볼 목록을 업데이트하고 필터링 방식으로 데이터를 처리합니다.

        Args:
            request (SubscriptionRequest): 구독할 심볼 정보를 담은 객체.

        Returns:
            bool: 항상 True를 반환하며, 실제 구독은 내부 필터링으로 처리됩니다.
        """
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
        """바이낸스에서 지원하는 모든 USDT 페어 심볼(코인) 목록을 조회합니다.

        바이낸스 REST API를 통해 모든 거래소 정보를 가져와 USDT로 끝나는 심볼 중
        'TRADING' 상태인 심볼만 추출하여 반환합니다.

        Returns:
            Set[str]: 바이낸스에서 지원하는 USDT 페어 심볼들의 집합.
                      API 호출 실패 시 빈 집합을 반환합니다.
        """
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
    """바이비트 거래소와 상호작용하기 위한 전문 클라이언트입니다。

    ExchangeClient를 상속받아 바이비트 WebSocket 및 REST API를 통해
    데이터를 수집하고 처리하는 기능을 구현합니다。
    """
    
    def __init__(self):
        super().__init__("bybit")
        self.websocket_client = None
        self.api_manager = APIManager("Bybit", self.spec.base_url if self.spec else "")
        
        # 바이비트 특화 설정
        if self.spec and self.spec.rest_rate_limits:
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
        """바이비트에서 수신된 데이터의 유효성을 검사합니다.

        데이터가 딕셔너리인 경우 'topic' 키를 포함하거나,
        'data' 키를 포함하고 그 값이 딕셔너리 또는 리스트인지 확인합니다.

        Args:
            data (Any): 유효성을 검사할 바이비트 데이터.

        Returns:
            bool: 데이터가 유효하면 True, 그렇지 않으면 False.
        """
        if isinstance(data, dict):
            # 바이비트 WebSocket 응답 구조 확인
            return (
                'topic' in data or 
                ('data' in data and isinstance(data['data'], (dict, list)))
            )
        return False
    
    async def connect(self) -> bool:
        """바이비트 WebSocket 서버에 연결을 시도합니다.

        EnhancedWebSocketClient를 사용하여 연결을 설정하고,
        연결 성공/실패, 메시지 수신, 연결 해제, 오류 발생 시 호출될 콜백 함수를 설정합니다.
        연결 성공 시 하트비트 태스크를 시작합니다.

        Returns:
            bool: 연결 성공 여부.
        """
        try:
            self.connection_stats["connection_attempts"] += 1
            
            if self.spec and self.spec.websocket_spec:
                self.websocket_client = EnhancedWebSocketClient(
                    uri=self.spec.websocket_spec.url,
                    name=f"Bybit-{id(self)}",
                    max_retries=self.spec.websocket_spec.reconnect_limit,
                    timeout=30.0
                )
            else:
                logger.error(f"Bybit WebSocket 사양을 찾을 수 없습니다.")
                return False
            
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
        """바이비트 WebSocket 연결의 하트비트를 관리합니다.

        연결이 활성 상태인 동안 주기적으로 ping 메시지를 전송하여 연결을 유지합니다.
        하트비트 간격은 거래소 사양에 따르거나 기본값(10초)을 사용합니다.
        """
        while self.is_connected:
            try:
                # 바이비트는 ping 메시지 전송 필요
                if self.websocket_client:
                    if self.websocket_client:
                        ping_message = {"op": "ping"}
                        await self.websocket_client.send_message(ping_message)
                
                if self.spec and self.spec.websocket_spec and self.spec.websocket_spec.heartbeat_interval:
                    await asyncio.sleep(self.spec.websocket_spec.heartbeat_interval)
                else:
                    await asyncio.sleep(10) # 기본값
                
            except Exception as e:
                logger.error(f"Bybit ping 오류: {e}")
                break
    
    async def _on_websocket_connect(self):
        """WebSocket 연결 성공 시 호출되는 콜백 함수입니다.

        연결 상태를 로깅하고 마지막 하트비트 시간을 업데이트합니다.
        """
        logger.info("Bybit WebSocket 연결 성공")
        self.last_heartbeat = time.time()
    
    async def _on_websocket_message(self, data: Union[Dict, List]):
        """WebSocket 메시지 수신 시 호출되는 콜백 함수입니다.

        수신된 메시지를 처리하고, 티커 데이터인 경우 정규화하여 `on_ticker_data` 콜백을 호출합니다。
        메시지 수신 통계를 업데이트합니다. Pong 메시지는 무시합니다.

        Args:
            data (Union[Dict, List]): 수신된 WebSocket 메시지 데이터.
        """
        try:
            self.connection_stats["messages_received"] += 1
            self.connection_stats["last_message_time"] = time.time()

            if isinstance(data, dict): # Add this check
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
            else:
                logger.warning(f"Bybit: Unexpected message format received: {type(data)}") # Log unexpected types
                            
        except Exception as e:
            logger.error(f"Bybit 메시지 처리 오류: {e}")
            self.connection_stats["errors"] += 1
            if self.on_error:
                await self.on_error(e)
    
    async def _on_websocket_disconnect(self):
        """WebSocket 연결 해제 시 호출되는 콜백 함수입니다.

        클라이언트의 연결 상태를 업데이트하고 `on_connection_change` 콜백을 호출합니다.
        """
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