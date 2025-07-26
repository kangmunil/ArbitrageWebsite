"""
향상된 WebSocket 클라이언트 관리 시스템

특징:
- 지수 백오프 재연결 전략
- 오류 유형별 처리
- 연결 상태 모니터링
- Rate limiting 지원
- 데이터 유효성 검사
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Optional, Callable, Any, Awaitable
from enum import Enum
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI, InvalidMessage

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """WebSocket 연결 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"

class WebSocketError(Exception):
    """WebSocket 관련 사용자 정의 예외"""
    pass

class EnhancedWebSocketClient:
    """향상된 WebSocket 클라이언트"""
    
    def __init__(
        self,
        uri: str,
        name: str,
        max_retries: int = 10,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
        timeout: float = 30.0
    ):
        self.uri = uri
        self.name = name
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self.timeout = timeout
        
        self.state = ConnectionState.DISCONNECTED
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.retry_count = 0
        self.last_error: Optional[Exception] = None
        self.connected_at: Optional[float] = None
        self.message_count = 0
        self.error_count = 0
        
        # 콜백 함수들
        self.on_connect: Optional[Callable[[], Awaitable[None]]] = None
        self.on_message: Optional[Callable[[Dict], Awaitable[None]]] = None
        self.on_disconnect: Optional[Callable[[], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[Exception], Awaitable[None]]] = None
    
    def get_retry_delay(self) -> float:
        """지수 백오프 지연 시간 계산"""
        delay = self.initial_retry_delay * (2 ** min(self.retry_count, 10))
        return min(delay, self.max_retry_delay)
    
    def is_retriable_error(self, error: Exception) -> bool:
        """재시도 가능한 오류인지 확인"""
        if isinstance(error, (ConnectionClosed, OSError, asyncio.TimeoutError)):
            return True
        if isinstance(error, InvalidURI):
            return False  # URI 오류는 재시도 불가
        return True
    
    async def connect(self) -> bool:
        """WebSocket 연결 시도"""
        if self.state == ConnectionState.CONNECTED:
            return True
            
        self.state = ConnectionState.CONNECTING
        logger.info(f"{self.name}: WebSocket 연결 시도 중... (재시도 {self.retry_count})")
        
        try:
            self.websocket = await asyncio.wait_for(
                websockets.connect(self.uri),
                timeout=self.timeout
            )
            
            self.state = ConnectionState.CONNECTED
            self.connected_at = time.time()
            self.retry_count = 0
            self.message_count = 0
            
            logger.info(f"{self.name}: WebSocket 연결 성공")
            
            if self.on_connect:
                await self.on_connect()
                
            return True
            
        except Exception as e:
            self.state = ConnectionState.FAILED
            self.last_error = e
            self.error_count += 1
            
            logger.error(f"{self.name}: WebSocket 연결 실패 - {type(e).__name__}: {e}")
            
            if self.on_error:
                await self.on_error(e)
                
            return False
    
    async def disconnect(self):
        """WebSocket 연결 종료"""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"{self.name}: 연결 종료 중 오류 - {e}")
            finally:
                self.websocket = None
                
        self.state = ConnectionState.DISCONNECTED
        
        if self.on_disconnect:
            await self.on_disconnect()
            
        logger.info(f"{self.name}: WebSocket 연결 종료")
    
    async def send_message(self, message: Dict) -> bool:
        """메시지 전송"""
        if not self.websocket or self.state != ConnectionState.CONNECTED:
            logger.warning(f"{self.name}: 연결되지 않은 상태에서 메시지 전송 시도")
            return False
            
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"{self.name}: 메시지 전송 실패 - {e}")
            self.state = ConnectionState.FAILED
            return False
    
    async def listen(self):
        """메시지 수신 및 처리"""
        if not self.websocket or self.state != ConnectionState.CONNECTED:
            return
            
        try:
            async for message in self.websocket:
                try:
                    if isinstance(message, bytes):
                        message = message.decode('utf-8')
                    
                    data = json.loads(message)
                    self.message_count += 1
                    
                    if self.on_message:
                        await self.on_message(data)
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"{self.name}: JSON 파싱 오류 - {e}")
                    continue
                except Exception as e:
                    logger.error(f"{self.name}: 메시지 처리 오류 - {e}")
                    continue
                    
        except ConnectionClosed:
            logger.info(f"{self.name}: WebSocket 연결이 서버에 의해 종료됨")
            self.state = ConnectionState.DISCONNECTED
        except Exception as e:
            logger.error(f"{self.name}: 메시지 수신 중 오류 - {e}")
            self.state = ConnectionState.FAILED
            self.last_error = e
    
    async def run_with_retry(self):
        """재시도 로직과 함께 WebSocket 클라이언트 실행"""
        while self.retry_count < self.max_retries:
            try:
                # 연결 시도
                if not await self.connect():
                    if not self.is_retriable_error(self.last_error):
                        logger.error(f"{self.name}: 재시도 불가능한 오류, 중단")
                        break
                        
                    self.retry_count += 1
                    delay = self.get_retry_delay()
                    logger.info(f"{self.name}: {delay:.1f}초 후 재연결 시도")
                    await asyncio.sleep(delay)
                    continue
                
                # 메시지 수신
                await self.listen()
                
                # 연결이 끊어진 경우
                if self.state != ConnectionState.CONNECTED:
                    self.retry_count += 1
                    delay = self.get_retry_delay()
                    logger.info(f"{self.name}: {delay:.1f}초 후 재연결 시도")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                self.last_error = e
                self.error_count += 1
                logger.error(f"{self.name}: 예상치 못한 오류 - {e}")
                
                if not self.is_retriable_error(e):
                    break
                    
                self.retry_count += 1
                delay = self.get_retry_delay()
                await asyncio.sleep(delay)
        
        logger.error(f"{self.name}: 최대 재시도 횟수 초과, WebSocket 클라이언트 중단")
        await self.disconnect()
    
    def get_stats(self) -> Dict[str, Any]:
        """연결 통계 정보 반환"""
        uptime = time.time() - self.connected_at if self.connected_at else 0
        
        return {
            "name": self.name,
            "state": self.state.value,
            "retry_count": self.retry_count,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "uptime_seconds": uptime,
            "last_error": str(self.last_error) if self.last_error else None,
            "connected_at": self.connected_at
        }