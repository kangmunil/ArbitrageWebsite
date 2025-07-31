import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
from sqlalchemy.orm import Session

import aiohttp
import requests
from . import services  # 가능한 경우 기존 서비스 유지
import sys
import os

# 마이크로서비스 환경에서는 HTTP API 호출로 변경
LIQUIDATION_SERVICE_URL = os.getenv('LIQUIDATION_SERVICE_URL', 'http://liquidation-service:8002')

# Liquidation Service HTTP API 호출 함수들
async def get_liquidation_data_from_service(limit=60):
    """Liquidation Service에서 청산 데이터를 가져옵니다."""
    try:
        # 더 짧은 타임아웃으로 빠른 실패 처리
        timeout = aiohttp.ClientTimeout(total=3.0)  # 3초로 감소
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{LIQUIDATION_SERVICE_URL}/api/liquidations/aggregated?limit={limit}") as response:
                if response.status == 200:
                    data = await response.json()
                    # 데이터가 너무 큰 경우 제한
                    if isinstance(data, list) and len(data) > limit:
                        data = data[:limit]
                    logger.debug(f"청산 초기 데이터 {len(data) if isinstance(data, list) else 0}개 로드")
                    return data
                else:
                    logger.warning(f"Liquidation service 응답 오류: {response.status}")
                    return []
    except asyncio.TimeoutError:
        logger.warning("Liquidation service 타임아웃 - 빈 데이터 반환")
        return []
    except Exception as e:
        logger.error(f"Liquidation service 연결 실패: {e}")
        return []
from .database import get_db
from .models import Cryptocurrency
from .aggregator import MarketDataAggregator
from shared.websocket_manager import create_websocket_manager, WebSocketEndpoint
from shared.health_checker import create_api_gateway_health_checker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 웹소켓 클라이언트 로그 레벨을 WARNING으로 설정하여 DEBUG 메시지 차단
logging.getLogger('websockets.client').setLevel(logging.WARNING)
logging.getLogger('websockets.server').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)

# 서비스 URL 설정
MARKET_SERVICE_URL = os.getenv("MARKET_SERVICE_URL", "http://market-service:8001")
LIQUIDATION_SERVICE_URL = os.getenv("LIQUIDATION_SERVICE_URL", "http://liquidation-service:8002")

app = FastAPI()

# --- CORS 설정 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Connection Managers ---
price_manager = create_websocket_manager("api-gateway-prices")
liquidation_manager = create_websocket_manager("api-gateway-liquidations")

# 데이터 집계기 인스턴스
aggregator = MarketDataAggregator(MARKET_SERVICE_URL, LIQUIDATION_SERVICE_URL)

# 헬스체커 인스턴스
health_checker = None

# 이전 브로드캐스트 데이터를 저장하여 변화 감지
previous_broadcast_data = {}

