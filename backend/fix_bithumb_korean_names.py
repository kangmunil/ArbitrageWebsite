#!/usr/bin/env python3
"""
빗썸 한글명 문제 수정 스크립트
- 잘못된 인코딩 문제 해결 (예: ADA의 'ì—\x90ì\x9d´ë‹¤' → '에이다')
- 심볼 그대로 저장된 문제 해결 (예: '1INCH' → '1인치')
- CoinGecko 데이터로 올바른 한글명 매핑
"""

import asyncio
import logging
import re
from datetime import datetime
from sqlalchemy import or_, func

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager, CoinMaster, BithumbListing
from collectors.coingecko_metadata_collector import CoinGeckoMetadataCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_problematic_query(session):
    """문제 있는 빗썸 코인을 찾는 SQLAlchemy 쿼리 조건을 반환"""
    return session.query(BithumbListing).filter(
        BithumbListing.is_active == True,
        or_(
            BithumbListing.korean_name.is_(None),
            func.trim(BithumbListing.korean_name) == '',
            # 잘못된 인코딩 (특수 문자 포함)
            BithumbListing.korean_name.regexp_match(r'[^\w가-힣ㄱ-ㅎㅏ-ㅣ\s]') ,
            # 심볼과 동일한 경우 (영문/숫자만으로 구성)
            BithumbListing.korean_name.regexp_match(r'^[A-Z0-9]+$')
        )
    )

def fix_bithumb_korean_names():
    """빗썸 한글명 문제 수정"""
    logger.info("🔧 빗썸 한글명 문제 수정 시작...")
    
    total_fixed = 0
    encoding_fixed = 0
    symbol_fixed = 0
    
    with db_manager.get_session_context() as session:
        # DB에서 직접 문제 있는 빗썸 코인들 조회
        problematic_coins = get_problematic_query(session).all()
        
        logger.info(f"📊 수정 대상 빗썸 코인: {len(problematic_coins)}개")
        
        for bithumb_coin in problematic_coins:
            korean_name = bithumb_coin.korean_name
            
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
            else:
                logger.warning(f"⚠️ {bithumb_coin.symbol}: coin_master에 한글명 없음")
        
        if total_fixed > 0:
            session.commit()
    
    logger.info(f"\n✅ 빗썸 한글명 수정 완료:")
    logger.info(f"   📊 전체 수정: {total_fixed}개")
    logger.info(f"   🔤 인코딩 문제 수정: {encoding_fixed}개")
    logger.info(f"   📝 심볼→한글명 수정: {symbol_fixed}개")
    
    return total_fixed

async def update_missing_metadata():
    """누락된 메타데이터 업데이트"""
    logger.info("🌍 CoinGecko에서 누락된 메타데이터 수집...")
    
    async with CoinGeckoMetadataCollector() as collector:
        # CoinGecko 코인 목록 조회
        await collector.fetch_coins_list()
        
        # 메타데이터가 필요한 심볼들 찾기
        symbols_needed = collector.get_symbols_needing_metadata()
        
        if symbols_needed:
            logger.info(f"📋 메타데이터 수집 대상: {len(symbols_needed)}개")
            await collector.collect_metadata_for_symbols(symbols_needed)
        else:
            logger.info("✅ 모든 심볼의 메타데이터가 이미 있습니다")
        
        # 빗썸 한글명 매핑 재실행
        collector.update_bithumb_korean_names()

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
        
        # 여전히 문제 있는 코인들 조회
        still_problematic_query = get_problematic_query(session)
        problem_count = still_problematic_query.count()
        
        coverage = (with_korean / total_bithumb * 100) if total_bithumb > 0 else 0
        
        logger.info(f"\n📈 빗썸 한글명 현황:")
        logger.info(f"   📊 전체 코인: {total_bithumb}개")
        logger.info(f"   ✅ 한글명 있음: {with_korean}개 ({coverage:.1f}%)")
        logger.info(f"   ❌ 문제 있음: {problem_count}개")
        
        if problem_count > 0:
            logger.info(f"\n🔍 여전히 문제 있는 코인들:")
            problematic_coins = still_problematic_query.all()
            for coin in problematic_coins:
                logger.info(f"   - {coin.symbol}: '{coin.korean_name}'")

async def main():
    """메인 실행 함수"""
    try:
        logger.info("🚀 빗썸 한글명 문제 수정 시작")
        
        # 1. 누락된 메타데이터 수집
        await update_missing_metadata()
        
        # 2. 빗썸 한글명 문제 수정
        fixed_count = fix_bithumb_korean_names()
        
        # 3. 결과 확인
        check_results()
        
        logger.info(f"🎉 빗썸 한글명 수정 완료! ({fixed_count}개 수정)")
        return True
        
    except Exception as e:
        logger.error(f"❌ 빗썸 한글명 수정 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(main())
