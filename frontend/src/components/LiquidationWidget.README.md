# 실시간 청산 데이터 위젯 (LiquidationWidget)

사이드바(320px 고정폭)에 표시되는 실시간 암호화폐 청산 데이터 위젯입니다.

## 주요 기능

### 📊 거래소별 요약 섹션
- 5개 주요 거래소(Binance, Bybit, OKX, Bitget, Kraken)의 청산 현황
- 클릭으로 상세 데이터 확장/축소
- 상위 2개 거래소는 **굵은 글씨**로 강조
- 급증(100만 달러 이상) 거래소는 **오렌지 테두리**로 표시

### 📋 상세 청산 리스트
- 선택된 거래소의 개별 청산 내역
- **Long**(파랑)/Short(빨강) 필터링 옵션
- 청산 규모 축약 표시 ($1.2M, $350K 등)
- 상대적 시간 표시 ("5분 전", "1시간 전")
- **자동 순환** 모드 (5초 간격)

### 📈 전체 현황 미니 차트
- 전체 거래소 청산 합계
- 5x1 그리드 히트맵으로 거래소별 비교
- 강도별 색상 표시

## 사용 방법

```jsx
import LiquidationWidget from './components/LiquidationWidget';

function App() {
  return (
    <div className="flex">
      <main className="flex-1">
        {/* 메인 콘텐츠 */}
      </main>
      <aside>
        <LiquidationWidget />
      </aside>
    </div>
  );
}
```

## 데이터 소스

### REST API
- `GET /liquidations/summary?window=5m` - 거래소별 요약
- `GET /liquidations/detail?exchange=Binance&window=5m` - 상세 내역

### WebSocket
- `ws://localhost:8000/ws/liquidations` - 실시간 업데이트

## 기술 스택

- **React 18** + Hooks
- **TailwindCSS** - 스타일링
- **lucide-react** - 아이콘
- **axios** - HTTP 클라이언트
- **WebSocket** - 실시간 통신

## 반응형 설계

- 고정 폭: **320px**
- 높이: **100vh** (overflow-y: auto)
- 모바일 최적화: 터치 친화적 버튼 크기

## 성능 최적화

- 30초마다 자동 새로고침
- WebSocket 재연결 로직 (3초 딜레이)
- 최대 20개 상세 항목 표시
- 자동 순환 시 1개 항목만 렌더링