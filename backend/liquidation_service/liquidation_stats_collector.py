"""
통계 기반 청산 데이터 수집 서비스 모듈.

각 거래소에서 24시간 통계와 실시간 요약 데이터를 수집합니다.
"""

import asyncio
import json
import aiohttp
try:
    import websockets  # type: ignore
    websocket_connect = getattr(websockets, 'connect', None)
except ImportError:
    websockets = None
    websocket_connect = None
from datetime import datetime
from typing import Dict, List, Optional, Deque
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

# 통합된 청산 데이터 저장용 (메모리 기반, 최근 24시간)
liquidation_stats_data: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=24))  # 1시간 버킷 * 24시간 = 24

# WebSocket 연결 관리자
liquidation_websocket_manager = None

# Binance 실제 청산 데이터 수집을 위한 부분 체결 추적
binance_partial_fills: Dict[str, Dict] = {}  # 주문 ID별 부분 체결 상태 추적

# 멀티팩터 동적 캘리브레이션 모델 파라미터
CALIBRATION_PARAMS = {
    # α 값을 15-20배 상향, β 값을 1/10으로 하향 - 실제 청산 규모($5.53M)에 맞춰 대폭 조정
    'binance': {'α': 0.0000002, 'β': 120000000, 'γ': 10.0, 'κ': 0.5},     # 최대 거래소 - α 20배 증가
    'bybit': {'α': 0.0000003, 'β': 100000000, 'γ': 12.0, 'κ': 0.6},       # 2위 거래소 - α 20배 증가  
    'okx': {'α': 0.00000012, 'β': 80000000, 'γ': 8.0, 'κ': 0.4},          # 3위 거래소 - α 15배 증가
    'bitmex': {'α': 0.0000006, 'β': 50000000, 'γ': 20.0, 'κ': 0.8},       # 높은 레버리지 - α 20배 증가
    'bitget': {'α': 0.00000024, 'β': 70000000, 'γ': 15.0, 'κ': 0.7},      # 신흥 거래소 - α 20배 증가
    'hyperliquid': {'α': 0.00000008, 'β': 30000000, 'γ': 5.0, 'κ': 0.3}   # DeFi 거래소 - α 16배 증가
}

# 거래소별 청산 시뮬레이션 특성 파라미터 (기존 백업용)
EXCHANGE_LIQUIDATION_PROFILES = {
    'binance': {
        'base_liquidation_rate': 0.001,     # 최대 거래소, 높은 청산 비율
        'volatility_multiplier': 2.0,       # 높은 변동성 승수
        'long_bias': 0.50,                  # 균형잡힌 롱/숏 비율
        'leverage_factor': 25.0,            # 평균 레버리지
        'liquidation_threshold': 0.03,      # 3% 가격 변동 시 청산 증가
        'market_hours_factor': 1.0,         # 글로벌 거래소
        'weekend_factor': 0.8,              # 주말 청산 감소
        'min_liquidation_size': 500,        # 최소 청산 크기 ($)
        'max_liquidation_size': 10000000,   # 최대 청산 크기 ($)
    },
    'bybit': {
        'base_liquidation_rate': 0.0008,    # 거래량 대비 기본 청산 비율 (0.08%)
        'volatility_multiplier': 1.8,       # 변동성 승수
        'long_bias': 0.45,                  # 롱 청산 비율 (45% 롱, 55% 숏)
        'leverage_factor': 25.0,            # 평균 레버리지
        'liquidation_threshold': 0.04,      # 4% 가격 변동 시 청산 증가
        'market_hours_factor': 0.7,         # 아시아 시간 가중치
        'weekend_factor': 0.6,              # 주말 청산 감소
        'min_liquidation_size': 100,        # 최소 청산 크기 ($)
        'max_liquidation_size': 2000000,    # 최대 청산 크기 ($)
    },
    'okx': {
        'base_liquidation_rate': 0.0006,
        'volatility_multiplier': 1.5,
        'long_bias': 0.48,
        'leverage_factor': 20.0,
        'liquidation_threshold': 0.035,
        'market_hours_factor': 0.8,
        'weekend_factor': 0.65,
        'min_liquidation_size': 50,
        'max_liquidation_size': 1500000,
    },
    'bitmex': {
        'base_liquidation_rate': 0.0012,    # BitMEX는 높은 레버리지로 청산 많음
        'volatility_multiplier': 2.2,
        'long_bias': 0.42,                  # 숏 포지션 선호 경향
        'leverage_factor': 50.0,
        'liquidation_threshold': 0.02,      # 2% 변동으로도 청산
        'market_hours_factor': 0.9,         # 글로벌 거래소
        'weekend_factor': 0.75,
        'min_liquidation_size': 200,
        'max_liquidation_size': 5000000,
    },
    'bitget': {
        'base_liquidation_rate': 0.0007,
        'volatility_multiplier': 1.6,
        'long_bias': 0.50,
        'leverage_factor': 30.0,
        'liquidation_threshold': 0.038,
        'market_hours_factor': 0.75,
        'weekend_factor': 0.7,
        'min_liquidation_size': 80,
        'max_liquidation_size': 1800000,
    },
    'hyperliquid': {
        'base_liquidation_rate': 0.0004,    # 신규 거래소로 청산 적음
        'volatility_multiplier': 1.3,
        'long_bias': 0.52,
        'leverage_factor': 15.0,
        'liquidation_threshold': 0.045,
        'market_hours_factor': 0.85,
        'weekend_factor': 0.8,
        'min_liquidation_size': 150,
        'max_liquidation_size': 800000,
    }
}


