#!/usr/bin/env python3
"""
MEXC 거래소 코인 리스트 수집기
MEXC Spot V3 API를 사용하여 USDT 페어 데이터를 수집하고 데이터베이스에 저장합니다.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MEXCCoinCollector:
    """MEXC 코인 리스트 수집기"""
    
    def __init__(self):
        self.base_url = "https://api.mexc.com"
        self.session = None
        
        # 통계
        self.stats = {
            "total_symbols": 0,
            "usdt_pairs": 0,
            "saved_count": 0,
            "updated_count": 0,
            "failed_count": 0
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "ArbitrageWebsite-MEXCCollector/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    def create_mexc_table(self):
        """MEXC listings 테이블 생성"""
        logger.info("🔧 MEXC listings 테이블 생성...")
        
        try:
            with db_manager.get_session_context() as session:
                from sqlalchemy import text
                
                create_table_sql = '''
                CREATE TABLE IF NOT EXISTS mexc_listings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(50) NOT NULL COMMENT '거래 심볼',
                    base_asset VARCHAR(20) NOT NULL COMMENT '기본 자산',
                    quote_asset VARCHAR(20) NOT NULL COMMENT '견적 자산',
                    trading_pair VARCHAR(50) NOT NULL COMMENT '거래쌍',
                    status VARCHAR(20) DEFAULT 'TRADING' COMMENT '거래 상태',
                    full_name VARCHAR(100) COMMENT '풀네임',
                    is_spot_trading_allowed BOOLEAN DEFAULT TRUE COMMENT '스팟 거래 허용',
                    is_margin_trading_allowed BOOLEAN DEFAULT FALSE COMMENT '마진 거래 허용',
                    base_asset_precision INT DEFAULT 8 COMMENT '기본 자산 정밀도',
                    quote_asset_precision INT DEFAULT 8 COMMENT '견적 자산 정밀도',
                    order_types JSON COMMENT '주문 타입들',
                    max_quote_amount DECIMAL(20,8) COMMENT '최대 견적 금액',
                    maker_commission DECIMAL(10,6) DEFAULT 0 COMMENT '메이커 수수료',
                    taker_commission DECIMAL(10,6) DEFAULT 0 COMMENT '테이커 수수료',
                    contract_address VARCHAR(100) COMMENT '컨트랙트 주소',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '활성 상태',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_symbol (symbol),
                    INDEX idx_base_asset (base_asset),
                    INDEX idx_quote_asset (quote_asset),
                    INDEX idx_active (is_active),
                    INDEX idx_trading_allowed (is_spot_trading_allowed)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='MEXC 상장 코인 목록';
                '''
                
                session.execute(text(create_table_sql))
                session.commit()
                logger.info("✅ mexc_listings 테이블 생성 완료")
                
        except Exception as e:
            logger.error(f"❌ 테이블 생성 실패: {e}")
            raise
    
    async def fetch_mexc_exchange_info(self) -> list:
        """MEXC exchangeInfo API로부터 거래 정보 수집"""
        logger.info("🌐 MEXC exchangeInfo API 호출...")
        
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        try:
            url = f"{self.base_url}/api/v3/exchangeInfo"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"MEXC API 오류: {response.status}")
                
                data = await response.json()
                symbols_data = data.get('symbols', [])
                
                self.stats["total_symbols"] = len(symbols_data)
                logger.info(f"📊 전체 심볼 수: {len(symbols_data)}개")
                
                # USDT 페어만 필터링
                usdt_pairs = []
                for symbol_info in symbols_data:
                    if (symbol_info.get('quoteAsset') == 'USDT' and 
                        symbol_info.get('isSpotTradingAllowed', False)):
                        
                        # 데이터 정리
                        cleaned_data = {
                            'symbol': symbol_info.get('symbol', ''),
                            'base_asset': symbol_info.get('baseAsset', ''),
                            'quote_asset': symbol_info.get('quoteAsset', ''),
                            'status': 'TRADING' if symbol_info.get('status') == 1 else 'INACTIVE',
                            'full_name': symbol_info.get('fullName', ''),
                            'is_spot_trading_allowed': symbol_info.get('isSpotTradingAllowed', False),
                            'is_margin_trading_allowed': symbol_info.get('isMarginTradingAllowed', False),
                            'base_asset_precision': symbol_info.get('baseAssetPrecision', 8),
                            'quote_asset_precision': symbol_info.get('quoteAssetPrecision', 8),
                            'order_types': symbol_info.get('orderTypes', []),
                            'max_quote_amount': symbol_info.get('maxQuoteAmount'),
                            'maker_commission': symbol_info.get('makerCommission', 0),
                            'taker_commission': symbol_info.get('takerCommission', 0),
                            'contract_address': symbol_info.get('contractAddress', '')
                        }
                        
                        usdt_pairs.append(cleaned_data)
                
                self.stats["usdt_pairs"] = len(usdt_pairs)
                logger.info(f"✅ USDT 페어 수: {len(usdt_pairs)}개 필터링 완료")
                
                # 처음 5개와 마지막 5개 로그
                logger.info("📋 처음 5개 USDT 페어:")
                for i, pair in enumerate(usdt_pairs[:5]):
                    logger.info(f"   {i+1}. {pair['symbol']} ({pair['base_asset']}/{pair['quote_asset']})")
                
                logger.info("📋 마지막 5개 USDT 페어:")
                for i, pair in enumerate(usdt_pairs[-5:]):
                    logger.info(f"   {len(usdt_pairs)-4+i}. {pair['symbol']} ({pair['base_asset']}/{pair['quote_asset']})")
                
                return usdt_pairs
                
        except Exception as e:
            logger.error(f"❌ MEXC API 호출 실패: {e}")
            raise
    
    def save_mexc_data(self, usdt_pairs: list):
        """MEXC 데이터를 데이터베이스에 저장"""
        logger.info("💾 MEXC 데이터 저장 시작...")
        
        try:
            with db_manager.get_session_context() as session:
                from sqlalchemy import text
                import json
                
                # 기존 데이터 비활성화
                session.execute(text("UPDATE mexc_listings SET is_active = FALSE WHERE 1=1"))
                
                saved_count = 0
                updated_count = 0
                failed_count = 0
                
                for pair in usdt_pairs:
                    try:
                        # JSON 데이터 준비
                        order_types_json = json.dumps(pair['order_types']) if pair['order_types'] else None
                        
                        # trading_pair 생성
                        trading_pair = f"{pair['base_asset']}/{pair['quote_asset']}"
                        
                        # 데이터 삽입/업데이트
                        session.execute(text('''
                            INSERT INTO mexc_listings 
                            (symbol, base_asset, quote_asset, trading_pair, status, full_name,
                             is_spot_trading_allowed, is_margin_trading_allowed, 
                             base_asset_precision, quote_asset_precision, order_types,
                             max_quote_amount, maker_commission, taker_commission, 
                             contract_address, is_active, last_updated)
                            VALUES 
                            (:symbol, :base_asset, :quote_asset, :trading_pair, :status, :full_name,
                             :is_spot_trading_allowed, :is_margin_trading_allowed,
                             :base_asset_precision, :quote_asset_precision, :order_types,
                             :max_quote_amount, :maker_commission, :taker_commission,
                             :contract_address, TRUE, NOW())
                            ON DUPLICATE KEY UPDATE
                            base_asset = VALUES(base_asset),
                            quote_asset = VALUES(quote_asset),
                            trading_pair = VALUES(trading_pair),
                            status = VALUES(status),
                            full_name = VALUES(full_name),
                            is_spot_trading_allowed = VALUES(is_spot_trading_allowed),
                            is_margin_trading_allowed = VALUES(is_margin_trading_allowed),
                            base_asset_precision = VALUES(base_asset_precision),
                            quote_asset_precision = VALUES(quote_asset_precision),
                            order_types = VALUES(order_types),
                            max_quote_amount = VALUES(max_quote_amount),
                            maker_commission = VALUES(maker_commission),
                            taker_commission = VALUES(taker_commission),
                            contract_address = VALUES(contract_address),
                            is_active = TRUE,
                            last_updated = NOW()
                        '''), {
                            'symbol': pair['symbol'],
                            'base_asset': pair['base_asset'],
                            'quote_asset': pair['quote_asset'],
                            'trading_pair': trading_pair,
                            'status': pair['status'],
                            'full_name': pair['full_name'][:100] if pair['full_name'] else None,
                            'is_spot_trading_allowed': pair['is_spot_trading_allowed'],
                            'is_margin_trading_allowed': pair['is_margin_trading_allowed'],
                            'base_asset_precision': pair['base_asset_precision'],
                            'quote_asset_precision': pair['quote_asset_precision'],
                            'order_types': order_types_json,
                            'max_quote_amount': pair['max_quote_amount'],
                            'maker_commission': pair['maker_commission'],
                            'taker_commission': pair['taker_commission'],
                            'contract_address': pair['contract_address'][:100] if pair['contract_address'] else None
                        })
                        
                        saved_count += 1
                        
                        if pair['full_name']:
                            updated_count += 1
                        
                    except Exception as e:
                        failed_count += 1
                        logger.warning(f"⚠️ {pair['symbol']} 저장 실패: {e}")
                        continue
                
                session.commit()
                
                self.stats["saved_count"] = saved_count
                self.stats["updated_count"] = updated_count
                self.stats["failed_count"] = failed_count
                
                logger.info(f"✅ MEXC 데이터 저장 완료:")
                logger.info(f"   💾 저장된 코인: {saved_count}개")
                logger.info(f"   📝 메타데이터 포함: {updated_count}개")
                logger.info(f"   ❌ 실패: {failed_count}개")
                
        except Exception as e:
            logger.error(f"❌ 데이터 저장 실패: {e}")
            raise
    
    def verify_results(self):
        """저장 결과 검증"""
        logger.info("🔍 MEXC 데이터 저장 결과 검증...")
        
        try:
            with db_manager.get_session_context() as session:
                from sqlalchemy import text
                
                # 전체 통계
                total_count = session.execute(text("SELECT COUNT(*) FROM mexc_listings WHERE is_active = TRUE")).scalar()
                
                # 메타데이터 통계
                with_fullname = session.execute(text("SELECT COUNT(*) FROM mexc_listings WHERE is_active = TRUE AND full_name IS NOT NULL AND full_name != ''")).scalar()
                
                # 거래 상태별 통계
                trading_count = session.execute(text("SELECT COUNT(*) FROM mexc_listings WHERE is_active = TRUE AND status = 'TRADING'")).scalar()
                
                # 최근 업데이트된 코인들
                recent_coins = session.execute(text("""
                    SELECT symbol, base_asset, quote_asset, full_name, status 
                    FROM mexc_listings 
                    WHERE is_active = TRUE 
                    ORDER BY last_updated DESC 
                    LIMIT 10
                """)).fetchall()
                
                logger.info(f"\n📊 MEXC 데이터 검증 결과:")
                logger.info(f"   📊 전체 활성 코인: {total_count:,}개")
                logger.info(f"   📝 풀네임 포함: {with_fullname:,}개")
                logger.info(f"   ✅ 거래 가능: {trading_count:,}개")
                
                logger.info(f"\n🔍 최근 업데이트된 코인 (상위 10개):")
                for coin in recent_coins:
                    full_name = coin[3] if coin[3] else 'N/A'
                    logger.info(f"   {coin[0]} ({coin[1]}/{coin[2]}) - {full_name} [{coin[4]}]")
                
                return {
                    "total_count": total_count,
                    "with_fullname": with_fullname,
                    "trading_count": trading_count
                }
                
        except Exception as e:
            logger.error(f"❌ 결과 검증 실패: {e}")
            return {}
    
    def print_collection_summary(self, elapsed_time):
        """수집 결과 요약 출력"""
        logger.info("\n" + "="*80)
        logger.info("📊 MEXC 코인 리스트 수집 완료")
        logger.info("="*80)
        
        logger.info(f"\n🌐 API 수집 결과:")
        logger.info(f"   📊 전체 심볼: {self.stats['total_symbols']:,}개")
        logger.info(f"   💰 USDT 페어: {self.stats['usdt_pairs']:,}개")
        
        logger.info(f"\n💾 데이터베이스 저장:")
        logger.info(f"   ✅ 저장 성공: {self.stats['saved_count']:,}개")
        logger.info(f"   📝 메타데이터 포함: {self.stats['updated_count']:,}개")
        logger.info(f"   ❌ 저장 실패: {self.stats['failed_count']:,}개")
        
        logger.info(f"\n⏱️ 수집 시간: {elapsed_time:.1f}초")
        
        success_rate = (self.stats['saved_count'] / self.stats['usdt_pairs'] * 100) if self.stats['usdt_pairs'] > 0 else 0
        logger.info(f"🎯 성공률: {success_rate:.1f}%")
        
        logger.info("\n" + "="*80)

async def main():
    """메인 실행 함수"""
    try:
        logger.info("🚀 MEXC 코인 리스트 수집 시작")
        start_time = time.time()
        
        async with MEXCCoinCollector() as collector:
            # 1. 테이블 생성
            collector.create_mexc_table()
            
            # 2. MEXC API에서 데이터 수집
            usdt_pairs = await collector.fetch_mexc_exchange_info()
            
            # 3. 데이터베이스에 저장
            collector.save_mexc_data(usdt_pairs)
            
            # 4. 결과 검증
            results = collector.verify_results()
            
            # 5. 요약 출력
            elapsed_time = time.time() - start_time
            collector.print_collection_summary(elapsed_time)
            
            logger.info(f"🎉 MEXC 코인 리스트 수집 완료! ({results.get('total_count', 0)}개 코인)")
            return True
            
    except Exception as e:
        logger.error(f"❌ MEXC 수집 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(main())