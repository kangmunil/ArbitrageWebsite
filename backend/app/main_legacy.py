import asyncio
import logging
import os
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from sqlalchemy.orm import Session

from core import get_db, CoinMaster
from services.premium_service import MarketDataAggregator
from shared.websocket_manager import create_websocket_manager, WebSocketEndpoint
from shared.health_checker import create_api_gateway_health_checker

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 서비스 URL 설정
MARKET_SERVICE_URL = os.getenv("MARKET_SERVICE_URL", "http://market-service:8001")
LIQUIDATION_SERVICE_URL = os.getenv("LIQUIDATION_SERVICE_URL", "http://liquidation-service:8002")

# FastAPI 앱 초기화
app = FastAPI(title="Arbitrage Monitor API Gateway", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Managers
price_manager = create_websocket_manager("api-gateway-prices")
liquidation_manager = create_websocket_manager("api-gateway-liquidations")

# 데이터 집계기 인스턴스
aggregator = MarketDataAggregator(MARKET_SERVICE_URL, LIQUIDATION_SERVICE_URL)

# 헬스체커 인스턴스
health_checker = None

# --- 동적 우선순위 업데이트 함수 ---
def update_major_coins_by_volume(all_coins_data):
    """한국 거래소 거래량 기준으로 상위 20개 코인을 동적으로 선정"""
    global major_coins_by_volume, last_volume_update
    
    current_time = time.time()
    # 5분마다 우선순위 갱신
    if current_time - last_volume_update < 300:  # 5분 = 300초
        return
    
    # Upbit + Bithumb 거래량 기준으로 정렬
    korean_volume_coins = []
    for coin in all_coins_data:
        upbit_volume = coin.get('upbit_volume_krw', 0) or 0
        bithumb_volume = coin.get('bithumb_volume_krw', 0) or 0
        total_korean_volume = upbit_volume + bithumb_volume
        
        if total_korean_volume > 0:
            korean_volume_coins.append((coin['symbol'], total_korean_volume))
    
    # 거래량 기준 내림차순 정렬 후 상위 20개 선택
    korean_volume_coins.sort(key=lambda x: x[1], reverse=True)
    new_major_coins = {coin[0] for coin in korean_volume_coins[:20]}
    
    # 변경사항이 있을 때만 로그 출력
    if new_major_coins != major_coins_by_volume:
        removed = major_coins_by_volume - new_major_coins
        added = new_major_coins - major_coins_by_volume
        logger.info(f"🔄 한국 거래량 기준 우선순위 갱신: 제외 {removed}, 추가 {added}")
        
    major_coins_by_volume = new_major_coins
    last_volume_update = current_time

async def send_major_coin_update(coin_data):
    """Major 코인 개별 즉시 업데이트 (50ms 스로틀링)"""
    symbol = coin_data['symbol']
    current_time = time.time() * 1000  # 밀리초
    
    # 50ms 스로틀링 체크
    if symbol in major_coin_throttle:
        if current_time - major_coin_throttle[symbol] < 50:
            return False  # 스로틀링으로 스킵
    
    # 즉시 개별 전송
    await price_manager.broadcast_json([coin_data], "major_update")
    major_coin_throttle[symbol] = current_time
    return True

async def buffer_minor_coin_update(coin_data):
    """Minor 코인을 버퍼에 추가 (100ms 주기로 배치 전송)"""
    global minor_coin_buffer
    
    # 버퍼 크기 제한 (최대 100개)
    if len(minor_coin_buffer) < 100:
        minor_coin_buffer.append(coin_data)

def get_active_watched_coins():
    """현재 활성화된 사용자 관심 코인 반환 (5분 이내)"""
    global user_watched_coins
    current_time = time.time()
    
    # 만료된 관심 코인 제거
    expired_coins = [symbol for symbol, timestamp in user_watched_coins.items() 
                    if current_time - timestamp > WATCH_DURATION]
    for symbol in expired_coins:
        del user_watched_coins[symbol]
    
    return set(user_watched_coins.keys())

def add_user_watched_coin(symbol):
    """사용자 관심 코인 추가 (5분간 Major 코인으로 우선순위 부여)"""
    global user_watched_coins
    user_watched_coins[symbol] = time.time()
    logger.info(f"👀 사용자 관심 코인 추가: {symbol} (5분간 우선 업데이트)")

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
            if symbol in major_coins and random.random() < 0.4:  # 40% 확률로 변동
                # Upbit 가격에 ±0.2% 변동 (미세한 변동)
                if coin_data.get("upbit_price"):
                    variation = random.uniform(-0.002, 0.002)  # ±0.2% 변동
                    coin_data["upbit_price"] *= (1 + variation)
                # Binance 가격에 ±0.2% 변동
                if coin_data.get("binance_price"):
                    variation = random.uniform(-0.002, 0.002)  # ±0.2% 변동
                    coin_data["binance_price"] *= (1 + variation)


        if all_coins_data:
            # 1. 한국 거래량 기준 우선순위 동적 갱신 (5분마다)
            update_major_coins_by_volume(all_coins_data)
            
            # 2. 변화 감지 및 하이브리드 전송
            major_updates = 0
            minor_updates = 0
            
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
                    # 우선순위 판단: 거래량 상위 20개 + 사용자 관심 코인
                    is_major = (symbol in major_coins_by_volume or 
                               symbol in get_active_watched_coins())
                    
                    if is_major:
                        # Major 코인 → 즉시 개별 업데이트
                        sent = await send_major_coin_update(coin_data)
                        if sent:
                            major_updates += 1
                    else:
                        # Minor 코인 → 배치 버퍼에 추가
                        await buffer_minor_coin_update(coin_data)
                        minor_updates += 1
                    
                # 현재 데이터를 이전 데이터로 저장
                previous_broadcast_data[symbol] = {
                    "upbit_price": current_upbit_price,
                    "binance_price": current_binance_price
                }
            
            # 3. 로그 출력
            if price_manager.is_connected() and (major_updates > 0 or minor_updates > 0):
                major_list = [coin for coin in major_coins_by_volume if coin in [c['symbol'] for c in all_coins_data]][:5]
                logger.info(f"📡 하이브리드 업데이트: Major {major_updates}개 즉시 전송, Minor {minor_updates}개 버퍼 대기 | 현재 Major: {', '.join(major_list)}...")
        else:
            logger.warning("No coin data to broadcast - aggregator returned empty data")

async def minor_coin_batch_sender():
    """Minor 코인들을 100ms 주기로 배치 전송"""
    global minor_coin_buffer
    
    while True:
        await asyncio.sleep(0.1)  # 100ms 대기
        
        if minor_coin_buffer and price_manager.is_connected():
            # 버퍼에 있는 모든 코인을 배치로 전송
            batch_data = minor_coin_buffer.copy()
            minor_coin_buffer.clear()
            
            await price_manager.broadcast_json(batch_data, "minor_batch")
            logger.info(f"📦 Minor 배치 전송: {len(batch_data)}개 코인")


# --- FastAPI Events ---
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 개선된 6단계 구동 프로세스를 실행합니다."""
    global health_checker
    
    logger.info("🚀 API Gateway 시작 - 개선된 구동 프로세스 적용")
    
    try:
        # 개선된 구동 관리자를 통한 시스템 시작
        from startup_manager import start_system
        
        startup_result = await start_system()
        
        if startup_result['success']:
            logger.info("✅ 시스템 구동 완료 - 서비스 준비됨")
        else:
            logger.error(f"❌ 시스템 구동 실패: {startup_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"💥 시스템 구동 중 예외: {e}")
    
    # 기존 서비스 컴포넌트 초기화 (백업으로 유지)
    await _initialize_service_components()

async def _initialize_service_components():
    """기존 서비스 컴포넌트들 초기화"""
    global health_checker
    
    # 헬스체커 초기화
    health_checker = create_api_gateway_health_checker(
        aggregator, 
        price_manager, 
        liquidation_manager
    )
    
    # 가격 집계 및 브로드캐스트 태스크 시작
    logger.info("📊 가격 집계 태스크를 시작합니다.")
    asyncio.create_task(price_aggregator())
    
    # Minor 코인 배치 전송 태스크 시작
    logger.info("📦 Minor 코인 배치 전송 태스크를 시작합니다.")
    asyncio.create_task(minor_coin_batch_sender())

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
    await endpoint.handle_connection(websocket, send_initial=True, streaming_interval=0.2)  # 0.2초 간격으로 실시간

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

@app.get("/api/coin-images")
async def get_coin_images(db: Session = Depends(get_db)) -> Dict[str, str]:
    """데이터베이스에서 모든 활성 코인의 심볼과 이미지 URL 매핑을 조회하여 반환합니다.

    데이터베이스에서 `is_active` 상태가 True이고 `logo_url`이 있는 모든 암호화폐 정보를 가져와
    심볼(예: "BTC")을 키로 하고 이미지 URL을 값으로 하는 딕셔너리를 생성합니다.

    Args:
        db (Session, optional): FastAPI의 Dependency Injection을 통해 제공되는 데이터베이스 세션.

    Returns:
        Dict[str, str]: 암호화폐 심볼과 이미지 URL 매핑을 담은 딕셔너리.
                        조회 중 오류 발생 시 빈 딕셔너리를 반환합니다.
    """
    try:
        # 데이터베이스에서 이미지 URL이 있는 코인 정보 조회
        cryptocurrencies = db.query(Cryptocurrency).filter(
            Cryptocurrency.is_active == True,
            Cryptocurrency.logo_url.isnot(None),
            Cryptocurrency.logo_url != ''
        ).all()
        
        # 심볼 -> 이미지 URL 매핑 딕셔너리 생성
        coin_images = {}
        for crypto in cryptocurrencies:
            coin_images[crypto.symbol] = crypto.logo_url
        
        logger.info(f"코인 이미지 URL {len(coin_images)}개 반환")
        return coin_images
        
    except Exception as e:
        logger.error(f"코인 이미지 URL 조회 오류: {e}")
        # 오류 시 빈 딕셔너리 반환
        return {}

@app.get("/api/coin-metadata/{symbol}")
async def get_coin_metadata(symbol: str, db: Session = Depends(get_db)):
    """특정 코인의 상세 메타데이터를 조회합니다.
    
    Args:
        symbol (str): 조회할 코인 심볼 (예: BTC, ETH)
        db (Session): 데이터베이스 세션
    
    Returns:
        Dict: 코인의 상세 메타데이터 또는 404 오류
    """
    try:
        coin = db.query(Cryptocurrency).filter(
            Cryptocurrency.symbol == symbol.upper(),
            Cryptocurrency.is_active == True
        ).first()
        
        if not coin:
            return {"error": f"코인 '{symbol}'을 찾을 수 없습니다"}
        
        metadata = {
            "symbol": coin.symbol,
            "name_ko": coin.name_ko,
            "name_en": coin.name_en,
            "logo_url": coin.logo_url,
            "market_cap_rank": coin.market_cap_rank,
            "circulating_supply": float(getattr(coin, 'circulating_supply', 0)) if getattr(coin, 'circulating_supply', None) is not None else None,
            "max_supply": float(getattr(coin, 'max_supply', 0)) if getattr(coin, 'max_supply', None) is not None else None,
            "category": coin.category,
            "website_url": coin.website_url,
            "whitepaper_url": coin.whitepaper_url
        }
        
        logger.info(f"코인 메타데이터 조회: {symbol}")
        return metadata
        
    except Exception as e:
        logger.error(f"코인 메타데이터 조회 오류: {e}")
        return {"error": "메타데이터 조회 중 오류가 발생했습니다"}

@app.get("/api/coins/by-category/{category}")
async def get_coins_by_category(category: str, db: Session = Depends(get_db)):
    """카테고리별 코인 목록을 조회합니다.
    
    Args:
        category (str): 카테고리명 (예: DeFi, Layer1, Meme)
        db (Session): 데이터베이스 세션
    
    Returns:
        List[Dict]: 해당 카테고리의 코인 목록
    """
    try:
        coins = db.query(Cryptocurrency).filter(
            Cryptocurrency.category == category,
            Cryptocurrency.is_active == True
        ).order_by(Cryptocurrency.market_cap_rank.asc()).all()
        
        coin_list = []
        for coin in coins:
            coin_data = {
                "symbol": coin.symbol,
                "name_ko": coin.name_ko,
                "name_en": coin.name_en,
                "logo_url": coin.logo_url,
                "market_cap_rank": coin.market_cap_rank,
                "category": coin.category
            }
            coin_list.append(coin_data)
        
        logger.info(f"카테고리별 코인 조회: {category} ({len(coin_list)}개)")
        return coin_list
        
    except Exception as e:
        logger.error(f"카테고리별 코인 조회 오류: {e}")
        return []

@app.get("/api/coins/top-marketcap")
async def get_top_marketcap_coins(limit: int = 20, db: Session = Depends(get_db)):
    """시가총액 순위별 상위 코인 목록을 조회합니다.
    
    Args:
        limit (int): 조회할 코인 개수 (기본 20개)
        db (Session): 데이터베이스 세션
    
    Returns:
        List[Dict]: 시가총액 순위별 코인 목록
    """
    try:
        coins = db.query(Cryptocurrency).filter(
            Cryptocurrency.is_active == True,
            Cryptocurrency.market_cap_rank.isnot(None)
        ).order_by(Cryptocurrency.market_cap_rank.asc()).limit(limit).all()
        
        coin_list = []
        for coin in coins:
            coin_data = {
                "symbol": coin.symbol,
                "name_ko": coin.name_ko,
                "name_en": coin.name_en,
                "logo_url": coin.logo_url,
                "market_cap_rank": coin.market_cap_rank,
                "category": coin.category,
                "website_url": coin.website_url
            }
            coin_list.append(coin_data)
        
        logger.info(f"시가총액 상위 {len(coin_list)}개 코인 조회")
        return coin_list
        
    except Exception as e:
        logger.error(f"시가총액 상위 코인 조회 오류: {e}")
        return []

@app.post("/api/coin-metadata/update/{symbol}")
async def update_coin_metadata(symbol: str, db: Session = Depends(get_db)):
    """특정 코인의 메타데이터를 CoinGecko에서 가져와 업데이트합니다.
    
    Args:
        symbol (str): 업데이트할 코인 심볼 (예: BTC, ETH)
        db (Session): 데이터베이스 세션
    
    Returns:
        Dict: 업데이트 결과
    """
    try:
        from .metadata_collector import OptimizedMetadataCollector
        
        async with OptimizedMetadataCollector() as collector:
            # bulk_update_metadata는 리스트를 받으므로 단일 심볼을 리스트로 전달
            results = await collector.bulk_update_metadata([symbol.upper()])
            
            if results and results[0].success:
                # 업데이트된 데이터 다시 조회
                updated_coin = db.query(Cryptocurrency).filter(Cryptocurrency.symbol == symbol.upper()).first()
                if updated_coin:
                    return {
                        "success": True,
                        "message": f"{symbol.upper()} 메타데이터가 성공적으로 업데이트되었습니다",
                        "symbol": symbol.upper(),
                        "updated_fields": results[0].updated_fields,
                        "metadata": {
                            "symbol": updated_coin.symbol,
                            "name_ko": updated_coin.name_ko,
                            "name_en": updated_coin.name_en,
                            "logo_url": updated_coin.logo_url,
                            "market_cap_rank": updated_coin.market_cap_rank,
                            "circulating_supply": float(updated_coin.circulating_supply) if updated_coin.circulating_supply else None,
                            "max_supply": float(updated_coin.max_supply) if updated_coin.max_supply else None,
                            "category": updated_coin.category,
                            "website_url": updated_coin.website_url,
                            "whitepaper_url": updated_coin.whitepaper_url
                        }
                    }
                else:
                    return {"success": False, "message": "업데이트 후 데이터를 조회하지 못했습니다."}
            else:
                error_message = results[0].error if results else "알 수 없는 오류"
                return {
                    "success": False,
                    "message": f"{symbol.upper()} 메타데이터 업데이트에 실패했습니다: {error_message}",
                    "symbol": symbol.upper()
                }
                
    except Exception as e:
        logger.error(f"메타데이터 업데이트 API 오류: {e}")
        return {
            "success": False,
            "error": f"메타데이터 업데이트 중 오류가 발생했습니다: {str(e)}"
        }

@app.get("/api/categories")
async def get_available_categories(db: Session = Depends(get_db)):
    """사용 가능한 모든 카테고리 목록을 조회합니다.
    
    Returns:
        List[Dict]: 카테고리별 코인 개수 정보
    """
    try:
        from sqlalchemy import func
        
        # 카테고리별 코인 개수 집계
        categories = db.query(
            Cryptocurrency.category,
            func.count(Cryptocurrency.id).label('count')
        ).filter(
            Cryptocurrency.is_active == True,
            Cryptocurrency.category.isnot(None)
        ).group_by(Cryptocurrency.category).all()
        
        category_list = []
        for category, count in categories:
            category_list.append({
                "category": category,
                "count": count
            })
        
        # 코인 개수 기준 내림차순 정렬
        category_list.sort(key=lambda x: x['count'], reverse=True)
        
        logger.info(f"카테고리 목록 조회: {len(category_list)}개")
        return category_list
        
    except Exception as e:
        logger.error(f"카테고리 목록 조회 오류: {e}")
        return []

@app.get("/api/system/startup-status")
async def get_startup_status():
    """시스템 구동 상태 조회"""
    try:
        from startup_manager import get_startup_status
        return get_startup_status()
    except Exception as e:
        logger.error(f"구동 상태 조회 오류: {e}")
        return {"error": "구동 상태를 조회할 수 없습니다"}

@app.post("/api/system/restart")
async def restart_system():
    """시스템 재시작"""
    try:
        from startup_manager import start_system
        result = await start_system()
        return result
    except Exception as e:
        logger.error(f"시스템 재시작 오류: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/backup/status")
async def get_backup_status():
    """백업 상태 조회 (순수 Python 백업 시스템)"""
    try:
        from .backup_manager import get_python_backup_status
        return await get_python_backup_status()
    except Exception as e:
        logger.error(f"백업 상태 조회 오류: {e}")
        return {"error": "백업 상태를 조회할 수 없습니다"}

@app.post("/api/backup/create")
async def create_backup():
    """수동 백업 생성 (순수 Python 백업 시스템)"""
    try:
        from .backup_manager import create_python_backup
        result = await create_python_backup()
        return result
    except Exception as e:
        logger.error(f"백업 생성 오류: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/backup/list")
async def list_backups():
    """백업 파일 목록 조회 (순수 Python 백업 시스템)"""
    try:
        from .backup_manager import python_backup_manager
        backups = await python_backup_manager.list_backups()
        return {"backups": backups}
    except Exception as e:
        logger.error(f"백업 목록 조회 오류: {e}")
        return {"error": "백업 목록을 조회할 수 없습니다"}

@app.post("/api/backup/cleanup")
async def cleanup_old_backups():
    """오래된 백업 정리 (순수 Python 백업 시스템)"""
    try:
        from .backup_manager import cleanup_python_backups
        result = await cleanup_python_backups()
        return result
    except Exception as e:
        logger.error(f"백업 정리 오류: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/backup/restore/{filename}")
async def restore_backup(filename: str):
    """백업에서 데이터베이스 복원 (순수 Python 백업 시스템)"""
    try:
        from .backup_manager import python_backup_manager
        result = await python_backup_manager.restore_backup(filename)
        return result
    except Exception as e:
        logger.error(f"백업 복원 오류: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/watch-coin/{symbol}")
async def watch_coin(symbol: str):
    """사용자가 관심있는 코인을 5분간 우선 업데이트 대상으로 추가"""
    try:
        symbol = symbol.upper()
        add_user_watched_coin(symbol)
        
        return {
            "success": True,
            "message": f"{symbol} 코인이 5분간 우선 업데이트 대상으로 추가되었습니다",
            "symbol": symbol,
            "duration": WATCH_DURATION,
            "active_watched": list(get_active_watched_coins())
        }
    except Exception as e:
        logger.error(f"관심 코인 추가 오류: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/watched-coins")
async def get_watched_coins():
    """현재 사용자 관심 코인 목록 조회"""
    try:
        active_coins = get_active_watched_coins()
        return {
            "success": True,
            "watched_coins": list(active_coins),
            "count": len(active_coins),
            "duration": WATCH_DURATION
        }
    except Exception as e:
        logger.error(f"관심 코인 목록 조회 오류: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# === 최적화된 메타데이터 수집 API ===

@app.post("/api/metadata/bulk-sync")
async def bulk_sync_metadata_endpoint(symbols: Optional[List[str]] = None):
    """배치 메타데이터 동기화 (최적화된 버전)"""
    try:
        from .metadata_collector import bulk_sync_metadata
        
        # symbols가 None일 경우 빈 리스트를 전달하여 bulk_sync_metadata의 타입 힌트와 일치시킴
        sync_symbols = symbols if symbols is not None else []
        logger.info(f"🔄 배치 메타데이터 동기화 시작: {len(sync_symbols) if sync_symbols else 'ALL'}")
        
        results = await bulk_sync_metadata(sync_symbols)
        
        # 결과 통계
        success_count = sum(1 for r in results if r.success)
        updated_count = sum(1 for r in results if r.success and r.updated_fields and 'created' not in r.updated_fields)
        created_count = sum(1 for r in results if r.success and r.updated_fields and 'created' in r.updated_fields)
        failed_count = sum(1 for r in results if not r.success)
        
        return {
            "success": True,
            "total_processed": len(results),
            "success_count": success_count,
            "updated_count": updated_count,
            "created_count": created_count,
            "failed_count": failed_count,
            "results": [
                {
                    "symbol": r.symbol,
                    "success": r.success,
                    "updated_fields": r.updated_fields,
                    "error": r.error
                } for r in results
            ]
        }
        
    except Exception as e:
        logger.error(f"배치 메타데이터 동기화 오류: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/metadata/cache-stats")
async def get_metadata_cache_stats_endpoint():
    """메타데이터 캐시 통계 조회"""
    try:
        from .metadata_collector import get_metadata_cache_stats
        
        stats = await get_metadata_cache_stats()
        return {
            "success": True,
            "cache_stats": stats
        }
        
    except Exception as e:
        logger.error(f"캐시 통계 조회 오류: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/metadata/sync-priority/{symbol}")
async def sync_priority_coin_metadata(symbol: str):
    """우선순위 코인 메타데이터 동기화"""
    try:
        from .metadata_collector import bulk_sync_metadata
        
        symbol = symbol.upper()
        results = await bulk_sync_metadata([symbol])
        
        if results and results[0].success:
            return {
                "success": True,
                "symbol": symbol,
                "updated_fields": results[0].updated_fields,
                "message": f"{symbol} 메타데이터 동기화 완료"
            }
        else:
            error = results[0].error if results else "Unknown error"
            return {
                "success": False,
                "symbol": symbol,
                "error": error
            }
            
    except Exception as e:
        logger.error(f"{symbol} 메타데이터 동기화 오류: {e}")
        return {"success": False, "symbol": symbol, "error": str(e)}

# === 주기적 마켓 목록 업데이트 API ===

@app.post("/api/markets/update-all")
async def update_all_markets_endpoint():
    """모든 거래소 마켓 목록 업데이트"""
    try:
        from .market_updater import update_all_exchange_markets
        
        logger.info("🔄 전체 거래소 마켓 목록 업데이트 시작")
        results = await update_all_exchange_markets()
        
        # 결과 통계
        successful_count = sum(1 for r in results if r.success)
        total_new_markets = sum(r.new_markets for r in results if r.success)
        total_active_markets = sum(r.active_markets for r in results if r.success)
        
        return {
            "success": True,
            "total_exchanges": len(results),
            "successful_exchanges": successful_count,
            "total_active_markets": total_active_markets,
            "total_new_markets": total_new_markets,
            "exchange_results": [
                {
                    "exchange": r.exchange,
                    "success": r.success,
                    "active_markets": r.active_markets,
                    "new_markets": r.new_markets,
                    "errors": r.errors
                } for r in results
            ]
        }
        
    except Exception as e:
        logger.error(f"전체 마켓 업데이트 오류: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/markets/update/{exchange_id}")
async def update_exchange_markets_endpoint(exchange_id: str):
    """특정 거래소 마켓 목록 업데이트"""
    try:
        from .market_updater import update_single_exchange_markets
        
        logger.info(f"🔄 {exchange_id} 마켓 목록 업데이트 시작")
        result = await update_single_exchange_markets(exchange_id)
        
        if result.success:
            return {
                "success": True,
                "exchange": result.exchange,
                "active_markets": result.active_markets,
                "new_markets": result.new_markets,
                "deactivated_markets": result.deactivated_markets,
                "message": f"{exchange_id} 마켓 업데이트 완료"
            }
        else:
            return {
                "success": False,
                "exchange": result.exchange,
                "errors": result.errors
            }
            
    except Exception as e:
        logger.error(f"{exchange_id} 마켓 업데이트 오류: {e}")
        return {"success": False, "exchange": exchange_id, "error": str(e)}

@app.post("/api/markets/cleanup")
async def cleanup_inactive_markets_endpoint(days: int = 7):
    """비활성 마켓 정리"""
    try:
        from .market_updater import cleanup_old_markets
        
        logger.info(f"🧹 {days}일 이상 된 비활성 마켓 정리 시작")
        deactivated_count = await cleanup_old_markets(days)
        
        return {
            "success": True,
            "days_threshold": days,
            "deactivated_count": deactivated_count,
            "message": f"{deactivated_count}개 오래된 마켓 비활성화 완료"
        }
        
    except Exception as e:
        logger.error(f"비활성 마켓 정리 오류: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/markets/stats")
async def get_market_stats_endpoint():
    """마켓 통계 조회"""
    try:
        from .market_updater import get_current_market_stats
        
        stats = get_current_market_stats()
        return {
            "success": True,
            "market_stats": stats
        }
        
    except Exception as e:
        logger.error(f"마켓 통계 조회 오류: {e}")
        return {"success": False, "error": str(e)}

# === 데이터 검증 및 품질 관리 API ===

@app.get("/api/data/column-info")
async def get_column_specifications():
    """Cryptocurrencies 테이블 컬럼 사양 조회"""
    try:
        from .data_validator import get_column_info
        
        column_specs = get_column_info()
        
        # ColumnInfo 객체를 딕셔너리로 변환
        result = {}
        for col_name, col_info in column_specs.items():
            result[col_name] = {
                "name": col_info.name,
                "data_type": col_info.data_type,
                "auto_collectible": col_info.auto_collectible,
                "data_source": col_info.data_source,
                "validation_rules": col_info.validation_rules,
                "sample_values": col_info.sample_values,
                "notes": col_info.notes
            }
        
        return {
            "success": True,
            "column_specifications": result
        }
        
    except Exception as e:
        logger.error(f"컬럼 사양 조회 오류: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/data/collectibility-analysis")
async def get_data_collectibility():
    """데이터 수집 가능성 분석"""
    try:
        from .data_validator import get_data_collectibility_analysis
        
        analysis = get_data_collectibility_analysis()
        return {
            "success": True,
            "collectibility_analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"데이터 수집 가능성 분석 오류: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/data/quality-report")
async def get_data_quality_report():
    """데이터 품질 보고서"""
    try:
        from .data_validator import generate_quality_report
        
        report = generate_quality_report()
        return {
            "success": True,
            "quality_report": report
        }
        
    except Exception as e:
        logger.error(f"데이터 품질 보고서 생성 오류: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/data/validate")
async def validate_cryptocurrency_data(crypto_data: Dict):
    """암호화폐 데이터 검증"""
    try:
        from .data_validator import validate_crypto_data
        
        validation_results = validate_crypto_data(crypto_data)
        
        # ValidationResult 객체를 딕셔너리로 변환
        results = []
        for result in validation_results:
            results.append({
                "column": result.column,
                "is_valid": result.is_valid,
                "value": result.value,
                "errors": result.errors,
                "warnings": result.warnings
            })
        
        overall_valid = all(r.is_valid for r in validation_results)
        total_errors = sum(len(r.errors) for r in validation_results)
        total_warnings = sum(len(r.warnings) for r in validation_results)
        
        return {
            "success": True,
            "overall_valid": overall_valid,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "validation_results": results
        }
        
    except Exception as e:
        logger.error(f"데이터 검증 오류: {e}")
        return {"success": False, "error": str(e)}
