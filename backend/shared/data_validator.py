"""
공통 데이터 검증 및 변환 유틸리티

모든 마이크로서비스에서 사용할 수 있는 데이터 검증, 변환, 정규화 로직을 제공합니다.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import re

logger = logging.getLogger(__name__)


class DataValidator:
    """데이터 검증 및 변환 클래스"""
    
    @staticmethod
    def is_valid_price(price: Any) -> bool:
        """가격 데이터가 유효한지 검증"""
        try:
            price_float = float(price)
            return price_float > 0 and price_float != float('inf')
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_volume(volume: Any) -> bool:
        """거래량 데이터가 유효한지 검증"""
        try:
            volume_float = float(volume)
            return volume_float >= 0 and volume_float != float('inf')
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_symbol(symbol: str) -> bool:
        """심볼이 유효한 형식인지 검증"""
        if not isinstance(symbol, str):
            return False
        # 영문자/숫자 조합, 2-10자리
        pattern = r'^[A-Z0-9]{2,10}$'
        return bool(re.match(pattern, symbol.upper()))
    
    @staticmethod
    def sanitize_price(price: Any, default: float = 0.0) -> float:
        """가격 데이터를 안전하게 float로 변환"""
        try:
            price_float = float(price)
            if price_float > 0 and price_float != float('inf'):
                return price_float
            return default
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def sanitize_volume(volume: Any, default: float = 0.0) -> float:
        """거래량 데이터를 안전하게 float로 변환"""
        try:
            volume_float = float(volume)
            if volume_float >= 0 and volume_float != float('inf'):
                return volume_float
            return default
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def sanitize_symbol(symbol: Any) -> Optional[str]:
        """심볼을 표준 형식으로 정규화"""
        if not isinstance(symbol, str):
            return None
        
        clean_symbol = symbol.upper().strip()
        if DataValidator.is_valid_symbol(clean_symbol):
            return clean_symbol
        return None
    
    @staticmethod
    def sanitize_exchange_rate(rate: Any, default: float = 1300.0) -> float:
        """환율 데이터를 안전하게 처리"""
        try:
            rate_float = float(rate)
            # 환율이 너무 비현실적인 값이면 기본값 사용
            if 1000 <= rate_float <= 2000:
                return rate_float
            return default
        except (ValueError, TypeError):
            return default


class PriceDataNormalizer:
    """가격 데이터 정규화 클래스"""
    
    @staticmethod
    def normalize_upbit_ticker(raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """업비트 티커 데이터 정규화"""
        try:
            symbol = DataValidator.sanitize_symbol(raw_data.get('code', '').replace('KRW-', ''))
            if not symbol:
                return None
            
            return {
                'symbol': symbol,
                'price': DataValidator.sanitize_price(raw_data.get('trade_price')),
                'volume': DataValidator.sanitize_volume(raw_data.get('acc_trade_price_24h')),
                'change_rate': DataValidator.sanitize_price(raw_data.get('signed_change_rate', 0), 0),
                'timestamp': raw_data.get('trade_timestamp', int(datetime.now().timestamp() * 1000))
            }
        except Exception as e:
            logger.warning(f"업비트 데이터 정규화 실패: {e}")
            return None
    
    @staticmethod
    def normalize_binance_ticker(raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """바이낸스 티커 데이터 정규화"""
        try:
            symbol = DataValidator.sanitize_symbol(raw_data.get('s', '').replace('USDT', ''))
            if not symbol:
                return None
            
            return {
                'symbol': symbol,
                'price': DataValidator.sanitize_price(raw_data.get('c')),
                'volume': DataValidator.sanitize_volume(raw_data.get('q')),  # USDT 거래대금
                'change_rate': DataValidator.sanitize_price(raw_data.get('P', 0), 0) / 100,  # %를 소수로
                'timestamp': int(raw_data.get('E', datetime.now().timestamp() * 1000))
            }
        except Exception as e:
            logger.warning(f"바이낸스 데이터 정규화 실패: {e}")
            return None
    
    @staticmethod
    def normalize_bybit_ticker(raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """바이비트 티커 데이터 정규화"""
        try:
            symbol = DataValidator.sanitize_symbol(raw_data.get('symbol', '').replace('USDT', ''))
            if not symbol:
                return None
            
            return {
                'symbol': symbol,
                'price': DataValidator.sanitize_price(raw_data.get('lastPrice')),
                'volume': DataValidator.sanitize_volume(raw_data.get('turnover24h')),  # USDT 거래대금
                'change_rate': DataValidator.sanitize_price(raw_data.get('price24hPcnt', 0), 0),
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
        except Exception as e:
            logger.warning(f"바이비트 데이터 정규화 실패: {e}")
            return None
    
    @staticmethod
    def normalize_bithumb_ticker(raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """빗썸 티커 데이터 정규화"""
        try:
            symbol = DataValidator.sanitize_symbol(raw_data.get('symbol', '').replace('_KRW', ''))
            if not symbol:
                return None
            
            return {
                'symbol': symbol,
                'price': DataValidator.sanitize_price(raw_data.get('closePrice')),
                'volume': DataValidator.sanitize_volume(raw_data.get('value')),  # KRW 거래대금
                'change_rate': DataValidator.sanitize_price(raw_data.get('chgRate', 0), 0),
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
        except Exception as e:
            logger.warning(f"빗썸 데이터 정규화 실패: {e}")
            return None


class LiquidationDataNormalizer:
    """청산 데이터 정규화 클래스"""
    
    @staticmethod
    def normalize_liquidation_direction(side: str, position_side: Optional[str] = None) -> str:
        """청산 방향을 표준화 (long/short)"""
        side_lower = str(side).lower()
        pos_side_lower = str(position_side).lower() if position_side else ""
        
        # 바이낸스 스타일: side + positionSide 조합
        if pos_side_lower == "long" or side_lower == "sell":
            return "long"  # 롱 포지션 청산
        elif pos_side_lower == "short" or side_lower == "buy":
            return "short"  # 숏 포지션 청산
        
        # 기본값은 long
        return "long"
    
    @staticmethod
    def normalize_liquidation_data(raw_data: Dict[str, Any], exchange: str) -> Optional[Dict[str, Any]]:
        """청산 데이터 정규화"""
        try:
            # 심볼 정규화
            symbol_raw = raw_data.get('symbol', raw_data.get('s', ''))
            symbol = DataValidator.sanitize_symbol(symbol_raw.replace('USDT', '').replace('PERP', ''))
            if not symbol:
                return None
            
            # 청산 금액 계산
            price = DataValidator.sanitize_price(raw_data.get('averagePrice', raw_data.get('p', 0)))
            quantity = DataValidator.sanitize_volume(raw_data.get('originalQuantity', raw_data.get('q', 0)))
            usd_amount = price * quantity
            
            if usd_amount <= 0:
                return None
            
            # 방향 정규화
            side = raw_data.get('side', raw_data.get('S', ''))
            position_side = raw_data.get('positionSide', '')
            direction = LiquidationDataNormalizer.normalize_liquidation_direction(side, position_side)
            
            return {
                'symbol': symbol,
                'exchange': exchange.lower(),
                'direction': direction,
                'usd_amount': usd_amount,
                'price': price,
                'quantity': quantity,
                'timestamp': int(raw_data.get('transactionTime', raw_data.get('T', datetime.now().timestamp() * 1000)))
            }
            
        except Exception as e:
            logger.warning(f"{exchange} 청산 데이터 정규화 실패: {e}")
            return None


class PremiumCalculator:
    """김치 프리미엄 계산 유틸리티"""
    
    @staticmethod
    def calculate_premium(domestic_price: float, global_price: float, exchange_rate: float = 1300.0) -> float:
        """김치 프리미엄 계산"""
        try:
            if domestic_price <= 0 or global_price <= 0 or exchange_rate <= 0:
                return 0.0
            
            global_price_krw = global_price * exchange_rate
            premium = ((domestic_price - global_price_krw) / global_price_krw) * 100
            
            # 극단적인 값 필터링 (-50% ~ +50%)
            return max(-50.0, min(50.0, premium))
            
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    @staticmethod
    def format_premium(premium: float) -> str:
        """프리미엄을 표시용 문자열로 포맷"""
        try:
            formatted = f"{premium:+.2f}%"
            return formatted
        except:
            return "0.00%"


class DataAggregator:
    """데이터 집계 유틸리티"""
    
    @staticmethod
    def merge_coin_data(upbit_data: Dict, binance_data: Dict, 
                       exchange_rate: float = 1300.0, usdt_krw_rate: float = 1300.0) -> Dict[str, Any]:
        """코인 데이터 병합"""
        try:
            symbol = upbit_data.get('symbol') or binance_data.get('symbol')
            if not symbol:
                return {}
            
            upbit_price = upbit_data.get('price', 0)
            binance_price = binance_data.get('price', 0)
            
            # 거래량 KRW 변환
            upbit_volume_krw = upbit_data.get('volume', 0)  # 이미 KRW
            binance_volume_usd = binance_data.get('volume', 0)
            binance_volume_krw = binance_volume_usd * usdt_krw_rate
            
            # 프리미엄 계산
            premium = PremiumCalculator.calculate_premium(upbit_price, binance_price, exchange_rate)
            
            return {
                'symbol': symbol,
                'upbit_price': upbit_price,
                'binance_price': binance_price,
                'domestic_price': upbit_price,
                'global_price': binance_price,
                'premium': premium,
                'premium_formatted': PremiumCalculator.format_premium(premium),
                'domestic_volume': upbit_volume_krw,
                'global_volume': binance_volume_krw,
                'domestic_change': upbit_data.get('change_rate', 0) * 100,
                'global_change': binance_data.get('change_rate', 0) * 100,
                'timestamp': max(
                    upbit_data.get('timestamp', 0),
                    binance_data.get('timestamp', 0)
                )
            }
            
        except Exception as e:
            logger.error(f"코인 데이터 병합 실패 ({symbol}): {e}")
            return {}


# 공통 검증 함수들
def validate_service_response(response_data: Dict[str, Any]) -> bool:
    """서비스 응답 데이터 유효성 검증"""
    required_fields = ['success', 'data']
    return all(field in response_data for field in required_fields)


def sanitize_api_response(data: Any, default: Any = None) -> Any:
    """API 응답 데이터 안전화"""
    if data is None:
        return default
    
    try:
        # JSON 직렬화 가능한지 테스트
        import json
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        logger.warning(f"API 응답 데이터 직렬화 실패: {type(data)}")
        return default