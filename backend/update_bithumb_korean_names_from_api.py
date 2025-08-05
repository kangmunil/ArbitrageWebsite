#!/usr/bin/env python3
"""
빗썸 공식 API로부터 한글명 업데이트 스크립트
- 빗썸 /v1/market/all API 사용
- 공식 한글명으로 정확한 업데이트
"""

import requests
import logging
from datetime import datetime
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager, BithumbListing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BithumbKoreanNameUpdater:
    """빗썸 API로 한글명 업데이트"""
    
    def __init__(self):
        self.api_urls = [
            "https://api.bithumb.com/v2.1.5/market/all",  # 최신 버전 우선
            "https://api.bithumb.com/v1/market/all"       # 대체 버전
        ]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KimchiPremium-BithumbUpdater/1.0'
        })
        
        # 통계
        self.stats = {
            "api_markets_fetched": 0,
            "db_coins_found": 0,
            "updated_count": 0,
            "no_match_count": 0,
            "failed_count": 0
        }
    
    def fetch_bithumb_markets(self) -> dict:
        """빗썸 API에서 마켓 정보 조회"""
        logger.info("🌐 빗썸 API에서 마켓 정보 조회...")
        
        for api_url in self.api_urls:
            try:
                logger.info(f"📡 API 호출: {api_url}")
                response = self.session.get(api_url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # API 응답 구조 확인
                    if 'data' in data and isinstance(data['data'], list):
                        markets_data = data['data']
                    elif isinstance(data, list):
                        markets_data = data
                    else:
                        logger.warning(f"⚠️ 예상치 못한 응답 구조: {list(data.keys())}")
                        continue
                    
                    # 심볼 → 한글명 매핑 생성
                    market_mapping = {}
                    for item in markets_data:
                        if 'market' in item and 'korean_name' in item:
                            market_code = item['market']
                            korean_name = item['korean_name']
                            
                            if korean_name and korean_name.strip():
                                # KRW- 접두사 제거 (예: KRW-BTC → BTC)
                                if market_code.startswith('KRW-'):
                                    symbol = market_code[4:]  # KRW- 제거
                                else:
                                    symbol = market_code
                                
                                market_mapping[symbol] = korean_name.strip()
                    
                    self.stats["api_markets_fetched"] = len(market_mapping)
                    logger.info(f"✅ {len(market_mapping)}개 마켓 정보 수집 완료")
                    logger.info(f"📋 수집된 예시: {list(market_mapping.items())[:5]}")
                    
                    return market_mapping
                    
                else:
                    logger.warning(f"⚠️ API 호출 실패: {response.status_code}")
                    continue
                    
            except Exception as e:
                logger.error(f"❌ API 호출 오류 ({api_url}): {e}")
                continue
        
        raise Exception("모든 빗썸 API 호출 실패")
    
    def update_bithumb_listings(self, market_mapping: dict) -> int:
        """빗썸 listings 테이블 업데이트"""
        logger.info("🔄 빗썸 listings 한글명 업데이트...")
        
        updated_count = 0
        no_match_count = 0
        
        with db_manager.get_session_context() as session:
            # 활성화된 빗썸 코인들 조회
            bithumb_coins = session.query(BithumbListing).filter_by(is_active=True).all()
            self.stats["db_coins_found"] = len(bithumb_coins)
            
            logger.info(f"📊 DB 빗썸 코인: {len(bithumb_coins)}개")
            
            for coin in bithumb_coins:
                symbol = coin.symbol
                
                # API에서 한글명 찾기
                if symbol in market_mapping:
                    korean_name = market_mapping[symbol]
                    old_name = coin.korean_name
                    
                    # 한글명 업데이트
                    coin.korean_name = korean_name
                    coin.last_updated = datetime.now()
                    updated_count += 1
                    
                    logger.info(f"✅ {symbol}: '{old_name}' → '{korean_name}'")
                    
                else:
                    no_match_count += 1
                    logger.warning(f"⚠️ {symbol}: API에서 찾을 수 없음")
            
            # 변경사항 저장
            session.commit()
        
        self.stats["updated_count"] = updated_count
        self.stats["no_match_count"] = no_match_count
        
        logger.info(f"✅ 업데이트 완료: {updated_count}개 수정, {no_match_count}개 매칭 실패")
        return updated_count
    
    def print_update_stats(self):
        """업데이트 통계 출력"""
        logger.info("\n📊 빗썸 한글명 업데이트 통계:")
        logger.info(f"   🌐 API 마켓 수집: {self.stats['api_markets_fetched']}개")
        logger.info(f"   💾 DB 빗썸 코인: {self.stats['db_coins_found']}개")
        logger.info(f"   ✅ 업데이트 성공: {self.stats['updated_count']}개")
        logger.info(f"   ⚠️ 매칭 실패: {self.stats['no_match_count']}개")
        logger.info(f"   ❌ 처리 실패: {self.stats['failed_count']}개")
    
    def verify_results(self):
        """업데이트 결과 검증"""
        logger.info("🔍 업데이트 결과 검증...")
        
        with db_manager.get_session_context() as session:
            # 전체 통계
            total_coins = session.query(BithumbListing).filter_by(is_active=True).count()
            
            # 한글명이 있는 코인들
            with_korean = session.query(BithumbListing).filter(
                BithumbListing.is_active == True,
                BithumbListing.korean_name.isnot(None),
                BithumbListing.korean_name != ''
            ).count()
            
            # 실제 한글이 포함된 이름들
            korean_names = session.query(BithumbListing).filter(
                BithumbListing.is_active == True,
                BithumbListing.korean_name.op('REGEXP')('[가-힣]')
            ).all()
            
            coverage = (with_korean / total_coins * 100) if total_coins > 0 else 0
            
            logger.info(f"\n📈 업데이트 후 현황:")
            logger.info(f"   📊 전체 빗썸 코인: {total_coins}개")
            logger.info(f"   ✅ 한글명 보유: {with_korean}개 ({coverage:.1f}%)")
            logger.info(f"   🇰🇷 실제 한글명: {len(korean_names)}개")
            
            # 업데이트된 한글명 예시
            logger.info("\n🔍 업데이트된 한글명 예시:")
            for i, coin in enumerate(korean_names[:15]):
                logger.info(f"   {coin.symbol}: {coin.korean_name}")
            
            return {
                "total_coins": total_coins,
                "with_korean": with_korean,
                "korean_names_count": len(korean_names),
                "coverage": coverage
            }

def main():
    """메인 실행 함수"""
    try:
        logger.info("🚀 빗썸 공식 API로 한글명 업데이트 시작")
        
        updater = BithumbKoreanNameUpdater()
        
        # 1. 빗썸 API에서 마켓 정보 조회
        market_mapping = updater.fetch_bithumb_markets()
        
        # 2. 데이터베이스 업데이트
        updated_count = updater.update_bithumb_listings(market_mapping)
        
        # 3. 통계 출력
        updater.print_update_stats()
        
        # 4. 결과 검증
        results = updater.verify_results()
        
        logger.info(f"\n🎉 빗썸 한글명 업데이트 완료!")
        logger.info(f"   ✨ {updated_count}개 코인의 한글명이 정확하게 업데이트되었습니다")
        logger.info(f"   📊 한글명 커버리지: {results['coverage']:.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 빗썸 한글명 업데이트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()