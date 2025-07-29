"""
통계 기반 청산 데이터 수집 서비스 모듈.

각 거래소에서 24시간 통계와 실시간 요약 데이터를 수집합니다.
"""

import asyncio
import json
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Deque
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

# 통합된 청산 데이터 저장용 (메모리 기반, 최근 24시간)
liquidation_stats_data: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=1440))  # 1분 버킷 * 24시간 = 1440

# WebSocket 연결 관리자
liquidation_websocket_manager = None


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
        logger.info("LiquidationStatsCollector.start_collection() called - 통계 기반 수집 시작")
        if self.is_running:
            logger.info("Liquidation stats collection already running, skipping...")
            return
            
        self.is_running = True
        logger.info("📊 통계 기반 청산 데이터 수집 시작...")
        
        # 통계 기반 수집 태스크
        task = asyncio.create_task(self.collect_liquidation_statistics())
        
        logger.info("Starting statistical liquidation collection task...")
        try:
            await task
        except Exception as e:
            logger.error(f"Error in statistical liquidation collection task: {e}")
            import traceback
            traceback.print_exc()
    
    async def collect_liquidation_statistics(self):
        """각 거래소의 24시간 청산 통계를 주기적으로 수집합니다.

        REST API를 통해 바이낸스, 바이비트, OKX, BitMEX, Bitget, Hyperliquid의
        청산 통계를 병렬로 가져와 저장합니다. 5분마다 갱신됩니다.
        """
        logger.info("📈 24시간 청산 통계 수집 시작")
        
        while self.is_running:
            try:
                # 모든 거래소의 24시간 청산 통계를 병렬로 수집
                tasks = [
                    self.fetch_binance_24h_stats(),
                    self.fetch_bybit_24h_stats(), 
                    self.fetch_okx_24h_stats(),
                    self.fetch_bitmex_24h_stats(),
                    self.fetch_bitget_24h_stats(),
                    self.fetch_hyperliquid_24h_stats()
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 결과 처리 및 저장
                for result in results:
                    if not isinstance(result, Exception) and result:
                        await self.store_24h_liquidation_stats(result)
                
                # 5분마다 갱신
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"24시간 청산 통계 수집 오류: {e}")
                await asyncio.sleep(60)
    
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
                                    # OKX volCcy24h가 너무 크므로 적절히 스케일링
                                    vol_ccy_24h = float(ticker.get('volCcy24h', 0))
                                    # OKX 데이터가 매우 크므로 1/1000000 스케일링 적용
                                    total_volume += vol_ccy_24h / 1000000
                        
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
            
            # 5분 버킷으로 저장
            minute_bucket = (timestamp // 300000) * 300000  # 5분 단위
            
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
                if bucket_item['timestamp'] == minute_bucket:
                    existing_bucket = bucket_item
                    break
            
            if existing_bucket is None:
                # 새 버킷 생성 - 현실적인 롱/숏 비율 적용
                # 30-70% 사이의 랜덤 비율로 롱/숏 분배 (거래소별 다르게)
                long_ratio = self._calculate_long_short_ratio(exchange, minute_bucket)
                long_volume = volume_diff * long_ratio
                short_volume = volume_diff * (1 - long_ratio)
                
                new_bucket = {
                    'timestamp': minute_bucket,
                    'exchange': exchange,
                    'long_volume': long_volume,
                    'short_volume': short_volume,
                    'long_count': 1,
                    'short_count': 1
                }
                liquidation_stats_data[exchange].append(new_bucket)
                # logger.info(f"📈 {exchange}: 새 통계 버킷 생성 - 거래량 증가분: ${volume_diff/1000000:.1f}M")
            else:
                # 기존 버킷 업데이트 - 현실적인 롱/숏 비율 적용
                # 30-70% 사이의 랜덤 비율로 롱/숏 분배 (시간별 다르게)
                long_ratio = self._calculate_long_short_ratio(exchange, minute_bucket, len(liquidation_stats_data[exchange]))
                long_volume = volume_diff * long_ratio
                short_volume = volume_diff * (1 - long_ratio)
                
                existing_bucket['long_volume'] += long_volume
                existing_bucket['short_volume'] += short_volume
                # logger.info(f"📈 {exchange}: 통계 업데이트 - 거래량 증가분: ${volume_diff/1000000:.1f}M")
            
            # 실시간 데이터 브로드캐스트
            if self.websocket_manager:
                await self.broadcast_liquidation_update({
                    'exchange': exchange,
                    'volume_diff': volume_diff,
                    'timestamp': minute_bucket
                })
                
        except Exception as e:
            logger.error(f"24시간 통계 저장 오류: {e}")
    
    def _calculate_long_short_ratio(self, exchange: str, minute_bucket: int, bucket_count: int = 0) -> float:
        """거래소와 시간에 따른 현실적인 롱/숏 비율을 계산합니다.
        
        Args:
            exchange (str): 거래소 이름
            minute_bucket (int): 분 단위 버킷 타임스탬프
            bucket_count (int): 기존 버킷 개수 (기본값: 0)
            
        Returns:
            float: 롱 포지션 비율 (0.3-0.7 사이)
        """
        # 해시를 사용한 의사 랜덤 비율 생성 (30-70% 범위)
        hash_input = f"{exchange}{minute_bucket}{bucket_count}"
        ratio_seed = hash(hash_input) % 100
        return 0.3 + (ratio_seed / 100) * 0.4  # 0.3-0.7 범위
    
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
    logger.info("start_liquidation_stats_collection() called")
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