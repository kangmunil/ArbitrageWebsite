#!/usr/bin/env python3
"""
Cryptocurrencies 테이블 데이터 검증 시스템

각 컬럼별 데이터 수집 가능성과 검증 규칙을 정의합니다.
- 자동 수집 가능한 데이터와 수동 입력 필요한 데이터 구분
- 데이터 유효성 검증 규칙
- 데이터 품질 모니터링
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from .database import SessionLocal
from .models import Cryptocurrency

logger = logging.getLogger(__name__)

@dataclass
class ColumnInfo:
    """컬럼 정보"""
    name: str
    data_type: str
    auto_collectible: bool  # 자동 수집 가능 여부
    data_source: str        # 데이터 소스
    validation_rules: List[str]
    sample_values: List[str]
    notes: str

@dataclass
class ValidationResult:
    """검증 결과"""
    column: str
    is_valid: bool
    value: Any
    errors: List[str]
    warnings: List[str]

class CryptocurrencyDataValidator:
    """암호화폐 데이터 검증기"""
    
    def __init__(self):
        self.column_specs = self._define_column_specifications()
        self.validation_stats = {
            'total_validated': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'warnings_count': 0
        }
    
    def _define_column_specifications(self) -> Dict[str, ColumnInfo]:
        """각 컬럼의 사양 정의"""
        return {
            'id': ColumnInfo(
                name='id',
                data_type='int (AI PK)',
                auto_collectible=True,
                data_source='자동 생성',
                validation_rules=['AUTO_INCREMENT', 'PRIMARY_KEY', 'NOT_NULL'],
                sample_values=['1', '2', '3'],
                notes='자동 증가 기본키, 수정 불가'
            ),
            
            'crypto_id': ColumnInfo(
                name='crypto_id',
                data_type='varchar(255)',
                auto_collectible=True,
                data_source='심볼 기반 자동 생성',
                validation_rules=['UNIQUE', 'NOT_NULL', 'LOWERCASE', 'NO_SPACES'],
                sample_values=['btc', 'eth', 'xrp'],
                notes='심볼의 소문자 버전, 고유 식별자'
            ),
            
            'symbol': ColumnInfo(
                name='symbol',
                data_type='varchar(255)',
                auto_collectible=True,
                data_source='거래소 API (Upbit, Binance, Bybit, Bithumb)',
                validation_rules=['NOT_NULL', 'UPPERCASE', '2-10자', 'ALPHANUMERIC'],
                sample_values=['BTC', 'ETH', 'XRP', 'ADA'],
                notes='✅ 완전 자동 수집 가능, 거래소 API에서 직접 획득'
            ),
            
            'name_ko': ColumnInfo(
                name='name_ko',
                data_type='varchar(255)',
                auto_collectible=False,
                data_source='수동 입력 또는 한국 거래소 API',
                validation_rules=['KOREAN_CHARS', 'OPTIONAL'],
                sample_values=['비트코인', '이더리움', '리플'],
                notes='❌ 자동 수집 어려움 - Upbit API에 부분적으로 있으나 완전하지 않음'
            ),
            
            'name_en': ColumnInfo(
                name='name_en',
                data_type='varchar(255)',
                auto_collectible=True,
                data_source='CoinGecko API',
                validation_rules=['NOT_EMPTY', 'ENGLISH_CHARS'],
                sample_values=['Bitcoin', 'Ethereum', 'Ripple'],
                notes='✅ CoinGecko API로 완전 자동 수집 가능'
            ),
            
            'logo_url': ColumnInfo(
                name='logo_url',
                data_type='varchar(255)',
                auto_collectible=True,
                data_source='CoinGecko API',
                validation_rules=['VALID_URL', 'IMAGE_FORMAT', 'HTTPS'],
                sample_values=[
                    'https://assets.coingecko.com/coins/images/1/large/bitcoin.png',
                    'https://assets.coingecko.com/coins/images/279/large/ethereum.png'
                ],
                notes='✅ CoinGecko API로 고품질 로고 이미지 자동 수집 가능'
            ),
            
            'is_active': ColumnInfo(
                name='is_active',
                data_type='tinyint(1)',
                auto_collectible=True,
                data_source='거래소 API 마켓 존재 여부',
                validation_rules=['BOOLEAN', 'DEFAULT_TRUE'],
                sample_values=['1', '0'],
                notes='✅ 거래소 마켓 리스트 존재 여부로 자동 판별 가능'
            ),
            
            'market_cap_rank': ColumnInfo(
                name='market_cap_rank',
                data_type='int',
                auto_collectible=True,
                data_source='CoinGecko API',
                validation_rules=['POSITIVE_INT', '1-20000 범위', 'NULLABLE'],
                sample_values=['1', '2', '3', '50'],
                notes='✅ CoinGecko API로 실시간 시가총액 순위 자동 수집 가능'
            ),
            
            'circulating_supply': ColumnInfo(
                name='circulating_supply',
                data_type='decimal(30,8)',
                auto_collectible=True,
                data_source='CoinGecko API',
                validation_rules=['POSITIVE_DECIMAL', 'MAX_30_8', 'NULLABLE'],
                sample_values=['19725000.00000000', '120280000.00000000'],
                notes='✅ CoinGecko API로 실시간 유통량 자동 수집 가능'
            ),
            
            'max_supply': ColumnInfo(
                name='max_supply',
                data_type='decimal(30,8)',
                auto_collectible=True,
                data_source='CoinGecko API',
                validation_rules=['POSITIVE_DECIMAL', 'MAX_30_8', 'NULLABLE', 'GREATER_THAN_CIRCULATING'],
                sample_values=['21000000.00000000', 'NULL'],
                notes='✅ CoinGecko API로 자동 수집 가능 (일부 코인은 max_supply 없음)'
            ),
            
            'category': ColumnInfo(
                name='category',
                data_type='varchar(100)',
                auto_collectible=True,
                data_source='CoinGecko API',
                validation_rules=['PREDEFINED_CATEGORIES', 'NULLABLE'],
                sample_values=['Store of Value', 'Smart Contract Platform', 'DeFi', 'Layer 1'],
                notes='✅ CoinGecko API로 카테고리 자동 분류 가능 (18개 주요 카테고리)'
            ),
            
            'website_url': ColumnInfo(
                name='website_url',
                data_type='varchar(255)',
                auto_collectible=True,
                data_source='CoinGecko API',
                validation_rules=['VALID_URL', 'HTTPS_PREFERRED', 'NULLABLE'],
                sample_values=['https://bitcoin.org', 'https://ethereum.org'],
                notes='✅ CoinGecko API로 공식 웹사이트 자동 수집 가능'
            ),
            
            'whitepaper_url': ColumnInfo(
                name='whitepaper_url',
                data_type='varchar(255)',
                auto_collectible=False,
                data_source='CoinGecko API (부분적)',
                validation_rules=['VALID_URL', 'PDF_PREFERRED', 'NULLABLE'],
                sample_values=['https://bitcoin.org/bitcoin.pdf'],
                notes='⚠️ 부분적 자동 수집 - CoinGecko에 일부만 있음, 수동 보완 필요'
            )
        }
    
    def validate_symbol(self, symbol: str) -> ValidationResult:
        """심볼 검증"""
        errors = []
        warnings = []
        
        if not symbol:
            errors.append("심볼이 비어있습니다")
        elif not symbol.isupper():
            warnings.append("심볼은 대문자로 저장되어야 합니다")
        elif not re.match(r'^[A-Z0-9]{1,10}$', symbol):
            errors.append("심볼은 1-10자의 영문 대문자와 숫자만 허용됩니다")
        
        return ValidationResult(
            column='symbol',
            is_valid=len(errors) == 0,
            value=symbol.upper() if symbol else None,
            errors=errors,
            warnings=warnings
        )
    
    def validate_decimal_field(self, value: Any, field_name: str, max_digits: int = 30, decimal_places: int = 8) -> ValidationResult:
        """DECIMAL 필드 검증"""
        errors = []
        warnings = []
        
        if value is None:
            return ValidationResult(field_name, True, None, [], [])
        
        try:
            if isinstance(value, str):
                decimal_value = Decimal(value)
            elif isinstance(value, (int, float)):
                decimal_value = Decimal(str(value))
            else:
                decimal_value = Decimal(value)
            
            if decimal_value < 0:
                errors.append(f"{field_name}은 음수일 수 없습니다")
            
            # 자릿수 검증
            str_value = str(decimal_value)
            if '.' in str_value:
                integer_part, decimal_part = str_value.split('.')
                if len(integer_part) > (max_digits - decimal_places):
                    errors.append(f"{field_name}의 정수 부분이 너무 큽니다 (최대 {max_digits - decimal_places}자리)")
                if len(decimal_part) > decimal_places:
                    warnings.append(f"{field_name}의 소수점 이하 자릿수가 {decimal_places}자리로 제한됩니다")
            
            return ValidationResult(field_name, len(errors) == 0, decimal_value, errors, warnings)
            
        except (InvalidOperation, ValueError) as e:
            errors.append(f"{field_name}의 숫자 형식이 올바르지 않습니다: {e}")
            return ValidationResult(field_name, False, value, errors, warnings)
    
    def validate_url(self, url: str, field_name: str) -> ValidationResult:
        """URL 검증"""
        errors = []
        warnings = []
        
        if not url:
            return ValidationResult(field_name, True, None, [], [])
        
        url_pattern = re.compile(
            r'^https?://'  # http:// 또는 https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 도메인
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # 포트
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            errors.append(f"{field_name}의 URL 형식이 올바르지 않습니다")
        elif not url.startswith('https://'):
            warnings.append(f"{field_name}은 HTTPS를 사용하는 것이 권장됩니다")
        
        return ValidationResult(field_name, len(errors) == 0, url, errors, warnings)
    
    def validate_category(self, category: str) -> ValidationResult:
        """카테고리 검증"""
        valid_categories = {
            'Store of Value', 'Smart Contract Platform', 'Layer 1', 'Layer 2',
            'DeFi', 'Meme', 'Gaming', 'NFT', 'Oracle', 'Privacy',
            'Stablecoin', 'Exchange Token', 'Wrapped Token', 'Infrastructure',
            'Analytics', 'Metaverse', 'AI', 'RWA'
        }
        
        errors = []
        warnings = []
        
        if not category:
            return ValidationResult('category', True, None, [], [])
        
        if category not in valid_categories:
            warnings.append(f"알 수 없는 카테고리: {category}. 유효한 카테고리: {', '.join(valid_categories)}")
        
        return ValidationResult('category', True, category, errors, warnings)
    
    def validate_cryptocurrency_record(self, record: Dict[str, Any]) -> List[ValidationResult]:
        """전체 암호화폐 레코드 검증"""
        results = []
        
        # 필수 필드 검증
        symbol_result = self.validate_symbol(record.get('symbol', ''))
        results.append(symbol_result)
        
        # DECIMAL 필드들 검증
        if 'circulating_supply' in record:
            results.append(self.validate_decimal_field(
                record['circulating_supply'], 'circulating_supply'
            ))
        
        if 'max_supply' in record:
            results.append(self.validate_decimal_field(
                record['max_supply'], 'max_supply'
            ))
        
        # URL 필드들 검증
        if 'logo_url' in record:
            results.append(self.validate_url(record['logo_url'], 'logo_url'))
        
        if 'website_url' in record:
            results.append(self.validate_url(record['website_url'], 'website_url'))
        
        if 'whitepaper_url' in record:
            results.append(self.validate_url(record['whitepaper_url'], 'whitepaper_url'))
        
        # 카테고리 검증
        if 'category' in record:
            results.append(self.validate_category(record['category']))
        
        # 통계 업데이트
        self.validation_stats['total_validated'] += 1
        if all(r.is_valid for r in results):
            self.validation_stats['valid_records'] += 1
        else:
            self.validation_stats['invalid_records'] += 1
        
        self.validation_stats['warnings_count'] += sum(len(r.warnings) for r in results)
        
        return results
    
    def analyze_data_collectibility(self) -> Dict[str, Any]:
        """데이터 수집 가능성 분석"""
        auto_collectible = []
        manual_required = []
        partial_auto = []
        
        for col_name, col_info in self.column_specs.items():
            if col_info.auto_collectible:
                if 'CoinGecko' in col_info.data_source:
                    auto_collectible.append(col_name)
                elif '부분적' in col_info.notes:
                    partial_auto.append(col_name)
                else:
                    auto_collectible.append(col_name)
            else:
                manual_required.append(col_name)
        
        return {
            'summary': {
                'total_columns': len(self.column_specs),
                'auto_collectible': len(auto_collectible),
                'manual_required': len(manual_required),
                'partial_auto': len(partial_auto),
                'automation_rate': f"{(len(auto_collectible) / len(self.column_specs)) * 100:.1f}%"
            },
            'auto_collectible_fields': auto_collectible,
            'manual_required_fields': manual_required,
            'partial_auto_fields': partial_auto,
            'data_sources': {
                'CoinGecko API': ['name_en', 'logo_url', 'market_cap_rank', 'circulating_supply', 'max_supply', 'category', 'website_url'],
                '거래소 API': ['symbol', 'is_active'],
                '자동 생성': ['id', 'crypto_id'],
                '수동 입력': ['name_ko'],
                '부분적 자동': ['whitepaper_url']
            }
        }
    
    def generate_data_quality_report(self) -> Dict[str, Any]:
        """데이터 품질 보고서 생성"""
        db = SessionLocal()
        try:
            total_records = db.query(Cryptocurrency).count()
            
            # 각 필드별 NULL 값 비율 계산
            field_completeness = {}
            
            for field_name in ['symbol', 'name_en', 'logo_url', 'market_cap_rank', 
                             'circulating_supply', 'max_supply', 'category', 'website_url', 'whitepaper_url']:
                
                if hasattr(Cryptocurrency, field_name):
                    non_null_count = db.query(Cryptocurrency).filter(
                        getattr(Cryptocurrency, field_name).isnot(None)
                    ).count()
                    
                    field_completeness[field_name] = {
                        'non_null_count': non_null_count,
                        'null_count': total_records - non_null_count,
                        'completeness_rate': f"{(non_null_count / total_records * 100):.1f}%" if total_records > 0 else "0%"
                    }
            
            return {
                'total_records': total_records,
                'field_completeness': field_completeness,
                'validation_stats': self.validation_stats,
                'generated_at': datetime.now().isoformat()
            }
            
        finally:
            db.close()
    
    def get_column_specifications(self) -> Dict[str, ColumnInfo]:
        """컬럼 사양 반환"""
        return self.column_specs

# 전역 검증기 인스턴스
data_validator = CryptocurrencyDataValidator()

# 편의 함수들
def validate_crypto_data(record: Dict[str, Any]) -> List[ValidationResult]:
    """암호화폐 데이터 검증"""
    return data_validator.validate_cryptocurrency_record(record)

def get_data_collectibility_analysis() -> Dict[str, Dict]:
    """데이터 수집 가능성 분석"""
    return data_validator.analyze_data_collectibility()

def generate_quality_report() -> Dict[str, Any]:
    """데이터 품질 보고서 생성"""
    return data_validator.generate_data_quality_report()

def get_column_info() -> Dict[str, ColumnInfo]:
    """컬럼 정보 조회"""
    return data_validator.get_column_specifications()

# CLI 실행용
if __name__ == "__main__":
    import json
    
    print("=== Cryptocurrencies 테이블 데이터 분석 ===")
    
    # 수집 가능성 분석
    collectibility = get_data_collectibility_analysis()
    print(f"\n📊 데이터 수집 가능성 요약:")
    print(f"- 총 컬럼 수: {collectibility['summary']['total_columns']}")
    print(f"- 자동 수집 가능: {collectibility['summary']['auto_collectible']}")
    print(f"- 수동 입력 필요: {collectibility['summary']['manual_required']}")
    print(f"- 자동화율: {collectibility['summary']['automation_rate']}")
    
    # 데이터 품질 보고서
    quality_report = generate_quality_report()
    print(f"\n📈 데이터 품질 현황:")
    print(f"- 총 레코드 수: {quality_report['total_records']}")
    
    print(f"\n🔍 컬럼별 상세 정보:")
    for col_name, col_info in get_column_info().items():
        status = "✅ 자동" if col_info.auto_collectible else "❌ 수동"
        print(f"- {col_name}: {status} | {col_info.data_source}")