#!/usr/bin/env python3
"""
전체 시스템 통합 테스트
1. 거래소 등록 설정
2. CCXT 가격 수집
3. 김치프리미엄 계산
4. 시스템 상태 확인
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from setup_exchange_registry import setup_exchange_registry, get_exchange_summary
from ccxt_price_collector import CCXTPriceCollector
from kimchi_premium_calculator import KimchiPremiumCalculator
from core import db_manager, PriceSnapshot, KimchiPremium, CoinMaster

logger = logging.getLogger(__name__)

class SystemIntegrationTest:
    """시스템 통합 테스트"""
    
    def __init__(self):
        self.test_results = {
            "exchange_registry": {"status": "pending", "details": {}},
            "price_collection": {"status": "pending", "details": {}},
            "kimchi_calculation": {"status": "pending", "details": {}},
            "system_status": {"status": "pending", "details": {}}
        }
    
    def test_exchange_registry_setup(self) -> bool:
        """거래소 등록 정보 설정 테스트"""
        logger.info("🏦 1. 거래소 등록 정보 테스트...")
        
        try:
            # 거래소 등록 정보 설정
            setup_count = setup_exchange_registry()
            
            # 현황 조회
            summary = get_exchange_summary()
            
            self.test_results["exchange_registry"] = {
                "status": "success",
                "details": {
                    "setup_count": setup_count,
                    "total_exchanges": summary["total_exchanges"],
                    "active_exchanges": summary["active_exchanges"],
                    "global_exchanges": summary["global_exchanges"],
                    "korea_exchanges": summary["korea_exchanges"]
                }
            }
            
            logger.info(f"✅ 거래소 등록 완료: {summary['active_exchanges']}개 활성")
            return True
            
        except Exception as e:
            logger.error(f"❌ 거래소 등록 실패: {e}")
            self.test_results["exchange_registry"]["status"] = "failed"
            self.test_results["exchange_registry"]["error"] = str(e)
            return False
    
    async def test_price_collection(self) -> bool:
        """CCXT 가격 수집 테스트"""
        logger.info("💰 2. CCXT 가격 수집 테스트...")
        
        try:
            async with CCXTPriceCollector() as collector:
                # 가격 수집 실행
                result = await collector.run_collection_cycle()
                
                # 통계 조회
                stats = collector.get_collection_stats()
                
                self.test_results["price_collection"] = {
                    "status": "success" if result["success"] else "failed",
                    "details": {
                        "total_symbols": result.get("total_symbols", 0),
                        "total_prices": result.get("total_prices", 0),
                        "saved_count": result.get("saved_count", 0),
                        "failed_symbols": result.get("failed_symbols", 0),
                        "active_exchanges": stats["active_exchanges"],
                        "symbol_mapping_count": stats["symbol_mapping_count"]
                    }
                }
                
                if result["success"]:
                    logger.info(f"✅ 가격 수집 완료: {result['total_prices']}개 가격")
                    return True
                else:
                    logger.error(f"❌ 가격 수집 실패: {result.get('error')}")
                    self.test_results["price_collection"]["error"] = result.get("error")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 가격 수집 테스트 실패: {e}")
            self.test_results["price_collection"]["status"] = "failed"
            self.test_results["price_collection"]["error"] = str(e)
            return False
    
    async def test_kimchi_calculation(self) -> bool:
        """김치프리미엄 계산 테스트"""
        logger.info("🧮 3. 김치프리미엄 계산 테스트...")
        
        try:
            async with KimchiPremiumCalculator() as calculator:
                # 김치프리미엄 계산 실행
                result = await calculator.run_calculation_cycle()
                
                # 통계 조회
                stats = calculator.get_calculation_stats()
                
                self.test_results["kimchi_calculation"] = {
                    "status": "success" if result["success"] else "failed",
                    "details": {
                        "total_calculations": result.get("total_calculations", 0),
                        "saved_count": result.get("saved_count", 0),
                        "processed_coins": stats["processed_coins"],
                        "successful_calculations": stats["successful_calculations"],
                        "failed_calculations": stats["failed_calculations"]
                    }
                }
                
                if result["success"]:
                    logger.info(f"✅ 김치프리미엄 계산 완료: {result['total_calculations']}개")
                    return True
                else:
                    logger.error(f"❌ 김치프리미엄 계산 실패: {result.get('error')}")
                    self.test_results["kimchi_calculation"]["error"] = result.get("error")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 김치프리미엄 계산 테스트 실패: {e}")
            self.test_results["kimchi_calculation"]["status"] = "failed"
            self.test_results["kimchi_calculation"]["error"] = str(e)
            return False
    
    def test_system_status(self) -> bool:
        """시스템 전체 상태 확인"""
        logger.info("📊 4. 시스템 상태 확인...")
        
        try:
            with db_manager.get_session_context() as session:
                # 데이터베이스 현황 조회
                coin_master_count = session.query(CoinMaster).filter_by(is_active=True).count()
                
                # 최근 가격 데이터 (1시간 이내)
                from datetime import timedelta, timezone
                one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
                recent_prices = session.query(PriceSnapshot).filter(
                    PriceSnapshot.collected_at >= one_hour_ago
                ).count()
                
                # 최근 김치프리미엄 데이터 (1시간 이내)
                recent_kimchi = session.query(KimchiPremium).filter(
                    KimchiPremium.calculated_at >= one_hour_ago
                ).count()
                
                # 거래소별 가격 데이터 분포
                exchange_distribution = {}
                from sqlalchemy import func
                price_data = session.query(
                    PriceSnapshot.exchange_id,
                    func.count(PriceSnapshot.id).label('count')
                ).filter(
                    PriceSnapshot.collected_at >= one_hour_ago
                ).group_by(PriceSnapshot.exchange_id).all()
                
                for exchange_id, count in price_data:
                    exchange_distribution[exchange_id] = count
                
                self.test_results["system_status"] = {
                    "status": "success",
                    "details": {
                        "coin_master_count": coin_master_count,
                        "recent_prices": recent_prices,
                        "recent_kimchi": recent_kimchi,
                        "exchange_distribution": exchange_distribution,
                        "test_time": datetime.now().isoformat()
                    }
                }
                
                logger.info(f"✅ 시스템 상태 확인 완료:")
                logger.info(f"   - 등록된 코인: {coin_master_count}개")
                logger.info(f"   - 최근 가격 데이터: {recent_prices}개")
                logger.info(f"   - 최근 김치프리미엄: {recent_kimchi}개")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ 시스템 상태 확인 실패: {e}")
            self.test_results["system_status"]["status"] = "failed"
            self.test_results["system_status"]["error"] = str(e)
            return False
    
    async def run_complete_test(self) -> Dict:
        """전체 시스템 테스트 실행"""
        logger.info("🚀 전체 시스템 통합 테스트 시작")
        
        start_time = time.time()
        
        # 1. 거래소 등록 테스트
        registry_success = self.test_exchange_registry_setup()
        
        # 2. 가격 수집 테스트 (거래소 등록이 성공한 경우만)
        price_success = False
        if registry_success:
            price_success = await self.test_price_collection()
        
        # 3. 김치프리미엄 계산 테스트 (가격 수집이 성공한 경우만)
        kimchi_success = False
        if price_success:
            # 가격 수집 후 잠시 대기 (데이터 안정화)
            await asyncio.sleep(2)
            kimchi_success = await self.test_kimchi_calculation()
        
        # 4. 시스템 상태 확인
        status_success = self.test_system_status()
        
        # 전체 결과 평가
        all_success = registry_success and price_success and kimchi_success and status_success
        
        elapsed_time = time.time() - start_time
        
        # 최종 결과
        final_result = {
            "overall_success": all_success,
            "elapsed_time": elapsed_time,
            "test_results": self.test_results,
            "summary": {
                "exchange_registry": "✅" if registry_success else "❌",
                "price_collection": "✅" if price_success else "❌",
                "kimchi_calculation": "✅" if kimchi_success else "❌",
                "system_status": "✅" if status_success else "❌"
            }
        }
        
        return final_result
    
    def print_test_summary(self, results: Dict):
        """테스트 결과 요약 출력"""
        logger.info("\n" + "="*60)
        logger.info("📊 전체 시스템 통합 테스트 결과")
        logger.info("="*60)
        
        logger.info(f"⏱️ 총 소요 시간: {results['elapsed_time']:.1f}초")
        logger.info(f"🎯 전체 성공 여부: {'✅ 성공' if results['overall_success'] else '❌ 실패'}")
        
        logger.info("\n📋 세부 결과:")
        for test_name, status in results["summary"].items():
            logger.info(f"   {test_name}: {status}")
        
        # 상세 통계
        if results["test_results"]["price_collection"]["status"] == "success":
            price_details = results["test_results"]["price_collection"]["details"]
            logger.info(f"\n💰 가격 수집 통계:")
            logger.info(f"   - 수집된 가격: {price_details.get('total_prices', 0)}개")
            logger.info(f"   - 활성 거래소: {price_details.get('active_exchanges', 0)}개")
        
        if results["test_results"]["kimchi_calculation"]["status"] == "success":
            kimchi_details = results["test_results"]["kimchi_calculation"]["details"]
            logger.info(f"\n🧮 김치프리미엄 통계:")
            logger.info(f"   - 계산된 프리미엄: {kimchi_details.get('total_calculations', 0)}개")
            logger.info(f"   - 성공한 계산: {kimchi_details.get('successful_calculations', 0)}개")
        
        logger.info("\n" + "="*60)

async def main():
    """메인 실행 함수"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 통합 테스트 실행
        test_runner = SystemIntegrationTest()
        results = await test_runner.run_complete_test()
        
        # 결과 출력
        test_runner.print_test_summary(results)
        
        # 성공 여부에 따라 종료 코드 설정
        if results["overall_success"]:
            logger.info("🎉 전체 시스템 통합 테스트 성공!")
            return True
        else:
            logger.error("❌ 전체 시스템 통합 테스트 실패!")
            return False
            
    except Exception as e:
        logger.error(f"❌ 통합 테스트 실행 실패: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)