class LiquidationStatsCollector:
    """통계 기반 청산 데이터 수집기 클래스.

    각 거래소에서 24시간 통계와 실시간 요약 데이터를 수집하고 처리합니다.
    """
    
    def __init__(self):
        """LiquidationStatsCollector 클래스의 생성자입니다.

        수집기의 실행 상태, WebSocket 관리자, 그리고 이전 24시간 통계 데이터를 초기화합니다.
        """
        self.is_running = False
        self.websocket_manager = None
        self.last_24h_stats = {}  # 이전 통계 저장용
        self.binance_websocket_task = None  # Binance 실시간 청산 수집 태스크
        self.market_volatility_cache = {}  # 시장 변동성 캐시
        self.liquidation_history = defaultdict(list)  # 거래소별 청산 히스토리
        self.market_data_cache = {}  # 미결제약정, 펀딩비율 등 캐시
        self.calibration_history = defaultdict(list)  # 캘리브레이션 히스토리
        
    def set_websocket_manager(self, manager):
        """수집기가 사용할 WebSocket 관리자 인스턴스를 설정합니다.

        이 관리자는 수집된 청산 데이터를 클라이언트에 브로드캐스트하는 데 사용됩니다.

        Args:
            manager: WebSocket 연결을 관리하는 객체 (예: ConnectionManager 인스턴스).
        """
        self.websocket_manager = manager
        
    async def start_collection(self):
        """통계 기반 청산 데이터 수집 프로세스를 시작합니다.

        이미 실행 중인 경우 다시 시작하지 않습니다.
        `collect_liquidation_statistics` 태스크를 생성하고 실행합니다.
        """
        logger.debug("LiquidationStatsCollector.start_collection() called - 통계 기반 수집 시작")
        if self.is_running:
            logger.debug("Liquidation stats collection already running, skipping...")
            return
            
        self.is_running = True
        logger.info("📊 청산 데이터 수집 서비스 시작")
        
        # 통계 기반 수집 태스크 (모든 거래소 통일)
        stats_task = asyncio.create_task(self.collect_liquidation_statistics())
        
        # 실시간 WebSocket 수집 비활성화 - 모든 거래소를 멀티팩터 시뮬레이션으로 통일
        # self.binance_websocket_task = asyncio.create_task(self.collect_binance_real_liquidations())
        
        logger.debug("Starting statistical liquidation collection task for all exchanges...")
        logger.info("📊 모든 거래소에 멀티팩터 시뮬레이션 모델 적용")
        
        try:
            # 통계 기반 태스크만 실행
            await stats_task
        except Exception as e:
            logger.error(f"Error in liquidation collection tasks: {e}")
            import traceback
            traceback.print_exc()
    
    async def collect_liquidation_statistics(self):
        """각 거래소의 24시간 청산 통계를 주기적으로 수집합니다.

        REST API를 통해 바이낸스, 바이비트, OKX, BitMEX, Bitget, Hyperliquid의
        청산 통계를 병렬로 가져와 저장합니다. 5분마다 갱신됩니다.
        """
        logger.debug("📈 24시간 청산 통계 수집 시작")
        
        while self.is_running:
            try:
                # 거래소별 24시간 청산 통계를 병렬로 수집
                # 모든 거래소에 멀티팩터 시뮬레이션 모델 적용 (데이터 일관성 확보)
                tasks = [
                    self.fetch_binance_24h_stats(),  # 시뮬레이션 모델 적용을 위해 활성화
                    self.fetch_bybit_24h_stats(), 
                    self.fetch_okx_24h_stats(),
                    self.fetch_bitmex_24h_stats(),
                    self.fetch_bitget_24h_stats(),
                    self.fetch_hyperliquid_24h_stats()
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 성공한 결과 처리 (타입 체킹 개선)
                successful_results = [r for r in results if not isinstance(r, Exception) and r is not None and isinstance(r, dict)]
                for stats in successful_results:
                    await self.store_24h_liquidation_stats(stats)

                # 실패한 예외 처리
                failed_exceptions = [r for r in results if isinstance(r, Exception)]
                for exc in failed_exceptions:
                    logger.error(f"청산 통계 수집 중 예외 발생: {exc}")
                
                # 1시간마다 갱신 (3600초)
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"24시간 청산 통계 수집 오류: {e}")
                await asyncio.sleep(60)
    
    async def collect_binance_real_liquidations(self):
        """Binance 실시간 청산 데이터를 WebSocket으로 수집합니다.
        
        부분 체결을 고려하여 실제 체결된 수량(l)만큼의 USD 임팩트를 계산합니다.
        """
        logger.info("🚀 Binance 실시간 청산 WebSocket 수집 시작")
        
        while self.is_running:
            try:
                if websocket_connect is None:
                    logger.error("websockets 라이브러리가 설치되지 않았습니다.")
                    await asyncio.sleep(60)
                    continue
                    
                uri = "wss://fstream.binance.com/ws/!forceOrder@arr"
                
                async with websocket_connect(uri) as websocket:
                    logger.info("✅ Binance 청산 WebSocket 연결 성공")
                    
                    async for message in websocket:
                        try:
                            liquidation_data = json.loads(message)
                            await self.process_binance_liquidation_event(liquidation_data)
                        except Exception as e:
                            logger.error(f"청산 이벤트 처리 오류: {e}")
                            
            except Exception as e:
                logger.error(f"Binance 청산 WebSocket 연결 오류: {e}")
                logger.info("🔄 5초 후 재연결 시도...")
                await asyncio.sleep(5)
    
    async def process_binance_liquidation_event(self, data):
        """Binance 청산 이벤트를 처리하고 부분 체결을 고려합니다.
        
        Args:
            data: Binance forceOrder 이벤트 데이터
        """
        try:
            # 청산 주문 정보 추출
            order_info = data.get('o', {})
            symbol = order_info.get('s', '')  # BTCUSDT
            side = order_info.get('S', '')    # SELL(롱청산) or BUY(숏청산)
            
            # 부분 체결 정보
            last_filled_qty = float(order_info.get('l', 0))      # 이번에 체결된 수량
            cumulative_filled_qty = float(order_info.get('z', 0)) # 누적 체결 수량
            original_qty = float(order_info.get('q', 0))         # 원래 주문 수량
            avg_price = float(order_info.get('ap', 0))           # 평균 체결 가격
            execution_type = order_info.get('X', '')             # FILLED, PARTIALLY_FILLED
            
            timestamp = data.get('E', 0)  # 이벤트 시간 (밀리초)
            
            # USDT 페어만 처리
            if 'USDT' not in symbol or last_filled_qty <= 0:
                return
            
            # 실제 체결된 수량 기반 USD 임팩트 계산
            usd_impact = last_filled_qty * avg_price
            
            # 1시간 버킷으로 집계
            hour_bucket = (timestamp // 3600000) * 3600000
            
            # 롱/숏 청산 분류
            if side == "SELL":  # 롱 포지션 청산
                await self.add_real_liquidation_to_bucket(
                    hour_bucket, "binance", "long", usd_impact, 1
                )
                liquidation_type = "롱청산"
            elif side == "BUY":  # 숏 포지션 청산
                await self.add_real_liquidation_to_bucket(
                    hour_bucket, "binance", "short", usd_impact, 1
                )
                liquidation_type = "숏청산"
            else:
                return
            
            # 개발 모드에서만 상세 로그 (주요 청산만)
            if usd_impact > 10000:  # $10K 이상 청산만 로그
                fill_status = "완전체결" if execution_type == "FILLED" else f"부분체결({cumulative_filled_qty:.3f}/{original_qty:.3f})"
                logger.info(
                    f"💥 Binance {liquidation_type}: {symbol} ${usd_impact:,.0f} "
                    f"({last_filled_qty:.3f} × ${avg_price:,.2f}) [{fill_status}]"
                )
                
        except Exception as e:
            logger.error(f"Binance 청산 이벤트 처리 실패: {e}")
    
    async def add_real_liquidation_to_bucket(self, hour_bucket: int, exchange: str, side: str, usd_value: float, count: int):
        """실제 청산 데이터를 시간 버킷에 추가합니다.
        
        Args:
            hour_bucket: 1시간 단위 타임스탬프
            exchange: 거래소 이름
            side: 'long' 또는 'short'
            usd_value: USD 청산 가치
            count: 청산 건수
        """
        try:
            # 기존 버킷 찾기
            existing_bucket = None
            for bucket_item in liquidation_stats_data[exchange]:
                if bucket_item['timestamp'] == hour_bucket:
                    existing_bucket = bucket_item
                    break
            
            if existing_bucket is None:
                # 새 버킷 생성
                new_bucket = {
                    'timestamp': hour_bucket,
                    'exchange': exchange,
                    'long_volume': usd_value if side == 'long' else 0,
                    'short_volume': usd_value if side == 'short' else 0,
                    'long_count': count if side == 'long' else 0,
                    'short_count': count if side == 'short' else 0,
                    'is_real_data': True  # 실제 데이터 표시
                }
                liquidation_stats_data[exchange].append(new_bucket)
            else:
                # 기존 버킷 업데이트
                if side == 'long':
                    existing_bucket['long_volume'] += usd_value
                    existing_bucket['long_count'] += count
                else:
                    existing_bucket['short_volume'] += usd_value
                    existing_bucket['short_count'] += count
                existing_bucket['is_real_data'] = True
            
            # 실시간 브로드캐스트
            if self.websocket_manager:
                await self.broadcast_liquidation_update({
                    'exchange': exchange,
                    'side': side,
                    'usd_value': usd_value,
                    'timestamp': hour_bucket,
                    'type': 'real_liquidation'
                })
                
        except Exception as e:
            logger.error(f"실제 청산 데이터 버킷 추가 실패: {e}")
    
    def calculate_market_volatility(self, exchange: str, current_volume: float) -> float:
        """시장 변동성을 계산합니다.
        
        Args:
            exchange: 거래소 이름
            current_volume: 현재 거래량
            
        Returns:
            변동성 지수 (1.0 = 평균, >1.0 = 높은 변동성)
        """
        history = self.liquidation_history[exchange]
        if len(history) < 2:
            return 1.0
        
        # 최근 5개 데이터 포인트의 거래량 변동성 계산
        recent_volumes = [h['volume'] for h in history[-5:]]
        if len(recent_volumes) < 2:
            return 1.0
            
        avg_volume = sum(recent_volumes) / len(recent_volumes)
        if avg_volume == 0:
            return 1.0
            
        # 표준편차 기반 변동성
        variance = sum((v - avg_volume) ** 2 for v in recent_volumes) / len(recent_volumes)
        std_dev = variance ** 0.5
        volatility = min(3.0, max(0.3, 1.0 + (std_dev / avg_volume)))
        
        return volatility
    
    def get_time_factor(self) -> Dict[str, float]:
        """시간대별 가중치를 계산합니다.

        Returns:
            시간대, 주말, 변동성 증폭 계수를 포함하는 딕셔너리.
        """
        import datetime
        now = datetime.datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0=월요일, 6=일요일
        
        # 시간대별 가중치 (UTC 기준)
        if 0 <= hour <= 6:      # 아시아 오전
            time_factor = 1.2
        elif 7 <= hour <= 14:   # 유럽 오전
            time_factor = 1.1
        elif 15 <= hour <= 22:  # 미국 오전
            time_factor = 1.3   # 가장 활발한 시간
        else:                   # 새벽
            time_factor = 0.7
            
        # 주말 감소
        weekend_factor = 0.6 if weekday >= 5 else 1.0
        
        return {
            'time_factor': time_factor,
            'weekend_factor': weekend_factor,
            'volatility_boost': 1.5 if 15 <= hour <= 22 else 1.0
        }
    
    def simulate_realistic_liquidations(self, exchange: str, volume_24h: float, 
                                      timestamp: int) -> Dict[str, float]:
        """실제 시장 특성을 반영한 청산 시뮬레이션.
        
        Args:
            exchange: 거래소 이름
            volume_24h: 24시간 거래량
            timestamp: 현재 타임스탬프
            
        Returns:
            청산 데이터 (long_volume, short_volume, long_count, short_count)
        """
        profile = EXCHANGE_LIQUIDATION_PROFILES.get(exchange, {})
        if not profile:
            return {'long_volume': 0, 'short_volume': 0, 'long_count': 0, 'short_count': 0}
        
        # 시장 변동성 계산
        volatility = self.calculate_market_volatility(exchange, volume_24h)
        
        # 시간대 가중치
        time_factors = self.get_time_factor()
        
        # 기본 청산량 계산 (거래량 * 기본 청산 비율)
        base_liquidation = volume_24h * profile['base_liquidation_rate']
        
        # 변동성, 시간대, 주말 요인 적용
        adjusted_liquidation = (
            base_liquidation * 
            (volatility ** profile['volatility_multiplier']) *
            time_factors['time_factor'] *
            time_factors['weekend_factor'] *
            profile['market_hours_factor']
        )
        
        # 무작위성 추가 (±30% 범위)
        import random
        random_factor = random.uniform(0.7, 1.3)
        total_liquidation = adjusted_liquidation * random_factor
        
        # 최소/최대 제한 적용
        total_liquidation = max(profile['min_liquidation_size'], 
                              min(profile['max_liquidation_size'], total_liquidation))
        
        # 롱/숏 분배 (시장 상황에 따라 동적 조정)
        long_bias = profile['long_bias']
        
        # 변동성이 높을 때 롱 청산 증가 (레버리지 효과)
        if volatility > 1.5:
            long_bias += 0.1  # 롱 청산 10% 증가
        elif volatility < 0.8:
            long_bias -= 0.05  # 롱 청산 5% 감소
            
        long_bias = max(0.2, min(0.8, long_bias))  # 20-80% 범위 제한
        
        # 개별 청산 이벤트 시뮬레이션
        long_volume, short_volume = 0, 0
        long_count, short_count = 0, 0
        
        # 여러 개의 개별 청산으로 분할
        num_liquidations = max(1, int(total_liquidation / 50000))  # 5만달러당 1건
        num_liquidations = min(200, num_liquidations)  # 최대 200건 (실제 청산 빈도 반영)
        
        for _ in range(num_liquidations):
            # 개별 청산 크기 (로그 정규분포)
            liquidation_size = random.lognormvariate(
                mu=10.0,  # 평균 약 $22,000 (실제 청산 규모 반영)
                sigma=1.8  # 표준편차 증가로 더 큰 변동성
            )
            liquidation_size = max(100, min(500000, liquidation_size))
            
            # 롱/숏 결정
            if random.random() < long_bias:
                long_volume += liquidation_size
                long_count += 1
            else:
                short_volume += liquidation_size
                short_count += 1
        
        # 총량 조정
        total_simulated = long_volume + short_volume
        if total_simulated > 0:
            scale_factor = total_liquidation / total_simulated
            long_volume *= scale_factor
            short_volume *= scale_factor
        
        # 히스토리 업데이트 (최근 24시간 유지)
        self.liquidation_history[exchange].append({
            'timestamp': timestamp,
            'volume': volume_24h,
            'liquidation': total_liquidation,
            'volatility': volatility
        })
        
        # 24시간 이상 된 데이터 제거
        cutoff_time = timestamp - (24 * 3600 * 1000)
        self.liquidation_history[exchange] = [
            h for h in self.liquidation_history[exchange] 
            if h['timestamp'] > cutoff_time
        ]
        
        return {
            'long_volume': long_volume,
            'short_volume': short_volume,
            'long_count': long_count,
            'short_count': short_count,
            'volatility': volatility,
            'time_factor': time_factors['time_factor']
        }
    
    async def fetch_market_multifactor_data(self, exchange: str, volume_24h: float) -> Dict[str, float]:
        """멀티팩터 모델을 위한 시장 데이터 수집.
        
        Args:
            exchange: 거래소 이름
            volume_24h: 24시간 거래량
            
        Returns:
            Dict containing OI, funding_rate, volatility, etc.
        """
        try:
            # 거래소별 API 엔드포인트
            api_endpoints = {
                'binance': {
                    'oi': 'https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT',
                    'funding': 'https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1'
                },
                'bybit': {
                    'oi': 'https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT',
                    'funding': 'https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1'
                },
                'okx': {
                    'oi': 'https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP',
                    'funding': 'https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP'
                },
                'bitmex': {
                    'oi': 'https://www.bitmex.com/api/v1/instrument?symbol=XBTUSD',
                    'funding': 'https://www.bitmex.com/api/v1/funding?symbol=XBTUSD&count=1&reverse=true'
                }
            }
            
            if exchange not in api_endpoints:
                return self._get_default_market_data(exchange, volume_24h)
            
            market_data = {}
            endpoints = api_endpoints[exchange]
            
            async with aiohttp.ClientSession() as session:
                # 미결제약정 (Open Interest) 수집
                try:
                    async with session.get(endpoints['oi'], timeout=5) as response:
                        if response.status == 200:
                            oi_data = await response.json()
                            market_data['open_interest'] = self._extract_open_interest(exchange, oi_data)
                        else:
                            market_data['open_interest'] = volume_24h * 0.5  # 추정치
                except Exception:
                    market_data['open_interest'] = volume_24h * 0.5
                
                # 펀딩 비율 (Funding Rate) 수집
                try:
                    async with session.get(endpoints['funding'], timeout=5) as response:
                        if response.status == 200:
                            funding_data = await response.json()
                            market_data['funding_rate'] = self._extract_funding_rate(exchange, funding_data)
                        else:
                            market_data['funding_rate'] = 0.0001  # 기본값 0.01%
                except Exception:
                    market_data['funding_rate'] = 0.0001
                
                # 가격 변동성 계산 (최근 거래량 기반)
                market_data['volatility'] = self.calculate_market_volatility(exchange, volume_24h)
                
                return market_data
                
        except Exception as e:
            logger.error(f"{exchange} 멀티팩터 데이터 수집 오류: {e}")
            return self._get_default_market_data(exchange, volume_24h)
    
    def _extract_open_interest(self, exchange: str, data: dict) -> float:
        """거래소별 미결제약정 데이터 추출."""
        try:
            if exchange == 'binance':
                return float(data.get('openInterest', 0))
            elif exchange == 'bybit':
                return float(data.get('result', {}).get('list', [{}])[0].get('openInterest', 0))
            elif exchange == 'okx':
                return float(data.get('data', [{}])[0].get('oi', 0))
            elif exchange == 'bitmex':
                return float(data[0].get('openInterest', 0)) if data else 0
            return 0
        except Exception:
            return 0
    
    def _extract_funding_rate(self, exchange: str, data: dict) -> float:
        """거래소별 펀딩 비율 데이터 추출."""
        try:
            if exchange == 'binance':
                return float(data[0].get('fundingRate', 0)) if data else 0
            elif exchange == 'bybit':
                return float(data.get('result', {}).get('list', [{}])[0].get('fundingRate', 0))
            elif exchange == 'okx':
                return float(data.get('data', [{}])[0].get('fundingRate', 0))
            elif exchange == 'bitmex':
                return float(data[0].get('fundingRate', 0)) if data else 0
            return 0
        except Exception:
            return 0
    
    def _get_default_market_data(self, exchange: str, volume_24h: float) -> Dict[str, float]:
        """기본 시장 데이터 (API 실패 시)."""
        return {
            'open_interest': volume_24h * 0.5,  # 거래량의 50% 추정
            'funding_rate': 0.0001,  # 0.01% 기본값
            'volatility': 1.0  # 정상 변동성
        }
    
    def calculate_multifactor_liquidation_lambda(self, exchange: str, volume: float, 
                                                market_data: Dict[str, float]) -> float:
        """멀티팩터 모델 기반 청산 강도 λ(t) 계산.
        
        λ(t) = V(t) × α × (OI(t)/(OI(t)+β)) × (1+γ|F(t)|) × (1+κσ(t))
        
        Args:
            exchange: 거래소 이름
            volume: V(t) - 현재 거래량
            market_data: OI, 펀딩비율, 변동성 등
            
        Returns:
            청산 강도 λ(t)
        """
        params = CALIBRATION_PARAMS.get(exchange, CALIBRATION_PARAMS['bybit'])
        
        # V(t) - 거래량
        V_t = volume
        
        # OI(t) - 미결제약정
        OI_t = market_data.get('open_interest', V_t * 0.5)
        
        # F(t) - 펀딩 비율
        F_t = market_data.get('funding_rate', 0.0001)
        
        # σ(t) - 변동성
        sigma_t = market_data.get('volatility', 1.0)
        
        # 파라미터 추출
        α = params['α']
        β = params['β']
        γ = params['γ']
        κ = params['κ']
        
        # λ(t) 계산
        oi_factor = OI_t / (OI_t + β)
        funding_factor = 1 + γ * abs(F_t)
        volatility_factor = 1 + κ * sigma_t
        
        lambda_t = V_t * α * oi_factor * funding_factor * volatility_factor
        
        # 디버깅 로그 (개발용)
        if exchange == 'bybit':  # Bybit 예시로 디버깅
            logger.debug(f"🔍 {exchange} λ(t) 계산: V_t={V_t/1e6:.1f}M, α={α:.6f}, "
                        f"OI_factor={oi_factor:.3f}, funding_factor={funding_factor:.3f}, "
                        f"volatility_factor={volatility_factor:.3f}, λ(t)={lambda_t:.2e}")
        
        return max(0, lambda_t)
    
    def poisson_liquidation_sampling(self, lambda_t: float, time_window: int = 3600) -> int:
        """Poisson 분포 기반 청산 이벤트 수 샘플링.
        
        Args:
            lambda_t: 청산 강도
            time_window: 시간 윈도우 (초, 기본 1시간)
            
        Returns:
            생성된 청산 이벤트 수
        """
        import random
        import math
        
        # 시간 윈도우에 맞춘 평균 이벤트 수
        mean_events = lambda_t * (time_window / 3600)  # 1시간 기준으로 정규화
        
        # Poisson 샘플링 (Knuth 알고리즘)
        if mean_events > 30:  # 큰 λ에 대해서는 정규분포 근사
            events = max(0, int(random.normalvariate(mean_events, math.sqrt(mean_events))))
        else:
            # 표준 Poisson 샘플링
            L = math.exp(-mean_events)
            k = 0
            p = 1.0
            
            while p > L:
                k += 1
                p *= random.random()
            
            events = k - 1
        
        return max(0, min(500, events))  # 0-500 범위 제한 (실제 청산 규모 반영)
    
    async def simulate_multifactor_liquidations(self, exchange: str, volume_24h: float, 
                                              timestamp: int) -> Dict[str, float]:
        """멀티팩터 + 동적 캘리브레이션 청산 시뮬레이션.
        
        Args:
            exchange: 거래소 이름
            volume_24h: 24시간 거래량
            timestamp: 현재 타임스탬프
            
        Returns:
            청산 데이터 (long_volume, short_volume, long_count, short_count)
        """
        try:
            # 1. 멀티팩터 시장 데이터 수집
            market_data = await self.fetch_market_multifactor_data(exchange, volume_24h)
            
            # 2. 청산 강도 λ(t) 계산
            lambda_t = self.calculate_multifactor_liquidation_lambda(exchange, volume_24h, market_data)
            
            # 3. Poisson 샘플링으로 이벤트 수 결정
            total_events = self.poisson_liquidation_sampling(lambda_t)
            
            if total_events == 0:
                return {'long_volume': 0, 'short_volume': 0, 'long_count': 0, 'short_count': 0}
            
            # 4. 롱/숏 분배 (펀딩비율 기반 동적 조정)
            funding_rate = market_data.get('funding_rate', 0.0001)
            base_long_ratio = EXCHANGE_LIQUIDATION_PROFILES[exchange]['long_bias']
            
            # 펀딩비율이 양수면 롱 포지션 많음 → 롱 청산 증가
            if funding_rate > 0.0002:  # 0.02% 이상
                long_ratio = min(0.8, base_long_ratio + funding_rate * 100)
            elif funding_rate < -0.0002:  # -0.02% 이하
                long_ratio = max(0.2, base_long_ratio + funding_rate * 100)
            else:
                long_ratio = base_long_ratio
            
            # 5. 개별 청산 크기 및 분배
            import random
            long_volume, short_volume = 0, 0
            long_count, short_count = 0, 0
            
            for _ in range(total_events):
                # 변동성 기반 청산 크기 조정
                volatility = market_data.get('volatility', 1.0)
                size_multiplier = 1.0 + (volatility - 1.0) * 0.5
                
                # 로그 정규분포 청산 크기 (실제 청산 규모에 맞춰 조정)
                base_size = random.lognormvariate(mu=9.5, sigma=1.2) * size_multiplier  # 평균 ~$13K
                liquidation_size = max(100, min(500000, base_size))  # $100 - $500K 범위 (실제 청산 규모)
                
                # 롱/숏 결정
                if random.random() < long_ratio:
                    long_volume += liquidation_size
                    long_count += 1
                else:
                    short_volume += liquidation_size
                    short_count += 1
            
            return {
                'long_volume': long_volume,
                'short_volume': short_volume,
                'long_count': long_count,
                'short_count': short_count,
                'lambda_t': lambda_t,
                'events': total_events,
                'funding_rate': funding_rate,
                'volatility': market_data.get('volatility', 1.0)
            }
            
        except Exception as e:
            logger.error(f"{exchange} 멀티팩터 청산 시뮬레이션 오류: {e}")
            return {'long_volume': 0, 'short_volume': 0, 'long_count': 0, 'short_count': 0}
    
    # === 24시간 통계 수집 메서드들 (REST API) ===
    
    async def fetch_binance_24h_stats(self):
        """바이낸스 선물 시장의 24시간 거래량 통계를 수집합니다.

        USDT 페어의 총 거래량(quoteVolume)을 합산하여 반환합니다.
        실제 청산 데이터도 함께 수집하여 통합 처리합니다.

        Returns:
            dict | None: 바이낸스의 24시간 통계 데이터 (exchange, total_volume_24h, timestamp)
                          또는 오류 발생 시 None.
        """
        return await self._fetch_exchange_24h_stats(
            'binance',
            "https://fapi.binance.com/fapi/v1/ticker/24hr",
            lambda ticker: 'USDT' in ticker.get('symbol', ''),
            'quoteVolume'
        )
    
    async def fetch_bybit_24h_stats(self):
        """바이비트 선물 시장의 24시간 거래량 통계를 수집합니다.

        USDT 페어의 총 거래량(turnover24h)을 합산하여 반환합니다.

        Returns:
            dict | None: 바이비트의 24시간 통계 데이터 (exchange, total_volume_24h, timestamp)
                          또는 오류 발생 시 None.
        """
        try:
            url = "https://api.bybit.com/v5/market/tickers?category=linear"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_volume = 0
                        if 'result' in data and 'list' in data['result']:
                            for ticker in data['result']['list']:
                                if 'USDT' in ticker.get('symbol', ''):
                                    total_volume += float(ticker.get('turnover24h', 0))
                        
                        return self._create_stats_response('bybit', total_volume)
                        
        except Exception as e:
            logger.error(f"바이비트 24시간 통계 오류: {e}")
            return None
    
    async def fetch_okx_24h_stats(self):
        """OKX 선물 시장의 24시간 거래량 통계를 수집합니다.

        USDT 페어의 총 거래량(volCcy24h)을 합산하여 반환합니다.
        OKX 데이터의 스케일링을 적용합니다.

        Returns:
            dict | None: OKX의 24시간 통계 데이터 (exchange, total_volume_24h, timestamp)
                          또는 오류 발생 시 None.
        """
        try:
            url = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_volume = 0
                        if 'data' in data:
                            for ticker in data['data']:
                                if 'USDT' in ticker.get('instId', ''):
                                    # OKX volCcy24h 스케일링 대폭 수정 (1/100000으로 조정)
                                    vol_ccy_24h = float(ticker.get('volCcy24h', 0))
                                    # 다른 거래소와 비슷한 수준으로 스케일링 대폭 조정
                                    total_volume += vol_ccy_24h / 100000
                        
                        stats = {
                            'exchange': 'okx',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        # logger.info(f"📊 OKX 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"OKX 24시간 통계 오류: {e}")
            return None
    
    async def fetch_bitmex_24h_stats(self):
        """BitMEX 선물 시장의 24시간 거래량 통계를 수집합니다.

        BitMEX의 `volume24h`는 컨트랙트 수량이므로, 이를 USD 거래대금으로 대략적으로 변환하여 반환합니다.

        Returns:
            dict | None: BitMEX의 24시간 통계 데이터 (exchange, total_volume_24h, timestamp)
                          또는 오류 발생 시 None.
        """
        try:
            url = "https://www.bitmex.com/api/v1/instrument/active"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_volume = 0
                        for instrument in data:
                            # BitMEX volume24h는 컨트랙트 수량이므로 현실적인 범위로 제한
                            volume_24h = float(instrument.get('volume24h', 0))
                            if volume_24h > 0:
                                # BitMEX 거래량을 현실적인 USD 거래대금으로 변환 (간소화)
                                # 대부분의 선물은 1 컨트랙트당 $1-100 정도로 가정
                                estimated_usd_volume = volume_24h * 0.001  # 컨트랙트를 USD로 대략 변환
                                total_volume += estimated_usd_volume
                        
                        stats = {
                            'exchange': 'bitmex',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        # logger.info(f"📊 BitMEX 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"BitMEX 24시간 통계 오류: {e}")
            return None
    
    async def fetch_bitget_24h_stats(self):
        """Bitget 선물 시장의 24시간 거래량 통계를 수집합니다.

        USDT 페어의 총 거래량(usdtVolume)을 합산하여 반환합니다.

        Returns:
            dict | None: Bitget의 24시간 통계 데이터 (exchange, total_volume_24h, timestamp)
                          또는 오류 발생 시 None.
        """
        try:
            url = "https://api.bitget.com/api/mix/v1/market/tickers?productType=umcbl"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_volume = 0
                        if 'data' in data:
                            for ticker in data['data']:
                                if 'USDT' in ticker.get('symbol', ''):
                                    total_volume += float(ticker.get('usdtVolume', 0))
                        
                        stats = {
                            'exchange': 'bitget',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        # logger.info(f"📊 Bitget 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"Bitget 24시간 통계 오류: {e}")
            return None
    
    async def fetch_hyperliquid_24h_stats(self):
        """Hyperliquid의 24시간 거래량 통계를 수집합니다.

        현재 Hyperliquid API의 실제 구조를 알 수 없어 임시로 고정값을 반환합니다.
        실제 API 확인 후 수정이 필요합니다.

        Returns:
            dict | None: Hyperliquid의 24시간 통계 데이터 (exchange, total_volume_24h, timestamp)
                          또는 오류 발생 시 None.
        """
        try:
            # Hyperliquid API는 다른 구조를 가질 수 있음
            # 임시로 고정값 사용 (실제 API 확인 후 수정 필요)
            total_volume = 500000000  # 500M USD
            
            stats = {
                'exchange': 'hyperliquid',
                'total_volume_24h': total_volume,
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
            
            # logger.info(f"📊 Hyperliquid 24시간 총 거래량: ${total_volume/1000000:.1f}M (임시값)")
            return stats
                        
        except Exception as e:
            logger.error(f"Hyperliquid 24시간 통계 오류: {e}")
            return None
    
    # === 데이터 저장 메서드들 ===
    
    def _create_stats_response(self, exchange: str, total_volume: float) -> dict:
        """통일된 형식의 통계 응답을 생성합니다.
        
        Args:
            exchange (str): 거래소 이름
            total_volume (float): 총 거래량
            
        Returns:
            dict: 통계 데이터 딕셔너리
        """
        return {
            'exchange': exchange,
            'total_volume_24h': total_volume,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
    
    async def _fetch_exchange_24h_stats(self, exchange: str, url: str, filter_func, volume_field: str) -> Optional[dict]:
        """거래소 24시간 통계를 가져오는 공통 메서드입니다.
        
        Args:
            exchange (str): 거래소 이름
            url (str): API URL
            filter_func: 티커 필터링 함수
            volume_field (str): 거래량 필드명
            
        Returns:
            Optional[dict]: 통계 데이터 또는 None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_volume = 0
                        for ticker in data:
                            if filter_func(ticker):
                                total_volume += float(ticker.get(volume_field, 0))
                        
                        return self._create_stats_response(exchange, total_volume)
                        
        except Exception as e:
            logger.error(f"{exchange} 24시간 통계 오류: {e}")
            return None

    async def store_24h_liquidation_stats(self, stats: dict):
        """수집된 24시간 청산 통계를 메모리에 저장하고 처리합니다.

        5분 단위의 버킷으로 데이터를 집계하며, 이전 통계와 비교하여 증가분을 계산합니다.
        계산된 증가분은 롱/숏 볼륨으로 분배되어 저장됩니다.
        새로운 데이터가 추가되면 WebSocket을 통해 클라이언트에 브로드캐스트합니다.

        Args:
            stats (dict): 수집된 단일 거래소의 24시간 통계 데이터.
                          'exchange', 'total_volume_24h', 'timestamp' 키를 포함해야 합니다.
        """
        try:
            exchange = stats['exchange']
            volume = stats['total_volume_24h']
            timestamp = stats['timestamp']
            
            # 1시간 버킷으로 저장
            hour_bucket = (timestamp // 3600000) * 3600000  # 1시간 단위
            
            # 이전 통계와 비교하여 증가분 계산
            prev_volume = self.last_24h_stats.get(exchange, 0)
            volume_diff = volume - prev_volume if prev_volume > 0 else volume * 0.01  # 첫 번째는 1%만 사용
            
            # 음수 방지
            if volume_diff < 0:
                volume_diff = volume * 0.01
            
            self.last_24h_stats[exchange] = volume
            
            # 기존 버킷 데이터 찾기 또는 새로 생성
            existing_bucket = None
            for bucket_item in liquidation_stats_data[exchange]:
                if bucket_item['timestamp'] == hour_bucket:
                    existing_bucket = bucket_item
                    break
            
            if existing_bucket is None:
                # 새 버킷 생성 - 멀티팩터 동적 캘리브레이션 모델
                liquidation_data = await self.simulate_multifactor_liquidations(
                    exchange, volume, timestamp
                )
                
                new_bucket = {
                    'timestamp': hour_bucket,
                    'exchange': exchange,
                    'long_volume': liquidation_data['long_volume'],
                    'short_volume': liquidation_data['short_volume'],
                    'long_count': liquidation_data['long_count'],
                    'short_count': liquidation_data['short_count'],
                    'is_multifactor_simulation': True,  # 멀티팩터 시뮬레이션 표시
                    'lambda_t': liquidation_data.get('lambda_t', 0),
                    'events': liquidation_data.get('events', 0),
                    'funding_rate': liquidation_data.get('funding_rate', 0.0001),
                    'volatility': liquidation_data.get('volatility', 1.0)
                }
                liquidation_stats_data[exchange].append(new_bucket)
                
                total_liquidation = liquidation_data['long_volume'] + liquidation_data['short_volume']
                logger.info(f"📈 {exchange}: 새 1시간 멀티팩터 버킷 - 청산량: ${total_liquidation/1000000:.1f}M "
                           f"(λ={liquidation_data.get('lambda_t', 0):.1e}, "
                           f"이벤트={liquidation_data.get('events', 0)}건, "
                           f"펀딩={liquidation_data.get('funding_rate', 0)*10000:.2f}bp)")
            else:
                # 기존 버킷 업데이트 - 멀티팩터 동적 캘리브레이션 모델
                liquidation_data = await self.simulate_multifactor_liquidations(
                    exchange, volume_diff, timestamp
                )
                
                existing_bucket['long_volume'] += liquidation_data['long_volume']
                existing_bucket['short_volume'] += liquidation_data['short_volume'] 
                existing_bucket['long_count'] += liquidation_data['long_count']
                existing_bucket['short_count'] += liquidation_data['short_count']
                existing_bucket['is_multifactor_simulation'] = True
                existing_bucket['lambda_t'] = liquidation_data.get('lambda_t', 0)
                existing_bucket['events'] = liquidation_data.get('events', 0)
                existing_bucket['funding_rate'] = liquidation_data.get('funding_rate', 0.0001)
                existing_bucket['volatility'] = liquidation_data.get('volatility', 1.0)
                
                total_liquidation = liquidation_data['long_volume'] + liquidation_data['short_volume']
                logger.info(f"📈 {exchange}: 1시간 멀티팩터 업데이트 - 청산량: ${total_liquidation/1000000:.1f}M "
                           f"(λ={liquidation_data.get('lambda_t', 0):.1e}, "
                           f"이벤트={liquidation_data.get('events', 0)}건, "
                           f"펀딩={liquidation_data.get('funding_rate', 0)*10000:.2f}bp)")
            
            # 실시간 데이터 브로드캐스트
            if self.websocket_manager:
                await self.broadcast_liquidation_update({
                    'exchange': exchange,
                    'volume_diff': volume_diff,
                    'timestamp': hour_bucket
                })
                
        except Exception as e:
            logger.error(f"24시간 통계 저장 오류: {e}")
    
    
    async def broadcast_liquidation_update(self, liquidation: dict):
        """새로운 청산 통계 업데이트를 WebSocket을 통해 연결된 클라이언트에 브로드캐스트합니다.

        Args:
            liquidation (dict): 브로드캐스트할 청산 데이터 업데이트 정보.
                                'exchange', 'volume_diff', 'timestamp' 키를 포함해야 합니다.
        """
        try:
            if self.websocket_manager and self.websocket_manager.active_connections:
                message = json.dumps({
                    'type': 'liquidation_stats_update',
                    'data': liquidation,
                    'exchange': liquidation['exchange']
                })
                await self.websocket_manager.broadcast(message)
        except Exception as e:
            logger.error(f"청산 통계 브로드캐스트 오류: {e}")


# 글로벌 수집기 인스턴스
liquidation_stats_collector = LiquidationStatsCollector()

def get_liquidation_data(exchange: Optional[str] = None, limit: int = 60) -> List[Dict]:
    """메모리에 저장된 최근 청산 통계 데이터를 반환합니다.

    특정 거래소의 데이터만 필터링하거나, 모든 거래소의 데이터를 합쳐서 반환할 수 있습니다.
    데이터는 타임스탬프 기준으로 정렬됩니다.

    Args:
        exchange (Optional[str], optional): 특정 거래소의 데이터를 필터링할 경우 거래소 이름.
                                            None이면 모든 거래소의 데이터를 반환합니다. 기본값은 None.
        limit (int, optional): 반환할 데이터의 최대 개수. 기본값은 60입니다.

    Returns:
        List[Dict]: 필터링되고 정렬된 청산 통계 데이터 목록.
    """
    if exchange:
        data = list(liquidation_stats_data[exchange])[-limit:]
        return sorted(data, key=lambda x: x['timestamp'])
    else:
        all_data = []
        for ex_data in liquidation_stats_data.values():
            all_data.extend(list(ex_data)[-limit:])
        return sorted(all_data, key=lambda x: x['timestamp'])[-limit:]


def get_aggregated_liquidation_data(limit: int = 60) -> List[Dict]:
    """거래소별로 집계된 청산 통계 데이터를 반환합니다.

    각 시간 버킷에 대해 모든 거래소의 롱/숏 볼륨을 합산하여 총계를 계산합니다.
    데이터는 타임스탬프 기준으로 정렬됩니다.

    Args:
        limit (int, optional): 반환할 데이터의 최대 개수. 기본값은 60입니다.

    Returns:
        List[Dict]: 집계된 청산 데이터 목록. 각 항목은 'timestamp', 'exchanges',
                    'total_long', 'total_short' 키를 포함합니다.
    """
    time_buckets: Dict[int, Dict] = {}
    
    for exchange, data_deque in liquidation_stats_data.items():
        recent_data = list(data_deque)[-limit:]
        
        for bucket in recent_data:
            timestamp = bucket.get('timestamp')
            if not timestamp:
                continue

            if timestamp not in time_buckets:
                time_buckets[timestamp] = {
                    'timestamp': timestamp,
                    'exchanges': {},
                    'total_long': 0,
                    'total_short': 0
                }

            exchange_name = bucket.get('exchange', 'unknown')
            time_buckets[timestamp]['exchanges'][exchange_name] = {
                'long_volume': bucket.get('long_volume', 0),
                'short_volume': bucket.get('short_volume', 0),
                'long_count': bucket.get('long_count', 0),
                'short_count': bucket.get('short_count', 0)
            }
            
            time_buckets[timestamp]['total_long'] += bucket.get('long_volume', 0)
            time_buckets[timestamp]['total_short'] += bucket.get('short_volume', 0)
    
    result = sorted(list(time_buckets.values()), key=lambda x: int(x.get('timestamp', 0)))
    return result[-limit:]


async def start_liquidation_stats_collection():
    """글로벌 청산 통계 수집기 인스턴스를 통해 청산 데이터 수집을 시작합니다.

    이 함수는 `liquidation_stats_collector`의 `start_collection` 메서드를 호출하여
    실제 데이터 수집 프로세스를 시작합니다.
    """
    logger.debug("start_liquidation_stats_collection() called")
    try:
        await liquidation_stats_collector.start_collection()
    except Exception as e:
        logger.error(f"Error in start_liquidation_stats_collection: {e}")
        import traceback
        traceback.print_exc()


def set_websocket_manager(manager):
    """글로벌 청산 통계 수집기 인스턴스에 WebSocket 관리자를 설정합니다.

    이 함수는 메인 애플리케이션의 WebSocket 관리자를 청산 통계 수집기에 연결하여,
    수집된 청산 데이터를 클라이언트에 브로드캐스트할 수 있도록 합니다.

    Args:
        manager: WebSocket 연결을 관리하는 객체 (예: ConnectionManager 인스턴스).
    """
    liquidation_stats_collector.set_websocket_manager(manager)
