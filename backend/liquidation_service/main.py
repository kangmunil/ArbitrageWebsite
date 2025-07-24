"""
청산 데이터 수집 전용 FastAPI 서비스.

이 서비스는 여러 거래소에서 실시간 청산 데이터를 수집하고
WebSocket을 통해 클라이언트에게 브로드캐스트합니다.
"""

import asyncio
import json
import os
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging

from liquidation_collector import LiquidationDataCollector, get_liquidation_data, get_aggregated_liquidation_data

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Liquidation Service", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 환경에서는 모든 오리진 허용
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- WebSocket Connection Manager ---
class ConnectionManager:
    """WebSocket 연결을 관리하는 클래스."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """새로운 WebSocket 연결을 수락하고 관리 리스트에 추가합니다."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결을 관리 리스트에서 제거합니다."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """모든 연결된 클라이언트에게 메시지를 브로드캐스트합니다."""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# 글로벌 청산 데이터 수집기
liquidation_collector = LiquidationDataCollector()

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 청산 데이터 수집 시작."""
    logger.info("🚀 Starting Liquidation Service...")
    
    # WebSocket 관리자 설정
    liquidation_collector.set_websocket_manager(manager)
    
    # 청산 데이터 수집 시작
    logger.info("⚡ Starting liquidation data collection...")
    try:
        asyncio.create_task(liquidation_collector.start_collection())
        logger.info("✅ Liquidation data collection started successfully")
    except Exception as e:
        logger.error(f"❌ Error starting liquidation collection: {e}")
        import traceback
        traceback.print_exc()

# --- REST API Endpoints ---
@app.get("/")
def read_root():
    """루트 엔드포인트 - 청산 서비스 상태 확인."""
    return {"message": "Liquidation Service is running!", "service": "liquidation"}

@app.get("/api/liquidations")
def get_liquidations_endpoint(exchange: Optional[str] = None, limit: int = 60):
    """청산 데이터를 조회합니다.
    
    Args:
        exchange (str, optional): 특정 거래소 데이터만 조회
        limit (int): 반환할 데이터 포인트 수 (기본값: 60분)
        
    Returns:
        list: 청산 데이터 리스트
    """
    return get_liquidation_data(exchange, limit)

@app.get("/api/liquidations/aggregated")
def get_aggregated_liquidations_endpoint(limit: int = 60):
    """집계된 청산 데이터를 조회합니다.
    
    모든 거래소의 청산 데이터를 시간별로 집계하여 반환합니다.
    
    Args:
        limit (int): 반환할 시간 포인트 수 (기본값: 60분)
        
    Returns:
        list: 시간별로 집계된 청산 데이터
    """
    return get_aggregated_liquidation_data(limit)

@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트."""
    return {
        "status": "healthy",
        "service": "liquidation",
        "active_connections": len(manager.active_connections)
    }

# --- WebSocket Endpoints ---
@app.websocket("/ws/liquidations")
async def liquidation_websocket_endpoint(websocket: WebSocket):
    """청산 데이터 WebSocket 엔드포인트.
    
    청산 데이터 실시간 업데이트를 WebSocket으로 전송합니다.
    """
    logger.info("Liquidation WebSocket connection attempt")
    await manager.connect(websocket)
    logger.info(f"Liquidation WebSocket connected! Total connections: {len(manager.active_connections)}")
    
    try:
        # 연결 시 최근 청산 데이터 전송
        recent_data = get_aggregated_liquidation_data(limit=60)
        if recent_data:
            initial_message = json.dumps({
                'type': 'liquidation_initial',
                'data': recent_data
            })
            await websocket.send_text(initial_message)
        
        # 연결 유지
        while True:
            await asyncio.sleep(1)
                
    except Exception as e:
        logger.error(f"Liquidation WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
        logger.info(f"Liquidation WebSocket client disconnected. Remaining: {len(manager.active_connections)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)