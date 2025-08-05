#!/usr/bin/env python3
"""
CoinGecko 메타데이터 자동 수집 시스템
- 코인 한글명 수집 (업비트는 API, 빗썸은 CoinGecko 매핑)
- 코인 아이콘 URL 자동 수집
- coin_master 테이블 자동 업데이트
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db_manager, CoinMaster, UpbitListing, BithumbListing, settings

logger = logging.getLogger(__name__)

class CoinGeckoMetadataCollector:
    """CoinGecko 기반 메타데이터 수집기"""
    
    def __init__(self):
        self.session = None
        self.base_url = settings.coingecko.base_url
        self.api_key = settings.coingecko.api_key
        self.rate_limit_delay = settings.coingecko.rate_limit_delay
        
        # 심볼 → CoinGecko ID 매핑 캐시
        self.symbol_to_id_cache = {}
        
        # 수집 통계
        self.stats = {
            "coins_list_fetched": 0,
            "metadata_updated": 0,
            "korean_names_updated": 0,
            "icons_updated": 0,
            "failed": 0
        }
        
        # 수동 심볼 매핑 (자주 발생하는 불일치 해결)
        self.manual_symbol_mapping = {
            'WAXP': 'wax',
            'LSK': 'lisk', 
            'PUNDIX': 'pundi-x-new',
            'HUNT': 'hunt-token',
            'PENGU': 'pudgy-penguins',
            'CARV': 'carv',
            'BORA': 'bora',
            'BOUNTY': 'bounty0x',
            'KAITO': 'kaito',
            'BLAST': 'blast',
            'DKA': 'dkargo',
            'TOKAMAK': 'tokamak-network',
            'NEWT': 'newton',
            'MOVE': 'move',
            'AERGO': 'aergo'
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        headers = {"User-Agent": "KimchiPremium-MetadataCollector/1.0"}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key
        
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def fetch_coins_list(self) -> Dict[str, str]:
        """CoinGecko 전체 코인 목록 조회 (심볼 → ID 매핑)"""
        logger.info("🌍 CoinGecko 코인 목록 조회...")
        
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        try:
            url = f"{self.base_url}/coins/list"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"CoinGecko API 오류: {response.status}")
                
                coins_data = await response.json()
                
                # 심볼을 대문자로 변환하여 매핑 (중복 시 첫 번째 우선)
                for coin in coins_data:
                    symbol = coin['symbol'].upper()
                    coin_id = coin['id']
                    
                    if symbol not in self.symbol_to_id_cache:
                        self.symbol_to_id_cache[symbol] = coin_id
                
                # 수동 매핑 오버라이드
                for symbol, coin_id in self.manual_symbol_mapping.items():
                    self.symbol_to_id_cache[symbol] = coin_id
                
                self.stats["coins_list_fetched"] = len(self.symbol_to_id_cache)
                logger.info(f"✅ {len(self.symbol_to_id_cache)}개 코인 ID 매핑 완료")
                return self.symbol_to_id_cache
                
        except Exception as e:
            logger.error(f"❌ CoinGecko 코인 목록 조회 실패: {e}")
            raise
    
    async def fetch_coin_metadata(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """특정 코인의 메타데이터 조회"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
            
        try:
            url = f"{self.base_url}/coins/{coin_id}"
            params = {
                'localization': 'true',  # 한국어 지역화 포함
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'false',
                'developer_data': 'false',
                'sparkline': 'false'
            }
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)
            
            async with self.session.get(url, params=params) as response:
                if response.status == 429:  # Rate limit
                    logger.warning(f"⏳ Rate limit, 대기...")
                    await asyncio.sleep(10)
                    return None
                elif response.status != 200:
                    logger.warning(f"⚠️ {coin_id} 조회 실패: {response.status}")
                    return None
                
                data = await response.json()
                
                # 한글명 추출 (여러 방법 시도)
                name_ko = None
                if 'localization' in data and 'ko' in data['localization']:
                    name_ko = data['localization']['ko']
                
                # 한글명이 영문명과 같으면 한글명 없는 것으로 처리
                if name_ko == data.get('name'):
                    name_ko = None
                
                metadata = {
                    'coingecko_id': coin_id,
                    'symbol': data['symbol'].upper(),
                    'name_en': data['name'],
                    'name_ko': name_ko,
                    'image_url': data.get('image', {}).get('large'),  # 64x64 아이콘
                    'market_cap_rank': data.get('market_cap_rank'),
                    'description': data.get('description', {}).get('en', '')[:500],  # 500자 제한
                    'homepage_url': data.get('links', {}).get('homepage', [None])[0]
                }
                
                return metadata
                
        except Exception as e:
            logger.error(f"❌ {coin_id} 메타데이터 조회 실패: {e}")
            return None
    
    def save_coin_metadata(self, metadata: Dict[str, Any]) -> bool:
        """코인 메타데이터 DB 저장"""
        try:
            with db_manager.get_session_context() as session:
                # 기존 레코드 확인
                existing = session.query(CoinMaster).filter_by(
                    coingecko_id=metadata['coingecko_id']
                ).first()
                
                if existing:
                    # 업데이트
                    metadata['updated_at'] = datetime.now()
                    for key, value in metadata.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    logger.debug(f"🔄 업데이트: {existing.symbol}({existing.coingecko_id})")
                else:
                    # 신규 추가
                    new_coin = CoinMaster(**metadata)
                    session.add(new_coin)
                    logger.debug(f"🆕 신규 추가: {new_coin.symbol}({new_coin.coingecko_id})")
                
                session.commit()
                self.stats["metadata_updated"] += 1
                
                if metadata.get('name_ko'):
                    self.stats["korean_names_updated"] += 1
                if metadata.get('image_url'):
                    self.stats["icons_updated"] += 1
                
                return True
                
        except Exception as e:
            logger.error(f"❌ {metadata['coingecko_id']} 저장 실패: {e}")
            self.stats["failed"] += 1
            return False
    
    def update_bithumb_korean_names(self):
        """빗썸 코인들에 CoinGecko 한글명 매핑"""
        logger.info("🏪 빗썸 코인 한글명 매핑...")
        
        updated_count = 0
        
        with db_manager.get_session_context() as session:
            # 한글명이 없는 빗썸 코인들 조회
            bithumb_coins = session.query(BithumbListing).filter(
                BithumbListing.is_active == True,
                BithumbListing.korean_name.is_(None)
            ).all()
            
            for bithumb_coin in bithumb_coins:
                # coin_master에서 해당 심볼의 한글명 찾기
                coin_master = session.query(CoinMaster).filter_by(
                    symbol=bithumb_coin.symbol,
                    is_active=True
                ).first()
                
                if coin_master and coin_master.name_ko is not None and coin_master.name_ko.strip():
                    bithumb_coin.korean_name = coin_master.name_ko
                    bithumb_coin.coingecko_id = coin_master.coingecko_id
                    updated_count += 1
                    logger.debug(f"🔄 {bithumb_coin.symbol} → {coin_master.name_ko}")
            
            session.commit()
        
        logger.info(f"✅ 빗썸 {updated_count}개 코인 한글명 매핑 완료")
        return updated_count
    
    def get_symbols_needing_metadata(self) -> List[str]:
        """메타데이터가 필요한 심볼들 조회"""
        with db_manager.get_session_context() as session:
            # 1. 업비트에 있지만 coin_master에 없는 심볼들
            upbit_symbols = session.query(UpbitListing.symbol).filter_by(is_active=True).all()
            upbit_symbols = [s[0] for s in upbit_symbols]
            
            # 2. 빗썸에 있지만 coin_master에 없는 심볼들
            bithumb_symbols = session.query(BithumbListing.symbol).filter_by(is_active=True).all()
            bithumb_symbols = [s[0] for s in bithumb_symbols]
            
            # 3. 전체 고유 심볼
            all_symbols = list(set(upbit_symbols + bithumb_symbols))
            
            # 4. coin_master에 이미 있는 심볼들
            existing_symbols = session.query(CoinMaster.symbol).filter_by(is_active=True).all()
            existing_symbols = [s[0] for s in existing_symbols]
            
            # 5. 누락된 심볼들
            missing_symbols = [s for s in all_symbols if s not in existing_symbols]
            
            logger.info(f"📊 메타데이터 수집 대상: {len(missing_symbols)}개 심볼")
            return missing_symbols
    
    async def collect_metadata_for_symbols(self, symbols: List[str]) -> int:
        """특정 심볼들의 메타데이터 수집"""
        logger.info(f"🔍 {len(symbols)}개 심볼 메타데이터 수집 시작...")
        
        success_count = 0
        
        for symbol in symbols:
            try:
                # CoinGecko ID 찾기
                coin_id = self.symbol_to_id_cache.get(symbol)
                if not coin_id:
                    logger.warning(f"⚠️ {symbol}: CoinGecko ID 없음")
                    continue
                
                # 메타데이터 조회
                metadata = await self.fetch_coin_metadata(coin_id)
                if not metadata:
                    continue
                
                # DB 저장
                if self.save_coin_metadata(metadata):
                    success_count += 1
                    logger.info(f"✅ {symbol}({metadata.get('name_ko', 'N/A')}) 수집 완료")
                
            except Exception as e:
                logger.error(f"❌ {symbol} 처리 실패: {e}")
                self.stats["failed"] += 1
        
        logger.info(f"🎉 메타데이터 수집 완료: {success_count}/{len(symbols)}")
        return success_count
    
    async def collect_all_metadata(self) -> Dict[str, int]:
        """전체 메타데이터 수집 프로세스"""
        logger.info("🚀 CoinGecko 메타데이터 전체 수집 시작")
        
        start_time = time.time()
        
        try:
            # 1. CoinGecko 코인 목록 조회
            await self.fetch_coins_list()
            
            # 2. 메타데이터가 필요한 심볼들 찾기
            symbols_needed = self.get_symbols_needing_metadata()
            
            if not symbols_needed:
                logger.info("✅ 모든 심볼의 메타데이터가 이미 있습니다")
                return {"updated": 0, "failed": 0}
            
            # 3. 우선순위 심볼 먼저 처리 (주요 코인)
            priority_symbols = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'LINK', 'MATIC']
            priority_needed = [s for s in priority_symbols if s in symbols_needed]
            regular_needed = [s for s in symbols_needed if s not in priority_symbols]
            
            # 4. 우선순위 심볼 수집
            if priority_needed:
                logger.info(f"⭐ 우선순위 {len(priority_needed)}개 심볼 수집...")
                await self.collect_metadata_for_symbols(priority_needed)
            
            # 5. 나머지 심볼 수집 (배치 처리)
            batch_size = 10  # Rate limit 고려
            for i in range(0, len(regular_needed), batch_size):
                batch = regular_needed[i:i + batch_size]
                logger.info(f"📦 배치 {i//batch_size + 1}: {len(batch)}개 심볼 수집...")
                await self.collect_metadata_for_symbols(batch)
                
                # 배치 간 휴식
                if i + batch_size < len(regular_needed):
                    await asyncio.sleep(5)
            
            # 6. 빗썸 한글명 매핑
            bithumb_updated = self.update_bithumb_korean_names()
            
            # 7. 통계 출력
            elapsed_time = time.time() - start_time
            self.print_collection_stats(elapsed_time)
            
            return {
                "metadata_updated": self.stats["metadata_updated"],
                "korean_names_updated": self.stats["korean_names_updated"],
                "icons_updated": self.stats["icons_updated"],
                "bithumb_mapped": bithumb_updated,
                "failed": self.stats["failed"]
            }
            
        except Exception as e:
            logger.error(f"❌ 메타데이터 수집 실패: {e}")
            raise
    
    def print_collection_stats(self, elapsed_time: float):
        """수집 통계 출력"""
        logger.info("\n📊 CoinGecko 메타데이터 수집 통계:")
        logger.info(f"   📋 CoinGecko 코인 목록: {self.stats['coins_list_fetched']:,}개")
        logger.info(f"   🔄 메타데이터 업데이트: {self.stats['metadata_updated']}개")
        logger.info(f"   🇰🇷 한글명 수집: {self.stats['korean_names_updated']}개")
        logger.info(f"   🖼️ 아이콘 URL 수집: {self.stats['icons_updated']}개")
        logger.info(f"   ❌ 실패: {self.stats['failed']}개")
        logger.info(f"   ⏱️ 소요 시간: {elapsed_time:.1f}초")
    
    def get_metadata_summary(self) -> Dict:
        """메타데이터 현황 요약"""
        with db_manager.get_session_context() as session:
            # coin_master 통계
            total_coins = session.query(CoinMaster).filter_by(is_active=True).count()
            coins_with_korean = session.query(CoinMaster).filter(
                CoinMaster.is_active == True,
                CoinMaster.name_ko.isnot(None)
            ).count()
            coins_with_icons = session.query(CoinMaster).filter(
                CoinMaster.is_active == True,
                CoinMaster.image_url.isnot(None)
            ).count()
            
            # 한국 거래소 한글명 커버리지
            upbit_total = session.query(UpbitListing).filter_by(is_active=True).count()
            bithumb_total = session.query(BithumbListing).filter_by(is_active=True).count()
            bithumb_with_korean = session.query(BithumbListing).filter(
                BithumbListing.is_active == True,
                BithumbListing.korean_name.isnot(None)
            ).count()
            
            return {
                "coin_master": {
                    "total_coins": total_coins,
                    "korean_names": coins_with_korean,
                    "korean_coverage": f"{(coins_with_korean/total_coins*100):.1f}%" if total_coins > 0 else "0%",
                    "icons": coins_with_icons,
                    "icon_coverage": f"{(coins_with_icons/total_coins*100):.1f}%" if total_coins > 0 else "0%"
                },
                "korean_exchanges": {
                    "upbit_coins": upbit_total,
                    "bithumb_coins": bithumb_total,
                    "bithumb_korean_names": bithumb_with_korean,
                    "bithumb_korean_coverage": f"{(bithumb_with_korean/bithumb_total*100):.1f}%" if bithumb_total > 0 else "0%"
                },
                "last_updated": datetime.now().isoformat()
            }

