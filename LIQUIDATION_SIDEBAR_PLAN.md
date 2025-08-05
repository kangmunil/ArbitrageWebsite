# 청산 데이터 & 롱숏 비율 사이드바 구현 계획

## 단계별 구현 전략

### Phase 1: 롱숏 비율 (즉시 구현 가능)
```javascript
// API 엔드포인트 예시
- Binance: /fapi/v1/longShortRatio (24h 데이터)
- Bitget: /api/v2/mix/market/long-short (24h 데이터)
```

**구현 위치:**
- `backend/market-data-service/` - 데이터 수집
- `frontend/src/components/SidebarLiquidations.js` - UI 컴포넌트

### Phase 2: 청산 데이터 (선택적 구현)

#### 옵션 A: 무료 대안 (간접 지표)
```javascript
// 활용 가능한 무료 데이터
- 미결제약정 (Open Interest)
- 펀딩비율 (Funding Rates) 
- 테이커 매수/매도 거래량
- 공포/탐욕 지수
```

#### 옵션 B: 유료 API 통합
```javascript
// CoinGlass API ($29/월)
- /public/v2/liquidation_chart
- 여러 거래소 집계 데이터
- 24시간 청산 볼륨
```

### Phase 3: UI/UX 설계

#### 사이드바 레이아웃
```
┌─────────────────────┐
│ 📊 시장 지표         │
├─────────────────────┤
│ 🟢 BTC 롱숏비율     │
│    롱: 65% 숏: 35%  │
├─────────────────────┤
│ 📉 24h 청산현황     │
│    총: $142M        │
│    롱: $98M (69%)   │
│    숏: $44M (31%)   │
├─────────────────────┤
│ ⚡ 주요 코인 현황    │
│    BTC: $2.1M       │
│    ETH: $1.8M       │
└─────────────────────┘
```

## 기술 구현 세부사항

### 백엔드 확장
1. **새로운 서비스**: `liquidation-data-collector`
2. **Redis 캐싱**: 1분 간격 업데이트
3. **WebSocket**: 실시간 데이터 스트리밍

### 프론트엔드 컴포넌트
```jsx
// 새 컴포넌트 구조
<SidebarMetrics>
  <LongShortRatio />
  <LiquidationSummary />
  <TopCoinsLiquidation />
</SidebarMetrics>
```

## 예산 고려사항

### 무료 구현 (Phase 1)
- 롱숏 비율만 구현
- 간접 청산 지표 활용
- 비용: $0

### 프리미엄 구현 (Phase 2)
- CoinGlass API 구독
- 완전한 청산 데이터
- 비용: $29/월 (~₩40,000)

## 권장 접근법

1. **먼저 롱숏 비율부터 구현** (무료, 즉시 가능)
2. **간접 지표로 청산 위험도 표시** (창의적 해결)
3. **트래픽/사용자 증가 시 유료 API 도입** (점진적 업그레이드)

이 방식으로 비용 부담 없이 기능을 시작하고, 필요에 따라 점진적으로 확장할 수 있습니다.