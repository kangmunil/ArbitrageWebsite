"""
최적화된 메인 애플리케이션

개선사항:
1. 효율적인 price_aggregator
2. 메모리 관리 최적화
3. 성능 모니터링 추가
4. 오류 처리 강화
"""

import asyncio
import json
import logging
import time
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import optimized_services
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from liquidation_service.liquidation_stats_collector import get_aggregated_liquidation_data, start_liquidation_stats_collection, set_websocket_manager
from .database import get_db
from .models import Cryptocurrency
from .optimized_services import shared_data, TickerData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "last_broadcast": None
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_stats["total_connections"] += 1
        self.connection_stats["active_connections"] = len(self.active_connections)
        logger.info(f"WebSocket 연결: {len(self.active_connections)}개 활성 연결")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.connection_stats["active_connections"] = len(self.active_connections)
            logger.info(f"WebSocket 연결 해제: {len(self.active_connections)}개 활성 연결")

    async def broadcast(self, message: str):
        if not self.active_connections:
            return
            
        disconnected_clients = []
        successful_sends = 0
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
                successful_sends += 1
            except Exception as e:
                logger.warning(f"WebSocket 전송 실패: {e}")
                disconnected_clients.append(connection)
        
        # 연결이 끊어진 클라이언트 정리
        for client in disconnected_clients:
            self.disconnect(client)
        
        self.connection_stats["messages_sent"] += successful_sends
        self.connection_stats["last_broadcast"] = time.time()
        
        if disconnected_clients:
            logger.info(f"{len(disconnected_clients)}개 연결 정리, {successful_sends}개 클라이언트에 전송 성공")

manager = ConnectionManager()
liquidation_manager = ConnectionManager()

# 최적화된 데이터 집계기
class OptimizedPriceAggregator:
    """최적화된 가격 데이터 집계기"""
    
    def __init__(self):
        self.last_broadcast_time = 0
        self.broadcast_interval = 1.0  # 1초
        self.last_data_hash = None
        self.stats = {
            "aggregations": 0,
            "broadcasts": 0,
            "skipped_broadcasts": 0,
            "processing_time": 0.0
        }
    
    def _calculate_premium(self, domestic_price: float, global_price: float, exchange_rate: float) -> Optional[float]:
        """김치 프리미엄 계산"""
        if not all([domestic_price, global_price, exchange_rate]):
            return None
            
        global_price_krw = global_price * exchange_rate
        if global_price_krw <= 0:
            return None
            
        premium = ((domestic_price - global_price_krw) / global_price_krw) * 100
        return round(premium, 2)
    
    def _build_coin_data(self, symbol: str, upbit_ticker: TickerData, 
                        binance_ticker: Optional[TickerData], 
                        bybit_ticker: Optional[TickerData],
                        exchange_rates) -> Dict:
        """개별 코인 데이터 구성"""
        
        # 기본 데이터 구조
        coin_data = {
            "symbol": symbol,
            "exchange_rate": exchange_rates.usd_krw if exchange_rates else None,
            "usdt_krw_rate": exchange_rates.usdt_krw if exchange_rates else None,
            
            # Upbit 데이터
            "upbit_price": upbit_ticker.price,
            "upbit_volume": upbit_ticker.volume,
            "upbit_change_percent": upbit_ticker.change_percent,
            
            # Binance 데이터
            "binance_price": binance_ticker.price if binance_ticker else None,
            "binance_volume": None,
            "binance_change_percent": binance_ticker.change_percent if binance_ticker else None,
            
            # Bybit 데이터  
            "bybit_price": bybit_ticker.price if bybit_ticker else None,
            "bybit_volume": None,
            "bybit_change_percent": bybit_ticker.change_percent if bybit_ticker else None,
        }
        
        # Binance 거래량 (USDT → KRW 변환)
        if binance_ticker and exchange_rates and exchange_rates.usdt_krw:
            coin_data["binance_volume"] = binance_ticker.volume * exchange_rates.usdt_krw
        
        # Bybit 거래량 (USDT → KRW 변환) 
        if bybit_ticker and exchange_rates and exchange_rates.usdt_krw:
            coin_data["bybit_volume"] = bybit_ticker.volume * exchange_rates.usdt_krw
        
        # 프리미엄 계산
        if binance_ticker and exchange_rates and exchange_rates.usd_krw:
            coin_data["premium"] = self._calculate_premium(
                upbit_ticker.price, binance_ticker.price, exchange_rates.usd_krw
            )
        
        return coin_data
    
    async def aggregate_and_broadcast(self):
        """데이터 집계 및 브로드캐스트"""
        start_time = time.time()
        
        try:
            # 공유 데이터 가져오기
            all_data = shared_data.get_all_data()
            upbit_tickers = all_data["upbit_tickers"]
            binance_tickers = all_data["binance_tickers"] 
            bybit_tickers = all_data["bybit_tickers"]
            exchange_rates = all_data["exchange_rates"]
            
            # 기본 데이터 검증
            if not upbit_tickers or not exchange_rates:
                return
            
            # 코인 데이터 구성
            all_coins_data = []
            
            for symbol, upbit_ticker in upbit_tickers.items():
                # 데이터 유효성 재검사
                if not upbit_ticker.is_valid():
                    continue
                
                binance_ticker = binance_tickers.get(symbol)
                bybit_ticker = bybit_tickers.get(symbol)
                
                # 해외 거래소 데이터 유효성 검사
                if binance_ticker and not binance_ticker.is_valid():
                    binance_ticker = None
                if bybit_ticker and not bybit_ticker.is_valid():
                    bybit_ticker = None
                
                coin_data = self._build_coin_data(
                    symbol, upbit_ticker, binance_ticker, bybit_ticker, exchange_rates
                )
                
                all_coins_data.append(coin_data)
            
            # 데이터 변경 확인 (해시 비교)
            current_data_hash = hash(json.dumps(all_coins_data, sort_keys=True))
            
            if current_data_hash == self.last_data_hash:
                self.stats["skipped_broadcasts"] += 1
                return
            
            self.last_data_hash = current_data_hash
            
            # 브로드캐스트
            if all_coins_data:
                message = json.dumps(all_coins_data)
                await manager.broadcast(message)
                
                self.stats["broadcasts"] += 1
                self.last_broadcast_time = time.time()
                
                logger.debug(f"{len(all_coins_data)}개 코인 데이터 브로드캐스트 완료")
        
        except Exception as e:
            logger.error(f"데이터 집계 중 오류: {e}")
        
        finally:
            # 성능 통계 업데이트
            processing_time = time.time() - start_time
            self.stats["aggregations"] += 1
            self.stats["processing_time"] += processing_time
            
            if processing_time > 0.1:  # 100ms 이상 걸리는 경우 경고
                logger.warning(f"느린 데이터 집계: {processing_time:.3f}초")
    
    async def run_periodic_aggregation(self):
        """주기적 데이터 집계 실행"""
        logger.info("가격 데이터 집계기 시작")
        
        while True:
            await self.aggregate_and_broadcast()
            await asyncio.sleep(self.broadcast_interval)
    
    def get_stats(self) -> Dict:
        """집계기 통계 반환"""
        avg_processing_time = (
            self.stats["processing_time"] / self.stats["aggregations"] 
            if self.stats["aggregations"] > 0 else 0
        )
        
        return {
            **self.stats,
            "avg_processing_time": round(avg_processing_time, 4),
            "last_broadcast_time": self.last_broadcast_time,
            "uptime_seconds": time.time() - self.last_broadcast_time if self.last_broadcast_time else 0
        }

