"""
Shared Market Data - 시장 데이터 공유 저장소

모든 거래소의 시장 데이터를 메모리와 Redis에 저장하고 관리합니다.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class SharedMarketData:
    """시장 데이터 공유 저장소"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        
        # 메모리 저장소 (Redis 백업용)
        self.memory_data = {
            "upbit_tickers": {},
            "bithumb_tickers": {},
            "binance_tickers": {},
            "bybit_tickers": {},
            "exchange_rates": {},
            "last_update": {}
        }
    
    def set_redis_client(self, redis_client: Optional[redis.Redis]):
        """Redis 클라이언트 설정"""
        self.redis_client = redis_client
    
    # === Data Update Methods ===
    
    async def update_upbit_data(self, symbol: str, data: Dict[str, Any]):
        """업비트 데이터 업데이트"""
        self.memory_data["upbit_tickers"][symbol] = data
        self.memory_data["last_update"]["upbit"] = datetime.now().isoformat()
        
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    "market:upbit", 
                    symbol, 
                    json.dumps(data)
                )
                await self.redis_client.expire("market:upbit", 300)  # 5분 TTL
            except Exception as e:
                logger.warning(f"Redis 업비트 데이터 저장 실패: {e}")
    
    async def update_binance_data(self, symbol: str, data: Dict[str, Any]):
        """바이낸스 데이터 업데이트"""
        self.memory_data["binance_tickers"][symbol] = data
        self.memory_data["last_update"]["binance"] = datetime.now().isoformat()
        
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    "market:binance", 
                    symbol, 
                    json.dumps(data)
                )
                await self.redis_client.expire("market:binance", 300)
            except Exception as e:
                logger.warning(f"Redis 바이낸스 데이터 저장 실패: {e}")
    
    async def update_bybit_data(self, symbol: str, data: Dict[str, Any]):
        """바이비트 데이터 업데이트"""
        self.memory_data["bybit_tickers"][symbol] = data
        self.memory_data["last_update"]["bybit"] = datetime.now().isoformat()
        
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    "market:bybit", 
                    symbol, 
                    json.dumps(data)
                )
                await self.redis_client.expire("market:bybit", 300)
            except Exception as e:
                logger.warning(f"Redis 바이비트 데이터 저장 실패: {e}")
    
    async def update_bithumb_data(self, symbol: str, data: Dict[str, Any]):
        """빗썸 데이터 업데이트"""
        self.memory_data["bithumb_tickers"][symbol] = data
        self.memory_data["last_update"]["bithumb"] = datetime.now().isoformat()
        
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    "market:bithumb", 
                    symbol, 
                    json.dumps(data)
                )
                await self.redis_client.expire("market:bithumb", 300)
            except Exception as e:
                logger.warning(f"Redis 빗썸 데이터 저장 실패: {e}")
    
    async def update_exchange_rate(self, rate_type: str, rate: float):
        """환율 데이터 업데이트"""
        self.memory_data["exchange_rates"][rate_type] = rate
        self.memory_data["last_update"][f"rate_{rate_type}"] = datetime.now().isoformat()
        
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    "market:rates", 
                    rate_type, 
                    str(rate)
                )
                await self.redis_client.expire("market:rates", 300)
            except Exception as e:
                logger.warning(f"Redis 환율 데이터 저장 실패: {e}")
    
    # === Data Retrieval Methods ===
    
    async def get_all_prices(self) -> List[Dict[str, Any]]:
        """모든 코인의 가격 데이터 반환"""
        all_symbols = set()
        all_symbols.update(self.memory_data["upbit_tickers"].keys())
        all_symbols.update(self.memory_data["bithumb_tickers"].keys())
        all_symbols.update(self.memory_data["binance_tickers"].keys())
        all_symbols.update(self.memory_data["bybit_tickers"].keys())
        
        prices_data = []
        for symbol in all_symbols:
            price_info = {
                "symbol": symbol,
                "upbit_price": self.memory_data["upbit_tickers"].get(symbol, {}).get("price"),
                "bithumb_price": self.memory_data["bithumb_tickers"].get(symbol, {}).get("price"),
                "binance_price": self.memory_data["binance_tickers"].get(symbol, {}).get("price"),
                "bybit_price": self.memory_data["bybit_tickers"].get(symbol, {}).get("price"),
            }
            
            # 최소한 하나의 거래소라도 가격이 있는 경우만 포함
            if any(price_info[f"{exchange}_price"] is not None 
                   for exchange in ["upbit", "bithumb", "binance", "bybit"]):
                prices_data.append(price_info)
        
        return prices_data
    
    async def get_all_volumes(self) -> List[Dict[str, Any]]:
        """모든 코인의 거래량 데이터 반환"""
        all_symbols = set()
        all_symbols.update(self.memory_data["upbit_tickers"].keys())
        all_symbols.update(self.memory_data["bithumb_tickers"].keys())
        all_symbols.update(self.memory_data["binance_tickers"].keys())
        all_symbols.update(self.memory_data["bybit_tickers"].keys())
        
        volumes_data = []
        exchange_rate = self.memory_data["exchange_rates"].get("USD_KRW", 1300)
        usdt_krw_rate = self.memory_data["exchange_rates"].get("USDT_KRW", 1300)
        
        for symbol in all_symbols:
            upbit_volume = self.memory_data["upbit_tickers"].get(symbol, {}).get("volume")
            bithumb_volume = self.memory_data["bithumb_tickers"].get(symbol, {}).get("volume")
            binance_volume_usd = self.memory_data["binance_tickers"].get(symbol, {}).get("volume")
            bybit_volume_usd = self.memory_data["bybit_tickers"].get(symbol, {}).get("volume")
            
            # USD 거래량을 KRW로 변환
            binance_volume_krw = None
            if binance_volume_usd is not None and usdt_krw_rate is not None:
                binance_volume_krw = binance_volume_usd * usdt_krw_rate
            
            bybit_volume_krw = None
            if bybit_volume_usd is not None and usdt_krw_rate is not None:
                bybit_volume_krw = bybit_volume_usd * usdt_krw_rate
            
            volume_info = {
                "symbol": symbol,
                "upbit_volume": upbit_volume,
                "bithumb_volume": bithumb_volume,
                "binance_volume": binance_volume_krw,
                "binance_volume_usd": binance_volume_usd,
                "bybit_volume": bybit_volume_krw,
                "bybit_volume_usd": bybit_volume_usd,
            }
            
            # 최소한 하나의 거래소라도 거래량이 있는 경우만 포함
            if any(volume_info[f"{exchange}_volume"] is not None 
                   for exchange in ["upbit", "bithumb", "binance", "bybit"]):
                volumes_data.append(volume_info)
        
        return volumes_data
    
    async def get_all_premiums(self) -> List[Dict[str, Any]]:
        """김치 프리미엄 데이터 반환"""
        all_symbols = set()
        all_symbols.update(self.memory_data["upbit_tickers"].keys())
        all_symbols.update(self.memory_data["bithumb_tickers"].keys())
        all_symbols.update(self.memory_data["binance_tickers"].keys())
        
        premiums_data = []
        exchange_rate = self.memory_data["exchange_rates"].get("USD_KRW", 1300)
        
        for symbol in all_symbols:
            upbit_price = self.memory_data["upbit_tickers"].get(symbol, {}).get("price")
            bithumb_price = self.memory_data["bithumb_tickers"].get(symbol, {}).get("price")
            binance_price = self.memory_data["binance_tickers"].get(symbol, {}).get("price")
            
            # 김치 프리미엄 계산 (국내 vs 해외)
            domestic_price = upbit_price or bithumb_price
            premium = None
            
            if domestic_price and binance_price and exchange_rate:
                binance_price_krw = binance_price * exchange_rate
                if binance_price_krw > 0:
                    premium = ((domestic_price - binance_price_krw) / binance_price_krw) * 100
            
            premium_info = {
                "symbol": symbol,
                "domestic_price": domestic_price,
                "global_price_usd": binance_price,
                "global_price_krw": binance_price * exchange_rate if binance_price and exchange_rate else None,
                "premium_percent": round(premium, 2) if premium is not None else None,
            }
            
            if premium_info["premium_percent"] is not None:
                premiums_data.append(premium_info)
        
        return premiums_data
    
    async def get_exchange_rates(self) -> Dict[str, Any]:
        """환율 정보 반환"""
        return {
            "usd_krw": self.memory_data["exchange_rates"].get("USD_KRW"),
            "usdt_krw": self.memory_data["exchange_rates"].get("USDT_KRW"),
            "last_update": {
                "usd_krw": self.memory_data["last_update"].get("rate_USD_KRW"),
                "usdt_krw": self.memory_data["last_update"].get("rate_USDT_KRW")
            }
        }
    
    async def get_combined_data(self) -> List[Dict[str, Any]]:
        """통합된 시장 데이터 반환 (API Gateway에서 사용)"""
        all_symbols = set()
        all_symbols.update(self.memory_data["upbit_tickers"].keys())
        all_symbols.update(self.memory_data["bithumb_tickers"].keys())
        all_symbols.update(self.memory_data["binance_tickers"].keys())
        all_symbols.update(self.memory_data["bybit_tickers"].keys())
        
        combined_data = []
        exchange_rate = self.memory_data["exchange_rates"].get("USD_KRW", 1300)
        usdt_krw_rate = self.memory_data["exchange_rates"].get("USDT_KRW", 1300)
        
        for symbol in all_symbols:
            upbit_ticker = self.memory_data["upbit_tickers"].get(symbol, {})
            bithumb_ticker = self.memory_data["bithumb_tickers"].get(symbol, {})
            binance_ticker = self.memory_data["binance_tickers"].get(symbol, {})
            bybit_ticker = self.memory_data["bybit_tickers"].get(symbol, {})
            
            upbit_price = upbit_ticker.get("price")
            bithumb_price = bithumb_ticker.get("price")
            binance_price = binance_ticker.get("price")
            bybit_price = bybit_ticker.get("price")
            
            # 김치 프리미엄 계산
            premium = None
            domestic_price = upbit_price or bithumb_price
            if domestic_price and binance_price and exchange_rate:
                binance_price_krw = binance_price * exchange_rate
                if binance_price_krw > 0:
                    premium = ((domestic_price - binance_price_krw) / binance_price_krw) * 100
            
            # 거래량 KRW 변환
            binance_volume_usd = binance_ticker.get("volume")
            binance_volume_krw = None
            if binance_volume_usd is not None and usdt_krw_rate is not None:
                binance_volume_krw = binance_volume_usd * usdt_krw_rate
            
            bybit_volume_usd = bybit_ticker.get("volume")
            bybit_volume_krw = None
            if bybit_volume_usd is not None and usdt_krw_rate is not None:
                bybit_volume_krw = bybit_volume_usd * usdt_krw_rate
            
            coin_data = {
                "symbol": symbol,
                "upbit_price": upbit_price,
                "upbit_volume": upbit_ticker.get("volume"),
                "upbit_change_percent": upbit_ticker.get("change_percent"),
                "bithumb_price": bithumb_price,
                "bithumb_volume": bithumb_ticker.get("volume"),
                "bithumb_change_percent": bithumb_ticker.get("change_percent"),
                "binance_price": binance_price,
                "binance_volume": binance_volume_krw,
                "binance_volume_usd": binance_volume_usd,
                "binance_change_percent": binance_ticker.get("change_percent"),
                "bybit_price": bybit_price,
                "bybit_volume": bybit_volume_krw,
                "bybit_volume_usd": bybit_volume_usd,
                "bybit_change_percent": bybit_ticker.get("change_percent"),
                "premium": round(premium, 2) if premium is not None else None,
                "exchange_rate": exchange_rate,
                "usdt_krw_rate": usdt_krw_rate,
            }
            
            # 최소한 하나의 거래소라도 가격 데이터가 있는 경우에만 추가
            if any(price is not None for price in [upbit_price, bithumb_price, binance_price, bybit_price]):
                combined_data.append(coin_data)
        
        return combined_data
    
    # === Debug Methods ===
    
    async def get_exchange_raw_data(self, exchange: str) -> Dict[str, Any]:
        """특정 거래소의 원시 데이터 반환"""
        return self.memory_data.get(f"{exchange}_tickers", {})
    
    async def get_stats(self) -> Dict[str, Any]:
        """공유 데이터 통계 반환"""
        return {
            "memory_stats": {
                "upbit_symbols": len(self.memory_data["upbit_tickers"]),
                "bithumb_symbols": len(self.memory_data["bithumb_tickers"]),
                "binance_symbols": len(self.memory_data["binance_tickers"]),
                "bybit_symbols": len(self.memory_data["bybit_tickers"]),
                "exchange_rates": len(self.memory_data["exchange_rates"])
            },
            "last_updates": self.memory_data["last_update"],
            "redis_connected": self.redis_client is not None
        }