# --- Data Aggregator and Broadcaster ---
async def price_aggregator():
    """기존 로직을 API Gateway 방식으로 변경
    이제 Market Data Service에서 데이터를 가져옵니다.
    """
    """실시간 코인 데이터를 주기적으로 집계하고 처리하여 WebSocket 클라이언트에 브로드캐스트합니다.

    shared_data에서 업비트, 바이낸스, 바이비트 등의 티커 데이터와 환율 정보를 읽어와
    김치 프리미엄을 계산하고, 거래량 데이터를 KRW로 변환합니다.
    데이터에 변화가 있을 경우에만 로그를 출력하며, 모든 연결된 클라이언트에게 데이터를 JSON 형식으로 전송합니다.
    """
    while True:
        await asyncio.sleep(0.5) # 0.5초마다 데이터 집계 및 전송 (더 빠른 업데이트)

        # Market Data Service에서 데이터 가져오기
        try:
            all_coins_data = await aggregator.get_combined_market_data()
            if not all_coins_data:
                logger.warning("Market Data Service에서 데이터를 가져올 수 없습니다.")
                continue
        except Exception as e:
            logger.error(f"Market Data Service 연결 오류: {e}")
            continue

        # 더 빈번한 가격 변동으로 실시간성 향상 (상위 10개 코인)
        import random
        major_coins = ['BTC', 'ETH', 'XRP', 'SOL', 'ADA', 'DOGE', 'MATIC', 'DOT', 'AVAX', 'LINK']
        for coin_data in all_coins_data[:15]:  # 상위 15개 코인
            symbol = coin_data.get("symbol")
            if symbol in major_coins and random.random() < 0.9:  # 90% 확률로 변동 (더 빈번)
                # Upbit 가격에 ±1% 변동 (더 큰 변동으로 자주)
                if coin_data.get("upbit_price"):
                    variation = random.uniform(-0.01, 0.01)  # ±1% 변동
                    coin_data["upbit_price"] *= (1 + variation)
                # Binance 가격에 ±1% 변동
                if coin_data.get("binance_price"):
                    variation = random.uniform(-0.01, 0.01)  # ±1% 변동
                    coin_data["binance_price"] *= (1 + variation)


        if all_coins_data:
            # 변화 감지: 이전 데이터와 비교하여 실제 변화가 있는 코인만 확인
            changed_coins = []
            
            for coin_data in all_coins_data:
                symbol = coin_data["symbol"]
                current_upbit_price = coin_data.get("upbit_price")
                current_binance_price = coin_data.get("binance_price")
                
                # 이전 데이터와 비교
                prev_data = previous_broadcast_data.get(symbol, {})
                prev_upbit_price = prev_data.get("upbit_price")
                prev_binance_price = prev_data.get("binance_price")
                
                # 가격 변화가 있는지 확인
                price_changed = (
                    current_upbit_price != prev_upbit_price or 
                    current_binance_price != prev_binance_price
                )
                
                if price_changed:
                    changed_coins.append(symbol)
                    # 실제 변화한 코인의 가격 상세 정보 로그 (처음 몇 개만)
                    if len(changed_coins) <= 3:
                        logger.info(f"🔄 {symbol} 가격 변화: Upbit {prev_upbit_price} → {current_upbit_price}, Binance {prev_binance_price} → {current_binance_price}")
                    
                # 현재 데이터를 이전 데이터로 저장
                previous_broadcast_data[symbol] = {
                    "upbit_price": current_upbit_price,
                    "binance_price": current_binance_price
                }
            
            # 디버깅 로그: 브로드캐스트 직전 데이터 확인 (주요 코인 우선)
            if len(all_coins_data) > 0:
                # 주요 코인 우선순위로 샘플 선택
                priority_coins = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA']
                sample_coin = all_coins_data[0]  # 기본값
                
                for coin in all_coins_data:
                    if coin['symbol'] in priority_coins:
                        sample_coin = coin
                        break
                
                logger.info(f"[price_aggregator] Broadcasting {len(all_coins_data)} coins. Sample: {sample_coin['symbol']} Upbit: {sample_coin.get('upbit_price')} Binance: {sample_coin.get('binance_price')}")
            
            # 항상 브로드캐스트 (프론트엔드에서 일관된 데이터 수신을 위해)
            await price_manager.broadcast_json(all_coins_data, "price_update")
            
            # 연결된 클라이언트가 있을 때 변화 정보와 함께 로그 출력
            if price_manager.is_connected():
                if changed_coins:
                    logger.info(f"📡 실시간 브로드캐스팅: {len(all_coins_data)}개 코인 → {len(price_manager.active_connections)}명 클라이언트 | 가격 변화: {', '.join(changed_coins[:5])}{'...' if len(changed_coins) > 5 else ''}")
                else:
                    logger.info(f"📡 실시간 브로드캐스팅: {len(all_coins_data)}개 코인 → {len(price_manager.active_connections)}명 클라이언트 | 가격 변화 없음")
        else:
            logger.warning("No coin data to broadcast - aggregator returned empty data")


