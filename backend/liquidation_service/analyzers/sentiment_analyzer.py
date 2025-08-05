"""Market Sentiment Analyzer

롱숏 비율과 청산 데이터를 종합한 시장 심리 분석 (미래 구현 예정)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
# import numpy as np  # 추후 구현 시 활성화

from models.data_schemas import MarketSentiment, LongShortRatio, LiquidationSummary
from utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """시장 심리 종합 분석기 (개발 중)"""
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.redis_cache = redis_cache
        
        # 심리 점수 가중치
        self.sentiment_weights = {
            "long_short_ratio": 0.60,    # 롱숏 비율 가중치
            "liquidation_data": 0.40     # 청산 데이터 가중치
        }
        
        # 심리 임계값
        self.sentiment_thresholds = {
            "extreme_bearish": -75,
            "bearish": -25,
            "neutral": 25,
            "bullish": 75,
            "extreme_bullish": 100
        }
    
    async def analyze_market_sentiment(
        self,
        symbol: str,
        long_short_ratios: Dict[str, LongShortRatio],
        liquidation_summary: Optional[LiquidationSummary] = None
    ) -> MarketSentiment:
        """종합 시장 심리 분석"""
        
        # 롱숏 비율 기반 심리 분석
        ls_sentiment = await self._analyze_long_short_sentiment(long_short_ratios)
        
        # 청산 데이터 기반 심리 분석
        liq_sentiment = await self._analyze_liquidation_sentiment(liquidation_summary)
        
        # 종합 심리 점수 계산
        total_sentiment = (
            ls_sentiment * self.sentiment_weights["long_short_ratio"] +
            liq_sentiment * self.sentiment_weights["liquidation_data"]
        )
        
        # 심리 라벨 결정
        sentiment_label = self._get_sentiment_label(total_sentiment)
        
        # 지배적 트렌드 분석
        dominant_trend = self._analyze_dominant_trend(total_sentiment, ls_sentiment, liq_sentiment)
        
        # 시장 단계 분석
        market_phase = self._analyze_market_phase(long_short_ratios, liquidation_summary)
        
        # 신뢰도 계산
        confidence = self._calculate_confidence(long_short_ratios, liquidation_summary)
        
        return MarketSentiment(
            symbol=symbol,
            timestamp=datetime.now(),
            sentiment_score=total_sentiment,
            sentiment_label=sentiment_label,
            long_short_sentiment=ls_sentiment,
            liquidation_sentiment=liq_sentiment,
            confidence=confidence,
            dominant_trend=dominant_trend,
            market_phase=market_phase
        )
    
    async def _analyze_long_short_sentiment(
        self, 
        long_short_ratios: Dict[str, LongShortRatio]
    ) -> float:
        """롱숏 비율 기반 심리 분석"""
        if not long_short_ratios:
            return 0
        
        sentiment_scores = []
        
        for exchange, ratio in long_short_ratios.items():
            # 롱숏 비율을 심리 점수로 변환
            ls_ratio = ratio.long_short_ratio
            
            if ls_ratio > 3.0:  # 롱 비율이 매우 높음 (과매수 위험)
                score = -30  # 역발상 신호
            elif ls_ratio > 2.0:  # 롱 비율이 높음
                score = -15
            elif ls_ratio > 1.5:  # 롱 비율이 약간 높음
                score = 10
            elif ls_ratio > 1.0:  # 롱 비율이 균형보다 약간 높음
                score = 20
            elif ls_ratio > 0.5:  # 숏 비율이 약간 높음
                score = -10
            elif ls_ratio > 0.3:  # 숏 비율이 높음
                score = 15  # 역발상 신호
            else:  # 숏 비율이 매우 높음 (과매도 반등 가능)
                score = 30
            
            # 상위 트레이더 데이터는 더 높은 가중치
            weight = 1.5 if ratio.top_traders_only else 1.0
            sentiment_scores.append(score * weight)
        
        # 가중 평균 계산
        if sentiment_scores:
            return sum(sentiment_scores) / len(sentiment_scores)
        return 0
    
    async def _analyze_liquidation_sentiment(
        self, 
        liquidation_summary: Optional[LiquidationSummary]
    ) -> float:
        """청산 데이터 기반 심리 분석"""
        if not liquidation_summary or liquidation_summary.total_liquidation_usd == 0:
            return 0
        
        # 청산 비율 분석
        long_percentage = liquidation_summary.long_percentage
        short_percentage = liquidation_summary.short_percentage
        
        # 청산 규모 분석 (USD 기준)
        total_liquidation = liquidation_summary.total_liquidation_usd
        
        # 규모별 영향도 계산
        if total_liquidation > 50_000_000:  # 5천만 달러 이상
            magnitude_multiplier = 2.0
        elif total_liquidation > 10_000_000:  # 1천만 달러 이상
            magnitude_multiplier = 1.5
        elif total_liquidation > 1_000_000:   # 100만 달러 이상
            magnitude_multiplier = 1.2
        else:
            magnitude_multiplier = 1.0
        
        # 청산 비율에 따른 심리 점수
        if long_percentage > 80:  # 롱 청산이 80% 이상
            sentiment_score = 30 * magnitude_multiplier  # 강세 신호 (숏 스퀴즈 가능)
        elif long_percentage > 60:  # 롱 청산이 60% 이상
            sentiment_score = 15 * magnitude_multiplier
        elif long_percentage > 40:  # 균형
            sentiment_score = 0
        elif long_percentage > 20:  # 숏 청산이 많음
            sentiment_score = -15 * magnitude_multiplier
        else:  # 숏 청산이 80% 이상
            sentiment_score = -30 * magnitude_multiplier  # 약세 신호
        
        return min(max(sentiment_score, -50), 50)  # -50 ~ 50 범위로 제한
    
    def _get_sentiment_label(self, sentiment_score: float) -> str:
        """심리 점수를 라벨로 변환"""
        if sentiment_score >= self.sentiment_thresholds["extreme_bullish"]:
            return "극도강세"
        elif sentiment_score >= self.sentiment_thresholds["bullish"]:
            return "강세"
        elif sentiment_score >= self.sentiment_thresholds["neutral"]:
            return "중립"
        elif sentiment_score >= self.sentiment_thresholds["bearish"]:
            return "약세"
        else:
            return "극도약세"
    
    def _analyze_dominant_trend(
        self, 
        total_sentiment: float, 
        ls_sentiment: float, 
        liq_sentiment: float
    ) -> str:
        """지배적 트렌드 분석"""
        if total_sentiment > 15:
            return "bullish"
        elif total_sentiment < -15:
            return "bearish"
        else:
            # 롱숏 비율과 청산 데이터가 상반된 신호를 보내는 경우
            if abs(ls_sentiment - liq_sentiment) > 30:
                return "conflicted"
            return "neutral"
    
    def _analyze_market_phase(
        self,
        long_short_ratios: Dict[str, LongShortRatio],
        liquidation_summary: Optional[LiquidationSummary]
    ) -> str:
        """시장 단계 분석 (Wyckoff 이론 기반)"""
        # 간단한 구현 (추후 개선 예정)
        
        if not long_short_ratios:
            return "unknown"
        
        # 평균 롱숏 비율 계산
        ratios = [ratio.long_short_ratio for ratio in long_short_ratios.values()]
        avg_ls_ratio = sum(ratios) / len(ratios) if ratios else 0
        
        # 청산 활동 수준
        high_liquidation = (
            liquidation_summary and 
            liquidation_summary.total_liquidation_usd > 10_000_000
        )
        
        if avg_ls_ratio > 2.0 and high_liquidation:
            return "distribution"  # 분산 단계 (상승 후 매도)
        elif avg_ls_ratio < 0.5 and high_liquidation:
            return "markdown"      # 하락 단계
        elif avg_ls_ratio > 1.5 and not high_liquidation:
            return "markup"        # 상승 단계
        elif avg_ls_ratio < 0.8 and not high_liquidation:
            return "accumulation"  # 축적 단계 (하락 후 매수)
        else:
            return "neutral"
    
    def _calculate_confidence(
        self,
        long_short_ratios: Dict[str, LongShortRatio],
        liquidation_summary: Optional[LiquidationSummary]
    ) -> float:
        """분석 신뢰도 계산"""
        confidence_factors = []
        
        # 데이터 가용성
        if long_short_ratios:
            confidence_factors.append(0.5)
        
        if liquidation_summary and liquidation_summary.total_events > 10:
            confidence_factors.append(0.3)
        
        # 거래소 간 일관성
        if len(long_short_ratios) > 1:
            ratios = [ratio.long_short_ratio for ratio in long_short_ratios.values()]
            mean_ratio = sum(ratios) / len(ratios)
            variance = sum((r - mean_ratio) ** 2 for r in ratios) / len(ratios)
            std_dev = variance ** 0.5  # 표준편차 계산
            consistency = max(0, 1 - std_dev)  # 표준편차가 낮을수록 일관성 높음
            confidence_factors.append(consistency * 0.2)
        
        return min(sum(confidence_factors), 1.0)
    
    async def get_sentiment_history(
        self, 
        symbol: str, 
        hours: int = 24
    ) -> List[Dict]:
        """심리 변화 히스토리 조회 (미구현)"""
        # TODO: Redis에서 과거 심리 데이터 조회
        return []
    
    async def detect_sentiment_shifts(
        self, 
        symbol: str
    ) -> Dict:
        """심리 전환점 감지 (미구현)"""
        # TODO: 급격한 심리 변화 감지 알고리즘
        return {
            "symbol": symbol,
            "shift_detected": False,
            "shift_magnitude": 0,
            "shift_direction": "none",
            "confidence": 0
        }


# 개발 중인 고급 기능들
class AdvancedSentimentAnalyzer:
    """고급 심리 분석 기능 (미래 구현)"""
    
    @staticmethod
    async def analyze_social_sentiment(symbol: str) -> Dict:
        """소셜 미디어 심리 분석"""
        return {"status": "not_implemented"}
    
    @staticmethod
    async def analyze_whale_sentiment(symbol: str) -> Dict:
        """대형 투자자 심리 분석"""
        return {"status": "not_implemented"}
    
    @staticmethod
    async def predict_sentiment_trend(symbol: str, hours: int = 24) -> Dict:
        """심리 트렌드 예측"""
        return {"status": "not_implemented"}