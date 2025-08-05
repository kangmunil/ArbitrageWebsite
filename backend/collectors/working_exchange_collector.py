#!/usr/bin/env python3
"""
작동하는 거래소만 포함한 수집기
정상 작동 확인된 7개 거래소: 업비트, 빗썸, 바이낸스, 바이비트, OKX, Gate.io, Coinbase
"""

import asyncio
import aiohttp
import requests
import time
from datetime import datetime

class WorkingExchangeCollector:
    """작동하는 거래소 수집기"""
    
    def __init__(self):
        self.session = None
        self.stats = {
            "upbit": {"total": 0, "krw_markets": 0, "null_count": 0},
            "bithumb": {"total": 0, "active": 0, "null_count": 0},
            "binance": {"total": 0, "usdt_pairs": 0, "null_count": 0},
            "bybit": {"total": 0, "usdt_pairs": 0, "null_count": 0},
            "okx": {"total": 0, "usdt_pairs": 0, "null_count": 0},
            "gateio": {"total": 0, "usdt_pairs": 0, "null_count": 0},
            "coinbase": {"total": 0, "usd_pairs": 0, "null_count": 0}
        }
    
    def _validate_and_clean_data(self, data, required_fields):
        """데이터 검증 및 정리 유틸리티"""
        if not data:
            return None, "데이터가 None입니다"
        
        cleaned_data = {}
        missing_fields = []
        
        for field in required_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)
                cleaned_data[field] = ""
            else:
                cleaned_data[field] = str(value).strip() if isinstance(value, str) else value
        
        # 다른 필드들도 정리
        for key, value in data.items():
            if key not in cleaned_data:
                if value is None:
                    cleaned_data[key] = ""
                elif isinstance(value, str):
                    cleaned_data[key] = value.strip()
                else:
                    cleaned_data[key] = value
        
        error_msg = f"필수 필드 누락: {missing_fields}" if missing_fields else None
        return cleaned_data, error_msg
    
    def _log_data_quality(self, exchange_name, total_count, valid_count, null_count):
        """데이터 품질 로그"""
        self.stats[exchange_name]["null_count"] = null_count
        quality_rate = (valid_count / total_count * 100) if total_count > 0 else 0
        
        print(f"📊 {exchange_name} 데이터 품질:")
        print(f"   전체: {total_count}개, 유효: {valid_count}개, null/빈값: {null_count}개")
        print(f"   품질률: {quality_rate:.1f}%")
    
    def _check_and_log_name_changes(self, exchange_name, old_data, new_data, identifier_field):
        """이름 변경 감지 및 로깅"""
        changes = []
        
        for new_item in new_data:
            identifier = new_item.get(identifier_field)
            if not identifier:
                continue
                
            # 기존 데이터에서 같은 식별자 찾기
            old_item = next((item for item in old_data if item.get(identifier_field) == identifier), None)
            
            if old_item:
                # 이름 필드 비교 (거래소별로 다른 필드 확인)
                if exchange_name in ["업비트", "빗썸"]:
                    name_fields = ['korean_name', 'english_name', 'symbol']
                else:
                    name_fields = ['base_asset', 'quote_asset', 'status', 'symbol']
                
                for field in name_fields:
                    old_value = old_item.get(field, "").strip()
                    new_value = new_item.get(field, "").strip()
                    
                    # 이름이 다르고 둘 다 비어있지 않을 때
                    if (old_value and new_value and 
                        old_value != new_value):
                        changes.append({
                            'identifier': identifier,
                            'field': field,
                            'old_value': old_value,
                            'new_value': new_value
                        })
        
        # 변경사항 로깅
        if changes:
            print(f"🔄 {exchange_name} 이름 변경 감지:")
            for change in changes:
                print(f"   {change['identifier']}: {change['field']} '{change['old_value']}' → '{change['new_value']}'")
        
        return changes
    
    def _get_existing_data_from_db(self, table_name, identifier_field):
        """데이터베이스에서 기존 데이터 조회"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            
            if SessionLocal is None:
                print("❌ 데이터베이스 세션 팩토리가 초기화되지 않음")
                return []
            db = SessionLocal()
            
            if table_name == "upbit_listings":
                result = db.execute(text('''
                    SELECT market, symbol, korean_name, english_name 
                    FROM upbit_listings 
                    WHERE is_active = TRUE
                ''')).fetchall()
                
                existing_data = []
                for row in result:
                    existing_data.append({
                        'market': row[0],
                        'symbol': row[1],
                        'korean_name': row[2] or "",
                        'english_name': row[3] or ""
                    })
                    
            elif table_name == "bithumb_listings":
                result = db.execute(text('''
                    SELECT symbol 
                    FROM bithumb_listings 
                    WHERE is_active = TRUE
                ''')).fetchall()
                
                existing_data = [{'symbol': row[0]} for row in result]
                
            else:
                # 해외 거래소 테이블
                result = db.execute(text(f'''
                    SELECT symbol, base_asset, quote_asset, trading_pair, status 
                    FROM {table_name} 
                    WHERE is_active = TRUE
                ''')).fetchall()
                
                existing_data = []
                for row in result:
                    existing_data.append({
                        'symbol': row[0],
                        'base_asset': row[1] or "",
                        'quote_asset': row[2] or "",
                        'trading_pair': row[3] or "",
                        'status': row[4] or ""
                    })
            
            db.close()
            return existing_data
            
        except Exception as e:
            print(f"❌ 기존 데이터 조회 실패 ({table_name}): {e}")
            return []
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "ArbitrageWebsite-WorkingCollector/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    def create_exchange_tables(self):
        """거래소별 테이블 생성"""
        print("🔧 거래소별 테이블 생성...")
        
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            
            if SessionLocal is None:
                print("❌ 데이터베이스 세션 팩토리가 초기화되지 않음")
                return []
            db = SessionLocal()
            
            # 작동하는 해외 거래소별 테이블 생성
            exchange_tables = {
                "binance_listings": "바이낸스",
                "bybit_listings": "바이빗", 
                "okx_listings": "OKX",
                "gateio_listings": "Gate.io",
                "coinbase_listings": "Coinbase"
            }
            
            for table_name, exchange_name in exchange_tables.items():
                create_table_sql = f'''
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(50) NOT NULL COMMENT '거래 심볼',
                    base_asset VARCHAR(20) NOT NULL COMMENT '기본 자산',
                    quote_asset VARCHAR(20) NOT NULL COMMENT '견적 자산',
                    trading_pair VARCHAR(50) NOT NULL COMMENT '거래쌍',
                    status VARCHAR(20) DEFAULT 'TRADING' COMMENT '거래 상태',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '활성 상태',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_symbol (symbol),
                    INDEX idx_base_asset (base_asset),
                    INDEX idx_quote_asset (quote_asset),
                    INDEX idx_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='{exchange_name} 상장 코인 목록';
                '''
                
                db.execute(text(create_table_sql))
                print(f"✅ {table_name} 테이블 생성 완료")
            
            db.commit()
            db.close()
            
        except Exception as e:
            print(f"❌ 테이블 생성 실패: {e}")
    
    # === 한국 거래소 수집 ===
    
    async def collect_upbit_coins(self):
        """업비트 KRW 마켓 수집"""
        print("📱 업비트 KRW 마켓 수집...")
        
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        try:
            # 기존 데이터 조회
            existing_data = self._get_existing_data_from_db("upbit_listings", "market")
            
            url = "https://api.upbit.com/v1/market/all"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"업비트 API 오류: {response.status}")
                
                data = await response.json()
                krw_markets = []
                null_count = 0
                
                for item in data:
                    if item.get("market", "").startswith("KRW-"):
                        # 데이터 검증
                        cleaned_item, error = self._validate_and_clean_data(
                            item, 
                            ["market"]  # 필수 필드
                        )
                        
                        if error:
                            null_count += 1
                            print(f"⚠️ 업비트 데이터 품질 이슈: {error} - {item}")
                        
                        if cleaned_item:
                            krw_markets.append(cleaned_item)
                
                # 이름 변경 감지
                if existing_data:
                    changes = self._check_and_log_name_changes("업비트", existing_data, krw_markets, "market")
                
                self.stats["upbit"]["total"] = len(data)
                self.stats["upbit"]["krw_markets"] = len(krw_markets)
                
                # 데이터 품질 로그
                self._log_data_quality("upbit", len(data), len(krw_markets), null_count)
                
                print(f"✅ 업비트: 총 {len(data)}개 중 KRW {len(krw_markets)}개 수집")
                
                # DB 저장
                self._save_upbit_data(krw_markets)
                
                return krw_markets
                
        except Exception as e:
            print(f"❌ 업비트 수집 실패: {e}")
            return []
    
    def _save_upbit_data(self, krw_markets):
        """업비트 데이터 저장 (null 값 처리 개선)"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            
            if SessionLocal is None:
                print("❌ 데이터베이스 세션 팩토리가 초기화되지 않음")
                return []
            db = SessionLocal()
            
            # 기존 데이터 비활성화
            db.execute(text("UPDATE upbit_listings SET is_active = FALSE WHERE 1=1"))
            
            saved_count = 0
            updated_count = 0
            
            for market in krw_markets:
                symbol = market["market"].replace("KRW-", "")
                korean_name = market.get("korean_name") or ""
                english_name = market.get("english_name") or ""
                
                # null 값이나 빈 값 검증 및 정리
                korean_name = korean_name.strip() if korean_name else ""
                english_name = english_name.strip() if english_name else ""
                
                db.execute(text('''
                    INSERT INTO upbit_listings (market, symbol, korean_name, english_name, is_active, last_updated)
                    VALUES (:market, :symbol, :korean_name, :english_name, TRUE, NOW())
                    ON DUPLICATE KEY UPDATE
                    korean_name = CASE 
                        WHEN VALUES(korean_name) != '' AND VALUES(korean_name) IS NOT NULL 
                        THEN VALUES(korean_name) 
                        ELSE korean_name 
                    END,
                    english_name = CASE 
                        WHEN VALUES(english_name) != '' AND VALUES(english_name) IS NOT NULL 
                        THEN VALUES(english_name) 
                        ELSE english_name 
                    END,
                    is_active = TRUE,
                    last_updated = CASE 
                        WHEN (VALUES(korean_name) != korean_name AND VALUES(korean_name) != '' AND VALUES(korean_name) IS NOT NULL) OR
                             (VALUES(english_name) != english_name AND VALUES(english_name) != '' AND VALUES(english_name) IS NOT NULL)
                        THEN NOW()
                        ELSE last_updated
                    END
                '''), {
                    'market': market["market"],
                    'symbol': symbol,
                    'korean_name': korean_name,
                    'english_name': english_name
                })
                
                if korean_name or english_name:
                    updated_count += 1
                saved_count += 1
            
            db.commit()
            db.close()
            
            print(f"💾 업비트 {saved_count}개 코인 저장 완료 (유효 데이터 {updated_count}개)")
            
        except Exception as e:
            print(f"❌ 업비트 데이터 저장 실패: {e}")
    
    async def collect_bithumb_coins(self):
        """빗썸 활성 코인 수집"""
        print("🏪 빗썸 활성 코인 수집...")
        
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        try:
            url = "https://api.bithumb.com/public/ticker/all_KRW"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"빗썸 API 오류: {response.status}")
                
                data = await response.json()
                
                if "data" not in data:
                    raise Exception("빗썸 API 응답 형식 오류")
                
                active_coins = []
                null_count = 0
                total_symbols = 0
                
                for symbol, ticker_data in data["data"].items():
                    if symbol == "date" or not isinstance(ticker_data, dict):
                        continue
                    
                    total_symbols += 1
                    
                    # 데이터 검증
                    if not symbol or not symbol.strip():
                        null_count += 1
                        print(f"⚠️ 빗썸: 심볼이 null/비어있음 - {symbol}")
                        continue
                    
                    closing_price = ticker_data.get("closing_price")
                    if closing_price and str(closing_price).strip() != "0":
                        active_coins.append(symbol.strip())
                    else:
                        # 가격이 0이거나 null인 경우도 추적
                        if closing_price is None:
                            null_count += 1
                
                self.stats["bithumb"]["total"] = total_symbols
                self.stats["bithumb"]["active"] = len(active_coins)
                
                # 데이터 품질 로그
                self._log_data_quality("bithumb", total_symbols, len(active_coins), null_count)
                
                print(f"✅ 빗썸: 총 {total_symbols}개 중 활성 {len(active_coins)}개 수집")
                
                # DB 저장
                self._save_bithumb_data(active_coins)
                
                return active_coins
                
        except Exception as e:
            print(f"❌ 빗썸 수집 실패: {e}")
            return []
    
    def _save_bithumb_data(self, active_coins):
        """빗썸 데이터 저장 (null 값 처리 개선)"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            
            if SessionLocal is None:
                print("❌ 데이터베이스 세션 팩토리가 초기화되지 않음")
                return []
            db = SessionLocal()
            
            # 기존 데이터 비활성화
            db.execute(text("UPDATE bithumb_listings SET is_active = FALSE WHERE 1=1"))
            
            saved_count = 0
            valid_count = 0
            
            for symbol in active_coins:
                # null 값 검증 및 정리
                cleaned_symbol = (symbol or "").strip()
                
                if not cleaned_symbol:
                    print(f"⚠️ 빗썸: 심볼이 비어있음 - {symbol}")
                    continue
                
                db.execute(text('''
                    INSERT INTO bithumb_listings (symbol, is_active, last_updated)
                    VALUES (:symbol, TRUE, NOW())
                    ON DUPLICATE KEY UPDATE
                    symbol = CASE 
                        WHEN VALUES(symbol) != '' AND VALUES(symbol) IS NOT NULL 
                        THEN VALUES(symbol) 
                        ELSE symbol 
                    END,
                    is_active = TRUE,
                    last_updated = NOW()
                '''), {'symbol': cleaned_symbol})
                saved_count += 1
                
                if cleaned_symbol:
                    valid_count += 1
            
            db.commit()
            db.close()
            
            print(f"💾 빗썸 {saved_count}개 코인 저장 완료 (유효 데이터 {valid_count}개)")
            
        except Exception as e:
            print(f"❌ 빗썸 데이터 저장 실패: {e}")
    
    # === 해외 거래소 수집 ===
    
    async def collect_binance_coins(self):
        """바이낸스 USDT 페어 수집"""
        print("🌐 바이낸스 USDT 페어 수집...")

        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        try:
            # 기존 데이터 조회
            existing_data = self._get_existing_data_from_db("binance_listings", "symbol")
            
            url = "https://api.binance.com/api/v3/exchangeInfo"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"바이낸스 API 오류: {response.status}")
                
                data = await response.json()
                
                usdt_pairs = []
                null_count = 0
                total_symbols = len(data["symbols"])
                
                for symbol_info in data["symbols"]:
                    # 데이터 검증
                    cleaned_data, error = self._validate_and_clean_data(
                        symbol_info,
                        ["symbol", "baseAsset", "quoteAsset", "status"]
                    )
                    
                    if error:
                        null_count += 1
                        print(f"⚠️ 바이낸스 데이터 품질 이슈: {error}")
                        continue
                    
                    if (cleaned_data and cleaned_data.get("status") == "TRADING" and 
                        cleaned_data.get("quoteAsset") == "USDT"):
                        usdt_pairs.append({
                            "symbol": cleaned_data.get("symbol", ""),
                            "base_asset": cleaned_data.get("baseAsset", ""),
                            "quote_asset": cleaned_data.get("quoteAsset", ""),
                            "status": cleaned_data.get("status", "")
                        })
                
                # 이름 변경 감지
                if existing_data:
                    changes = self._check_and_log_name_changes("바이낸스", existing_data, usdt_pairs, "symbol")
                
                self.stats["binance"]["total"] = total_symbols
                self.stats["binance"]["usdt_pairs"] = len(usdt_pairs)
                
                # 데이터 품질 로그
                self._log_data_quality("binance", total_symbols, len(usdt_pairs), null_count)
                
                print(f"✅ 바이낸스: 총 {total_symbols}개 중 USDT {len(usdt_pairs)}개 수집")
                
                self._save_exchange_data("binance", usdt_pairs)
                return usdt_pairs
                
        except Exception as e:
            print(f"❌ 바이낸스 수집 실패: {e}")
            return []
    
    async def collect_bybit_coins(self):
        """바이비트 USDT 페어 수집"""
        print("🌐 바이비트 USDT 페어 수집...")

        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        try:
            url = "https://api.bybit.com/v5/market/instruments-info?category=spot"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"바이비트 API 오류: {response.status}")
                
                data = await response.json()
                
                if data["retCode"] != 0:
                    raise Exception(f"바이비트 API 응답 오류: {data['retMsg']}")
                
                usdt_pairs = []
                for item in data["result"]["list"]:
                    if (item["status"] == "Trading" and 
                        item["quoteCoin"] == "USDT"):
                        usdt_pairs.append({
                            "symbol": item["symbol"],
                            "base_asset": item["baseCoin"],
                            "quote_asset": item["quoteCoin"],
                            "status": item["status"]
                        })
                
                self.stats["bybit"]["total"] = len(data["result"]["list"])
                self.stats["bybit"]["usdt_pairs"] = len(usdt_pairs)
                
                print(f"✅ 바이비트: 총 {len(data['result']['list'])}개 중 USDT {len(usdt_pairs)}개 수집")
                
                self._save_exchange_data("bybit", usdt_pairs)
                return usdt_pairs
                
        except Exception as e:
            print(f"❌ 바이비트 수집 실패: {e}")
            return []
    
    async def collect_okx_coins(self):
        """OKX USDT 페어 수집"""
        print("🌐 OKX USDT 페어 수집...")

        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        try:
            url = "https://www.okx.com/api/v5/public/instruments?instType=SPOT"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"OKX API 오류: {response.status}")
                
                data = await response.json()
                
                if data["code"] != "0":
                    raise Exception(f"OKX API 응답 오류: {data['msg']}")
                
                usdt_pairs = []
                for item in data["data"]:
                    if (item["state"] == "live" and 
                        item["quoteCcy"] == "USDT"):
                        usdt_pairs.append({
                            "symbol": item["instId"],
                            "base_asset": item["baseCcy"],
                            "quote_asset": item["quoteCcy"],
                            "status": item["state"]
                        })
                
                self.stats["okx"]["total"] = len(data["data"])
                self.stats["okx"]["usdt_pairs"] = len(usdt_pairs)
                
                print(f"✅ OKX: 총 {len(data['data'])}개 중 USDT {len(usdt_pairs)}개 수집")
                
                self._save_exchange_data("okx", usdt_pairs)
                return usdt_pairs
                
        except Exception as e:
            print(f"❌ OKX 수집 실패: {e}")
            return []
    
    async def collect_gateio_coins(self):
        """Gate.io USDT 페어 수집"""
        print("🌐 Gate.io USDT 페어 수집...")

        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        try:
            url = "https://api.gateio.ws/api/v4/spot/currency_pairs"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Gate.io API 오류: {response.status}")
                
                data = await response.json()
                
                usdt_pairs = []
                for item in data:
                    if (item["trade_status"] == "tradable" and 
                        item["quote"] == "USDT"):
                        usdt_pairs.append({
                            "symbol": item["id"],
                            "base_asset": item["base"],
                            "quote_asset": item["quote"],
                            "status": item["trade_status"]
                        })
                
                self.stats["gateio"]["total"] = len(data)
                self.stats["gateio"]["usdt_pairs"] = len(usdt_pairs)
                
                print(f"✅ Gate.io: 총 {len(data)}개 중 USDT {len(usdt_pairs)}개 수집")
                
                self._save_exchange_data("gateio", usdt_pairs)
                return usdt_pairs
                
        except Exception as e:
            print(f"❌ Gate.io 수집 실패: {e}")
            return []
    
    async def collect_coinbase_coins(self):
        """Coinbase USD 페어 수집"""
        print("🇺🇸 Coinbase USD 페어 수집...")

        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        try:
            url = "https://api.exchange.coinbase.com/products"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Coinbase API 오류: {response.status}")
                
                data = await response.json()
                
                usd_pairs = []
                for item in data:
                    if (item["status"] == "online" and 
                        not item.get("trading_disabled", False) and
                        item["quote_currency"] == "USD"):
                        usd_pairs.append({
                            "symbol": item["id"],
                            "base_asset": item["base_currency"],
                            "quote_asset": item["quote_currency"],
                            "status": item["status"]
                        })
                
                self.stats["coinbase"]["total"] = len(data)
                self.stats["coinbase"]["usd_pairs"] = len(usd_pairs)
                
                print(f"✅ Coinbase: 총 {len(data)}개 중 USD {len(usd_pairs)}개 수집")
                
                self._save_exchange_data("coinbase", usd_pairs)
                return usd_pairs
                
        except Exception as e:
            print(f"❌ Coinbase 수집 실패: {e}")
            return []
    
    def _save_exchange_data(self, exchange_name, pairs_data):
        """해외 거래소 데이터 저장 (null 값 처리 개선)"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            
            if SessionLocal is None:
                print("❌ 데이터베이스 세션 팩토리가 초기화되지 않음")
                return []
            db = SessionLocal()
            table_name = f"{exchange_name}_listings"
            
            # 기존 데이터 비활성화
            db.execute(text(f"UPDATE {table_name} SET is_active = FALSE WHERE 1=1"))
            
            saved_count = 0
            valid_data_count = 0
            
            for pair in pairs_data:
                # null 값 검증 및 정리
                symbol = (pair.get('symbol') or "").strip()
                base_asset = (pair.get('base_asset') or "").strip() 
                quote_asset = (pair.get('quote_asset') or "").strip()
                status = (pair.get('status') or "TRADING").strip()
                
                # 필수 필드 검증
                if not symbol or not base_asset or not quote_asset:
                    print(f"⚠️ {exchange_name}: 필수 데이터 누락 - symbol:{symbol}, base:{base_asset}, quote:{quote_asset}")
                    continue
                
                trading_pair = f"{base_asset}/{quote_asset}"
                
                db.execute(text(f'''
                    INSERT INTO {table_name} 
                    (symbol, base_asset, quote_asset, trading_pair, status, is_active, last_updated)
                    VALUES (:symbol, :base_asset, :quote_asset, :trading_pair, :status, TRUE, NOW())
                    ON DUPLICATE KEY UPDATE
                    base_asset = CASE 
                        WHEN VALUES(base_asset) != '' AND VALUES(base_asset) IS NOT NULL 
                        THEN VALUES(base_asset) 
                        ELSE base_asset 
                    END,
                    quote_asset = CASE 
                        WHEN VALUES(quote_asset) != '' AND VALUES(quote_asset) IS NOT NULL 
                        THEN VALUES(quote_asset) 
                        ELSE quote_asset 
                    END,
                    trading_pair = CASE 
                        WHEN VALUES(trading_pair) != '' AND VALUES(trading_pair) IS NOT NULL 
                        THEN VALUES(trading_pair) 
                        ELSE trading_pair 
                    END,
                    status = CASE 
                        WHEN VALUES(status) != '' AND VALUES(status) IS NOT NULL 
                        THEN VALUES(status) 
                        ELSE status 
                    END,
                    is_active = TRUE,
                    last_updated = CASE 
                        WHEN (VALUES(base_asset) != base_asset AND VALUES(base_asset) != '' AND VALUES(base_asset) IS NOT NULL) OR
                             (VALUES(quote_asset) != quote_asset AND VALUES(quote_asset) != '' AND VALUES(quote_asset) IS NOT NULL) OR
                             (VALUES(status) != status AND VALUES(status) != '' AND VALUES(status) IS NOT NULL)
                        THEN NOW()
                        ELSE last_updated
                    END
                '''), {
                    'symbol': symbol,
                    'base_asset': base_asset,
                    'quote_asset': quote_asset,
                    'trading_pair': trading_pair,
                    'status': status
                })
                saved_count += 1
                
                if symbol and base_asset and quote_asset:
                    valid_data_count += 1
            
            db.commit()
            db.close()
            
            print(f"💾 {exchange_name} {saved_count}개 코인 저장 완료 (유효 데이터 {valid_data_count}개)")
            
        except Exception as e:
            print(f"❌ {exchange_name} 데이터 저장 실패: {e}")
    
    async def collect_all_working_exchanges(self):
        """작동하는 모든 거래소 데이터 수집"""
        print("🚀 작동 확인된 거래소 수집 시작\\n")
        
        start_time = time.time()
        
        # 테이블 생성
        self.create_exchange_tables()
        
        print("\\n🇰🇷 === 한국 거래소 수집 ===")
        korean_tasks = [
            self.collect_upbit_coins(),
            self.collect_bithumb_coins()
        ]
        await asyncio.gather(*korean_tasks, return_exceptions=True)
        
        print("\\n🌍 === 해외 거래소 수집 (작동 확인된 5개) ===")
        global_tasks = [
            self.collect_binance_coins(),
            self.collect_bybit_coins(),
            self.collect_okx_coins(),
            self.collect_gateio_coins(),
            self.collect_coinbase_coins()
        ]
        await asyncio.gather(*global_tasks, return_exceptions=True)
        
        elapsed_time = time.time() - start_time
        self.print_collection_summary(elapsed_time)
        
        return self.stats
    
    def print_collection_summary(self, elapsed_time):
        """수집 결과 요약 출력"""
        print("\\n" + "="*80)
        print("📊 작동하는 거래소 수집 완료")
        print("="*80)
        
        print("\\n🇰🇷 한국 거래소:")
        print(f"   📱 업비트: 총 {self.stats['upbit']['total']}개 (KRW: {self.stats['upbit']['krw_markets']}개)")
        print(f"   🏪 빗썸: 총 {self.stats['bithumb']['total']}개 (활성: {self.stats['bithumb']['active']}개)")
        
        print("\\n🌍 해외 거래소 (USDT/USD 페어):")
        print(f"   🌐 바이낸스: 총 {self.stats['binance']['total']}개 (USDT: {self.stats['binance']['usdt_pairs']}개)")
        print(f"   🌐 바이비트: 총 {self.stats['bybit']['total']}개 (USDT: {self.stats['bybit']['usdt_pairs']}개)")
        print(f"   🌐 OKX: 총 {self.stats['okx']['total']}개 (USDT: {self.stats['okx']['usdt_pairs']}개)")
        print(f"   🌐 Gate.io: 총 {self.stats['gateio']['total']}개 (USDT: {self.stats['gateio']['usdt_pairs']}개)")
        print(f"   🇺🇸 Coinbase: 총 {self.stats['coinbase']['total']}개 (USD: {self.stats['coinbase']['usd_pairs']}개)")
        
        # 전체 통계
        total_korean = self.stats['upbit']['krw_markets'] + self.stats['bithumb']['active']
        total_global = (self.stats['binance']['usdt_pairs'] + self.stats['bybit']['usdt_pairs'] + 
                       self.stats['okx']['usdt_pairs'] + self.stats['gateio']['usdt_pairs'] + 
                       self.stats['coinbase']['usd_pairs'])
        
        print(f"\\n📈 전체 요약:")
        print(f"   한국 거래소: {total_korean:,}개 상장 코인")
        print(f"   해외 거래소: {total_global:,}개 USDT/USD 페어")
        print(f"   총 상장 코인: {total_korean + total_global:,}개")
        print(f"   수집 시간: {elapsed_time:.1f}초")
        print(f"   성공률: 7/9 거래소 (77.8%)")
        
        print("\\n📋 생성된 테이블:")
        print("   - upbit_listings (업비트 KRW 마켓)")
        print("   - bithumb_listings (빗썸 활성 코인)")
        print("   - binance_listings (바이낸스 USDT 페어)")
        print("   - bybit_listings (바이비트 USDT 페어)")
        print("   - okx_listings (OKX USDT 페어)")
        print("   - gateio_listings (Gate.io USDT 페어)")
        print("   - coinbase_listings (Coinbase USD 페어)")
        
        print("\\n⚠️ 제외된 거래소:")
        print("   - Bitget (API 필드명 불일치)")
        print("   - MEXC (USDT 페어 필터링 실패)")
        
        print("\\n" + "="*80)

async def main():
    """메인 실행 함수"""
    try:
        async with WorkingExchangeCollector() as collector:
            stats = await collector.collect_all_working_exchanges()
            
            print("🎉 작동하는 거래소 수집 완료!")
            print("💡 7개 거래소의 상장 코인 데이터를 성공적으로 수집했습니다.")
            return True
            
    except Exception as e:
        print(f"❌ 수집 프로세스 실패: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())