#!/usr/bin/env python3
"""
빗썸 한글명 수정 결과 확인 스크립트
"""

import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager, BithumbListing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_bithumb_fix_results():
    """빗썸 한글명 수정 결과 확인"""
    logger.info("📊 빗썸 한글명 수정 결과 확인...")
    
    with db_manager.get_session_context() as session:
        # 전체 빗썸 코인 수
        total_bithumb = session.query(BithumbListing).filter_by(is_active=True).count()
        
        # 한글명이 있는 코인 수 (NULL이 아니고 빈 문자열이 아닌 것)
        with_korean = session.query(BithumbListing).filter(
            BithumbListing.is_active == True,
            BithumbListing.korean_name.isnot(None),
            BithumbListing.korean_name != ''
        ).count()
        
        # 한글이 포함된 이름들 (실제 한글명)
        korean_names = session.query(BithumbListing).filter(
            BithumbListing.is_active == True,
            BithumbListing.korean_name.op('REGEXP')('[가-힣]')
        ).all()
        
        coverage = (with_korean / total_bithumb * 100) if total_bithumb > 0 else 0
        
        logger.info(f"\n📈 빗썸 한글명 현황:")
        logger.info(f"   📊 전체 코인: {total_bithumb}개")
        logger.info(f"   ✅ 한글명 있음: {with_korean}개 ({coverage:.1f}%)")
        logger.info(f"   🇰🇷 실제 한글명: {len(korean_names)}개")
        
        # 수정된 한글명 예시들 출력
        logger.info("\n🔍 수정된 한글명 예시들:")
        for i, coin in enumerate(korean_names[:15]):  # 처음 15개만
            logger.info(f"   {coin.symbol}: {coin.korean_name}")
        
        # ADA 특별 확인 (인코딩 문제가 있었던 코인)
        ada_coin = session.query(BithumbListing).filter_by(symbol='ADA').first()
        if ada_coin:
            logger.info(f"\n🎯 ADA 수정 결과: '{ada_coin.korean_name}'")
        
        # 여전히 문제 있는 코인들 확인
        problematic_coins = session.query(BithumbListing).filter(
            BithumbListing.is_active == True
        ).all()
        
        problem_count = 0
        problem_examples = []
        
        for coin in problematic_coins:
            korean_name = getattr(coin, 'korean_name', None)
            symbol = getattr(coin, 'symbol', '')
            is_problem = False
            
            # 문제 확인
            if not korean_name or not str(korean_name).strip():
                is_problem = True
            elif str(korean_name) == str(symbol):  # 심볼과 동일
                is_problem = True
            
            if is_problem:
                problem_count += 1
                if len(problem_examples) < 10:
                    problem_examples.append(f"{symbol}: '{korean_name}'")
        
        if problem_count > 0:
            logger.info(f"\n⚠️ 여전히 문제 있는 코인: {problem_count}개")
            for example in problem_examples:
                logger.info(f"   - {example}")
        else:
            logger.info("\n🎉 모든 코인이 올바른 한글명을 가지고 있습니다!")

def main():
    """메인 실행 함수"""
    try:
        check_bithumb_fix_results()
        return True
        
    except Exception as e:
        logger.error(f"❌ 확인 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()