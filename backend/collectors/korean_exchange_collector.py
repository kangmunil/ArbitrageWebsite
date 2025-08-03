#!/usr/bin/env python3
"""
분리된 한국거래소 데이터 수집기
업비트와 빗썸을 각각 독립적으로 수집하여 분리된 테이블에 저장
"""

import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db_manager, UpbitListing, BithumbListing, settings

logger = logging.getLogger(__name__)

class KoreanExchangeCollector:
    """한국 거래소 (업비트, 빗썸) 데이터 수집기"""
    
    def __init__(self):
        self.session = None
        self.upbit_api_url = "https://api.upbit.com/v1/market/all"
        self.bithumb_api_url = "https://api.bithumb.com/public/ticker/all_KRW"
        
        # 수집 통계
        self.stats = {
            "upbit": {"total": 0, "success": 0, "failed": 0},
            "bithumb": {"total": 0, "success": 0, "failed": 0}
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "KimchiPremium-Collector/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def collect_upbit_listings(self) -> List[Dict]:
        """업비트 상장 코인 수집"""
        logger.info("📊 업비트 상장 코인 수집 시작...")
        
        try:
            async with self.session.get(self.upbit_api_url) as response:
                if response.status != 200:
                    raise Exception(f"업비트 API 오류: {response.status}")
                
                data = await response.json()
                
                upbit_listings = []
                for item in data:
                    market = item.get("market", "")
                    
                    # KRW 마켓만 수집
                    if market.startswith("KRW-"):
                        symbol = market.split("-")[1]
                        listing = {
                            "market": market,
                            "symbol": symbol,
                            "korean_name": item.get("korean_name", symbol),
                            "english_name": item.get("english_name", ""),
                            "market_warning": item.get("market_warning", None),
                            "is_active": True
                        }
                        upbit_listings.append(listing)
                        self.stats["upbit"]["success"] += 1
                    
                    self.stats["upbit"]["total"] += 1
                
                logger.info(f"✅ 업비트: {len(upbit_listings)}개 KRW 마켓 수집 완료")
                return upbit_listings
                
        except Exception as e:
            logger.error(f"❌ 업비트 수집 실패: {e}")
            self.stats["upbit"]["failed"] = self.stats["upbit"]["total"]
            raise
    
    async def collect_bithumb_listings(self) -> List[Dict]:
        """빗썸 상장 코인 수집"""
        logger.info("📊 빗썸 상장 코인 수집 시작...")
        
        try:
            async with self.session.get(self.bithumb_api_url) as response:
                if response.status != 200:
                    raise Exception(f"빗썸 API 오류: {response.status}")
                
                data = await response.json()
                
                if "data" not in data:
                    raise Exception("빗썸 API 응답 형식 오류")
                
                bithumb_listings = []
                for symbol, ticker_data in data["data"].items():
                    # 'date' 키는 타임스탬프이므로 제외
                    if symbol == "date" or not isinstance(ticker_data, dict):
                        continue
                    
                    # 거래 가능한 코인만 수집 (가격 정보가 있는 것)
                    if "closing_price" in ticker_data and ticker_data["closing_price"] != "0":
                        listing = {
                            "symbol": symbol,
                            "korean_name": None,  # 빗썸은 한글명 API 제공 안함
                            "coingecko_id": None,  # 나중에 매핑
                            "is_active": True
                        }
                        bithumb_listings.append(listing)
                        self.stats["bithumb"]["success"] += 1
                    
                    self.stats["bithumb"]["total"] += 1
                
                logger.info(f"✅ 빗썸: {len(bithumb_listings)}개 활성 코인 수집 완료")
                return bithumb_listings
                
        except Exception as e:
            logger.error(f"❌ 빗썸 수집 실패: {e}")
            self.stats["bithumb"]["failed"] = self.stats["bithumb"]["total"]
            raise
    
    def save_upbit_listings(self, listings: List[Dict]) -> int:
        """업비트 상장 정보 DB 저장"""
        logger.info(f"💾 업비트 상장 정보 저장: {len(listings)}개")
        
        saved_count = 0
        
        with db_manager.get_session_context() as session:
            # 기존 데이터 비활성화
            session.query(UpbitListing).update({"is_active": False})
            
            for listing_data in listings:
                try:
                    # 기존 레코드 확인
                    existing = session.query(UpbitListing).filter_by(
                        market=listing_data["market"]
                    ).first()
                    
                    if existing:
                        # 업데이트
                        for key, value in listing_data.items():
                            setattr(existing, key, value)
                        existing.last_updated = datetime.now()
                        logger.debug(f"🔄 업데이트: {existing.market}")
                    else:
                        # 신규 추가
                        new_listing = UpbitListing(**listing_data)
                        session.add(new_listing)
                        logger.debug(f"🆕 신규 추가: {new_listing.market}")
                    
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ {listing_data.get('market')} 저장 실패: {e}")
            
            session.commit()
        
        logger.info(f"✅ 업비트 {saved_count}개 저장 완료")
        return saved_count
    
    def save_bithumb_listings(self, listings: List[Dict]) -> int:
        """빗썸 상장 정보 DB 저장"""
        logger.info(f"💾 빗썸 상장 정보 저장: {len(listings)}개")
        
        saved_count = 0
        
        with db_manager.get_session_context() as session:
            # 기존 데이터 비활성화
            session.query(BithumbListing).update({"is_active": False})
            
            for listing_data in listings:
                try:
                    # 기존 레코드 확인
                    existing = session.query(BithumbListing).filter_by(
                        symbol=listing_data["symbol"]
                    ).first()
                    
                    if existing:
                        # 업데이트 (한글명이 없으면 유지)
                        existing.is_active = listing_data["is_active"]
                        existing.last_updated = datetime.now()
                        logger.debug(f"🔄 업데이트: {existing.symbol}")
                    else:
                        # 신규 추가
                        new_listing = BithumbListing(**listing_data)
                        session.add(new_listing)
                        logger.debug(f"🆕 신규 추가: {new_listing.symbol}")
                    
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ {listing_data.get('symbol')} 저장 실패: {e}")
            
            session.commit()
        
        logger.info(f"✅ 빗썸 {saved_count}개 저장 완료")
        return saved_count
    
    async def collect_all_korean_exchanges(self) -> Dict[str, int]:
        """모든 한국 거래소 데이터 수집 및 저장"""
        logger.info("🇰🇷 한국 거래소 전체 데이터 수집 시작")
        
        results = {"upbit": 0, "bithumb": 0}
        
        try:
            # 1. 업비트 수집 및 저장
            upbit_listings = await self.collect_upbit_listings()
            results["upbit"] = self.save_upbit_listings(upbit_listings)
            
            # 2. 빗썸 수집 및 저장  
            bithumb_listings = await self.collect_bithumb_listings()
            results["bithumb"] = self.save_bithumb_listings(bithumb_listings)
            
            # 3. 수집 통계 출력
            self.print_collection_stats()
            
            logger.info(f"🎉 한국 거래소 수집 완료: 업비트 {results['upbit']}개, 빗썸 {results['bithumb']}개")
            return results
            
        except Exception as e:
            logger.error(f"❌ 한국 거래소 수집 실패: {e}")
            raise
    
    def print_collection_stats(self):
        """수집 통계 출력"""
        logger.info("\n📊 수집 통계:")
        logger.info(f"   업비트: 총 {self.stats['upbit']['total']}개, 성공 {self.stats['upbit']['success']}개, 실패 {self.stats['upbit']['failed']}개")
        logger.info(f"   빗썸: 총 {self.stats['bithumb']['total']}개, 성공 {self.stats['bithumb']['success']}개, 실패 {self.stats['bithumb']['failed']}개")
    
    def get_korean_exchange_summary(self) -> Dict:
        """한국 거래소 요약 정보 반환"""
        with db_manager.get_session_context() as session:
            upbit_count = session.query(UpbitListing).filter_by(is_active=True).count()
            bithumb_count = session.query(BithumbListing).filter_by(is_active=True).count()
            
            # 공통 코인 찾기
            upbit_symbols = session.query(UpbitListing.symbol).filter_by(is_active=True).all()
            bithumb_symbols = session.query(BithumbListing.symbol).filter_by(is_active=True).all()
            
            upbit_set = {symbol[0] for symbol in upbit_symbols}
            bithumb_set = {symbol[0] for symbol in bithumb_symbols}
            
            common_symbols = upbit_set.intersection(bithumb_set)
            
            return {
                "upbit": {
                    "total_coins": upbit_count,
                    "unique_coins": len(upbit_set - bithumb_set),
                },
                "bithumb": {
                    "total_coins": bithumb_count,
                    "unique_coins": len(bithumb_set - upbit_set),
                },
                "common_coins": len(common_symbols),
                "total_unique_coins": len(upbit_set.union(bithumb_set)),
                "last_updated": datetime.now().isoformat()
            }

async def main():
    """메인 실행 함수"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        logger.info("🚀 한국 거래소 데이터 수집 시작")
        
        async with KoreanExchangeCollector() as collector:
            # 전체 수집 실행
            results = await collector.collect_all_korean_exchanges()
            
            # 요약 정보 출력
            summary = collector.get_korean_exchange_summary()
            logger.info(f"\n📈 한국 거래소 요약:")
            logger.info(f"   업비트: {summary['upbit']['total_coins']}개 (독점 {summary['upbit']['unique_coins']}개)")
            logger.info(f"   빗썸: {summary['bithumb']['total_coins']}개 (독점 {summary['bithumb']['unique_coins']}개)")
            logger.info(f"   공통 코인: {summary['common_coins']}개")
            logger.info(f"   전체 고유 코인: {summary['total_unique_coins']}개")
        
        logger.info("🎉 한국 거래소 데이터 수집 완료!")
        
    except Exception as e:
        logger.error(f"❌ 수집 실패: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main())