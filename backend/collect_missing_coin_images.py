#!/usr/bin/env python3
"""
업비트/빗썸 코인 이미지 URL 수집 스크립트
CoinGecko API를 사용하여 누락된 코인 이미지를 수집하고 데이터베이스에 저장
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager, CoinMaster
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoinImageCollector:
    """코인 이미지 URL 수집기"""
    
    def __init__(self):
        self.session = None
        self.coingecko_coins = {}  # CoinGecko 코인 목록 캐시
        
        # 통계
        self.stats = {
            "missing_coins": 0,
            "coingecko_fetched": 0,
            "matched_coins": 0,
            "updated_coins": 0,
            "failed_coins": 0
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "ArbitrageWebsite-ImageCollector/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    def get_missing_coins(self):
        """이미지 URL이 없는 업비트/빗썸 코인들 조회"""
        logger.info("🔍 이미지 URL이 없는 코인들 조회...")
        
        with db_manager.get_session_context() as session:
            # 업비트 + 빗썸 코인 중 이미지가 없는 것들
            missing_coins = session.execute(text('''
                SELECT DISTINCT symbol
                FROM (
                    SELECT u.symbol FROM upbit_listings u WHERE u.is_active = true
                    UNION
                    SELECT b.symbol FROM bithumb_listings b WHERE b.is_active = true
                ) AS all_coins
                WHERE symbol NOT IN (
                    SELECT symbol FROM coin_master 
                    WHERE is_active = true 
                    AND image_url IS NOT NULL 
                    AND image_url != ''
                )
                ORDER BY symbol
            ''')).fetchall()
            
            missing_symbols = [coin[0] for coin in missing_coins]
            self.stats["missing_coins"] = len(missing_symbols)
            
            logger.info(f"📊 이미지 URL이 필요한 코인: {len(missing_symbols)}개")
            logger.info(f"📋 처음 10개: {missing_symbols[:10]}")
            
            return missing_symbols
    
    async def fetch_coingecko_coins_list(self):
        """CoinGecko 전체 코인 목록 조회"""
        logger.info("🌐 CoinGecko 코인 목록 조회...")
        
        try:
            url = "https://api.coingecko.com/api/v3/coins/list?include_platform=false"
            async with self.session.get(url) as response:
                if response.status == 200:
                    coins_data = await response.json()
                    
                    # 심볼 기반 매핑 생성
                    for coin in coins_data:
                        symbol = coin['symbol'].upper()
                        if symbol not in self.coingecko_coins:
                            self.coingecko_coins[symbol] = []
                        self.coingecko_coins[symbol].append({
                            'id': coin['id'],
                            'name': coin['name'],
                            'symbol': coin['symbol']
                        })
                    
                    self.stats["coingecko_fetched"] = len(coins_data)
                    logger.info(f"✅ CoinGecko 코인 {len(coins_data)}개 조회 완료")
                    
                else:
                    raise Exception(f"CoinGecko API 오류: {response.status}")
                    
        except Exception as e:
            logger.error(f"❌ CoinGecko 코인 목록 조회 실패: {e}")
            raise
    
    async def get_coin_details(self, coingecko_id: str):
        """특정 코인의 상세 정보 조회 (이미지 URL 포함)"""
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    coin_data = await response.json()
                    return {
                        'id': coin_data['id'],
                        'symbol': coin_data['symbol'].upper(),
                        'name': coin_data['name'],
                        'image_url': coin_data.get('image', {}).get('large', ''),
                        'market_cap_rank': coin_data.get('market_cap_rank'),
                        'description': coin_data.get('description', {}).get('en', '')[:500] if coin_data.get('description', {}).get('en') else ''
                    }
                elif response.status == 429:
                    # Rate limit - 잠시 대기
                    logger.warning(f"⏸️ Rate limit reached, waiting...")
                    await asyncio.sleep(10)
                    return None
                else:
                    logger.warning(f"⚠️ {coingecko_id} 조회 실패: {response.status}")
                    return None
                    
        except Exception as e:
            logger.warning(f"⚠️ {coingecko_id} 조회 오류: {e}")
            return None
    
    async def collect_missing_images(self, missing_symbols: list):
        """누락된 코인들의 이미지 URL 수집"""
        logger.info("🎯 누락된 코인 이미지 URL 수집 시작...")
        
        matched_coins = []
        
        for symbol in missing_symbols:
            if symbol in self.coingecko_coins:
                # 여러 매칭이 있을 수 있으므로 첫 번째 것 사용
                coingecko_matches = self.coingecko_coins[symbol]
                
                # 가장 적합한 매치 선택 (일반적으로 첫 번째가 가장 인기 있는 것)
                best_match = coingecko_matches[0]
                coingecko_id = best_match['id']
                
                logger.info(f"🔎 {symbol} → CoinGecko ID: {coingecko_id}")
                
                # 상세 정보 조회
                coin_details = await self.get_coin_details(coingecko_id)
                if coin_details and coin_details['image_url']:
                    matched_coins.append(coin_details)
                    logger.info(f"✅ {symbol}: {coin_details['image_url']}")
                else:
                    logger.warning(f"⚠️ {symbol}: 이미지 URL 없음")
                
                # Rate limiting 방지
                await asyncio.sleep(0.5)
            else:
                logger.warning(f"❌ {symbol}: CoinGecko에서 찾을 수 없음")
        
        self.stats["matched_coins"] = len(matched_coins)
        logger.info(f"🎯 매칭된 코인: {len(matched_coins)}개")
        
        return matched_coins
    
    def save_coin_images(self, matched_coins: list):
        """매칭된 코인들을 데이터베이스에 저장"""
        logger.info("💾 코인 이미지 데이터베이스 저장...")
        
        updated_count = 0
        failed_count = 0
        
        with db_manager.get_session_context() as session:
            for coin in matched_coins:
                try:
                    # 기존 레코드 확인
                    existing_coin = session.query(CoinMaster).filter_by(
                        symbol=coin['symbol'],
                        is_active=True
                    ).first()
                    
                    if existing_coin:
                        # 기존 레코드 업데이트
                        existing_coin.image_url = coin['image_url']
                        existing_coin.updated_at = datetime.now()
                        if not existing_coin.coingecko_id:
                            existing_coin.coingecko_id = coin['id']
                        if not existing_coin.name_en:
                            existing_coin.name_en = coin['name']
                        if coin['market_cap_rank']:
                            existing_coin.market_cap_rank = coin['market_cap_rank']
                        if coin['description']:
                            existing_coin.description = coin['description']
                    else:
                        # 새 레코드 생성
                        new_coin = CoinMaster(
                            coingecko_id=coin['id'],
                            symbol=coin['symbol'],
                            name_en=coin['name'],
                            image_url=coin['image_url'],
                            market_cap_rank=coin['market_cap_rank'],
                            description=coin['description'],
                            is_active=True,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        session.add(new_coin)
                    
                    updated_count += 1
                    logger.info(f"💾 {coin['symbol']}: 저장 완료")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ {coin['symbol']} 저장 실패: {e}")
                    continue
            
            session.commit()
        
        self.stats["updated_coins"] = updated_count
        self.stats["failed_coins"] = failed_count
        
        logger.info(f"✅ 저장 완료: {updated_count}개 성공, {failed_count}개 실패")
    
    def print_final_stats(self):
        """최종 통계 출력"""
        logger.info("\n" + "="*80)
        logger.info("📊 코인 이미지 수집 완료")
        logger.info("="*80)
        
        logger.info(f"\n🔍 수집 대상:")
        logger.info(f"   📊 이미지 필요 코인: {self.stats['missing_coins']}개")
        
        logger.info(f"\n🌐 CoinGecko 조회:")
        logger.info(f"   📥 전체 코인 수집: {self.stats['coingecko_fetched']}개")
        logger.info(f"   🎯 매칭 성공: {self.stats['matched_coins']}개")
        
        logger.info(f"\n💾 데이터베이스 저장:")
        logger.info(f"   ✅ 저장 성공: {self.stats['updated_coins']}개")
        logger.info(f"   ❌ 저장 실패: {self.stats['failed_coins']}개")
        
        success_rate = (self.stats['matched_coins'] / self.stats['missing_coins'] * 100) if self.stats['missing_coins'] > 0 else 0
        logger.info(f"\n🎯 성공률: {success_rate:.1f}%")
        
        logger.info("\n" + "="*80)

async def main():
    """메인 실행 함수"""
    try:
        logger.info("🚀 코인 이미지 URL 수집 시작")
        start_time = time.time()
        
        async with CoinImageCollector() as collector:
            # 1. 이미지가 없는 코인들 조회
            missing_symbols = collector.get_missing_coins()
            
            if not missing_symbols:
                logger.info("✅ 모든 코인이 이미지 URL을 가지고 있습니다!")
                return True
            
            # 2. CoinGecko 코인 목록 조회
            await collector.fetch_coingecko_coins_list()
            
            # 3. 누락된 코인들의 이미지 URL 수집
            matched_coins = await collector.collect_missing_images(missing_symbols)
            
            if not matched_coins:
                logger.warning("⚠️ 매칭된 코인이 없습니다.")
                return False
            
            # 4. 데이터베이스에 저장
            collector.save_coin_images(matched_coins)
            
            # 5. 최종 통계
            elapsed_time = time.time() - start_time
            collector.print_final_stats()
            logger.info(f"⏱️ 소요 시간: {elapsed_time:.1f}초")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ 코인 이미지 수집 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(main())