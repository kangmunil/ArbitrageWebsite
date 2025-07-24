# SidebarLiquidations 컴포넌트

**실시간 암호화폐 청산 데이터**를 표시하는 320px 사이드바 컴포넌트입니다.

## 🎯 전체 UI 흐름

```
실시간 청산 데이터   (업데이트: 21:58:55)

Bitmex  롱 $0.88M / 숏 $0.86M
Bybit   롱 $1.88M / 숏 $0.00M  ← 상위 2개 굵은 글씨
Bitget  롱 $0.20M / 숏 $0.70M
Okx     롱 $0.42M / 숏 $0.00M
Binance 롱 $0.12M / 숏 $0.01M

───────── 5분 거래소별 청산 (M USD) ─────────
▌▐  ▌▐  ▌▐  ← 가로 스택 막대 (롱=파랑, 숏=빨강)
```

## 설치 의존성

```bash
# 필수 패키지
npm install recharts lucide-react dayjs axios

# TypeScript 지원 (선택사항)
npm install -D @types/react @types/node
```

## 사용 방법

```tsx
import SidebarLiquidations from './components/SidebarLiquidations';

function App() {
  return (
    <div className="flex">
      <main className="flex-1">
        {/* 메인 콘텐츠 */}
      </main>
      <aside className="w-80">
        <SidebarLiquidations />
      </aside>
    </div>
  );
}
```

## 주요 기능

### 📊 거래소별 요약
- 상위 5개 거래소의 롱/숏 청산 현황
- 상위 2개 거래소는 **굵은 글씨**로 강조
- 금액 표시: `1,234,000 → 1.23M` 형식

### 📈 5분 이동창 스택형 바 차트
- Recharts 기반 스택 바 차트
- 롱 포지션: 파란색 (#3b82f6)
- 숏 포지션: 빨간색 (#ef4444)
- 높이: 110px, 반응형 폭
- 커스텀 툴팁: "롱 $2.1M", "숏 $1.5M"

### ⚡ 실시간 업데이트
- 15초 간격 자동 polling
- WebSocket 실시간 데이터 수신
- 네트워크 오류 시 캐시된 데이터 fallback

## API 엔드포인트

```typescript
// 요약 데이터
GET /api/liquidations/aggregated?limit=60

// 트렌드 데이터 (예정)
GET /liquidations/trend?window=5m
```

## 데이터 구조

```typescript
interface LiquidationSummary {
  exchange: string;
  long: number;
  short: number;
}

interface LiquidationTrend {
  minute: string;  // "21:30"
  long: number;    // USD(백만) 단위
  short: number;
}
```

## 성능 최적화

- ✅ 15초 polling으로 서버 부하 최소화
- ✅ WebSocket 재연결 로직 (3초 딜레이)
- ✅ 5분 캐시로 네트워크 오류 대응
- ✅ 100% 높이 제약에서 `overflow-y: auto`

## 스타일링

- **Tailwind CSS** 전용 (인라인 스타일 없음)
- **다크 테마** 기본 (gray-900 배경)
- **반응형** 320px 고정폭
- **접근성** 고려 (aria-label, 키보드 탐색)

## 에러 처리

1. **API 오류**: 캐시된 데이터 사용 (5분 이내)
2. **WebSocket 오류**: 자동 재연결 시도
3. **타임아웃**: 10초 후 더미 데이터 표시
4. **파싱 오류**: 콘솔 로그 + 이전 상태 유지