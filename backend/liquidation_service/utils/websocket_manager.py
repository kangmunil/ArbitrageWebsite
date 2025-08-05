"""WebSocket Connection Manager

웹소켓 연결 관리 및 재연결 로직 (미래 확장용)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
import json

logger = logging.getLogger(__name__)


class WebSocketManager:
    """웹소켓 연결 관리자 (기본 구현)"""
    
    def __init__(
        self,
        name: str = "WebSocketManager",
        max_reconnect_attempts: int = 10,
        reconnect_delay: int = 5,
        ping_interval: int = 20,
        ping_timeout: int = 10
    ):
        self.name = name
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        
        # 연결 상태
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        
        # 콜백 함수들
        self.message_handlers: Dict[str, Callable] = {}
        self.error_handlers: Dict[str, Callable] = {}
        self.connection_handlers: Dict[str, Callable] = {}
        
        # 통계
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "total_messages": 0,
            "connection_errors": 0,
            "reconnections": 0
        }
    
    async def connect(
        self,
        url: str,
        name: str,
        message_handler: Optional[Callable] = None,
        error_handler: Optional[Callable] = None,
        connection_handler: Optional[Callable] = None
    ) -> bool:
        """웹소켓 연결 시작"""
        if name in self.connections:
            logger.warning(f"Connection {name} already exists")
            return False
        
        # 핸들러 등록
        if message_handler:
            self.message_handlers[name] = message_handler
        if error_handler:
            self.error_handlers[name] = error_handler
        if connection_handler:
            self.connection_handlers[name] = connection_handler
        
        # 연결 작업 시작
        task = asyncio.create_task(
            self._connection_loop(url, name)
        )
        self.connection_tasks[name] = task
        
        logger.info(f"Starting WebSocket connection: {name}")
        return True
    
    async def disconnect(self, name: str) -> bool:
        """웹소켓 연결 종료"""
        if name not in self.connection_tasks:
            logger.warning(f"Connection {name} not found")
            return False
        
        # 연결 작업 취소
        task = self.connection_tasks[name]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # 정리
        if name in self.connections:
            try:
                await self.connections[name].close()
            except Exception:
                pass
            del self.connections[name]
        
        del self.connection_tasks[name]
        
        # 핸들러 정리
        self.message_handlers.pop(name, None)
        self.error_handlers.pop(name, None)
        self.connection_handlers.pop(name, None)
        
        logger.info(f"Disconnected WebSocket: {name}")
        return True
    
    async def disconnect_all(self):
        """모든 웹소켓 연결 종료"""
        connection_names = list(self.connection_tasks.keys())
        
        for name in connection_names:
            await self.disconnect(name)
        
        logger.info("All WebSocket connections disconnected")
    
    async def send_message(self, name: str, message: Any) -> bool:
        """특정 연결로 메시지 전송"""
        if name not in self.connections:
            logger.error(f"Connection {name} not found")
            return False
        
        try:
            websocket = self.connections[name]
            
            if isinstance(message, (dict, list)):
                message = json.dumps(message, default=str)
            
            await websocket.send(message)
            return True
        
        except Exception as e:
            logger.error(f"Error sending message to {name}: {e}")
            return False
    
    async def broadcast_message(self, message: Any, exclude: Optional[List[str]] = None):
        """모든 연결에 메시지 브로드캐스트"""
        if exclude is None:
            exclude = []
        
        if isinstance(message, (dict, list)):
            message = json.dumps(message, default=str)
        
        disconnect_list = []
        
        for name, websocket in self.connections.items():
            if name in exclude:
                continue
            
            try:
                await websocket.send(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {name}: {e}")
                disconnect_list.append(name)
        
        # 실패한 연결들 정리
        for name in disconnect_list:
            await self.disconnect(name)
    
    async def _connection_loop(self, url: str, name: str):
        """웹소켓 연결 루프 (재연결 포함)"""
        reconnect_count = 0
        
        while reconnect_count < self.max_reconnect_attempts:
            try:
                logger.info(f"Connecting to {url} ({name})...")
                
                async with websockets.connect(
                    url,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                    close_timeout=10
                ) as websocket:
                    
                    self.connections[name] = websocket
                    self.stats["total_connections"] += 1
                    self.stats["active_connections"] = len(self.connections)
                    
                    logger.info(f"Connected to {url} ({name})")
                    reconnect_count = 0  # 연결 성공 시 리셋
                    
                    # 연결 핸들러 호출
                    if name in self.connection_handlers:
                        try:
                            await self.connection_handlers[name](websocket, name)
                        except Exception as e:
                            logger.error(f"Error in connection handler for {name}: {e}")
                    
                    # 메시지 수신 루프
                    async for message in websocket:
                        try:
                            self.stats["total_messages"] += 1
                            
                            # 메시지 핸들러 호출
                            if name in self.message_handlers:
                                await self.message_handlers[name](message, name)
                            else:
                                logger.debug(f"Received message from {name}: {message[:100]}...")
                                
                        except Exception as e:
                            logger.error(f"Error processing message from {name}: {e}")
                            
                            # 에러 핸들러 호출
                            if name in self.error_handlers:
                                try:
                                    await self.error_handlers[name](e, name)
                                except Exception as handler_error:
                                    logger.error(f"Error in error handler for {name}: {handler_error}")
            
            except ConnectionClosed:
                logger.warning(f"WebSocket connection closed: {name}")
                reconnect_count += 1
                self.stats["connection_errors"] += 1
                
            except WebSocketException as e:
                logger.error(f"WebSocket error for {name}: {e}")
                reconnect_count += 1
                self.stats["connection_errors"] += 1
                
            except Exception as e:
                logger.error(f"Unexpected error for {name}: {e}")
                reconnect_count += 1
                self.stats["connection_errors"] += 1
            
            finally:
                # 연결 정리
                if name in self.connections:
                    del self.connections[name]
                    self.stats["active_connections"] = len(self.connections)
            
            # 재연결 대기
            if reconnect_count < self.max_reconnect_attempts:
                logger.info(f"Reconnecting to {name} in {self.reconnect_delay} seconds... "
                          f"(attempt {reconnect_count})")
                self.stats["reconnections"] += 1
                await asyncio.sleep(self.reconnect_delay)
        
        logger.error(f"Max reconnection attempts reached for {name}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 조회"""
        return {
            "manager_name": self.name,
            "active_connections": list(self.connections.keys()),
            "connection_count": len(self.connections),
            "running_tasks": len(self.connection_tasks),
            "statistics": self.stats.copy()
        }
    
    def is_connected(self, name: str) -> bool:
        """특정 연결 상태 확인"""
        return name in self.connections
    
    async def health_check(self) -> Dict[str, Any]:
        """헬스 체크"""
        health_status = {
            "manager": self.name,
            "status": "healthy",
            "connections": {},
            "overall_health": True
        }
        
        for name, websocket in self.connections.items():
            try:
                # 간단한 ping 테스트
                pong_waiter = await websocket.ping()
                await asyncio.wait_for(pong_waiter, timeout=5)
                
                health_status["connections"][name] = {
                    "status": "healthy",
                    "state": websocket.state.name if hasattr(websocket.state, 'name') else str(websocket.state)
                }
            except Exception as e:
                health_status["connections"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["overall_health"] = False
        
        if not health_status["overall_health"]:
            health_status["status"] = "degraded"
        
        return health_status


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)
    
    manager = WebSocketManager("TestManager")
    
    # 간단한 메시지 핸들러
    async def message_handler(message, name):
        print(f"Received from {name}: {message[:100]}...")
    
    # 에러 핸들러
    async def error_handler(error, name):
        print(f"Error in {name}: {error}")
    
    try:
        # 바이낸스 청산 스트림 연결 테스트
        await manager.connect(
            "wss://fstream.binance.com/ws/!forceOrder@arr",
            "binance_liquidations",
            message_handler=message_handler,
            error_handler=error_handler
        )
        
        # 10초 동안 실행
        await asyncio.sleep(10)
        
        # 상태 확인
        status = manager.get_connection_status()
        print(f"Connection Status: {status}")
        
        # 헬스 체크
        health = await manager.health_check()
        print(f"Health Check: {health}")
    
    finally:
        await manager.disconnect_all()


if __name__ == "__main__":
    asyncio.run(main())