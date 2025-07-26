"""
데이터 정규화 및 일관성 보장 시스템

주요 기능:
1. 거래소별 데이터 형식 통일
2. 실시간 데이터 유효성 검증
3. 이상치 탐지 및 필터링
4. 데이터 일관성 검사
5. 심볼 매핑 및 변환
"""

import time
import logging
import asyncio
import statistics
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import numpy as np

from .exchange_specifications import get_exchange_spec, normalize_ticker_data

logger = logging.getLogger(__name__)

class DataQuality(Enum):
    """데이터 품질 등급"""
    EXCELLENT = "excellent"  # 완벽한 데이터
    GOOD = "good"           # 양호한 데이터
    ACCEPTABLE = "acceptable"  # 허용 가능한 데이터
    POOR = "poor"           # 품질 불량 데이터
    INVALID = "invalid"     # 유효하지 않은 데이터

class ValidationResult(Enum):
    """검증 결과"""
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"

@dataclass
class NormalizedTicker:
    """정규화된 티커 데이터"""
    symbol: str
    exchange: str
    
    # 가격 정보
    price: float
    price_usd: Optional[float] = None
    price_krw: Optional[float] = None
    
    # 거래량 정보 (통일된 단위: quote currency)
    volume_24h: float = 0.0
    volume_24h_usd: Optional[float] = None
    volume_24h_krw: Optional[float] = None
    
    # 변동률 (퍼센트 단위)
    change_24h_percent: float = 0.0
    
    # 메타데이터
    timestamp: float = field(default_factory=time.time)
    data_quality: DataQuality = DataQuality.GOOD
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    # 검증 정보
    validation_score: float = 1.0  # 0.0 ~ 1.0
    anomaly_flags: List[str] = field(default_factory=list)

@dataclass
class PriceConsistencyCheck:
    """가격 일관성 검사 결과"""
    symbol: str
    exchanges: List[str]
    prices: Dict[str, float]
    max_deviation: float  # 최대 편차 (%)
    is_consistent: bool
    outliers: List[str]  # 이상치가 발견된 거래소

