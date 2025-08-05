# Market Sentiment & Liquidation Service Architecture

## 🎯 목표
- **롱숏 비율**: Binance/Bitget API로 직접 수집
- **청산 데이터**: 무료 방법으로 실시간 수집 및 추정
- **시장 심리**: 종합적인 지표 제공

## 📁 디렉토리 구조
```
liquidation_service/
├── main.py                    # FastAPI 서버
├── __init__.py
├── requirements.txt
├── Dockerfile
├── collectors/               # 데이터 수집 모듈
│   ├── __init__.py
│   ├── long_short_collector.py      # 롱숏 비율 API 수집
│   ├── liquidation_websocket.py     # 바이낸스 청산 웹소켓
│   └── market_indicators.py         # 간접 지표 수집
├── analyzers/               # 데이터 분석 모듈
│   ├── __init__.py
│   ├── liquidation_estimator.py     # 청산 추정 알고리즘
│   └── sentiment_analyzer.py        # 시장 심리 분석
├── models/                  # 데이터 모델
│   ├── __init__.py
│   └── data_schemas.py
├── utils/                   # 유틸리티
│   ├── __init__.py
│   ├── websocket_manager.py
│   └── redis_cache.py
├── logs/
└── shared/ -> ../shared/
```

## 🔄 데이터 플로우

### 1. 롱숏 비율 수집 (직접 API)
```
Binance API ──┐
Bitget API ──┼──→ Long/Short Collector ──→ Redis Cache ──→ API Response
OKX API ────┘
```

### 2. 청산 데이터 수집 (무료 혁신적 방법)
```
┌─ Binance Liquidation WebSocket (!forceOrder@arr)
├─ Price Volatility Analysis
├─ Funding Rate Extremes  
├─ Open Interest Changes
└─ Volume Spike Detection
    ↓
  Liquidation Estimator Algorithm
    ↓
  Aggregated Liquidation Data
```

## 💡 청산 데이터 무료 구현 전략

### Method 1: 바이낸스 청산 웹소켓
```python
# 실시간 청산 이벤트 수집
websocket_url = "wss://fstream.binance.com/ws/!forceOrder@arr"
# 개별 청산 → 24시간 집계 → 시간별/코인별 통계
```

### Method 2: 간접 지표 기반 추정
```python
# 청산 위험도 계산 공식
liquidation_risk = (
    funding_rate_extreme * 0.3 +      # 펀딩비율 극값
    price_volatility * 0.25 +         # 가격 변동성
    oi_decrease_rate * 0.25 +         # 미결제약정 감소율  
    volume_spike * 0.2                # 거래량 급증
)
```

### Method 3: 시장 이벤트 감지
```python
# 청산 연쇄반응 감지
if (price_drop > 5% and volume_increase > 200% 
    and funding_rate > 0.1%):
    estimated_liquidation = calculate_liquidation_volume()
```

## 🚀 API 엔드포인트 설계

```
GET /api/long-short/{symbol}     # 롱숏 비율
GET /api/liquidations/24h        # 24시간 청산 데이터
GET /api/liquidations/real-time  # 실시간 청산 스트림
GET /api/market-sentiment        # 종합 시장 심리
GET /api/liquidation-heatmap     # 청산 히트맵 데이터
```

## 🔧 기술 스택

- **FastAPI**: REST API 서버
- **WebSocket**: 실시간 데이터 스트리밍  
- **Redis**: 데이터 캐싱 및 집계
- **aiohttp**: 비동기 HTTP 클라이언트
- **websockets**: WebSocket 클라이언트
- **pandas**: 데이터 분석 및 집계

## 📊 데이터 품질 보장

1. **Multiple Source Validation**: 여러 지표 교차 검증
2. **Historical Backtesting**: 과거 데이터로 추정 알고리즘 검증
3. **Real-time Monitoring**: 데이터 품질 실시간 모니터링
4. **Fallback Mechanisms**: 데이터 소스 장애 시 대체 방안

이 아키텍처로 무료로도 상당히 정확한 청산 데이터를 제공할 수 있습니다!