#!/usr/bin/env python3
"""
CCXT 기반 9개 거래소 가격 수집 시스템
- 해외 7개 거래소: Binance, Bybit, OKX, Gate.io, Bitget, MEXC, Coinbase
- 국내 2개 거래소: Upbit, Bithumb (CCXT 호환)
- 실시간 가격 데이터 수집 및 정규화
"""

import asyncio
import ccxt.pro as ccxt
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from decimal import Decimal
import time
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db_manager, CoinMaster, PriceSnapshot, ExchangeRegistry, settings

logger = logging.getLogger(__name__)

class CCXTPriceCollector:
    """CCXT를 이용한 9개 거래소 가격 수집기"""
    
    def __init__(self):
        # 거래소 설정 (want.txt 기준)
        self.exchange_configs = {
            # 해외 거래소 (USD/USDT 기반)
            "binance": {"ccxt_id": "binance", "region": "global", "base_currency": "USDT"},
            "bybit": {"ccxt_id": "bybit", "region": "global", "base_currency": "USDT"},
            "okx": {"ccxt_id": "okx", "region": "global", "base_currency": "USDT"},
            "gateio": {"ccxt_id": "gateio", "region": "global", "base_currency": "USDT"},
            "bitget": {"ccxt_id": "bitget", "region": "global", "base_currency": "USDT"},
            "mexc": {"ccxt_id": "mexc", "region": "global", "base_currency": "USDT"},
            "coinbase": {"ccxt_id": "coinbasepro", "region": "global", "base_currency": "USD"},
            
            # 국내 거래소 (KRW 기반)
            "upbit": {"ccxt_id": "upbit", "region": "korea", "base_currency": "KRW"},
            "bithumb": {"ccxt_id": "bithumb", "region": "korea", "base_currency": "KRW"}
        }
        
        # 거래소 인스턴스 저장
        self.exchanges = {}
        
        # 심볼 매핑 캐시 (CoinGecko ID ↔ 거래소별 심볼)
        self.symbol_mapping = {}
        
        # 수집 통계
        self.stats = {
            "total_requests": 0,
            "successful_collections": 0,
            "failed_collections": 0,
            "exchanges_status": {},
            "last_collection_time": None
        }
        
        # 수동 심볼 매핑 (거래소별 차이 해결)
        self.manual_symbol_overrides = {
            "WAXP": {"symbol": "WAX", "exchanges": ["binance", "bybit"]},
            "PUNDIX": {"symbol": "PUNDIX", "exchanges": ["binance"]},
            "USDT": {"symbol": "USDT", "skip": ["coinbase"]},  # Coinbase는 USD 중심
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.initialize_exchanges()
        await self.load_symbol_mapping()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close_exchanges()
    
    async def initialize_exchanges(self):
        """CCXT 거래소 인스턴스 초기화"""
        logger.info("🔄 CCXT 거래소 초기화...")
        
        for exchange_name, config in self.exchange_configs.items():
            try:
                # CCXT 클래스 가져오기
                exchange_class = getattr(ccxt, config["ccxt_id"])
                
                # 거래소 설정
                exchange_config = {
                    "enableRateLimit": True,
                    "sandbox": False,  # 실제 운영 환경
                    "timeout": 30000,  # 30초 타임아웃
                }
                
                # API 키가 있는 경우 추가 (선택사항)
                api_key_attr = f"{exchange_name.upper()}_API_KEY"
                if hasattr(settings, api_key_attr):
                    exchange_config["apiKey"] = getattr(settings, api_key_attr)
                    exchange_config["secret"] = getattr(settings, f"{exchange_name.upper()}_SECRET")
                
                # 거래소 인스턴스 생성
                exchange = exchange_class(exchange_config)
                
                # 마켓 로드 (한 번만 실행)
                await exchange.load_markets()
                
                self.exchanges[exchange_name] = exchange
                self.stats["exchanges_status"][exchange_name] = "connected"
                
                logger.info(f"✅ {exchange_name}: {len(exchange.markets)} 마켓 로드됨")
                
            except Exception as e:
                logger.error(f"❌ {exchange_name} 초기화 실패: {e}")
                self.stats["exchanges_status"][exchange_name] = f"failed: {str(e)}"
        
        logger.info(f"🎉 {len(self.exchanges)}/{len(self.exchange_configs)} 거래소 초기화 완료")
    
    async def close_exchanges(self):
        """거래소 연결 종료"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close()
                logger.debug(f"🔐 {exchange_name} 연결 종료")
            except Exception as e:
                logger.warning(f"⚠️ {exchange_name} 종료 중 오류: {e}")
    
    async def load_symbol_mapping(self):
        """심볼 매핑 로드 (CoinGecko ID ↔ 거래소 심볼)"""
        logger.info("📋 심볼 매핑 로드...")
        
        with db_manager.get_session_context() as session:
            # coin_master에서 활성 코인들 조회
            active_coins = session.query(CoinMaster).filter_by(is_active=True).all()
            
            for coin in active_coins:
                coingecko_id = coin.coingecko_id
                symbol = coin.symbol
                
                # 거래소별 심볼 매핑 생성
                self.symbol_mapping[coingecko_id] = {
                    "symbol": symbol,
                    "exchange_symbols": {}
                }
                
                # 각 거래소별 매핑 확인
                for exchange_name, exchange in self.exchanges.items():
                    base_currency = self.exchange_configs[exchange_name]["base_currency"]
                    
                    # 거래쌍 후보들
                    trading_pairs = [
                        f"{symbol}/{base_currency}",
                        f"{symbol}/USDT" if base_currency != "USDT" else None,
                        f"{symbol}/USD" if base_currency != "USD" else None,
                        f"{symbol}/KRW" if base_currency == "KRW" else None
                    ]
                    
                    # 유효한 거래쌍 찾기
                    for pair in trading_pairs:
                        if pair and pair in exchange.markets:
                            self.symbol_mapping[coingecko_id]["exchange_symbols"][exchange_name] = pair
                            break
        
        # 수동 오버라이드 적용
        self.apply_manual_symbol_overrides()
        
        mapped_count = len([m for m in self.symbol_mapping.values() 
                           if m["exchange_symbols"]])
        logger.info(f"✅ {mapped_count}개 코인의 거래소 매핑 완료")
    
    def apply_manual_symbol_overrides(self):
        """수동 심볼 매핑 오버라이드 적용"""
        for override_symbol, config in self.manual_symbol_overrides.items():
            # 해당 심볼을 가진 코인 찾기
            for coingecko_id, mapping in self.symbol_mapping.items():
                if mapping["symbol"] == override_symbol:
                    if "skip" in config:
                        # 특정 거래소에서 제외
                        for skip_exchange in config["skip"]:
                            mapping["exchange_symbols"].pop(skip_exchange, None)
                    
                    if "exchanges" in config:
                        # 특정 거래소에만 적용
                        for exchange_name in list(mapping["exchange_symbols"].keys()):
                            if exchange_name not in config["exchanges"]:
                                mapping["exchange_symbols"].pop(exchange_name, None)
                    break
    
    async def fetch_ticker_for_exchange(self, exchange_name: str, symbol_pair: str) -> Optional[Dict]:
        """특정 거래소에서 티커 데이터 조회"""
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            return None
        
        try:
            ticker = await exchange.fetch_ticker(symbol_pair)
            
            # 정규화된 데이터 반환
            return {
                "exchange_id": exchange_name,
                "symbol_pair": symbol_pair,
                "last_price": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume_24h": ticker.get("quoteVolume"),  # 거래대금 기준
                "price_change_24h": ticker.get("percentage"),
                "timestamp": ticker.get("timestamp"),
                "datetime": ticker.get("datetime")
            }
            
        except Exception as e:
            logger.warning(f"⚠️ {exchange_name} {symbol_pair} 조회 실패: {e}")
            return None
    
    async def collect_prices_for_symbol(self, coingecko_id: str) -> List[Dict]:
        """특정 코인의 모든 거래소 가격 수집"""
        if coingecko_id not in self.symbol_mapping:
            return []
        
        mapping = self.symbol_mapping[coingecko_id]
        symbol = mapping["symbol"]
        exchange_symbols = mapping["exchange_symbols"]
        
        if not exchange_symbols:
            logger.debug(f"📋 {symbol}: 거래소 매핑 없음")
            return []
        
        # 모든 거래소에서 동시 수집
        tasks = []
        for exchange_name, symbol_pair in exchange_symbols.items():
            task = self.fetch_ticker_for_exchange(exchange_name, symbol_pair)
            tasks.append(task)
        
        # 결과 수집
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 성공한 결과만 필터링
        valid_results = []
        for result in results:
            if isinstance(result, dict) and result.get("last_price"):
                result["coingecko_id"] = coingecko_id
                result["symbol"] = symbol
                valid_results.append(result)
                self.stats["successful_collections"] += 1
            else:
                self.stats["failed_collections"] += 1
        
        return valid_results
    
    async def collect_all_prices(self, batch_size: int = 10) -> Dict[str, List[Dict]]:
        """모든 코인의 가격 데이터 수집"""
        logger.info("🔍 전체 코인 가격 수집 시작...")
        
        start_time = time.time()
        all_symbols = list(self.symbol_mapping.keys())
        
        # 배치 단위로 처리 (Rate Limit 고려)
        all_results = {}
        
        for i in range(0, len(all_symbols), batch_size):
            batch_symbols = all_symbols[i:i + batch_size]
            batch_tasks = []
            
            # 배치 내 모든 심볼 동시 수집
            for coingecko_id in batch_symbols:
                task = self.collect_prices_for_symbol(coingecko_id)
                batch_tasks.append((coingecko_id, task))
            
            # 배치 실행
            batch_results = await asyncio.gather(
                *[task for _, task in batch_tasks], 
                return_exceptions=True
            )
            
            # 결과 저장
            for j, (coingecko_id, _) in enumerate(batch_tasks):
                if j < len(batch_results) and isinstance(batch_results[j], list):
                    all_results[coingecko_id] = batch_results[j]
                else:
                    all_results[coingecko_id] = []
            
            # 배치 간 대기 (Rate Limit 방지)
            if i + batch_size < len(all_symbols):
                await asyncio.sleep(1)
            
            logger.info(f"📦 배치 {i//batch_size + 1}/{(len(all_symbols)-1)//batch_size + 1} 완료")
        
        elapsed_time = time.time() - start_time
        total_prices = sum(len(prices) for prices in all_results.values())
        
        self.stats["last_collection_time"] = datetime.now()
        
        logger.info(f"✅ 가격 수집 완료: {total_prices}개 가격 데이터 ({elapsed_time:.1f}초)")
        return all_results
    
    def save_price_snapshots(self, price_data: Dict[str, List[Dict]]) -> int:
        """가격 데이터를 DB에 저장"""
        logger.info("💾 가격 데이터 저장...")
        
        saved_count = 0
        current_time = datetime.now(timezone.utc)
        
        with db_manager.get_session_context() as session:
            for coingecko_id, prices in price_data.items():
                for price_info in prices:
                    try:
                        # PriceSnapshot 객체 생성
                        snapshot = PriceSnapshot(
                            coingecko_id=coingecko_id,
                            exchange_id=price_info["exchange_id"],
                            symbol=price_info["symbol"],
                            trading_pair=price_info["symbol_pair"],
                            price=Decimal(str(price_info["last_price"])),
                            volume_24h=Decimal(str(price_info.get("volume_24h", 0))) if price_info.get("volume_24h") else None,
                            price_change_24h=Decimal(str(price_info.get("price_change_24h", 0))) if price_info.get("price_change_24h") else None,
                            collected_at=current_time
                        )
                        
                        session.add(snapshot)
                        saved_count += 1
                        
                    except Exception as e:
                        logger.error(f"❌ {coingecko_id} {price_info.get('exchange_id')} 저장 실패: {e}")
            
            session.commit()
        
        logger.info(f"✅ {saved_count}개 가격 데이터 저장 완료")
        return saved_count
    
    async def run_collection_cycle(self, save_to_db: bool = True) -> Dict[str, Any]:
        """한 번의 수집 사이클 실행"""
        logger.info("🚀 가격 수집 사이클 시작")
        
        try:
            # 1. 가격 데이터 수집
            price_data = await self.collect_all_prices()
            
            # 2. DB 저장
            saved_count = 0
            if save_to_db:
                saved_count = self.save_price_snapshots(price_data)
            
            # 3. 통계 업데이트
            total_prices = sum(len(prices) for prices in price_data.values())
            self.stats["total_requests"] += len(price_data)
            
            # 4. 결과 반환
            result = {
                "success": True,
                "total_symbols": len(price_data),
                "total_prices": total_prices,
                "saved_count": saved_count,
                "failed_symbols": len([k for k, v in price_data.items() if not v]),
                "exchange_status": self.get_exchange_status()
            }
            
            logger.info(f"🎉 수집 사이클 완료: {total_prices}개 가격, {saved_count}개 저장")
            return result
            
        except Exception as e:
            logger.error(f"❌ 수집 사이클 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def get_exchange_status(self) -> Dict[str, Any]:
        """거래소별 상태 정보 반환"""
        status = {}
        for exchange_name, exchange in self.exchanges.items():
            try:
                status[exchange_name] = {
                    "connected": True,
                    "markets_count": len(exchange.markets) if hasattr(exchange, 'markets') else 0,
                    "region": self.exchange_configs[exchange_name]["region"],
                    "base_currency": self.exchange_configs[exchange_name]["base_currency"]
                }
            except:
                status[exchange_name] = {"connected": False}
        
        return status
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """수집 통계 반환"""
        return {
            "stats": self.stats.copy(),
            "symbol_mapping_count": len(self.symbol_mapping),
            "active_exchanges": len(self.exchanges),
            "exchange_status": self.get_exchange_status()
        }
    
    def print_collection_summary(self):
        """수집 요약 출력"""
        stats = self.get_collection_stats()
        
        logger.info("\n📊 CCXT 가격 수집 통계:")
        logger.info(f"   🔄 총 요청: {stats['stats']['total_requests']}")
        logger.info(f"   ✅ 성공: {stats['stats']['successful_collections']}")
        logger.info(f"   ❌ 실패: {stats['stats']['failed_collections']}")
        logger.info(f"   📋 매핑된 심볼: {stats['symbol_mapping_count']}개")
        logger.info(f"   🌐 활성 거래소: {stats['active_exchanges']}/9개")
        
        if stats['stats']['last_collection_time']:
            logger.info(f"   ⏰ 마지막 수집: {stats['stats']['last_collection_time'].strftime('%Y-%m-%d %H:%M:%S')}")

async def main():
    """메인 실행 함수"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        logger.info("🚀 CCXT 9개 거래소 가격 수집 시작")
        
        async with CCXTPriceCollector() as collector:
            # 한 번의 수집 사이클 실행
            result = await collector.run_collection_cycle()
            
            # 통계 출력
            collector.print_collection_summary()
            
            if result["success"]:
                logger.info(f"🎉 수집 완료: {result['total_prices']}개 가격 수집, {result['saved_count']}개 저장")
                return True
            else:
                logger.error(f"❌ 수집 실패: {result.get('error')}")
                return False
                
    except Exception as e:
        logger.error(f"❌ CCXT 수집기 실행 실패: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())