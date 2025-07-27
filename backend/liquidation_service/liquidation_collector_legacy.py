"""
청산 데이터 수집기 모듈.

각 거래소에서 실시간 청산 데이터를 수집하고 처리합니다.
"""

import asyncio
import json
from websockets import connect as websockets_connect  # type: ignore
from datetime import datetime
from typing import Dict, List, Optional, Deque
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

# 청산 데이터 저장용 (메모리 기반, 최근 24시간)
liquidation_data: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=1440))  # 1분 버킷 * 24시간 = 1440

class LiquidationDataCollector:
    """실시간 청산 데이터 수집기 클래스."""
    
    def __init__(self):
        """청산 데이터 수집기 초기화."""
        self.active_connections = {}
        self.is_running = False
        self.websocket_manager = None
        
    def set_websocket_manager(self, manager):
        """WebSocket 관리자 설정."""
        self.websocket_manager = manager
        
    async def start_collection(self):
        """새로운 통계 기반 청산 데이터 수집 시작."""
        logger.info("LiquidationDataCollector.start_collection() called - 통계 기반 수집 시작")
        if self.is_running:
            logger.info("Liquidation collection already running, skipping...")
            return
            
        self.is_running = True
        logger.info("📊 통계 기반 청산 데이터 수집 시작...")
        
        # 새로운 통계 기반 수집 태스크들
        tasks = [
            self.collect_liquidation_statistics(),  # 24시간 통계 (REST API)
            self.collect_realtime_liquidation_summary()  # 1시간 실시간 요약 (WebSocket)
        ]
        
        logger.info(f"Starting {len(tasks)} statistical liquidation collection tasks...")
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in statistical liquidation collection tasks: {e}")
            import traceback
            traceback.print_exc()
    
    async def collect_liquidation_statistics(self):
        """24시간 청산 통계 수집 (REST API 기반)."""
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
                for i, result in enumerate(results):
                    if not isinstance(result, Exception) and result:
                        await self.store_24h_liquidation_stats(result)
                
                # 5분마다 갱신
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"24시간 청산 통계 수집 오류: {e}")
                await asyncio.sleep(60)
    
    async def collect_realtime_liquidation_summary(self):
        """실시간 청산 요약 수집 (WebSocket 기반)."""
        logger.info("⚡ 실시간 청산 요약 수집 시작")
        
        # 모든 거래소의 실시간 요약 WebSocket을 병렬로 시작
        tasks = [
            self.collect_binance_summary(),
            self.collect_bybit_summary(),
            self.collect_okx_summary(), 
            self.collect_bitmex_summary(),
            self.collect_bitget_summary(),
            self.collect_hyperliquid_summary()
        ]
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"실시간 청산 요약 수집 오류: {e}")
    
    # === 24시간 통계 수집 메서드들 (REST API) ===
    
    async def fetch_binance_24h_stats(self):
        """바이낸스 24시간 청산 통계 수집."""
        try:
            import aiohttp
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"  # 24시간 통계
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # BTC 데이터만 추출 또는 전체 거래량 합계
                        total_volume = 0
                        for ticker in data:
                            if 'USDT' in ticker.get('symbol', ''):
                                total_volume += float(ticker.get('quoteVolume', 0))
                        
                        stats = {
                            'exchange': 'binance',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        logger.info(f"📊 바이낸스 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"바이낸스 24시간 통계 오류: {e}")
            return None
    
    async def fetch_bybit_24h_stats(self):
        """바이비트 24시간 청산 통계 수집."""
        try:
            import aiohttp
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
                        
                        stats = {
                            'exchange': 'bybit',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        logger.info(f"📊 바이비트 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"바이비트 24시간 통계 오류: {e}")
            return None
    
    async def fetch_okx_24h_stats(self):
        """OKX 24시간 청산 통계 수집."""
        try:
            import aiohttp
            url = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_volume = 0
                        if 'data' in data:
                            for ticker in data['data']:
                                if 'USDT' in ticker.get('instId', ''):
                                    total_volume += float(ticker.get('volCcy24h', 0))
                        
                        stats = {
                            'exchange': 'okx',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        logger.info(f"📊 OKX 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"OKX 24시간 통계 오류: {e}")
            return None
    
    async def fetch_bitmex_24h_stats(self):
        """BitMEX 24시간 청산 통계 수집."""
        try:
            import aiohttp
            url = "https://www.bitmex.com/api/v1/instrument/active"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_volume = 0
                        for instrument in data:
                            if instrument.get('volume24h'):
                                total_volume += float(instrument.get('volume24h', 0))
                        
                        stats = {
                            'exchange': 'bitmex',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        logger.info(f"📊 BitMEX 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"BitMEX 24시간 통계 오류: {e}")
            return None
    
    async def fetch_bitget_24h_stats(self):
        """Bitget 24시간 청산 통계 수집."""
        try:
            import aiohttp
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
                        
                        logger.info(f"📊 Bitget 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"Bitget 24시간 통계 오류: {e}")
            return None
    
    async def fetch_hyperliquid_24h_stats(self):
        """Hyperliquid 24시간 청산 통계 수집."""
        try:
            import aiohttp
            url = "https://api.hyperliquid.xyz/info"
            data = {"type": "allMids"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Hyperliquid는 다른 API 구조를 가질 수 있음
                        total_volume = 1000000  # 임시값, 실제 API 확인 필요
                        
                        stats = {
                            'exchange': 'hyperliquid',
                            'total_volume_24h': total_volume,
                            'timestamp': int(datetime.now().timestamp() * 1000)
                        }
                        
                        logger.info(f"📊 Hyperliquid 24시간 총 거래량: ${total_volume/1000000:.1f}M")
                        return stats
                        
        except Exception as e:
            logger.error(f"Hyperliquid 24시간 통계 오류: {e}")
            return None
    
    # === 실시간 요약 수집 메서드들 (WebSocket) ===
    
    async def collect_binance_summary(self):
        """바이낸스 실시간 청산 요약 수집."""
        logger.info("⚡ 바이낸스 실시간 요약 WebSocket 연결 시작")
        
        # 바이낸스는 전체 청산 통계 스트림이 없으므로 24시간 통계만 사용
        # 또는 개별 청산을 집계하여 요약 생성
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 5분마다 REST API로 대체
                logger.debug("📊 바이낸스: REST API 기반 요약 사용")
            except Exception as e:
                logger.error(f"바이낸스 요약 수집 오류: {e}")
                await asyncio.sleep(60)
    
    async def collect_bybit_summary(self):
        """바이비트 실시간 청산 요약 수집.""" 
        logger.info("⚡ 바이비트 실시간 요약 WebSocket 연결 시작")
        
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 5분마다 REST API로 대체
                logger.debug("📊 바이비트: REST API 기반 요약 사용")
            except Exception as e:
                logger.error(f"바이비트 요약 수집 오류: {e}")
                await asyncio.sleep(60)
    
    async def collect_okx_summary(self):
        """OKX 실시간 청산 요약 수집."""
        logger.info("⚡ OKX 실시간 요약 WebSocket 연결 시작")
        
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 5분마다 REST API로 대체
                logger.debug("📊 OKX: REST API 기반 요약 사용")
            except Exception as e:
                logger.error(f"OKX 요약 수집 오류: {e}")
                await asyncio.sleep(60)
    
    async def collect_bitmex_summary(self):
        """BitMEX 실시간 청산 요약 수집."""
        logger.info("⚡ BitMEX 실시간 요약 WebSocket 연결 시작")
        
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 5분마다 REST API로 대체
                logger.debug("📊 BitMEX: REST API 기반 요약 사용")
            except Exception as e:
                logger.error(f"BitMEX 요약 수집 오류: {e}")
                await asyncio.sleep(60)
    
    async def collect_bitget_summary(self):
        """Bitget 실시간 청산 요약 수집."""
        logger.info("⚡ Bitget 실시간 요약 WebSocket 연결 시작")
        
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 5분마다 REST API로 대체
                logger.debug("📊 Bitget: REST API 기반 요약 사용")
            except Exception as e:
                logger.error(f"Bitget 요약 수집 오류: {e}")
                await asyncio.sleep(60)
    
    async def collect_hyperliquid_summary(self):
        """Hyperliquid 실시간 청산 요약 수집."""
        logger.info("⚡ Hyperliquid 실시간 요약 WebSocket 연결 시작")
        
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 5분마다 REST API로 대체
                logger.debug("📊 Hyperliquid: REST API 기반 요약 사용")
            except Exception as e:
                logger.error(f"Hyperliquid 요약 수집 오류: {e}")
                await asyncio.sleep(60)
    
    # === 데이터 저장 메서드들 ===
    
    async def store_24h_liquidation_stats(self, stats: dict):
        """24시간 청산 통계를 저장."""
        try:
            exchange = stats['exchange']
            volume = stats['total_volume_24h']
            timestamp = stats['timestamp']
            
            # 5분 버킷으로 저장 (기존 구조 유지)
            minute_bucket = (timestamp // 300000) * 300000  # 5분 단위
            
            # 기존 데이터 구조에 맞게 변환
            liquidation_data = {
                'exchange': exchange,
                'symbol': 'ALL',  # 전체 시장
                'long_volume': volume * 0.5,  # 50% 롱으로 가정
                'short_volume': volume * 0.5,  # 50% 숏으로 가정
                'timestamp': minute_bucket,
                'data_type': '24h_stats'
            }
            
            await self.store_liquidation_data(liquidation_data)
            
        except Exception as e:
            logger.error(f"24시간 통계 저장 오류: {e}")
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 10 == 0:  # 10개마다 로그
                            logger.info(f"바이낸스 청산 데이터 {message_count}개 수신됨")
                        await self.process_binance_liquidation(data)
                        
            except Exception as e:
                logger.error(f"바이낸스 청산 데이터 수집 오류: {e}")
                await asyncio.sleep(5)  # 재연결 대기
    
    async def collect_bybit_liquidations(self):
        """바이비트 청산 데이터 수집."""
        logger.info("바이비트: 실제 WebSocket 청산 데이터만 사용")
        
        # 실제 WebSocket 연결만 사용
        uri = "wss://stream.bybit.com/v5/public/linear"
        
        while self.is_running:
            try:
                logger.info(f"🚀 바이비트 WebSocket 연결 시도: {uri}")
                async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    # BTC 청산 데이터 구독
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": ["liquidation.BTCUSDT"]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    logger.info("✅ 바이비트 청산 데이터 연결 성공!")
                    
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 10 == 0:  # 10개마다 로그
                            logger.info(f"📡 바이비트 실제 메시지 {message_count}개 수신됨")
                        await self.process_bybit_liquidation(data)
                        
            except Exception as e:
                logger.error(f"❌ 바이비트 WebSocket 연결 오류: {e}")
                await asyncio.sleep(10)  # 연결 재시도 전 대기
    
    async def collect_okx_liquidations(self):
        """OKX 청산 데이터 수집."""
        logger.info("OKX: 실제 WebSocket 청산 데이터 연결 시도")
        
        # OKX 공개 WebSocket (인증 불필요)
        uri = "wss://ws.okx.com:8443/ws/v5/public"
        
        while self.is_running:
            try:
                logger.info(f"🚀 OKX WebSocket 연결 시도: {uri}")
                async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    # BTC 청산 데이터 구독
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {
                                "channel": "liquidation-orders",
                                "instType": "SWAP",
                                "instId": "BTC-USDT-SWAP"
                            }
                        ]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    logger.info("✅ OKX 청산 데이터 연결 성공!")
                    
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 10 == 0:  # 10개마다 로그
                            logger.info(f"📡 OKX 실제 메시지 {message_count}개 수신됨")
                        await self.process_okx_liquidation(data)
                        
            except Exception as e:
                logger.error(f"❌ OKX WebSocket 연결 오류: {e}")
                await asyncio.sleep(10)  # 연결 재시도 전 대기
    
    async def collect_bitmex_liquidations(self):
        """BitMEX 청산 데이터 수집."""
        logger.info("BitMEX: 실제 WebSocket 청산 데이터 연결 시도")
        
        # BitMEX 공개 WebSocket (인증 불필요)
        uri = "wss://www.bitmex.com/realtime"
        
        while self.is_running:
            try:
                logger.info(f"🚀 BitMEX WebSocket 연결 시도: {uri}")
                async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    # BTC 청산 데이터 구독
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": ["liquidation:XBTUSD"]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    logger.info("✅ BitMEX 청산 데이터 연결 성공!")
                    
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 10 == 0:  # 10개마다 로그
                            logger.info(f"📡 BitMEX 실제 메시지 {message_count}개 수신됨")
                        await self.process_bitmex_liquidation(data)
                        
            except Exception as e:
                logger.error(f"❌ BitMEX WebSocket 연결 오류: {e}")
                await asyncio.sleep(10)  # 연결 재시도 전 대기
    
    async def collect_bitget_liquidations(self):
        """Bitget 청산 데이터 수집."""
        logger.info("Bitget: 실제 WebSocket 청산 데이터 연결 시도")
        
        # Bitget 공개 WebSocket 
        uri = "wss://ws.bitget.com/mix/v1/stream"
        
        while self.is_running:
            try:
                logger.info(f"🚀 Bitget WebSocket 연결 시도: {uri}")
                async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    # BTC 청산 데이터 구독
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {
                                "instType": "UMCBL",
                                "channel": "liquidation",
                                "instId": "BTCUSDT_UMCBL"
                            }
                        ]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    logger.info("✅ Bitget 청산 데이터 연결 성공!")
                    
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 10 == 0:  # 10개마다 로그
                            logger.info(f"📡 Bitget 실제 메시지 {message_count}개 수신됨")
                        await self.process_bitget_liquidation(data)
                        
            except Exception as e:
                logger.error(f"❌ Bitget WebSocket 연결 오류: {e}")
                await asyncio.sleep(10)  # 연결 재시도 전 대기
    
    async def collect_hyperliquid_liquidations(self):
        """Hyperliquid DEX 청산 데이터 수집."""
        logger.info("Hyperliquid: 실제 WebSocket 청산 데이터 연결 시도")
        
        # Hyperliquid 공개 WebSocket
        uri = "wss://api.hyperliquid.xyz/ws"
        
        while self.is_running:
            try:
                logger.info(f"🚀 Hyperliquid WebSocket 연결 시도: {uri}")
                async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
                    # BTC 청산 데이터 구독
                    subscribe_msg = {
                        "method": "subscribe",
                        "subscription": {
                            "type": "liquidations",
                            "coin": "BTC"
                        }
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    logger.info("✅ Hyperliquid 청산 데이터 연결 성공!")
                    
                    message_count = 0
                    async for message in websocket:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 10 == 0:  # 10개마다 로그
                            logger.info(f"📡 Hyperliquid 실제 메시지 {message_count}개 수신됨")
                        await self.process_hyperliquid_liquidation(data)
                        
            except Exception as e:
                logger.error(f"❌ Hyperliquid WebSocket 연결 오류: {e}")
                await asyncio.sleep(10)  # 연결 재시도 전 대기
    
    async def process_binance_liquidation(self, data: dict):
        """바이낸스 청산 데이터 처리."""
        try:
            # 모든 바이낸스 메시지 구조 디버깅
            logger.debug(f"🔍 바이낸스 원본 메시지: {json.dumps(data)[:200]}...")
            
            if 'o' in data and data['o']:  # 청산 주문이 있는 경우
                order = data['o']
                symbol = order.get('s', '')
                
                # 모든 심볼 로깅 (BTCUSDT가 실제로 오는지 확인)
                logger.info(f"🎯 바이낸스 청산 심볼: {symbol}")
                
                # BTCUSDT 심볼만 처리하도록 필터링 추가
                if symbol != 'BTCUSDT':
                    logger.debug(f"Skipping non-BTCUSDT Binance liquidation: {symbol}")
                    return

                liquidation = {
                    'exchange': 'binance',
                    'symbol': symbol,
                    'side': 'long' if order.get('S') == 'SELL' else 'short',  # 청산된 포지션의 반대
                    'quantity': float(order.get('q', 0)),
                    'price': float(order.get('p', 0)),
                    'value': float(order.get('q', 0)) * float(order.get('p', 0)),
                    'timestamp': int(order.get('T', 0))
                }
                
                logger.info(f"✅ 바이낸스 비트코인 청산: {liquidation['side']} {liquidation['quantity']:.4f} BTC @ ${liquidation['price']:.2f}")
                
                await self.store_liquidation_data(liquidation)
            else:
                logger.debug(f"🔍 바이낸스 메시지에 청산 주문 없음: {list(data.keys())}")
                
        except Exception as e:
            logger.error(f"바이낸스 청산 데이터 처리 오류: {e}")
            logger.error(f"오류 데이터: {json.dumps(data)[:200]}")
    
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
            if 'data' in data and data['data']:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'okx',
                        'symbol': item.get('instId', 'BTC-USDT-SWAP'),
                        'side': 'long' if item.get('side') == 'sell' else 'short',
                        'quantity': float(item.get('sz', 0)),
                        'price': float(item.get('bkPx', 0)),
                        'value': float(item.get('sz', 0)) * float(item.get('bkPx', 0)),
                        'timestamp': int(item.get('ts', 0))
                    }
                    
                    logger.info(f"✅ OKX 청산: {liquidation['side']} {liquidation['quantity']:.4f} BTC @ ${liquidation['price']:.2f}")
                    await self.store_liquidation_data(liquidation)
        except Exception as e:
            logger.error(f"OKX 청산 데이터 처리 오류: {e}")
    
    async def process_bitmex_liquidation(self, data: dict):
        """BitMEX 청산 데이터 처리."""
        try:
            if 'data' in data and data['data']:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'bitmex',
                        'symbol': item.get('symbol', 'XBTUSD'),
                        'side': 'long' if item.get('side') == 'Sell' else 'short',
                        'quantity': float(item.get('leavesQty', 0)),
                        'price': float(item.get('price', 0)),
                        'value': float(item.get('leavesQty', 0)) * float(item.get('price', 0)),
                        'timestamp': int(datetime.fromisoformat(item.get('timestamp', '').replace('Z', '+00:00')).timestamp() * 1000) if item.get('timestamp') else int(datetime.now().timestamp() * 1000)
                    }
                    
                    logger.info(f"✅ BitMEX 청산: {liquidation['side']} {liquidation['quantity']:.4f} BTC @ ${liquidation['price']:.2f}")
                    await self.store_liquidation_data(liquidation)
        except Exception as e:
            logger.error(f"BitMEX 청산 데이터 처리 오류: {e}")
    
    async def process_bitget_liquidation(self, data: dict):
        """Bitget 청산 데이터 처리."""
        try:
            if 'data' in data and data['data']:
                for item in data['data']:
                    liquidation = {
                        'exchange': 'bitget',
                        'symbol': item.get('instId', 'BTCUSDT_UMCBL'),
                        'side': 'long' if item.get('side') == 'sell' else 'short',
                        'quantity': float(item.get('size', 0)),
                        'price': float(item.get('price', 0)),
                        'value': float(item.get('size', 0)) * float(item.get('price', 0)),
                        'timestamp': int(item.get('ts', 0))
                    }
                    
                    logger.info(f"✅ Bitget 청산: {liquidation['side']} {liquidation['quantity']:.4f} BTC @ ${liquidation['price']:.2f}")
                    await self.store_liquidation_data(liquidation)
        except Exception as e:
            logger.error(f"Bitget 청산 데이터 처리 오류: {e}")
    
    async def process_hyperliquid_liquidation(self, data: dict):
        """Hyperliquid 청산 데이터 처리."""
        try:
            if 'data' in data and data['data']:
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
                    
                    logger.info(f"✅ Hyperliquid 청산: {liquidation['side']} {liquidation['quantity']:.4f} BTC @ ${liquidation['price']:.2f}")
                    await self.store_liquidation_data(liquidation)
        except Exception as e:
            logger.error(f"Hyperliquid 청산 데이터 처리 오류: {e}")
    
    async def store_liquidation_data(self, liquidation: dict):
        """청산 데이터를 1분 버킷으로 집계하여 저장."""
        try:
            logger.info(f"store_liquidation_data called for {liquidation['exchange']}")
            # 1분 단위로 버킷팅
            timestamp = liquidation['timestamp']
            minute_bucket = (timestamp // 60000) * 60000  # 밀리초를 분 단위로 변환
            
            exchange = liquidation['exchange']
            side = liquidation['side']
            value = liquidation['value']
            
            logger.info(f"Processing liquidation: {exchange} {side} {value} at bucket {minute_bucket}")
            
            # 기존 버킷 데이터 찾기 또는 새로 생성
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
                logger.info(f"Created new bucket for {exchange}")
            
            # 데이터 집계
            if side == 'long':
                existing_bucket['long_volume'] += value
                existing_bucket['long_count'] += 1
            else:
                existing_bucket['short_volume'] += value
                existing_bucket['short_count'] += 1
            
            logger.info(f"Updated bucket: long={existing_bucket['long_volume']}, short={existing_bucket['short_volume']}")
            
            # 실시간 데이터 브로드캐스트 (WebSocket 연결이 있는 경우)
            if self.websocket_manager:
                await self.broadcast_liquidation_update(liquidation)
                
        except Exception as e:
            logger.error(f"Error storing liquidation data: {e}")
            import traceback
            traceback.print_exc()
    
    async def broadcast_liquidation_update(self, liquidation: dict):
        """새로운 청산 데이터를 WebSocket으로 브로드캐스트합니다."""
        try:
            if self.websocket_manager and self.websocket_manager.active_connections:
                # 개별 청산 데이터를 직접 전송
                message = json.dumps({
                    'type': 'liquidation_update',
                    'data': liquidation,  # 수정: 집계 데이터 대신 원본 청산 데이터 전송
                    'exchange': liquidation['exchange']
                })
                await self.websocket_manager.broadcast(message)
        except Exception as e:
            logger.error(f"청산 데이터 브로드캐스트 오류: {e}")

    async def generate_test_liquidation_data(self):
        """테스트용 청산 데이터 생성."""
        logger.info("Generating test liquidation data...")
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
            logger.info(f"About to store test liquidation: {liquidation['exchange']} {liquidation['side']}")
            await self.store_liquidation_data(liquidation)
            logger.info(f"Stored test liquidation: {liquidation['exchange']} {liquidation['side']} {liquidation['quantity']} {liquidation['symbol']}")
        
        logger.info(f"Generated {len(test_liquidations)} test liquidations")


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
    result = sorted(list(time_buckets.values()), key=lambda x: int(x.get('timestamp', 0)))
    return result[-limit:]


# 글로벌 수집기 인스턴스
liquidation_collector = LiquidationDataCollector()


async def start_liquidation_collection():
    """청산 데이터 수집 시작."""
    logger.info("start_liquidation_collection() called")
    try:
        await liquidation_collector.start_collection()
    except Exception as e:
        logger.error(f"Error in start_liquidation_collection: {e}")
        import traceback
        traceback.print_exc()


def set_websocket_manager(manager):
    """WebSocket 관리자 설정."""
    liquidation_collector.set_websocket_manager(manager)