async def main():
    """메인 실행 함수"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        logger.info("🌍 CoinGecko 메타데이터 수집 시작")
        
        async with CoinGeckoMetadataCollector() as collector:
            # 전체 메타데이터 수집
            results = await collector.collect_all_metadata()
            
            # 현황 요약
            summary = collector.get_metadata_summary()
            
            logger.info(f"\n📈 메타데이터 현황 요약:")
            logger.info(f"   🌍 글로벌 코인: {summary['coin_master']['total_coins']}개")
            logger.info(f"   🇰🇷 한글명: {summary['coin_master']['korean_names']}개 ({summary['coin_master']['korean_coverage']})")
            logger.info(f"   🖼️ 아이콘: {summary['coin_master']['icons']}개 ({summary['coin_master']['icon_coverage']})")
            logger.info(f"   📱 업비트: {summary['korean_exchanges']['upbit_coins']}개 (한글명 100%)")
            logger.info(f"   🏪 빗썸: {summary['korean_exchanges']['bithumb_coins']}개 (한글명 {summary['korean_exchanges']['bithumb_korean_coverage']})")
        
        logger.info("🎉 CoinGecko 메타데이터 수집 완료!")
        return True
        
    except Exception as e:
        logger.error(f"❌ 메타데이터 수집 실패: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())