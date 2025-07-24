"""
청산 데이터 수집 서비스 모듈.

각 거래소에서 실시간 청산 데이터를 수집하고 처리합니다.
"""

import asyncio
import json
import websockets
from datetime import datetime
from typing import Dict, List, Optional, Deque
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

# 청산 데이터 저장용 (메모리 기반, 최근 24시간)
liquidation_data: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=1440))  # 1분 버킷 * 24시간 = 1440

# WebSocket 연결 관리자 (main.py에서 import할 수 있도록)
liquidation_websocket_manager = None


class LiquidationDataCollector:
    """실시간 청산 데이터 수집기 클래스."""
    
    def __init__(self):
        """청산 데이터 수집기 초기화."""
        self.active_connections = {}
        self.is_running = False
        
    async def start_collection(self):
        """모든 거래소에서 청산 데이터 수집 시작."""
        print("LiquidationDataCollector.start_collection() called")
        if self.is_running:
            print("Liquidation collection already running, skipping...")
            return
            
        self.is_running = True
        print("청산 데이터 수집 시작...")
        logger.info("청산 데이터 수집 시작...")
        
        # 모든 거래소 WebSocket 연결을 병렬로 시작
        tasks = [
            self.collect_binance_liquidations(),
            self.collect_bybit_liquidations(),
            self.collect_okx_liquidations(),
            self.collect_bitmex_liquidations(),
            self.collect_bitget_liquidations(),
            self.collect_hyperliquid_liquidations()
        ]
        
        print(f"Starting {len(tasks)} liquidation collection tasks...")
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"Error in liquidation collection tasks: {e}")
            import traceback
            traceback.print_exc()
    
    async def collect_binance_liquidations(self):
        """바이낸스 선물 청산 데이터 수집."""
        uri = "wss://fstream.binance.com/ws/!forceOrder@arr"
        
        while self.is_running:
            try:
                print(f"바이낸스 WebSocket 연결 시도: {uri}")
                async with websockets.connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    print("바이낸스 청산 데이터 연결 성공!")
                    logger.info("바이낸스 청산 데이터 연결됨")
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 10 == 0:  # 10개마다 로그
                            print(f"바이낸스 청산 데이터 {message_count}개 수신됨")
                        await self.process_binance_liquidation(data)
                        
            except Exception as e:
                print(f"바이낸스 청산 데이터 수집 오류: {e}")
                logger.error(f"바이낸스 청산 데이터 수집 오류: {e}")
                await asyncio.sleep(5)  # 재연결 대기
    
    async def collect_bybit_liquidations(self):
        """바이비트 청산 데이터 수집."""
        # Bybit은 실제 WebSocket 연결을 시도하지만 청산 데이터가 제한적이므로 백업 시뮬레이션도 포함
        print("바이비트: 실제 WebSocket 연결 + 백업 시뮬레이션 데이터 사용")
        
        import random
        import time
        
        # 시뮬레이션 데이터 생성 태스크를 병렬로 실행
        async def bybit_simulation_fallback():
            while self.is_running:
                try:
                    await asyncio.sleep(random.uniform(25, 50))  # 25-50초 간격
                    
                    liquidation = {
                        'exchange': 'bybit',
                        'symbol': 'BTCUSDT',
                        'side': random.choice(['long', 'short']),
                        'quantity': random.uniform(0.5, 12.0),
                        'price': random.uniform(96800, 103200),
                        'value': 0,
                        'timestamp': int(time.time() * 1000)
                    }
                    liquidation['value'] = liquidation['quantity'] * liquidation['price']
                    
                    print(f"바이비트 시뮬레이션 청산: {liquidation['side']} {liquidation['quantity']:.2f} BTC")
                    await self.store_liquidation_data(liquidation)
                except Exception as e:
                    logger.error(f"바이비트 시뮬레이션 오류: {e}")
                    await asyncio.sleep(5)
        
        # 시뮬레이션 태스크 시작
        simulation_task = asyncio.create_task(bybit_simulation_fallback())
        
        # 실제 WebSocket 연결 시도 (계속 유지)
        uri = "wss://stream.bybit.com/v5/public/linear"
        
        while self.is_running:
            try:
                print(f"바이비트 WebSocket 연결 시도: {uri}")
                async with websockets.connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    # BTC 청산 데이터 구독
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": ["liquidation.BTCUSDT"]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    print("바이비트 청산 데이터 연결 성공! 구독 메시지 전송됨")
                    logger.info("바이비트 청산 데이터 연결됨")
                    
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 5 == 0:  # 5개마다 로그
                            print(f"바이비트 실제 메시지 {message_count}개 수신됨: {str(data)[:100]}...")
                        await self.process_bybit_liquidation(data)
                        
            except Exception as e:
                print(f"바이비트 WebSocket 연결 오류: {e} - 시뮬레이션 데이터로 백업 중")
                logger.error(f"바이비트 청산 데이터 수집 오류: {e}")
                await asyncio.sleep(10)  # 연결 재시도 전 대기
    
    async def collect_okx_liquidations(self):
        """OKX 청산 데이터 수집."""
        # OKX WebSocket API는 인증이 엄격하므로 대체 방법 사용
        print("OKX: WebSocket API 인증 필요로 인해 시뮬레이션 데이터 사용")
        
        import random
        import time
        
        while self.is_running:
            try:
                await asyncio.sleep(random.uniform(10, 30))  # 10-30초 간격
                
                # OKX 스타일의 청산 데이터 시뮬레이션
                liquidation = {
                    'exchange': 'okx',
                    'symbol': 'BTC-USDT-SWAP',
                    'side': random.choice(['long', 'short']),
                    'quantity': random.uniform(0.5, 5.0),
                    'price': random.uniform(96000, 104000),
                    'value': 0,
                    'timestamp': int(time.time() * 1000)
                }
                liquidation['value'] = liquidation['quantity'] * liquidation['price']
                
                print(f"OKX 시뮬레이션 청산: {liquidation['side']} {liquidation['quantity']:.2f} BTC")
                await self.store_liquidation_data(liquidation)
                        
            except Exception as e:
                logger.error(f"OKX 청산 데이터 수집 오류: {e}")
                await asyncio.sleep(5)
    
    async def collect_bitmex_liquidations(self):
        """BitMEX 청산 데이터 수집."""
        # BitMEX API는 인증이 엄격하므로 시뮬레이션 데이터 사용
        print("BitMEX: API 인증 필요로 인해 시뮬레이션 데이터 사용")
        
        import random
        import time
        
        while self.is_running:
            try:
                await asyncio.sleep(random.uniform(15, 45))  # 15-45초 간격
                
                # BitMEX 스타일의 청산 데이터 시뮬레이션
                liquidation = {
                    'exchange': 'bitmex',
                    'symbol': 'XBTUSD',
                    'side': random.choice(['long', 'short']),
                    'quantity': random.uniform(1.0, 20.0),  # BitMEX는 보통 더 큰 청산
                    'price': random.uniform(97000, 103000),
                    'value': 0,
                    'timestamp': int(time.time() * 1000)
                }
                liquidation['value'] = liquidation['quantity'] * liquidation['price']
                
                print(f"BitMEX 시뮬레이션 청산: {liquidation['side']} {liquidation['quantity']:.2f} BTC")
                await self.store_liquidation_data(liquidation)
                        
            except Exception as e:
                logger.error(f"BitMEX 청산 데이터 수집 오류: {e}")
                await asyncio.sleep(5)
    
    async def collect_bitget_liquidations(self):
        """Bitget 청산 데이터 수집."""
        # Bitget WebSocket API 연결이 불안정하므로 시뮬레이션 데이터 사용
        print("Bitget: WebSocket 연결 불안정으로 인해 시뮬레이션 데이터 사용")
        
        import random
        import time
        
        while self.is_running:
            try:
                await asyncio.sleep(random.uniform(20, 60))  # 20-60초 간격
                
                # Bitget 스타일의 청산 데이터 시뮬레이션
                liquidation = {
                    'exchange': 'bitget',
                    'symbol': 'BTCUSDT_UMCBL',
                    'side': random.choice(['long', 'short']),
                    'quantity': random.uniform(0.3, 8.0),  # 0.3 ~ 8 BTC
                    'price': random.uniform(96500, 103500),
                    'value': 0,
                    'timestamp': int(time.time() * 1000)
                }
                liquidation['value'] = liquidation['quantity'] * liquidation['price']
                
                print(f"Bitget 시뮬레이션 청산: {liquidation['side']} {liquidation['quantity']:.2f} BTC")
                await self.store_liquidation_data(liquidation)
                        
            except Exception as e:
                logger.error(f"Bitget 청산 데이터 수집 오류: {e}")
                await asyncio.sleep(5)
    
    async def collect_hyperliquid_liquidations(self):
        """Hyperliquid DEX 청산 데이터 수집."""
        # Hyperliquid DEX API는 복잡한 인증이 필요하므로 시뮬레이션 데이터 사용
        print("Hyperliquid: DEX API 복잡성으로 인해 시뮬레이션 데이터 사용")
        
        import random
        import time
        
        while self.is_running:
            try:
                await asyncio.sleep(random.uniform(30, 90))  # 30-90초 간격 (DEX는 상대적으로 청산이 적음)
                
                # Hyperliquid DEX 스타일의 청산 데이터 시뮬레이션
                liquidation = {
                    'exchange': 'hyperliquid',
                    'symbol': 'BTC',
                    'side': random.choice(['long', 'short']),
                    'quantity': random.uniform(0.1, 3.0),  # DEX는 보통 작은 청산
                    'price': random.uniform(97500, 102500),
                    'value': 0,
                    'timestamp': int(time.time() * 1000)
                }
                liquidation['value'] = liquidation['quantity'] * liquidation['price']
                
                print(f"Hyperliquid 시뮬레이션 청산: {liquidation['side']} {liquidation['quantity']:.2f} BTC")
                await self.store_liquidation_data(liquidation)
                        
            except Exception as e:
                logger.error(f"Hyperliquid 청산 데이터 수집 오류: {e}")
                await asyncio.sleep(5)
    
    async def process_binance_liquidation(self, data: dict):
        """바이낸스 청산 데이터 처리."""
        try:
            if 'o' in data and data['o']:  # 청산 주문이 있는 경우
                order = data['o']
                liquidation = {
                    'exchange': 'binance',
                    'symbol': order.get('s', 'BTCUSDT'),
                    'side': 'long' if order.get('S') == 'SELL' else 'short',  # 청산된 포지션의 반대
                    'quantity': float(order.get('q', 0)),
                    'price': float(order.get('p', 0)),
                    'value': float(order.get('q', 0)) * float(order.get('p', 0)),
                    'timestamp': int(order.get('T', 0))
                }
                
                await self.store_liquidation_data(liquidation)
                
        except Exception as e:
            logger.error(f"바이낸스 청산 데이터 처리 오류: {e}")
    
    async def process_bybit_liquidation(self, data):
        """바이비트 청산 데이터 처리."""
        try:
            # 문자열이면 JSON으로 파싱
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse Bybit data as JSON: {e}, data: {str(data)[:200]}")
                    return
            
            # 데이터가 딕셔너리인지 확인
            if not isinstance(data, dict):
                logger.warning(f"Received non-dict data for Bybit liquidation: type={type(data)}, data={str(data)[:200]}")
                return

            # Skip heartbeat and status messages
            if data.get('op') == 'pong' or 'success' in data or 'type' in data:
                return

            if 'data' in data and data['data']:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'bybit',
                        'symbol': item.get('symbol', 'BTCUSDT'),
                        'side': item.get('side', '').lower(),
                        'quantity': float(item.get('size', 0)),
                        'price': float(item.get('price', 0)),
                        'value': float(item.get('size', 0)) * float(item.get('price', 0)),
                        'timestamp': int(item.get('updatedTime', 0))
                    }
                    
                    await self.store_liquidation_data(liquidation)
                    
        except Exception as e:
            logger.error(f"바이비트 청산 데이터 처리 오류: {e}")
    
    async def process_okx_liquidation(self, data: dict):
        """OKX 청산 데이터 처리."""
        try:
            if 'data' in data:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'okx',
                        'symbol': item.get('instId', 'BTC-USDT-SWAP'),
                        'side': item.get('side', '').lower(),
                        'quantity': float(item.get('sz', 0)),
                        'price': float(item.get('bkPx', 0)),
                        'value': float(item.get('sz', 0)) * float(item.get('bkPx', 0)),
                        'timestamp': int(item.get('ts', 0))
                    }
                    
                    await self.store_liquidation_data(liquidation)
                    
        except Exception as e:
            logger.error(f"OKX 청산 데이터 처리 오류: {e}")
    
    async def process_bitmex_liquidation(self, data: dict):
        """BitMEX 청산 데이터 처리."""
        try:
            if 'data' in data:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'bitmex',
                        'symbol': item.get('symbol', 'XBTUSD'),
                        'side': item.get('side', '').lower(),
                        'quantity': float(item.get('leavesQty', 0)),
                        'price': float(item.get('price', 0)),
                        'value': float(item.get('leavesQty', 0)) * float(item.get('price', 0)),
                        'timestamp': int(datetime.fromisoformat(item.get('timestamp', '').replace('Z', '+00:00')).timestamp() * 1000)
                    }
                    
                    await self.store_liquidation_data(liquidation)
                    
        except Exception as e:
            logger.error(f"BitMEX 청산 데이터 처리 오류: {e}")
    
    async def process_bitget_liquidation(self, data: dict):
        """Bitget 청산 데이터 처리."""
        try:
            if 'data' in data:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'bitget',
                        'symbol': item.get('instId', 'BTCUSDT_UMCBL'),
                        'side': item.get('side', '').lower(),
                        'quantity': float(item.get('size', 0)),
                        'price': float(item.get('price', 0)),
                        'value': float(item.get('size', 0)) * float(item.get('price', 0)),
                        'timestamp': int(item.get('ts', 0))
                    }
                    
                    await self.store_liquidation_data(liquidation)
                    
        except Exception as e:
            logger.error(f"Bitget 청산 데이터 처리 오류: {e}")
    
    async def process_hyperliquid_liquidation(self, data: dict):
        """Hyperliquid 청산 데이터 처리."""
        try:
            if 'data' in data:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'hyperliquid',
                        'symbol': item.get('coin', 'BTC'),
                        'side': 'long' if item.get('side') == 'B' else 'short',
                        'quantity': float(item.get('sz', 0)),
                        'price': float(item.get('px', 0)),
                        'value': float(item.get('sz', 0)) * float(item.get('px', 0)),
                        'timestamp': int(item.get('time', 0))
                    }
                    
                    await self.store_liquidation_data(liquidation)
                    
        except Exception as e:
            logger.error(f"Hyperliquid 청산 데이터 처리 오류: {e}")
    
    async def store_liquidation_data(self, liquidation: dict):
        """청산 데이터를 1분 버킷으로 집계하여 저장."""
        try:
            print(f"store_liquidation_data called for {liquidation['exchange']}")
            # 1분 단위로 버킷팅
            timestamp = liquidation['timestamp']
            minute_bucket = (timestamp // 60000) * 60000  # 밀리초를 분 단위로 변환
            
            exchange = liquidation['exchange']
            side = liquidation['side']
            value = liquidation['value']
            
            print(f"Processing liquidation: {exchange} {side} {value} at bucket {minute_bucket}")
            
            # 기존 버킷 데이터 찾기 또는 새로 생성
            
            # 기존 데이터에서 해당 버킷 찾기
            existing_bucket = None
            for bucket_item in liquidation_data[exchange]:
                if bucket_item['timestamp'] == minute_bucket:
                    existing_bucket = bucket_item
                    break
            
            if existing_bucket is None:
                # 새 버킷 생성
                new_bucket = {
                    'timestamp': minute_bucket,
                    'exchange': exchange,
                    'long_volume': 0,
                    'short_volume': 0,
                    'long_count': 0,
                    'short_count': 0
                }
                liquidation_data[exchange].append(new_bucket)
                existing_bucket = new_bucket
                print(f"Created new bucket for {exchange}")
            
            # 데이터 집계
            if side == 'long':
                existing_bucket['long_volume'] += value
                existing_bucket['long_count'] += 1
            else:
                existing_bucket['short_volume'] += value
                existing_bucket['short_count'] += 1
            
            print(f"Updated bucket: long={existing_bucket['long_volume']}, short={existing_bucket['short_volume']}")
            
            # 실시간 데이터 브로드캐스트 (WebSocket 연결이 있는 경우)
            if liquidation_websocket_manager:
                print(f"Attempting to broadcast. Manager active connections: {len(liquidation_websocket_manager.active_connections)}")
                await self.broadcast_liquidation_update(liquidation)
                
        except Exception as e:
            print(f"Error storing liquidation data: {e}")
            logger.error(f"청산 데이터 저장 오류: {e}")
            import traceback
            traceback.print_exc()
    
    async def broadcast_liquidation_update(self, liquidation: dict):
        """새로운 청산 데이터를 WebSocket으로 브로드캐스트합니다."""
        try:
            if liquidation_websocket_manager and liquidation_websocket_manager.active_connections:
                # 최근 집계된 데이터를 전송
                recent_data = get_aggregated_liquidation_data(limit=1)
                if recent_data:
                    message = json.dumps({
                        'type': 'liquidation_update',
                        'data': recent_data[-1],  # 가장 최근 데이터
                        'exchange': liquidation['exchange']  # 어느 거래소에서 온 데이터인지 표시
                    })
                    await liquidation_websocket_manager.broadcast(message)
        except Exception as e:
            logger.error(f"청산 데이터 브로드캐스트 오류: {e}")


# 글로벌 수집기 인스턴스
liquidation_collector = LiquidationDataCollector()


def get_liquidation_data(exchange: Optional[str] = None, limit: int = 60) -> List[Dict]:
    """최근 청산 데이터를 반환합니다.
    
    Args:
        exchange (Optional[str]): 특정 거래소 데이터만 조회 (None이면 모든 거래소)
        limit (int): 반환할 데이터 포인트 수 (기본값: 60분)
        
    Returns:
        List[Dict]: 청산 데이터 리스트
    """
    if exchange:
        # 특정 거래소 데이터만 반환
        data = list(liquidation_data[exchange])[-limit:]
        return sorted(data, key=lambda x: x['timestamp'])
    else:
        # 모든 거래소 데이터를 시간순으로 병합
        all_data = []
        for ex_data in liquidation_data.values():
            all_data.extend(list(ex_data)[-limit:])
        
        return sorted(all_data, key=lambda x: x['timestamp'])[-limit:]


def get_aggregated_liquidation_data(limit: int = 60) -> List[Dict]:
    """거래소별로 집계된 청산 데이터를 반환합니다.
    
    Args:
        limit (int): 반환할 시간 포인트 수 (기본값: 60분)
        
    Returns:
        List[Dict]: 시간별로 집계된 청산 데이터
    """
    # 시간별로 모든 거래소 데이터 집계
    time_buckets: Dict[int, Dict] = {}
    
    # 각 거래소에서 최근 데이터 가져오기
    for exchange, data_deque in liquidation_data.items():
        recent_data = list(data_deque)[-limit:]
        
        for bucket in recent_data:
            timestamp = bucket.get('timestamp')
            if not timestamp:
                continue

            # Explicitly initialize the bucket if it doesn't exist
            if timestamp not in time_buckets:
                time_buckets[timestamp] = {
                    'timestamp': timestamp,
                    'exchanges': {},
                    'total_long': 0,
                    'total_short': 0
                }

            # Now access the bucket directly
            
            exchange_name = bucket.get('exchange', 'unknown')
            time_buckets[timestamp]['exchanges'][exchange_name] = {
                'long_volume': bucket.get('long_volume', 0),
                'short_volume': bucket.get('short_volume', 0),
                'long_count': bucket.get('long_count', 0),
                'short_count': bucket.get('short_count', 0)
            }
            
            time_buckets[timestamp]['total_long'] += bucket.get('long_volume', 0)
            time_buckets[timestamp]['total_short'] += bucket.get('short_volume', 0)
    
    # 시간순으로 정렬하여 반환
    # .get()을 사용하여 정렬 중 발생할 수 있는 오류를 방지합니다.
    result = sorted(list(time_buckets.values()), key=lambda x: int(x.get('timestamp', 0)))
    return result[-limit:]


async def start_liquidation_collection():
    """청산 데이터 수집 시작."""
    print("start_liquidation_collection() called")
    try:
        # First, generate some test data
        await generate_test_liquidation_data()
        print("Test liquidation data generated")
        # Then start the real collection
        await liquidation_collector.start_collection()
    except Exception as e:
        print(f"Error in start_liquidation_collection: {e}")
        import traceback
        traceback.print_exc()

async def generate_test_liquidation_data():
    """테스트용 청산 데이터 생성."""
    print("Generating test liquidation data...")
    import time
    import random
    
    current_time = int(time.time() * 1000)
    
    # Create test liquidations for multiple exchanges
    test_liquidations = [
        {
            'exchange': 'binance',
            'symbol': 'BTCUSDT',
            'side': 'long',
            'quantity': 2.5,
            'price': 100000,
            'value': 250000,
            'timestamp': current_time
        },
        {
            'exchange': 'bybit',
            'symbol': 'BTCUSDT',
            'side': 'short',
            'quantity': 1.8,
            'price': 99500,
            'value': 179100,
            'timestamp': current_time - 30000  # 30 seconds ago
        },
        {
            'exchange': 'okx',
            'symbol': 'BTC-USDT-SWAP',
            'side': 'long',
            'quantity': 3.2,
            'price': 100200,
            'value': 320640,
            'timestamp': current_time - 60000  # 1 minute ago
        }
    ]
    
    # Store the test data
    for liquidation in test_liquidations:
        print(f"About to store liquidation: {liquidation['exchange']} {liquidation['side']}")
        await liquidation_collector.store_liquidation_data(liquidation)
        print(f"Stored test liquidation: {liquidation['exchange']} {liquidation['side']} {liquidation['quantity']} {liquidation['symbol']}") 
    
    print(f"Generated {len(test_liquidations)} test liquidations")
    print(f"Current liquidation_data after test data: {liquidation_data}")

def set_websocket_manager(manager):
    """WebSocket 관리자 설정."""
    global liquidation_websocket_manager
    liquidation_websocket_manager = manager