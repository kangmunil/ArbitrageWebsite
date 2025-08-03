#!/usr/bin/env python3
"""
기존 시스템에 메타데이터 동기화
우리가 수집한 한글명+아이콘 데이터를 기존 cryptocurrencies 테이블에 연동
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 새로운 시스템 임포트
from core import db_manager as new_db, CoinMaster

# 기존 시스템 임포트
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app'))

try:
    from database import SessionLocal, engine
    from models import Cryptocurrency
    from sqlalchemy import text
    old_system_available = True
except ImportError as e:
    print(f"⚠️ 기존 시스템 임포트 실패: {e}")
    print("기존 시스템이 설정되지 않았거나 의존성이 없을 수 있습니다.")
    old_system_available = False

import logging

logger = logging.getLogger(__name__)

class MetadataSync:
    """메타데이터 동기화 클래스"""
    
    def __init__(self):
        self.stats = {
            "source_coins": 0,
            "target_updated": 0,
            "target_created": 0,
            "skipped": 0,
            "errors": 0
        }
    
    def check_existing_system(self):
        """기존 시스템 데이터베이스 연결 및 테이블 확인"""
        if not old_system_available:
            return False, "기존 시스템 모듈을 임포트할 수 없습니다."
        
        try:
            # 데이터베이스 연결 테스트
            with engine.connect() as conn:
                # 테이블 존재 확인
                result = conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result]
                
                if 'cryptocurrencies' not in tables:
                    return False, "cryptocurrencies 테이블이 존재하지 않습니다."
                
                # 테이블 구조 확인
                result = conn.execute(text("DESCRIBE cryptocurrencies"))
                columns = [row[0] for row in result]
                
                required_columns = ['symbol', 'name_ko', 'name_en', 'logo_url']
                missing_columns = [col for col in required_columns if col not in columns]
                
                if missing_columns:
                    return False, f"필수 컬럼이 없습니다: {missing_columns}"
                
                return True, f"기존 시스템 확인 완료. 테이블: {len(tables)}개"
        
        except Exception as e:
            return False, f"데이터베이스 연결 실패: {e}"
    
    def get_source_metadata(self):
        """새로운 시스템에서 메타데이터 조회"""
        try:
            with new_db.get_session_context() as session:
                coins = session.query(CoinMaster).filter_by(is_active=True).all()
                
                source_data = []
                for coin in coins:
                    source_data.append({
                        'coingecko_id': coin.coingecko_id,
                        'symbol': coin.symbol,
                        'name_en': coin.name_en,
                        'name_ko': coin.name_ko,
                        'image_url': coin.image_url,
                        'market_cap_rank': coin.market_cap_rank,
                        'description': coin.description,
                        'homepage_url': coin.homepage_url
                    })
                
                self.stats["source_coins"] = len(source_data)
                logger.info(f"📊 소스 데이터: {len(source_data)}개 코인")
                return source_data
        
        except Exception as e:
            logger.error(f"❌ 소스 데이터 조회 실패: {e}")
            return []
    
    def check_target_data(self):
        """기존 시스템의 현재 데이터 확인"""
        try:
            db = SessionLocal()
            try:
                # 기존 코인 수 확인
                total_coins = db.query(Cryptocurrency).count()
                active_coins = db.query(Cryptocurrency).filter_by(is_active=True).count()
                
                # 한글명이 있는 코인 수 확인
                coins_with_korean = db.query(Cryptocurrency).filter(
                    Cryptocurrency.name_ko.isnot(None),
                    Cryptocurrency.name_ko != '',
                    Cryptocurrency.is_active == True
                ).count()
                
                # 아이콘이 있는 코인 수 확인
                coins_with_logo = db.query(Cryptocurrency).filter(
                    Cryptocurrency.logo_url.isnot(None),
                    Cryptocurrency.logo_url != '',
                    Cryptocurrency.is_active == True
                ).count()
                
                return {
                    "total_coins": total_coins,
                    "active_coins": active_coins,
                    "coins_with_korean": coins_with_korean,
                    "coins_with_logo": coins_with_logo,
                    "korean_coverage": f"{(coins_with_korean/active_coins*100):.1f}%" if active_coins > 0 else "0%",
                    "logo_coverage": f"{(coins_with_logo/active_coins*100):.1f}%" if active_coins > 0 else "0%"
                }
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"❌ 기존 데이터 확인 실패: {e}")
            return {}
    
    def sync_metadata(self, source_data):
        """메타데이터 동기화 실행"""
        try:
            db = SessionLocal()
            try:
                for coin_data in source_data:
                    try:
                        symbol = coin_data['symbol']
                        
                        # 기존 레코드 확인 (심볼 기준)
                        existing = db.query(Cryptocurrency).filter_by(
                            symbol=symbol, is_active=True
                        ).first()
                        
                        if existing:
                            # 업데이트
                            updated = False
                            
                            # 한글명 업데이트 (기존에 없거나 비어있으면)
                            if coin_data['name_ko'] and (not existing.name_ko or existing.name_ko.strip() == ''):
                                existing.name_ko = coin_data['name_ko']
                                updated = True
                            
                            # 영문명 업데이트 (기존에 없거나 비어있으면)
                            if coin_data['name_en'] and (not existing.name_en or existing.name_en.strip() == ''):
                                existing.name_en = coin_data['name_en']
                                updated = True
                            
                            # 로고 URL 업데이트 (기존에 없거나 비어있으면)
                            if coin_data['image_url'] and (not existing.logo_url or existing.logo_url.strip() == ''):
                                existing.logo_url = coin_data['image_url']
                                updated = True
                            
                            # 시가총액 순위 업데이트
                            if coin_data['market_cap_rank'] and (not existing.market_cap_rank or existing.market_cap_rank == 0):
                                existing.market_cap_rank = coin_data['market_cap_rank']
                                updated = True
                            
                            # 웹사이트 URL 업데이트 (있는 경우)
                            if coin_data['homepage_url'] and (not existing.website_url or existing.website_url.strip() == ''):
                                existing.website_url = coin_data['homepage_url']
                                updated = True
                            
                            if updated:
                                self.stats["target_updated"] += 1
                                logger.debug(f"🔄 업데이트: {symbol} ({coin_data['name_ko']})")
                            else:
                                self.stats["skipped"] += 1
                                logger.debug(f"⏭️ 스킵: {symbol} (이미 완전한 데이터)")
                        
                        else:
                            # 신규 생성
                            new_crypto = Cryptocurrency(
                                crypto_id=coin_data['coingecko_id'],
                                symbol=symbol,
                                name_ko=coin_data['name_ko'],
                                name_en=coin_data['name_en'],
                                logo_url=coin_data['image_url'],
                                market_cap_rank=coin_data['market_cap_rank'],
                                website_url=coin_data['homepage_url'],
                                is_active=True
                            )
                            db.add(new_crypto)
                            self.stats["target_created"] += 1
                            logger.debug(f"🆕 신규 생성: {symbol} ({coin_data['name_ko']})")
                    
                    except Exception as e:
                        logger.error(f"❌ {coin_data['symbol']} 처리 실패: {e}")
                        self.stats["errors"] += 1
                        continue
                
                # 커밋
                db.commit()
                logger.info(f"✅ 메타데이터 동기화 완료")
                
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"❌ 동기화 실패: {e}")
            raise
    
    def print_sync_summary(self, before_stats, after_stats):
        """동기화 결과 요약 출력"""
        logger.info("\n" + "="*60)
        logger.info("📊 메타데이터 동기화 결과")
        logger.info("="*60)
        
        logger.info(f"📋 처리 통계:")
        logger.info(f"   소스 코인: {self.stats['source_coins']}개")
        logger.info(f"   업데이트: {self.stats['target_updated']}개")
        logger.info(f"   신규 생성: {self.stats['target_created']}개")
        logger.info(f"   스킵: {self.stats['skipped']}개")
        logger.info(f"   오류: {self.stats['errors']}개")
        
        if before_stats and after_stats:
            logger.info(f"\n📈 변화 현황:")
            logger.info(f"   전체 코인: {before_stats['active_coins']} → {after_stats['active_coins']}")
            logger.info(f"   한글명: {before_stats['coins_with_korean']} → {after_stats['coins_with_korean']} ({before_stats['korean_coverage']} → {after_stats['korean_coverage']})")
            logger.info(f"   아이콘: {before_stats['coins_with_logo']} → {after_stats['coins_with_logo']} ({before_stats['logo_coverage']} → {after_stats['logo_coverage']})")
        
        logger.info("\n" + "="*60)
    
    def run_sync(self):
        """전체 동기화 프로세스 실행"""
        logger.info("🚀 메타데이터 동기화 시작")
        
        # 1. 기존 시스템 확인
        is_available, message = self.check_existing_system()
        if not is_available:
            logger.error(f"❌ 기존 시스템 확인 실패: {message}")
            return False
        
        logger.info(f"✅ {message}")
        
        # 2. 동기화 전 상태 확인
        before_stats = self.check_target_data()
        if before_stats:
            logger.info(f"📊 동기화 전 현황:")
            logger.info(f"   활성 코인: {before_stats['active_coins']}개")
            logger.info(f"   한글명 보유: {before_stats['coins_with_korean']}개 ({before_stats['korean_coverage']})")
            logger.info(f"   아이콘 보유: {before_stats['coins_with_logo']}개 ({before_stats['logo_coverage']})")
        
        # 3. 소스 데이터 조회
        source_data = self.get_source_metadata()
        if not source_data:
            logger.error("❌ 소스 데이터가 없습니다.")
            return False
        
        # 4. 동기화 실행
        self.sync_metadata(source_data)
        
        # 5. 동기화 후 상태 확인
        after_stats = self.check_target_data()
        
        # 6. 결과 요약 출력
        self.print_sync_summary(before_stats, after_stats)
        
        logger.info("🎉 메타데이터 동기화 완료!")
        return True

def main():
    """메인 함수"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        sync_manager = MetadataSync()
        success = sync_manager.run_sync()
        
        if success:
            logger.info("✅ 동기화 성공! 이제 웹사이트에서 한글명과 아이콘을 확인할 수 있습니다.")
            return True
        else:
            logger.error("❌ 동기화 실패")
            return False
    
    except Exception as e:
        logger.error(f"❌ 동기화 프로세스 실패: {e}")
        return False

if __name__ == "__main__":
    main()