class DataNormalizer:
    """데이터 정규화 엔진"""
    
    def __init__(self):
        # 환율 정보 (실시간 업데이트)
        self.usd_krw_rate: Optional[float] = None
        self.usdt_krw_rate: Optional[float] = None
        
        # 이상치 탐지 설정
        self.price_deviation_threshold = 10.0  # 10% 이상 차이
        self.volume_outlier_threshold = 3.0   # 3시그마 기준
        self.change_percent_threshold = 30.0  # 30% 이상 변동
        
        # 데이터 품질 기준
        self.quality_thresholds = {
            DataQuality.EXCELLENT: 0.95,
            DataQuality.GOOD: 0.85,
            DataQuality.ACCEPTABLE: 0.70,
            DataQuality.POOR: 0.50
        }
        
        # 심볼 매핑 (거래소별 차이 해결)
        self.symbol_mapping = {
            # 표준 심볼 -> 거래소별 변형
            "BTC": {"upbit": "BTC", "binance": "BTC", "bybit": "BTC"},
            "ETH": {"upbit": "ETH", "binance": "ETH", "bybit": "ETH"},
            # 추가 매핑 필요시 확장
        }
        
        # 이력 데이터 (이상치 탐지용)
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.volume_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        
    def update_exchange_rates(self, usd_krw: Optional[float], usdt_krw: Optional[float]):
        """환율 정보 업데이트"""
        if usd_krw and 1000 <= usd_krw <= 2000:
            self.usd_krw_rate = usd_krw
        if usdt_krw and 1000 <= usdt_krw <= 2000:
            self.usdt_krw_rate = usdt_krw
    
    def normalize_ticker(self, exchange: str, symbol: str, raw_data: Dict[str, Any]) -> Optional[NormalizedTicker]:
        """티커 데이터 정규화"""
        try:
            # 기본 정규화 (exchange_specifications.py 활용)
            normalized_basic = normalize_ticker_data(exchange, raw_data)
            if not normalized_basic:
                return None
            
            # 고급 정규화 및 검증
            ticker = NormalizedTicker(
                symbol=symbol,
                exchange=exchange,
                price=normalized_basic["price"],
                volume_24h=normalized_basic["volume"],
                change_24h_percent=normalized_basic["change_percent"],
                raw_data=raw_data
            )
            
            # 환율 적용하여 다중 통화 가격 계산
            self._apply_currency_conversion(ticker)
            
            # 데이터 검증 및 품질 평가
            validation_result = self._validate_ticker_data(ticker)
            ticker.validation_score = validation_result["score"]
            ticker.anomaly_flags = validation_result["anomalies"]
            ticker.data_quality = self._determine_quality_grade(ticker.validation_score)
            
            # 이력 데이터 업데이트
            self._update_history(ticker)
            
            return ticker
            
        except Exception as e:
            logger.error(f"데이터 정규화 실패 ({exchange}/{symbol}): {e}")
            return None
    
    def _apply_currency_conversion(self, ticker: NormalizedTicker):
        """통화 변환 적용"""
        if ticker.exchange in ["upbit", "bithumb"]:
            # 국내 거래소: KRW 기준
            ticker.price_krw = ticker.price
            if self.usd_krw_rate:
                ticker.price_usd = ticker.price / self.usd_krw_rate
            
            ticker.volume_24h_krw = ticker.volume_24h
            if self.usd_krw_rate:
                ticker.volume_24h_usd = ticker.volume_24h / self.usd_krw_rate
                
        else:
            # 해외 거래소: USD/USDT 기준
            ticker.price_usd = ticker.price
            if self.usdt_krw_rate:
                ticker.price_krw = ticker.price * self.usdt_krw_rate
            
            ticker.volume_24h_usd = ticker.volume_24h
            if self.usdt_krw_rate:
                ticker.volume_24h_krw = ticker.volume_24h * self.usdt_krw_rate
    
    def _validate_ticker_data(self, ticker: NormalizedTicker) -> Dict[str, Any]:
        """티커 데이터 검증"""
        score = 1.0
        anomalies = []
        
        # 1. 기본 유효성 검사
        if ticker.price <= 0:
            score -= 0.5
            anomalies.append("invalid_price")
        
        if ticker.volume_24h < 0:
            score -= 0.3
            anomalies.append("negative_volume")
        
        # 2. 변동률 이상치 검사
        if abs(ticker.change_24h_percent) > self.change_percent_threshold:
            score -= 0.2
            anomalies.append("extreme_price_change")
        
        # 3. 가격 일관성 검사 (이력 데이터 기반)
        price_history = list(self.price_history[f"{ticker.exchange}:{ticker.symbol}"])
        if len(price_history) >= 5:
            recent_prices = [p for p, _ in price_history[-5:]]
            avg_price = statistics.mean(recent_prices)
            
            if avg_price > 0:
                deviation = abs(ticker.price - avg_price) / avg_price * 100
                if deviation > self.price_deviation_threshold:
                    score -= 0.15
                    anomalies.append("price_deviation")
        
        # 4. 거래량 이상치 검사
        volume_history = list(self.volume_history[f"{ticker.exchange}:{ticker.symbol}"])
        if len(volume_history) >= 10:
            recent_volumes = [v for _, v in volume_history[-10:]]
            if recent_volumes:
                volume_mean = statistics.mean(recent_volumes)
                volume_std = statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0
                
                if volume_std > 0 and volume_mean > 0:
                    z_score = abs(ticker.volume_24h - volume_mean) / volume_std
                    if z_score > self.volume_outlier_threshold:
                        score -= 0.1
                        anomalies.append("volume_outlier")
        
        # 5. 데이터 신선도 검사
        data_age = time.time() - ticker.timestamp
        if data_age > 300:  # 5분 이상 된 데이터
            score -= 0.1
            anomalies.append("stale_data")
        
        return {
            "score": max(0.0, score),
            "anomalies": anomalies
        }
    
    def _determine_quality_grade(self, score: float) -> DataQuality:
        """품질 등급 결정"""
        for quality, threshold in self.quality_thresholds.items():
            if score >= threshold:
                return quality
        return DataQuality.INVALID
    
    def _update_history(self, ticker: NormalizedTicker):
        """이력 데이터 업데이트"""
        key = f"{ticker.exchange}:{ticker.symbol}"
        self.price_history[key].append((ticker.price, ticker.timestamp))
        self.volume_history[key].append((ticker.volume_24h, ticker.timestamp))

