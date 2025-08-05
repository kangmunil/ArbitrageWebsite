# 실시간 청산 & 롱숏 비율 위젯 (LiquidationWidget)

사이드바(320px 고정폭)에 표시되는 실시간 암호화폐 청산 데이터와 롱숏 비율을 통합한 위젯입니다.

## 주요 기능

### 📊 롱숏 비율 섹션 (상단)
- **실시간 롱숏 비율**: 주요 5개 코인 (BTC, ETH, SOL, DOGE, ADA)
- **시각적 게이지**: 롱/숏 비율을 막대 그래프로 표시
- **색상 코딩**: 
  - 롱 우세(>60%): 🟢 초록색
  - 균형(40-60%): 🟡 노란색  
  - 숏 우세(<40%): 🔴 빨간색
- **자동 업데이트**: 5분마다 새로운 데이터 갱신
- **거래소별 데이터**: Binance 기준 롱숏 비율

### 📋 24시간 청산 현황 섹션 (하단)
- **실시간 청산 집계**: Binance WebSocket 기반
- **코인별 청산 요약**: 
  - 총 청산액 (USD)
  - 롱 청산 비율 vs 숏 청산 비율
  - 청산 이벤트 개수
- **시각적 표시**:
  - 청산 규모별 색상 강도 (진한 빨강 = 큰 청산)
  - 롱/숏 비율 막대 차트
- **정렬 옵션**: 청산액 순, 이벤트 수 순
- **실시간 업데이트**: WebSocket 스트림 연결

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

### REST API (청산 서비스: Port 8002)
- `GET /api/long-short/BTCUSDT` - 개별 코인 롱숏 비율
- `GET /api/long-short/all` - 전체 코인 롱숏 비율
- `GET /api/liquidations/24h` - 24시간 청산 요약
- `GET /api/liquidations/aggregated?limit=10` - 상위 청산 데이터

### WebSocket (청산 서비스)
- `ws://localhost:8002/ws/liquidations` - 실시간 청산 스트림

### API Gateway 연동 (Port 8000)
- 기존 WebSocket과 병행 사용
- 청산 서비스 데이터 프록시 역할

## 위젯 레이아웃 구조

```
┌─────────────────────────────────┐ 320px
│ 📊 롱숏 비율 (상단 40%)          │
│ ┌─ BTC ──────────── 58% L 42% S │
│ ├─ ETH ──────────── 62% L 38% S │ 
│ ├─ SOL ──────────── 45% L 55% S │
│ ├─ DOGE ─────────── 51% L 49% S │
│ └─ ADA ──────────── 48% L 52% S │
│                                 │
│ 📋 24시간 청산 현황 (하단 60%)   │
│ ┌─ ETHUSDT ────── $262.8K (34건)│
│ ├─ SOLUSDT ────── $63.9K (21건) │
│ ├─ LTCUSDT ────── $61.7K (8건)  │
│ ├─ DOGEUSDT ───── $56.1K (18건) │
│ └─ BTCUSDT ────── $45.3K (15건) │
└─────────────────────────────────┘
```

## 기술 스택

- **React 18** + Hooks (useState, useEffect, useRef)
- **TailwindCSS** - 스타일링 및 반응형 디자인
- **lucide-react** - 아이콘 (TrendingUp, TrendingDown, Activity)
- **Custom Hooks**: 
  - `useLongShortData` - 롱숏 비율 데이터 관리
  - `useLiquidationData` - 청산 데이터 관리
- **WebSocket** - 실시간 데이터 스트림

## 반응형 설계

- **고정 폭**: 320px (사이드바 표준)
- **높이**: 가변 (콘텐츠에 따라 자동 조절)
- **스크롤**: 청산 리스트 영역만 스크롤 가능
- **모바일 최적화**: 터치에 최적화된 인터랙션

## 성능 최적화

- **메모이제이션**: React.memo로 불필요한 리렌더링 방지
- **데이터 캐싱**: 5분간 롱숏 비율 캐시 유지
- **WebSocket 최적화**: 자동 재연결 및 연결 상태 관리
- **렌더링 최적화**: 가상화 없이 최대 10개 항목만 표시

## 컴포넌트 구조

### 메인 컴포넌트: `LiquidationWidget.js`
```jsx
const LiquidationWidget = () => {
  // 상태 관리
  const [longShortData, setLongShortData] = useState({});
  const [liquidationData, setLiquidationData] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  
  // 커스텀 훅 사용
  const { data: lsData, loading: lsLoading } = useLongShortData();
  const { data: liqData, loading: liqLoading } = useLiquidationData();
  
  return (
    <div className="w-80 bg-white rounded-lg shadow-lg p-4">
      <LongShortSection data={lsData} loading={lsLoading} />
      <LiquidationSection data={liqData} loading={liqLoading} />
    </div>
  );
};
```

### 하위 컴포넌트들

#### `LongShortSection.js`
- 롱숏 비율 표시 섹션
- 5개 주요 코인의 비율을 막대 그래프로 표시
- 색상 코딩 및 애니메이션 효과

#### `LiquidationSection.js`  
- 24시간 청산 현황 표시 섹션
- 청산액 순으로 정렬된 코인 리스트
- 실시간 업데이트 표시

#### `ProgressBar.js`
- 재사용 가능한 진행률 표시 컴포넌트
- 롱/숏 비율과 청산 비율 모두에서 사용

#### 커스텀 훅들

##### `useLongShortData.js`
```jsx
const useLongShortData = () => {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('http://localhost:8002/api/long-short/all');
        const result = await response.json();
        setData(result.data);
      } catch (error) {
        console.error('Long/Short data fetch error:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5 * 60 * 1000); // 5분마다
    return () => clearInterval(interval);
  }, []);

  return { data, loading };
};
```

##### `useLiquidationData.js`
```jsx
const useLiquidationData = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const ws = useRef(null);

  useEffect(() => {
    // WebSocket 연결
    const connectWebSocket = () => {
      ws.current = new WebSocket('ws://localhost:8002/ws/liquidations');
      
      ws.current.onmessage = (event) => {
        const newData = JSON.parse(event.data);
        setData(newData.liquidations || []);
      };
    };

    connectWebSocket();
    return () => ws.current?.close();
  }, []);

  return { data, loading };
};
```

## 실시간 데이터 플로우

1. **초기 로드**: REST API로 현재 상태 가져오기
2. **실시간 업데이트**: WebSocket으로 청산 데이터 스트림
3. **주기적 갱신**: 5분마다 롱숏 비율 업데이트
4. **에러 처리**: 연결 실패 시 자동 재연결 시도

## 스타일링 가이드

### 색상 팔레트
- **롱 우세**: `bg-green-500` (#10B981)
- **균형**: `bg-yellow-500` (#F59E0B)  
- **숏 우세**: `bg-red-500` (#EF4444)
- **배경**: `bg-gray-50` (#F9FAFB)
- **텍스트**: `text-gray-800` (#1F2937)

### 애니메이션
- **진행바**: `transition-all duration-500 ease-in-out`
- **데이터 업데이트**: `animate-pulse` (로딩 시)
- **WebSocket 연결**: `animate-bounce` (연결 표시기)