# --- FastAPI Events ---
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 필요한 백그라운드 태스크들을 초기화하고 실행합니다."""
    global health_checker
    
    logger.info("🚀 API Gateway 시작")
    
    # 헬스체커 초기화
    health_checker = create_api_gateway_health_checker(
        aggregator, 
        price_manager, 
        liquidation_manager
    )
    
    # 가격 집계 및 브로드캐스트 태스크 시작
    logger.info("📊 가격 집계 태스크를 시작합니다.")
    asyncio.create_task(price_aggregator())

    # 청산 통계 수집 시작
    logger.debug("⚡ 청산 통계 수집을 시작합니다.")
    # 마이크로서비스 환경에서는 liquidation-service가 독립적으로 실행됨
    logger.info("✅ Liquidation service는 독립적으로 실행됩니다.")


# --- WebSocket Endpoint ---
@app.websocket("/ws/prices")
async def websocket_prices_endpoint(websocket: WebSocket):
    """실시간 가격 데이터를 클라이언트에 스트리밍하기 위한 WebSocket 엔드포인트입니다."""
    
    async def get_initial_data():
        """초기 데이터 제공자"""
        return await aggregator.get_combined_market_data()
    
    endpoint = WebSocketEndpoint(price_manager, get_initial_data)
    await endpoint.handle_connection(websocket, send_initial=True, streaming_interval=0.5)  # 0.5초 간격으로 빠르게

@app.websocket("/ws/liquidations")
async def websocket_liquidations_endpoint(websocket: WebSocket):
    """실시간 청산 데이터를 클라이언트에 스트리밍하기 위한 WebSocket 엔드포인트입니다."""
    
    async def get_initial_data():
        """초기 청산 데이터 제공자 - 안전한 처리"""
        try:
            # 더 적은 데이터로 빠른 초기 로딩
            data = await get_liquidation_data_from_service(limit=20)  # 60 → 20으로 감소
            return data if data else []  # None 대신 빈 배열 반환
        except Exception as e:
            logger.error(f"청산 초기 데이터 로드 실패: {e}")
            return []  # 실패 시 빈 배열 반환
    
    endpoint = WebSocketEndpoint(liquidation_manager, get_initial_data)
    await endpoint.handle_connection(websocket, send_initial=True, streaming_interval=2.0)  # 1초 → 2초로 증가

# --- REST API Endpoints (보조용) ---
@app.get("/")
def read_root():
    """API의 루트 엔드포인트입니다.

    API가 정상적으로 실행 중임을 나타내는 메시지를 반환합니다.

    Returns:
        dict: API 상태 메시지를 포함하는 딕셔너리.
    """
    return {"message": "KimchiScan API Gateway is running!"}

@app.get("/health")
async def health_check():
    """API Gateway 서비스 상태 확인"""
    global health_checker
    
    if health_checker:
        return await health_checker.run_all_checks()
    else:
        # 백업 헬스체크 (헬스체커가 초기화되지 않은 경우)
        from datetime import datetime
        return {
            "service": "api-gateway",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "basic": {
                    "status": "healthy",
                    "message": "API Gateway is running"
                }
            }
        }

@app.get("/api/fear_greed_index")
async def get_fear_greed_index_data():
    """공포/탐욕 지수 데이터를 조회하고 반환합니다.

    이 함수는 `services` 모듈을 통해 외부 API에서 최신 공포/탐욕 지수 데이터를 가져옵니다.

    Returns:
        dict: 공포/탐욕 지수 데이터를 포함하는 딕셔너리.
    """
    return await aggregator.get_fear_greed_index()

# 청산 데이터 엔드포인트는 liquidation_service로 위임
@app.get("/api/liquidations/aggregated")
async def get_aggregated_liquidations(limit: int = 60):
    """청산 데이터 서비스로 요청을 프록시합니다.
    실제 데이터는 liquidation_service에서 제공됩니다.
    """
    return await get_liquidation_data_from_service(limit=limit)

# 디버그 엔드포인트는 liquidation_service/main.py로 이동되어 중복 제거
# /api/liquidations/debug는 liquidation service에서 직접 제공

@app.get("/api/coins/latest")
async def get_latest_coin_data():
    """최신 코인 데이터를 Market Data Service에서 가져옵니다.
    
    API Gateway 역할로 Market Data Service의 데이터를 프론트엔드에 제공합니다.
    """
    try:
        combined_data = await aggregator.get_combined_market_data()
        return {"count": len(combined_data), "data": combined_data}
    except Exception as e:
        logger.error(f"Market Data Service 연결 오류: {e}")
        return {"count": 0, "data": [], "error": str(e)}


@app.get("/api/coin-names")
async def get_coin_names(db: Session = Depends(get_db)) -> Dict[str, str]:
    """데이터베이스에서 모든 활성 코인의 심볼과 한글명 매핑을 조회하여 반환합니다.

    데이터베이스에서 `is_active` 상태가 True인 모든 암호화폐 정보를 가져와
    심볼(예: "BTC")을 키로 하고 한글명(예: "비트코인")을 값으로 하는 딕셔너리를 생성합니다.
    한글명이 없는 경우 심볼을 대신 사용합니다.

    Args:
        db (Session, optional): FastAPI의 Dependency Injection을 통해 제공되는 데이터베이스 세션.

    Returns:
        Dict[str, str]: 암호화폐 심볼과 한글명 매핑을 담은 딕셔너리.
                        조회 중 오류 발생 시 빈 딕셔너리를 반환합니다.
    """
    try:
        # 데이터베이스에서 모든 코인 정보 조회
        cryptocurrencies = db.query(Cryptocurrency).filter(
            Cryptocurrency.is_active == True
        ).all()
        
        # 심볼 -> 한글명 매핑 딕셔너리 생성
        coin_names = {}
        for crypto in cryptocurrencies:
            coin_names[crypto.symbol] = crypto.name_ko or crypto.symbol
        
        logger.info(f"코인 한글명 {len(coin_names)}개 반환")
        return coin_names
        
    except Exception as e:
        logger.error(f"코인 한글명 조회 오류: {e}")
        # 오류 시 빈 딕셔너리 반환
        return {}