# 전역 집계기 인스턴스
price_aggregator = OptimizedPriceAggregator()

# --- WebSocket 엔드포인트 ---

@app.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지 대기 (연결 유지용)
            await websocket.receive_text()
    except Exception as e:
        logger.info(f"WebSocket 연결 종료: {e}")
    finally:
        manager.disconnect(websocket)

@app.websocket("/ws/liquidations")
async def liquidation_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # 청산 데이터 전송 (기존 로직 유지)
            liquidation_data = get_aggregated_liquidation_data(limit=60)
            await websocket.send_text(json.dumps(liquidation_data))
            await asyncio.sleep(5)  # 5초마다 전송
    except Exception as e:
        logger.info(f"청산 WebSocket 연결 종료: {e}")

# --- REST API 엔드포인트 ---

@app.get("/")
def read_root():
    return {"message": "KimchiScan API is running (Optimized)!"}

@app.get("/api/fear_greed_index")
async def get_fear_greed_index_data():
    """공포/탐욕 지수 데이터 조회"""
    return optimized_services.get_fear_greed_index()

@app.get("/api/liquidations/aggregated")
async def get_aggregated_liquidations(limit: int = 60):
    """집계된 청산 데이터 조회"""
    return get_aggregated_liquidation_data(limit=limit)

@app.get("/api/coin-names")
async def get_coin_names(db: Session = Depends(get_db)) -> Dict[str, str]:
    """코인 심볼 -> 한글명 매핑 반환"""
    try:
        cryptocurrencies = db.query(Cryptocurrency).filter(
            Cryptocurrency.is_active == True
        ).all()
        
        coin_names = {}
        for crypto in cryptocurrencies:
            coin_names[crypto.symbol] = crypto.name_ko or crypto.symbol
        
        logger.info(f"코인 한글명 {len(coin_names)}개 반환")
        return coin_names
        
    except Exception as e:
        logger.error(f"코인 한글명 조회 오류: {e}")
        return {}

@app.get("/api/stats")
async def get_system_stats():
    """시스템 통계 정보 반환"""
    return {
        "shared_data": shared_data.get_stats(),
        "price_aggregator": price_aggregator.get_stats(),
        "websocket_manager": manager.connection_stats,
        "timestamp": time.time()
    }

# --- 애플리케이션 시작 이벤트 ---

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    logger.info("최적화된 KimchiScan API 시작 중...")
    
    # 백그라운드 서비스들을 비동기적으로 시작
    asyncio.create_task(optimized_services.start_optimized_services())
    asyncio.create_task(price_aggregator.run_periodic_aggregation())
    
    # 청산 통계 서비스 시작
    set_websocket_manager(liquidation_manager)
    asyncio.create_task(start_liquidation_stats_collection())
    
    logger.info("모든 백그라운드 서비스 시작 완료")

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 실행"""
    logger.info("KimchiScan API 종료 중...")
    
    # 통계 로그 출력
    stats = await get_system_stats()
    logger.info(f"최종 시스템 통계: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)