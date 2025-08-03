#!/usr/bin/env python3
"""
김치프리미엄 계산기
- 국내(업비트, 빗썸) vs 해외(7개 거래소) 가격 차이 계산
- 환율 반영하여 실시간 김치프리미엄 산출
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import statistics

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db_manager, PriceSnapshot, KimchiPremium, ExchangeRate, CoinMaster

logger = logging.getLogger(__name__)

class KimchiPremiumCalculator:
    """김치프리미엄 계산기"""
    
    def __init__(self):
        self.session = None
        
        # 거래소 분류
        self.korean_exchanges = ["upbit", "bithumb"]
        self.global_exchanges = ["binance", "bybit", "okx", "gateio", "bitget", "mexc", "coinbase"]
        
        # 환율 API 설정
        self.exchange_rate_api = "https://api.exchangerate-api.com/v4/latest/USD"
        self.backup_rate_api = "https://api.fixer.io/latest?base=USD"
        
        # 계산 통계
        self.stats = {
            "processed_coins": 0,
            "successful_calculations": 0,
            "failed_calculations": 0,
            "missing_korean_prices": 0,
            "missing_global_prices": 0,
            "invalid_premiums": 0
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "KimchiPremium-Calculator/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def fetch_usd_krw_rate(self) -> Optional[Decimal]:
        """USD/KRW 환율 조회"""
        try:
            # 메인 API 시도
            async with self.session.get(self.exchange_rate_api) as response:
                if response.status == 200:
                    data = await response.json()
                    if "rates" in data and "KRW" in data["rates"]:
                        rate = Decimal(str(data["rates"]["KRW"]))
                        logger.debug(f"💱 환율 조회 성공: 1 USD = {rate} KRW")
                        return rate
            
            # 백업 API 시도
            async with self.session.get(self.backup_rate_api) as response:
                if response.status == 200:
                    data = await response.json()
                    if "rates" in data and "KRW" in data["rates"]:
                        rate = Decimal(str(data["rates"]["KRW"]))
                        logger.debug(f"💱 백업 환율 조회 성공: 1 USD = {rate} KRW")
                        return rate
            
            logger.warning("⚠️ 환율 API 조회 실패, DB에서 최근 환율 사용")
            return self.get_latest_exchange_rate_from_db()
            
        except Exception as e:
            logger.error(f"❌ 환율 조회 실패: {e}")
            return self.get_latest_exchange_rate_from_db()
    
    def get_latest_exchange_rate_from_db(self) -> Optional[Decimal]:
        """DB에서 최근 환율 조회"""
        try:
            with db_manager.get_session_context() as session:
                latest_rate = session.query(ExchangeRate).filter_by(
                    currency_pair="USD_KRW"
                ).order_by(ExchangeRate.updated_at.desc()).first()
                
                if latest_rate:
                    return latest_rate.rate
                
                # 기본값 사용 (대략적인 환율)
                logger.warning("⚠️ DB에 환율 정보 없음, 기본값 사용: 1300")
                return Decimal("1300")
                
        except Exception as e:
            logger.error(f"❌ DB 환율 조회 실패: {e}")
            return Decimal("1300")  # 기본값
    
    def save_exchange_rate(self, rate: Decimal) -> bool:
        """환율을 DB에 저장"""
        try:
            with db_manager.get_session_context() as session:
                # 기존 레코드 확인
                existing = session.query(ExchangeRate).filter_by(
                    currency_pair="USD_KRW"
                ).first()
                
                if existing:
                    existing.rate = rate
                    existing.updated_at = datetime.now()
                    existing.source = "exchangerate-api.com"
                else:
                    new_rate = ExchangeRate(
                        currency_pair="USD_KRW",
                        rate=rate,
                        source="exchangerate-api.com"
                    )
                    session.add(new_rate)
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ 환율 저장 실패: {e}")
            return False
    
    def get_recent_prices(self, minutes: int = 5) -> Dict[str, List[Dict]]:
        """최근 N분 내 가격 데이터 조회"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        with db_manager.get_session_context() as session:
            # 최근 가격 데이터 조회
            recent_prices = session.query(PriceSnapshot).filter(
                PriceSnapshot.collected_at >= cutoff_time,
                PriceSnapshot.price.isnot(None)
            ).all()
            
            # 코인별로 그룹화
            prices_by_coin = {}
            for price in recent_prices:
                coingecko_id = price.coingecko_id
                if coingecko_id not in prices_by_coin:
                    prices_by_coin[coingecko_id] = []
                
                prices_by_coin[coingecko_id].append({
                    "exchange_id": price.exchange_id,
                    "price": price.price,
                    "trading_pair": price.trading_pair,
                    "volume_24h": price.volume_24h,
                    "collected_at": price.collected_at
                })
            
            return prices_by_coin
    
    def calculate_average_prices(self, prices: List[Dict], exchanges: List[str]) -> Optional[Decimal]:
        """특정 거래소들의 평균 가격 계산"""
        filtered_prices = [
            price for price in prices 
            if price["exchange_id"] in exchanges and price["price"] > 0
        ]
        
        if not filtered_prices:
            return None
        
        # 단순 평균 (향후 거래량 가중평균으로 개선 가능)
        price_values = [float(price["price"]) for price in filtered_prices]
        avg_price = statistics.mean(price_values)
        
        return Decimal(str(avg_price))
    
    def calculate_kimchi_premium(self, korean_price: Decimal, global_price: Decimal, 
                               usd_krw_rate: Decimal) -> Decimal:
        """김치프리미엄 계산"""
        try:
            # 해외 가격을 KRW로 환산
            global_price_krw = global_price * usd_krw_rate
            
            # 김치프리미엄 = (국내가격 / 해외가격KRW - 1) * 100
            premium = (korean_price / global_price_krw - 1) * 100
            
            # 소수점 4자리까지 반올림
            return premium.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            
        except Exception as e:
            logger.error(f"❌ 김치프리미엄 계산 실패: {e}")
            return Decimal("0")
    
    async def calculate_all_premiums(self, price_window_minutes: int = 5) -> List[Dict]:
        """모든 코인의 김치프리미엄 계산"""
        logger.info("🧮 김치프리미엄 계산 시작...")
        
        # 1. 환율 조회
        usd_krw_rate = await self.fetch_usd_krw_rate()
        if not usd_krw_rate:
            logger.error("❌ 환율 조회 실패, 계산 중단")
            return []
        
        # 환율 저장
        self.save_exchange_rate(usd_krw_rate)
        
        # 2. 최근 가격 데이터 조회
        prices_by_coin = self.get_recent_prices(price_window_minutes)
        
        if not prices_by_coin:
            logger.warning("⚠️ 최근 가격 데이터 없음")
            return []
        
        # 3. 각 코인별 김치프리미엄 계산
        premium_results = []
        
        for coingecko_id, prices in prices_by_coin.items():
            try:
                self.stats["processed_coins"] += 1
                
                # 국내 평균가 계산
                korean_avg_price = self.calculate_average_prices(prices, self.korean_exchanges)
                if not korean_avg_price:
                    self.stats["missing_korean_prices"] += 1
                    logger.debug(f"📋 {coingecko_id}: 국내 가격 없음")
                    continue
                
                # 해외 평균가 계산
                global_avg_price = self.calculate_average_prices(prices, self.global_exchanges)
                if not global_avg_price:
                    self.stats["missing_global_prices"] += 1
                    logger.debug(f"📋 {coingecko_id}: 해외 가격 없음")
                    continue
                
                # 개별 거래소 가격 추출
                upbit_price = None
                bithumb_price = None
                
                for price in prices:
                    if price["exchange_id"] == "upbit":
                        upbit_price = price["price"]
                    elif price["exchange_id"] == "bithumb":
                        bithumb_price = price["price"]
                
                # 김치프리미엄 계산
                kimchi_premium = self.calculate_kimchi_premium(
                    korean_avg_price, global_avg_price, usd_krw_rate
                )
                
                # 비정상적인 프리미엄 필터링 (-50% ~ +50% 범위)
                if abs(kimchi_premium) > 50:
                    self.stats["invalid_premiums"] += 1
                    logger.debug(f"📋 {coingecko_id}: 비정상 프리미엄 {kimchi_premium}%")
                    continue
                
                # 결과 데이터 구성
                premium_data = {
                    "coingecko_id": coingecko_id,
                    "upbit_price": upbit_price,
                    "bithumb_price": bithumb_price,
                    "korean_avg_price": korean_avg_price,
                    "global_avg_price": global_avg_price,
                    "global_avg_price_krw": global_avg_price * usd_krw_rate,
                    "usd_krw_rate": usd_krw_rate,
                    "kimchi_premium": kimchi_premium,
                    "calculated_at": datetime.now(timezone.utc)
                }
                
                premium_results.append(premium_data)
                self.stats["successful_calculations"] += 1
                
                logger.debug(f"✅ {coingecko_id}: {kimchi_premium:.2f}%")
                
            except Exception as e:
                logger.error(f"❌ {coingecko_id} 프리미엄 계산 실패: {e}")
                self.stats["failed_calculations"] += 1
        
        logger.info(f"🧮 김치프리미엄 계산 완료: {len(premium_results)}개")
        return premium_results
    
    def save_kimchi_premiums(self, premium_data: List[Dict]) -> int:
        """김치프리미엄을 DB에 저장"""
        logger.info("💾 김치프리미엄 데이터 저장...")
        
        saved_count = 0
        
        with db_manager.get_session_context() as session:
            # 코인 심볼 정보 조회 (매핑용)
            coin_symbols = {}
            coins = session.query(CoinMaster).filter_by(is_active=True).all()
            for coin in coins:
                coin_symbols[coin.coingecko_id] = coin.symbol
            
            for premium_info in premium_data:
                try:
                    # 심볼 추가
                    symbol = coin_symbols.get(premium_info["coingecko_id"], "UNKNOWN")
                    
                    # KimchiPremium 객체 생성
                    kimchi_record = KimchiPremium(
                        coingecko_id=premium_info["coingecko_id"],
                        symbol=symbol,
                        upbit_price=premium_info.get("upbit_price"),
                        bithumb_price=premium_info.get("bithumb_price"),
                        korean_avg_price=premium_info["korean_avg_price"],
                        global_avg_price=premium_info["global_avg_price"],
                        global_avg_price_krw=premium_info["global_avg_price_krw"],
                        usd_krw_rate=premium_info["usd_krw_rate"],
                        kimchi_premium=premium_info["kimchi_premium"],
                        calculated_at=premium_info["calculated_at"]
                    )
                    
                    session.add(kimchi_record)
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ {premium_info.get('coingecko_id')} 저장 실패: {e}")
            
            session.commit()
        
        logger.info(f"✅ {saved_count}개 김치프리미엄 저장 완료")
        return saved_count
    
    async def run_calculation_cycle(self, save_to_db: bool = True) -> Dict[str, Any]:
        """김치프리미엄 계산 사이클 실행"""
        logger.info("🚀 김치프리미엄 계산 사이클 시작")
        
        try:
            # 1. 김치프리미엄 계산
            premium_data = await self.calculate_all_premiums()
            
            # 2. DB 저장
            saved_count = 0
            if save_to_db and premium_data:
                saved_count = self.save_kimchi_premiums(premium_data)
            
            # 3. 결과 반환
            result = {
                "success": True,
                "total_calculations": len(premium_data),
                "saved_count": saved_count,
                "stats": self.stats.copy()
            }
            
            logger.info(f"🎉 계산 사이클 완료: {len(premium_data)}개 계산, {saved_count}개 저장")
            return result
            
        except Exception as e:
            logger.error(f"❌ 계산 사이클 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def get_calculation_stats(self) -> Dict[str, Any]:
        """계산 통계 반환"""
        return self.stats.copy()
    
    def print_calculation_summary(self):
        """계산 요약 출력"""
        logger.info("\n📊 김치프리미엄 계산 통계:")
        logger.info(f"   🔄 처리된 코인: {self.stats['processed_coins']}")
        logger.info(f"   ✅ 성공한 계산: {self.stats['successful_calculations']}")
        logger.info(f"   ❌ 실패한 계산: {self.stats['failed_calculations']}")
        logger.info(f"   🇰🇷 국내가격 누락: {self.stats['missing_korean_prices']}")
        logger.info(f"   🌐 해외가격 누락: {self.stats['missing_global_prices']}")
        logger.info(f"   ⚠️ 비정상 프리미엄: {self.stats['invalid_premiums']}")

async def main():
    """메인 실행 함수"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        logger.info("🚀 김치프리미엄 계산기 시작")
        
        async with KimchiPremiumCalculator() as calculator:
            # 계산 사이클 실행
            result = await calculator.run_calculation_cycle()
            
            # 통계 출력
            calculator.print_calculation_summary()
            
            if result["success"]:
                logger.info(f"🎉 계산 완료: {result['total_calculations']}개 계산")
                return True
            else:
                logger.error(f"❌ 계산 실패: {result.get('error')}")
                return False
                
    except Exception as e:
        logger.error(f"❌ 김치프리미엄 계산기 실행 실패: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())