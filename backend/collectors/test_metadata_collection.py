#!/usr/bin/env python3
"""
CoinGecko 메타데이터 수집 테스트 (소수 코인만)
"""

import asyncio
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coingecko_metadata_collector import CoinGeckoMetadataCollector

async def test_metadata_collection():
    """메타데이터 수집 테스트"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        logger = logging.getLogger(__name__)
        logger.info("🧪 CoinGecko 메타데이터 수집 테스트 시작")
        
        async with CoinGeckoMetadataCollector() as collector:
            # CoinGecko 코인 목록 조회
            await collector.fetch_coins_list()
            
            # 주요 코인 몇 개만 테스트
            test_symbols = ['BTC', 'ETH', 'XRP']
            
            logger.info(f"🔍 테스트 대상: {test_symbols}")
            
            success_count = await collector.collect_metadata_for_symbols(test_symbols)
            
            # 빗썸 한글명 매핑 테스트
            bithumb_updated = collector.update_bithumb_korean_names()
            
            # 결과 요약
            summary = collector.get_metadata_summary()
            
            logger.info(f"\n📈 테스트 결과:")
            logger.info(f"   ✅ 메타데이터 수집: {success_count}/{len(test_symbols)}")
            logger.info(f"   🏪 빗썸 한글명 매핑: {bithumb_updated}개")
            logger.info(f"   🌍 전체 코인: {summary['coin_master']['total_coins']}개")
            logger.info(f"   🇰🇷 한글명: {summary['coin_master']['korean_names']}개")
            logger.info(f"   🖼️ 아이콘: {summary['coin_master']['icons']}개")
        
        logger.info("🎉 테스트 완료!")
        return True
        
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_metadata_collection())