class ConsistencyChecker:
    """데이터 일관성 검사기"""
    
    def __init__(self):
        self.consistency_threshold = 15.0  # 15% 편차 허용
        self.minimum_exchanges = 2  # 최소 비교 대상 거래소 수
        
    def check_price_consistency(
        self, 
        tickers: List[NormalizedTicker]
    ) -> Dict[str, PriceConsistencyCheck]:
        """가격 일관성 검사"""
        # 심볼별로 그룹화
        symbol_groups = defaultdict(list)
        for ticker in tickers:
            if ticker.data_quality not in [DataQuality.POOR, DataQuality.INVALID]:
                symbol_groups[ticker.symbol].append(ticker)
        
        results = {}
        
        for symbol, ticker_list in symbol_groups.items():
            if len(ticker_list) < self.minimum_exchanges:
                continue
            
            # KRW 기준 가격으로 통일 (국내외 거래소 비교)
            prices = {}
            valid_tickers = []
            
            for ticker in ticker_list:
                if ticker.price_krw and ticker.price_krw > 0:
                    prices[ticker.exchange] = ticker.price_krw
                    valid_tickers.append(ticker)
            
            if len(prices) < self.minimum_exchanges:
                continue
            
            # 편차 계산
            price_values = list(prices.values())
            mean_price = statistics.mean(price_values)
            max_deviation = 0.0
            outliers = []
            
            for exchange, price in prices.items():
                deviation = abs(price - mean_price) / mean_price * 100
                max_deviation = max(max_deviation, deviation)
                
                if deviation > self.consistency_threshold:
                    outliers.append(exchange)
            
            results[symbol] = PriceConsistencyCheck(
                symbol=symbol,
                exchanges=list(prices.keys()),
                prices=prices,
                max_deviation=max_deviation,
                is_consistent=max_deviation <= self.consistency_threshold,
                outliers=outliers
            )
        
        return results
    
    def detect_arbitrage_opportunities(
        self, 
        consistency_results: Dict[str, PriceConsistencyCheck]
    ) -> List[Dict[str, Any]]:
        """차익거래 기회 탐지"""
        opportunities = []
        
        for symbol, check in consistency_results.items():
            if not check.is_consistent and len(check.prices) >= 2:
                prices = check.prices
                min_exchange = min(prices, key=prices.get)
                max_exchange = max(prices, key=prices.get)
                
                min_price = prices[min_exchange]
                max_price = prices[max_exchange]
                
                # 차익거래 비율 계산
                arbitrage_percent = (max_price - min_price) / min_price * 100
                
                if arbitrage_percent > 2.0:  # 2% 이상 차이
                    opportunities.append({
                        "symbol": symbol,
                        "buy_exchange": min_exchange,
                        "sell_exchange": max_exchange,
                        "buy_price": min_price,
                        "sell_price": max_price,
                        "arbitrage_percent": arbitrage_percent,
                        "timestamp": time.time()
                    })
        
        return sorted(opportunities, key=lambda x: x["arbitrage_percent"], reverse=True)

