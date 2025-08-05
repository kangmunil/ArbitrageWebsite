#!/usr/bin/env python3
"""
빗썸 한글명 빠른 수정 스크립트
기존 coin_master 데이터를 활용하여 빠르게 수정
"""

import logging
import re
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager, CoinMaster, BithumbListing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_problematic_korean_name(korean_name: str) -> bool:
    """한글명이 문제가 있는지 확인"""
    if not korean_name:
        return True
    
    # 빈 문자열이거나 공백만 있는 경우
    if not korean_name.strip():
        return True
    
    # 잘못된 인코딩 (특수 문자 포함)
    if re.search(r'[^\w가-힣ㄱ-ㅎㅏ-ㅣ\s]', korean_name):
        return True
    
    # 심볼과 동일한 경우 (영문/숫자만으로 구성)
    if re.match(r'^[A-Z0-9]+$', korean_name):
        return True
    
    return False

def quick_fix_bithumb_names():
    """기존 coin_master 데이터로 빗썸 한글명 빠른 수정"""
    logger.info("🔧 빗썸 한글명 빠른 수정 시작...")
    
    total_fixed = 0
    encoding_fixed = 0
    symbol_fixed = 0
    
    with db_manager.get_session_context() as session:
        # 문제 있는 빗썸 코인들 조회
        bithumb_coins = session.query(BithumbListing).filter(
            BithumbListing.is_active == True
        ).all()
        
        logger.info(f"📊 전체 빗썸 코인: {len(bithumb_coins)}개")
        
        for bithumb_coin in bithumb_coins:
            korean_name = bithumb_coin.korean_name
            
            # 문제 있는 한글명인지 확인
            if is_problematic_korean_name(korean_name):
                # coin_master에서 정확한 한글명 찾기
                coin_master = session.query(CoinMaster).filter_by(
                    symbol=bithumb_coin.symbol,
                    is_active=True
                ).first()
                
                if coin_master and coin_master.name_ko and coin_master.name_ko.strip():
                    old_name = korean_name
                    bithumb_coin.korean_name = coin_master.name_ko
                    bithumb_coin.coingecko_id = coin_master.coingecko_id
                    total_fixed += 1
                    
                    # 문제 유형 분류
                    if old_name and re.search(r'[^\w가-힣ㄱ-ㅎㅏ-ㅣ\s]', old_name):
                        encoding_fixed += 1
                        logger.info(f"🔤 인코딩 수정: {bithumb_coin.symbol} '{old_name}' → '{coin_master.name_ko}'")
                    elif old_name == bithumb_coin.symbol:
                        symbol_fixed += 1
                        logger.info(f"📝 심볼 수정: {bithumb_coin.symbol} → '{coin_master.name_ko}'")
                    else:
                        logger.info(f"🔄 수정: {bithumb_coin.symbol} '{old_name}' → '{coin_master.name_ko}'")
        
        session.commit()
    
    logger.info(f"\n✅ 빗썸 한글명 수정 완료:")
    logger.info(f"   📊 전체 수정: {total_fixed}개")
    logger.info(f"   🔤 인코딩 문제 수정: {encoding_fixed}개")
    logger.info(f"   📝 심볼→한글명 수정: {symbol_fixed}개")
    
    return total_fixed

def check_results():
    """수정 결과 확인"""
    logger.info("📊 수정 결과 확인...")
    
    with db_manager.get_session_context() as session:
        # 전체 빗썸 코인 수
        total_bithumb = session.query(BithumbListing).filter_by(is_active=True).count()
        
        # 한글명이 있는 코인 수
        with_korean = session.query(BithumbListing).filter(
            BithumbListing.is_active == True,
            BithumbListing.korean_name.isnot(None),
            BithumbListing.korean_name != ''
        ).count()
        
        # 여전히 문제 있는 코인들
        still_problematic = session.query(BithumbListing).filter(
            BithumbListing.is_active == True
        ).all()
        
        problem_count = 0
        problem_examples = []
        for coin in still_problematic:
            if is_problematic_korean_name(coin.korean_name):
                problem_count += 1
                if len(problem_examples) < 10:  # 처음 10개만
                    problem_examples.append(f"{coin.symbol}: '{coin.korean_name}'")
        
        coverage = (with_korean / total_bithumb * 100) if total_bithumb > 0 else 0
        
        logger.info(f"\n📈 빗썸 한글명 현황:")
        logger.info(f"   📊 전체 코인: {total_bithumb}개")
        logger.info(f"   ✅ 한글명 있음: {with_korean}개 ({coverage:.1f}%)")
        logger.info(f"   ❌ 문제 있음: {problem_count}개")
        
        if problem_examples:
            logger.info(f"\n🔍 여전히 문제 있는 코인들 (처음 10개):")
            for example in problem_examples:
                logger.info(f"   - {example}")

def main():
    """메인 실행 함수"""
    try:
        logger.info("🚀 빗썸 한글명 빠른 수정 시작")
        
        # 빗썸 한글명 문제 수정
        fixed_count = quick_fix_bithumb_names()
        
        # 결과 확인
        check_results()
        
        logger.info(f"🎉 빗썸 한글명 수정 완료! ({fixed_count}개 수정)")
        return True
        
    except Exception as e:
        logger.error(f"❌ 빗썸 한글명 수정 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()