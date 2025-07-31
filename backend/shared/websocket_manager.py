"""
공통 WebSocket 연결 관리 모듈

모든 마이크로서비스에서 공통으로 사용할 수 있는 WebSocket 연결 관리 클래스를 제공합니다.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """WebSocket 연결을 관리하는 공통 클래스"""
    
    def __init__(self, service_name: str = "unknown"):
        self.service_name = service_name
        self.active_connections: List[WebSocket] = []
        self.connection_stats = {
            "total_connections": 0,
            "current_connections": 0,
            "last_connection": None,
            "last_disconnection": None
        }
    
    async def connect(self, websocket: WebSocket) -> None:
        """클라이언트 WebSocket 연결을 수락하고 관리합니다."""
        try:
            await websocket.accept()
            self.active_connections.append(websocket)
            
            # 통계 업데이트
            self.connection_stats["total_connections"] += 1
            self.connection_stats["current_connections"] = len(self.active_connections)
            self.connection_stats["last_connection"] = datetime.now().isoformat()
            
            logger.info(f"✅ [{self.service_name}] WebSocket 클라이언트 연결: {websocket.client} | 총 연결: {len(self.active_connections)}")
            
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] WebSocket 연결 실패: {e}")
            raise
    
    def disconnect(self, websocket: WebSocket) -> None:
        """활성 연결 목록에서 클라이언트를 제거합니다."""
        try:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                
                # 통계 업데이트
                self.connection_stats["current_connections"] = len(self.active_connections)
                self.connection_stats["last_disconnection"] = datetime.now().isoformat()
                
                logger.info(f"🔌 [{self.service_name}] WebSocket 클라이언트 연결 해제: {websocket.client} | 남은 연결: {len(self.active_connections)}")
            
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] WebSocket 연결 해제 오류: {e}")
    
    async def broadcast(self, message: str, message_type: str = "update") -> None:
        """모든 활성 WebSocket 클라이언트에게 메시지를 브로드캐스트합니다."""
        if not self.active_connections:
            return
        
        disconnected_clients = []
        
        for connection in self.active_connections:
            try:
                # 연결 상태 확인
                if connection.client_state.value != 1:  # CONNECTED = 1
                    disconnected_clients.append(connection)
                    continue
                    
                # 타임아웃을 추가하여 안전한 전송
                import asyncio
                await asyncio.wait_for(
                    connection.send_text(message),
                    timeout=5.0  # 5초 타임아웃
                )
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ [{self.service_name}] 브로드캐스트 타임아웃: {connection.client}")
                disconnected_clients.append(connection)
            except Exception as e:
                logger.warning(f"⚠️ [{self.service_name}] 브로드캐스트 실패 (연결 해제): {connection.client}")
                disconnected_clients.append(connection)
        
        # 연결이 끊긴 클라이언트 정리
        for client in disconnected_clients:
            self.disconnect(client)
        
        if len(self.active_connections) > 0:
            logger.debug(f"📡 [{self.service_name}] 브로드캐스트 완료: {len(self.active_connections)}명 클라이언트")
    
    async def broadcast_json(self, data: Any, message_type: str = "update") -> None:
        """JSON 데이터를 브로드캐스트합니다."""
        message = {
            "type": message_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "service": self.service_name
        }
        await self.broadcast(json.dumps(message), message_type)
    
    async def send_initial_data(self, websocket: WebSocket, data: Any, data_type: str = "initial") -> None:
        """새로 연결된 클라이언트에게 초기 데이터를 전송합니다."""
        try:
            # WebSocket 연결 상태 확인
            if websocket.client_state.value != 1:  # CONNECTED = 1
                logger.warning(f"⚠️ [{self.service_name}] WebSocket 연결 불안정, 초기 데이터 전송 건너뜀: {websocket.client}")
                return
            
            # 데이터가 None이거나 비어있으면 기본값 사용
            if data is None:
                data = []
                logger.debug(f"🔄 [{self.service_name}] 초기 데이터가 None이어서 빈 배열로 대체")
                
            initial_message = {
                "type": f"{data_type}_initial",
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "service": self.service_name
            }
            
            # JSON 직렬화 미리 테스트
            try:
                message_json = json.dumps(initial_message)
                if len(message_json) > 1000000:  # 1MB 이상이면 경고
                    logger.warning(f"⚠️ [{self.service_name}] 초기 데이터가 매우 큼: {len(message_json)} bytes")
            except Exception as json_err:
                logger.error(f"❌ [{self.service_name}] JSON 직렬화 실패: {json_err}")
                return
            
            # 짧은 타임아웃으로 빠른 전송
            import asyncio
            await asyncio.wait_for(
                websocket.send_text(message_json),
                timeout=5.0  # 10초 → 5초로 감소
            )
            logger.info(f"📤 [{self.service_name}] 초기 데이터 전송 완료: {websocket.client}")
            
        except asyncio.TimeoutError:
            logger.error(f"❌ [{self.service_name}] 초기 데이터 전송 타임아웃: {websocket.client}")
            # 연결을 강제로 해제하지 않고 계속 진행
        except Exception as e:
            logger.error(f"❌ [{self.service_name}] 초기 데이터 전송 실패: {e}")
            # 연결을 강제로 해제하지 않고 계속 진행
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """연결 통계 정보를 반환합니다."""
        return {
            "service": self.service_name,
            "active_connections": len(self.active_connections),
            "stats": self.connection_stats.copy()
        }
    
    def is_connected(self) -> bool:
        """활성 연결이 있는지 확인합니다."""
        return len(self.active_connections) > 0


class WebSocketEndpoint:
    """WebSocket 엔드포인트 헬퍼 클래스"""
    
    def __init__(self, manager: WebSocketConnectionManager, data_provider=None):
        self.manager = manager
        self.data_provider = data_provider
    
    async def handle_connection(self, websocket: WebSocket, 
                              send_initial: bool = True,
                              streaming_interval: float = 1.0) -> None:
        """WebSocket 연결을 처리하는 공통 로직"""
        await self.manager.connect(websocket)
        
        try:
            # 초기 데이터 전송
            if send_initial and self.data_provider:
                initial_data = await self.data_provider()
                await self.manager.send_initial_data(websocket, initial_data)
            
            # 연결 유지 및 스트리밍
            while True:
                try:
                    # 클라이언트로부터 메시지 수신 대기 (연결 유지용)
                    await asyncio.wait_for(websocket.receive_text(), timeout=streaming_interval)
                except asyncio.TimeoutError:
                    # 타임아웃은 정상 동작 (스트리밍 계속)
                    pass
                except Exception:
                    # 클라이언트 연결 끊김
                    break
                    
        except Exception as e:
            logger.info(f"🔌 [{self.manager.service_name}] WebSocket 연결 종료: {websocket.client}")
        finally:
            self.manager.disconnect(websocket)


# 서비스별 WebSocket 매니저 팩토리
def create_websocket_manager(service_name: str) -> WebSocketConnectionManager:
    """서비스별 WebSocket 매니저를 생성합니다."""
    return WebSocketConnectionManager(service_name)


# 공통 헬스체크 정보
def get_websocket_health_info(managers: List[WebSocketConnectionManager]) -> Dict[str, Any]:
    """여러 WebSocket 매니저의 헬스체크 정보를 통합합니다."""
    total_connections = sum(len(manager.active_connections) for manager in managers)
    
    manager_stats = {}
    for manager in managers:
        manager_stats[manager.service_name] = manager.get_connection_stats()
    
    return {
        "total_websocket_connections": total_connections,
        "managers": manager_stats
    }