class DataPipeline:
    """데이터 처리 파이프라인"""
    
    def __init__(self):
        self.normalizer = DataNormalizer()
        self.consistency_checker = ConsistencyChecker()
        
        # 처리된 데이터 저장
        self.normalized_data: Dict[str, Dict[str, NormalizedTicker]] = defaultdict(dict)
        self.consistency_results: Dict[str, PriceConsistencyCheck] = {}
        self.arbitrage_opportunities: List[Dict[str, Any]] = []
        
        # 통계 정보
        self.processing_stats = {
            "total_processed": 0,
            "successful_normalizations": 0,
            "failed_normalizations": 0,
            "quality_distribution": defaultdict(int),
            "last_update": time.time()
        }
        
    async def process_ticker_data(
        self, 
        exchange: str, 
        symbol: str, 
        raw_data: Dict[str, Any]
    ) -> Optional[NormalizedTicker]:
        """티커 데이터 처리"""
        self.processing_stats["total_processed"] += 1
        
        try:
            # 데이터 정규화
            normalized = self.normalizer.normalize_ticker(exchange, symbol, raw_data)
            
            if normalized:
                # 처리된 데이터 저장
                self.normalized_data[symbol][exchange] = normalized
                self.processing_stats["successful_normalizations"] += 1
                self.processing_stats["quality_distribution"][normalized.data_quality.value] += 1
                
                # 품질이 낮은 데이터는 로그 기록
                if normalized.data_quality in [DataQuality.POOR, DataQuality.INVALID]:
                    logger.warning(
                        f"낮은 품질 데이터 감지: {exchange}/{symbol} "
                        f"(품질: {normalized.data_quality.value}, "
                        f"점수: {normalized.validation_score:.2f}, "
                        f"이상: {normalized.anomaly_flags})"
                    )
                
                return normalized
            else:
                self.processing_stats["failed_normalizations"] += 1
                return None
                
        except Exception as e:
            logger.error(f"데이터 처리 실패 ({exchange}/{symbol}): {e}")
            self.processing_stats["failed_normalizations"] += 1
            return None
    
    async def run_consistency_check(self):
        """일관성 검사 실행"""
        try:
            # 모든 정규화된 데이터 수집
            all_tickers = []
            for symbol_data in self.normalized_data.values():
                all_tickers.extend(symbol_data.values())
            
            # 일관성 검사
            self.consistency_results = self.consistency_checker.check_price_consistency(all_tickers)
            
            # 차익거래 기회 탐지
            self.arbitrage_opportunities = self.consistency_checker.detect_arbitrage_opportunities(
                self.consistency_results
            )
            
            # 결과 로깅
            inconsistent_count = sum(1 for check in self.consistency_results.values() if not check.is_consistent)
            if inconsistent_count > 0:
                logger.info(f"가격 불일치 감지: {inconsistent_count}개 심볼")
            
            if self.arbitrage_opportunities:
                logger.info(f"차익거래 기회 {len(self.arbitrage_opportunities)}개 발견")
                
        except Exception as e:
            logger.error(f"일관성 검사 실패: {e}")
    
    def get_normalized_data(self, symbol: str = None, exchange: str = None) -> Dict[str, Any]:
        """정규화된 데이터 반환"""
        if symbol and exchange:
            return self.normalized_data.get(symbol, {}).get(exchange)
        elif symbol:
            return self.normalized_data.get(symbol, {})
        else:
            return dict(self.normalized_data)
    
    def get_data_quality_report(self) -> Dict[str, Any]:
        """데이터 품질 보고서"""
        total_processed = self.processing_stats["total_processed"]
        success_rate = (
            self.processing_stats["successful_normalizations"] / total_processed * 100
            if total_processed > 0 else 0
        )
        
        return {
            "processing_stats": dict(self.processing_stats),
            "success_rate": round(success_rate, 2),
            "quality_distribution": dict(self.processing_stats["quality_distribution"]),
            "consistency_summary": {
                "total_symbols_checked": len(self.consistency_results),
                "consistent_symbols": sum(1 for check in self.consistency_results.values() if check.is_consistent),
                "inconsistent_symbols": sum(1 for check in self.consistency_results.values() if not check.is_consistent),
            },
            "arbitrage_opportunities": len(self.arbitrage_opportunities),
            "data_freshness": time.time() - self.processing_stats["last_update"]
        }
    
    def get_arbitrage_opportunities(self, min_percent: float = 1.0) -> List[Dict[str, Any]]:
        """차익거래 기회 반환"""
        return [
            opp for opp in self.arbitrage_opportunities 
            if opp["arbitrage_percent"] >= min_percent
        ]
    
    async def start_periodic_checks(self, interval: int = 60):
        """주기적 일관성 검사 시작"""
        while True:
            try:
                await self.run_consistency_check()
                self.processing_stats["last_update"] = time.time()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"주기적 일관성 검사 오류: {e}")
                await asyncio.sleep(10)