# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cryptocurrency arbitrage monitoring website that displays price differences between Korean exchanges (Upbit, Bithumb) and overseas exchanges (Binance, Bybit). The application calculates the "Kimchi Premium" - the price difference between Korean and international cryptocurrency exchanges.

## Development Commands

### Backend (FastAPI)
- **Start backend locally**: `cd backend && uvicorn app.main:app --reload`
- **Install dependencies**: `cd backend && pip install -r requirements.txt`
- **Database setup**: `cd backend && python app/create_db_tables.py` (creates MySQL tables)
- **Seed database**: `cd backend && python app/seed.py` (populates initial data)

### Frontend (React)
- **Start frontend locally**: `cd frontend && npm start`
- **Install dependencies**: `cd frontend && npm install`
- **Build for production**: `cd frontend && npm run build`
- **Run tests**: `cd frontend && npm test`

### Docker Development
- **Start entire stack**: `docker-compose up --build`
- **Backend only**: `docker-compose up backend db`
- **Stop services**: `docker-compose down`

## Architecture

### Backend Structure
- **FastAPI application** with WebSocket support for real-time price updates
- **SQLAlchemy ORM** with MySQL database (models: Exchange, Cryptocurrency, CoinPrice, PremiumHistory)
- **Real-time price fetching** from multiple exchanges via REST APIs
- **WebSocket connection manager** for broadcasting price updates to connected clients
- **Background task** (`price_updater`) runs every 1 second to fetch and broadcast prices

### Key Backend Components
- `main.py`: FastAPI app, WebSocket endpoints, and background price updater
- `services.py`: Exchange API integrations (Upbit, Binance, Bithumb, Bybit, etc.)
- `liquidation_services.py`: Real-time liquidation data collection from multiple exchanges
- `models.py`: SQLAlchemy database models
- `schemas.py`: Pydantic data schemas for API request/response validation
- `database.py`: Database connection and session management
- `create_db_tables.py`: Database table creation script
- `seed.py`: Database seeding script

### Frontend Structure  
- **React 18** with functional components and hooks
- **WebSocket client** connects to backend for real-time price updates
- **Chart.js** for price charts and gauges
- **Axios** for REST API calls

### Key Frontend Components
- `CoinTable.js`: Main price comparison table with **12-column Tailwind CSS grid layout**
- `PriceChart.js`: Bitcoin historical price chart using Binance API
- `FearGreedIndex.js`: Crypto Fear & Greed Index gauge
- `LiquidationChart.js`: Real-time liquidation data visualization
- `PriceDisplay.js`: Price display component
- `Header.js`: Application header and navigation
- `Header.css`: Header component styling

#### Frontend UI Architecture Details

**CoinTable Grid Layout** (`CoinTable.js`):
- **Grid System**: Tailwind CSS 12-column responsive grid (`grid-cols-12`)
- **Column Distribution**: name(3), price(3), premium(2), change(2), volume(2)
- **Price Formatting**: Dynamic decimal places based on price magnitude:
  ```javascript
  const formatPrice = (price, currency = '₩') => {
    if (price < 0.01) return `${currency}${price.toFixed(6)}`;      // 소수 6자리
    if (price < 1) return `${currency}${price.toFixed(4)}`;         // 소수 4자리  
    if (price < 100) return `${currency}${price.toFixed(2)}`;       // 소수 2자리
    return `${currency}${Math.round(price).toLocaleString()}`;      // 정수 + 천단위
  };
  ```
- **Volume Display**: KRW amounts in 억원 units, USD in M(million) units
- **Real-time Updates**: WebSocket-driven state updates with timestamp display

### Detailed Data Flow Architecture

#### 1. Real-Time Price Data Flow
```
External APIs → Backend Services → Background Task → WebSocket → Frontend
```

**Price Update Process (`main.py`)**:
1. **WebSocket Clients** continuously stream real-time data:
   - **Upbit WebSocket**: `wss://api.upbit.com/websocket/v1` - KRW market tickers
   - **Binance WebSocket**: `wss://stream.binance.com:9443/ws/!ticker@arr` - USDT market tickers  
   - **Bybit WebSocket**: `wss://stream.bybit.com/v5/public/spot` - USDT market tickers
2. **Shared Data Store** (`services.py`): Central memory store updated by WebSocket clients:
   ```python
   shared_data = {
       "upbit_tickers": {},    # Real-time Upbit data
       "binance_tickers": {},  # Real-time Binance data  
       "bybit_tickers": {},    # Real-time Bybit data
       "exchange_rate": None,  # USD/KRW from Naver Finance
       "usdt_krw_rate": None,  # USDT/KRW from Upbit API
   }
   ```
3. **Price Aggregator** (`main.py:price_aggregator()`): 
   - Combines shared_data into unified coin objects every 1 second
   - Calculates Kimchi Premium: `((upbit_price - binance_price_krw) / binance_price_krw) * 100`
   - **Volume Unit Consistency**: Converts all volumes to KRW trading amounts
4. **WebSocket Broadcasting**: `ConnectionManager` broadcasts JSON array to all clients
5. **Frontend Reception**: `App.js` receives updates → `allCoinsData` state → `CoinTable.js` renders

#### 1.1. Critical Volume Data Architecture (Fixed)

**Volume Unit Standardization Issue Resolution**:
- **Problem**: Mixed volume units caused inconsistent displays (BTC count vs trading amounts)
- **Solution**: Standardized all exchanges to use **trading amounts** in local currency

**Backend Volume Processing** (`services.py`):
```python
# Upbit: Use acc_trade_price_24h (KRW trading amount)
"volume": data['acc_trade_price_24h'],  # KRW 거래대금

# Binance: Use ticker['q'] (USDT quote asset volume = trading amount)  
"volume": float(ticker['q']),  # USDT 거래대금 (not ticker['v'] = BTC count)

# Backend conversion to KRW (main.py:price_aggregator)
binance_volume_krw = usdt_volume * usdt_krw_rate  # Direct conversion
```

**Frontend Volume Display** (`CoinTable.js`):
```javascript
// Domestic volume (already in KRW)
{(coin.domestic_volume / 100_000_000).toFixed(0)}억 원

// Global volume (converted to USD for display)  
${(coin.global_volume / 1_000_000).toFixed(1)}M
```

**Volume Data Flow Debugging Process**:
1. **WS Message Verification**: Confirmed raw volume fields exist in WebSocket data
2. **Parsing Function Analysis**: Verified correct volume field extraction (`acc_trade_price_24h`, `ticker['q']`)
3. **Shared Data Inspection**: Validated volume data reaches shared_data store correctly
4. **Frontend State Check**: Confirmed volume data propagates through React state
5. **UI Display Verification**: Ensured proper volume formatting and unit display

#### 2. Liquidation Data Flow
```
Exchange WebSockets → Liquidation Collector → Memory Storage → API/WebSocket → Frontend
```

**Liquidation Collection Process (`liquidation_services.py`)**:
1. `LiquidationDataCollector` manages multiple exchange connections:
   - **Binance**: Real WebSocket to `wss://fstream.binance.com/ws/!forceOrder@arr`
   - **Other Exchanges**: Simulation data (Bybit, OKX, BitMEX, Bitget, Hyperliquid)
2. Data aggregated in 1-minute buckets with 24-hour memory retention
3. Long/short position tracking with volume calculations
4. **REST API**: `/api/liquidations/aggregated` provides historical aggregation
5. **WebSocket**: `/ws/liquidations` streams real-time updates
6. Frontend components:
   - `SidebarLiquidations.js`: Exchange summary with 5-minute trend charts
   - `LiquidationChart.js`: Detailed stream view + timeline charts

#### 3. Frontend Real-Time Processing
**WebSocket Connections (`App.js`)**:
- **Price WebSocket**: `ws://localhost:8000/ws/prices` with Firefox compatibility handling
- **Liquidation WebSocket**: Managed by `useLiquidations.js` hook with normalization

**Data Normalization (`useLiquidations.js`)**:
- Handles different exchange API formats for liquidation data
- Maps `side` and `positionSide` fields to consistent long/short directions
- Provides caching strategy (5-minute cache) with fallback to dummy data

### Database Schema
- **exchanges**: Exchange information (Upbit, Binance, etc.)
- **cryptocurrencies**: Supported crypto symbols and metadata  
- **coin_prices**: Historical price data storage
- **premium_histories**: Historical premium calculation records

## Key Dependencies
- **Backend**: fastapi, uvicorn, sqlalchemy, pymysql, cryptography, requests, websockets, beautifulsoup4, lxml, aiohttp
- **Frontend**: react, axios, chart.js, react-chartjs-2, react-gauge-chart, recharts, dayjs, lucide-react, web-vitals

## Project Structure

### Complete Directory Layout
```
ArbitrageWebsite/
├── docker-compose.yml                         # Docker orchestration (Backend, Frontend, MySQL)
├── CLAUDE.md                                  # Project instructions for Claude Code
├── AGENTS.md                                  # Additional documentation  
├── GEMINI.md                                  # Korean documentation for Gemini
├── README.md                                  # Basic project description
│
├── backend/                                   # FastAPI Backend
│   ├── Dockerfile                             # Backend container configuration
│   ├── requirements.txt                       # Python dependencies
│   ├── venv/                                  # Python virtual environment  
│   ├── data/                                  # CSV data files for seeding
│   │   ├── exchanges.csv                      # Exchange information
│   │   └── cryptocurrencies.csv               # Cryptocurrency metadata
│   └── app/                                   # Main application code
│       ├── main.py                            # FastAPI app with WebSocket support
│       ├── database.py                        # Database connection management
│       ├── models.py                          # SQLAlchemy database models
│       ├── schemas.py                         # Pydantic data schemas
│       ├── services.py                        # External API integrations
│       ├── liquidation_services.py            # Liquidation data collection
│       ├── create_db_tables.py                # Database table creation script
│       └── seed.py                            # Database seeding script
│
└── frontend/                                  # React Frontend
    ├── Dockerfile                             # Frontend container configuration
    ├── package.json                           # Node.js dependencies and scripts
    ├── package-lock.json                      # Dependency lock file
    └── src/                                   # React source code
        ├── index.js                           # React application entry point
        ├── index.css                          # Main stylesheet
        ├── App.js                             # Main application component
        ├── App.css                            # Main application styles
        ├── reportWebVitals.js                 # Performance monitoring
        └── components/                        # React components
            ├── Header.js                      # Application header
            ├── Header.css                     # Header component styling
            ├── CoinTable.js                   # Main price comparison table
            ├── PriceChart.js                  # Bitcoin historical price chart
            ├── FearGreedIndex.js              # Crypto Fear & Greed Index gauge
            ├── LiquidationChart.js            # Detailed liquidation visualization  
            ├── SidebarLiquidations.js         # 320px sidebar liquidation widget
            ├── SidebarLiquidations.README.md  # Component documentation
            ├── LiquidationWidget.README.md    # Component documentation
            └── PriceDisplay.js                # Price display component
        └── hooks/                             # Custom React hooks
            └── useLiquidations.js             # Liquidation data management hook
```

### Key Components Detail

#### Backend Components
- **`liquidation_services.py`**: Real-time liquidation data collection from multiple exchanges via WebSocket
- **WebSocket endpoints**: `/ws/prices` (price data) and `/ws/liquidations` (liquidation data)
- **ConnectionManager class**: Manages WebSocket connections and broadcasts

#### Frontend Components  
- **`SidebarLiquidations.js`**: 320px sidebar widget for real-time liquidation summary with 5-minute trend charts
- **`LiquidationChart.js`**: Detailed liquidation visualization with stream view and timeline charts  
- **`useLiquidations.js`**: Custom hook managing liquidation WebSocket connections and data normalization
- **WebSocket connections**: Connects to both `/ws/prices` and `/ws/liquidations` endpoints
- **Exchange selection**: Dropdown filters for domestic vs global exchanges

### API Endpoints
- **GET `/exchanges`**: List of supported exchanges
- **GET `/cryptocurrencies`**: List of supported cryptocurrencies
- **GET `/api/historical_prices/{symbol}`**: Historical price data
- **GET `/api/fear_greed_index`**: Crypto Fear & Greed Index
- **GET `/api/prices/{symbol}`**: Current price for specific symbol
- **GET `/api/liquidations`**: Raw liquidation data
- **GET `/api/liquidations/aggregated`**: Aggregated liquidation statistics
- **WebSocket `/ws/prices`**: Real-time price data stream
- **WebSocket `/ws/liquidations`**: Real-time liquidation data stream

## Technical Implementation Details

### WebSocket Architecture
- **ConnectionManager** (`main.py`): Manages multiple client connections with automatic cleanup
- **Dual WebSocket endpoints**: `/ws/prices` (1-second updates) and `/ws/liquidations` (real-time events)
- **Browser compatibility**: Special Firefox handling for WebSocket connections
- **Reconnection logic**: Automatic reconnection with exponential backoff on disconnection

### Performance Optimizations
- **Memory-based liquidation storage**: 24-hour retention in memory (no database writes for real-time data)
- **Symbol limiting**: BTC, ETH, XRP, SOL for optimal performance
- **Cached exchange rates**: USD/KRW rate updated every 10-second intervals
- **Client-side memoization**: React `useCallback` optimizations in custom hooks
- **Recharts optimization**: Efficient liquidation chart rendering with data aggregation
- **Component-level documentation**: README files for complex components aid development

### Error Handling & Resilience
- **WebSocket reconnection**: Automatic reconnection on connection loss with 3-5 second delays
- **Fallback mechanisms**: Cached data (5-minute expiry) → dummy data for development
- **Cross-browser compatibility**: Firefox-specific WebSocket connection handling
- **API timeout handling**: 10-second timeouts with graceful degradation

### Data Normalization
- **Exchange API mapping**: Handles different liquidation data formats across exchanges
- **Long/short direction accuracy**: Maps `side` + `positionSide` combinations correctly
- **USD conversion**: Consistent USD amount formatting across all exchanges
- **Development debugging**: Console logging for direction accuracy verification
- **Time formatting**: dayjs library for consistent date/time formatting across components
- **Icon standardization**: lucide-react for consistent iconography

## Development Notes
- Frontend connects to backend WebSocket at `ws://localhost:8000/ws/prices` and `ws://localhost:8000/ws/liquidations`
- Backend fetches USD/KRW exchange rate from Naver Finance via web scraping
- Supported cryptocurrencies are limited to BTC, ETH, XRP, SOL for performance
- Some global exchanges (OKX, Gate.io, MEXC) are commented out in the code
- Database credentials are hardcoded in docker-compose.yml for development
- **Real-time data**: CSV files used for initial seeding, but all pricing data fetched live from exchange APIs
- **Database setup**: Run `docker exec arbitragewebsite-backend-1 python -m app.create_db_tables` after starting containers
- **Database seeding**: Run `docker exec arbitragewebsite-backend-1 python -m app.seed` to populate initial data from CSV files
- **Liquidation data**: Only Binance provides real liquidation data; others use simulation for development
- **Component documentation**: Complex components include README.md files with implementation details
- **Performance monitoring**: reportWebVitals.js tracks React app performance metrics

## Recent Development Session (Volume Fix)

### Problem Identification
- **Initial Issue**: 코인 가격이 안뜬다 (coin prices not showing)
- **UI Migration**: Converted HTML table to Tailwind CSS 12-column grid system
- **Volume Data Inconsistency**: Major issue with trading volume units mixing BTC counts vs trading amounts
- **Small Price Display**: SHIB, BONK, PEPE, XEC decimal formatting issues

### Systematic Debugging Approach
Applied 4-step debugging methodology for volume display issues:
1. **WebSocket Raw Data** → Volume field verification in real-time messages
2. **Parsing Functions** → Data extraction logic validation (`services.py`)
3. **State Management** → React state propagation verification (`App.js`)
4. **UI Rendering** → Display formatting and unit consistency (`CoinTable.js`)

### Critical Fixes Applied

#### Backend Volume Standardization (`services.py`):
```python
# Before (inconsistent units):
# Upbit: data['acc_trade_volume_24h']  # BTC 거래량 (count)
# Binance: ticker['v']                 # BTC 거래량 (count)

# After (standardized to trading amounts):
# Upbit: data['acc_trade_price_24h']   # KRW 거래대금 (amount)
# Binance: ticker['q']                 # USDT 거래대금 (amount)
```

#### Backend Volume Calculation Fix (`main.py`):
```python
# Before (complex calculation):
# binance_volume_krw = volume * price * exchange_rate

# After (direct conversion):
# binance_volume_krw = usdt_volume * usdt_krw_rate
```

#### Frontend Price Formatting (`CoinTable.js`):
- **Small decimals** (<0.01): 6 decimal places for SHIB, BONK, PEPE, XEC
- **Medium decimals** (<1): 4 decimal places
- **Regular prices** (≥100): Integer with thousand separators

### Results Achieved
- **Volume Accuracy**: Upbit ~400억원, Binance ~2.7조원 (realistic values)
- **Real-time Updates**: All coins update dynamically from WebSocket streams
- **UI Consistency**: Clean 12-column grid layout with proper decimal formatting
- **Performance**: Sub-second price updates across all supported exchanges

### Technical Insights Gained
- **WebSocket Architecture**: Separate data collection from aggregation/broadcasting
- **Volume Unit Standards**: Always use trading amounts, not trading volumes
- **Frontend State Flow**: WebSocket → App.js → CoinTable.js state propagation
- **Debugging Methodology**: Systematic 4-layer approach prevents missed issues
- **CSS Grid Migration**: HTML tables to Tailwind CSS grid for responsive design

## Recent Development Session (바이낸스 청산 데이터 수집 문제 해결)

### Problem Identification
- **초기 문제**: 바이낸스 거래소가 실시간 청산 데이터에서 누락됨
- **WebSocket 연결**: 바이낸스 청산 WebSocket은 정상 연결되어 데이터 수신 중
- **필터링 문제**: BTCUSDT만 처리하도록 설정했으나 실제로는 다른 코인 청산이 더 빈번
- **Websockets 호환성**: websockets 15.0.1 → 11.0.3 다운그레이드로 인한 API 변경

### Systematic Debugging Process
1. **백엔드 로그 분석**: 바이낸스 WebSocket 메시지 수신 확인
2. **청산 데이터 메모리 검사**: `/api/liquidations/debug` 엔드포인트로 저장 상태 확인
3. **필터링 로직 검토**: BTCUSDT 외 코인(PENGUUSDC, ZORAUSDT 등)이 실제 청산 대상
4. **Import 문제 해결**: websockets.connect() 사용법 수정

### Critical Fixes Applied

#### 바이낸스 청산 필터링 제거 (`liquidation_services.py`):
```python
# Before (BTCUSDT 필터링):
if symbol != 'BTCUSDT':
    logger.debug(f"바이낸스 비트코인 외 코인 스킵: {symbol}")
    return

# After (모든 코인 처리):
logger.debug(f"바이낸스 청산 처리: {symbol}")
```

#### Websockets 11.0.3 호환성 수정:
```python
# Before: import websockets
# After: from websockets import connect as websockets_connect  # type: ignore

# WebSocket 연결 사용법:
async with websockets_connect(uri, ping_timeout=20, ping_interval=20) as websocket:
```

#### 수정된 파일들:
- `services.py`: WebSocket import 및 연결 방식 수정
- `liquidation_services.py`: 바이낸스 필터링 제거, WebSocket import 수정
- `enhanced_websocket.py`: WebSocket import 수정

### Results Achieved
- **바이낸스 청산 데이터 수집 성공**: 실시간으로 CKBUSDT, ZORAUSDT, REIUSDT, SPKUSDT 등 다양한 코인 청산 수집
- **6개 거래소 완전 지원**: Binance, OKX, Bitget, BitMEX, Hyperliquid, Bybit 모두 프론트엔드 표시
- **Pylance 오류 해결**: `# type: ignore` 주석으로 타입 검사 문제 해결
- **시뮬레이션 최적화**: 실제 데이터 충분으로 시뮬레이션 비활성화하여 리소스 절약

### Technical Architecture Updates
- **청산 데이터 플로우**: 바이낸스 WebSocket → 실시간 수신 → 메모리 저장 → API 응답 → 프론트엔드
- **필터링 정책 변경**: BTCUSDT 제한 → 모든 코인 청산 데이터 수집
- **Websockets 버전**: 15.0.1 → 11.0.3 (FastAPI 호환성)
- **Import 방식**: 직접 import로 타입 검사 문제 우회

## Recent Development Session (실시간 가격/프리미엄 변화 애니메이션 구현)

### Problem Identification
- **최초 문제**: 코인 가격과 김치 프리미엄 변화 시 시각적 피드백(플래시 애니메이션) 부재
- **기술적 도전**: React 최적화와 실시간 데이터 업데이트 간의 충돌
- **사용자 요구사항**: 가격 상승 시 초록색, 하락 시 빨간색 플래시 효과

### Critical Architecture Decision: Direct DOM Manipulation
React의 메모이제이션과 최적화가 실시간 애니메이션을 방해하여 **직접 DOM 조작 방식** 채택:

#### PriceCell 구현 (`PriceCell.js`):
```javascript
// React 상태 대신 직접 DOM 조작
const PriceCell = ({ price, currency, formatPrice }) => {
  const spanRef = useRef(null);
  const prevPriceRef = useRef(null);
  
  useEffect(() => {
    const currentPrice = price;
    const prevPrice = prevPriceRef.current;
    
    if (prevPrice !== currentPrice) {
      const change = currentPrice > prevPrice ? 'up' : 'down';
      
      // 즉시 DOM 업데이트
      spanRef.current.textContent = formatPrice(currentPrice, currency);
      
      // 플래시 애니메이션 적용
      const flashClass = change === 'up' 
        ? 'bg-green-400/60 border-2 border-green-300 shadow-xl scale-105'
        : 'bg-red-400/60 border-2 border-red-300 shadow-xl scale-105';
      
      // 1.5초 플래시 후 원래 상태로 복구
      spanRef.current.className = baseClass + ' ' + flashClass;
      setTimeout(() => spanRef.current.className = baseClass, 1500);
    }
  }, [price]);
  
  return <span ref={spanRef}>{formatPrice(price, currency)}</span>;
};
```

#### PremiumCell 구현 (`PremiumCell.js`):
```javascript
// 김치 프리미엄 변화 애니메이션 (동일한 패턴)
const PremiumCell = ({ premium }) => {
  const spanRef = useRef(null);
  const prevPremiumRef = useRef(null);
  
  useEffect(() => {
    if (prevPremium !== currentPremium) {
      const change = currentPremium > prevPremium ? 'up' : 'down';
      
      // 에메랄드/빨강 색상으로 김치 프리미엄 변화 표시
      const flashClass = change === 'up'
        ? 'bg-emerald-400/60 border-2 border-emerald-300 shadow-xl'
        : 'bg-red-400/60 border-2 border-red-300 shadow-xl';
      
      spanRef.current.className = baseClass + ' ' + flashClass;
      setTimeout(() => spanRef.current.className = baseClass, 1500);
    }
  }, [premium]);
};
```

### Debugging Process: 실시간 데이터 흐름 추적

#### 1. 백엔드 데이터 수집 검증
- **WebSocket 연결 상태**: ✅ 정상 (557개 코인 실시간 브로드캐스팅)
- **거래소 데이터**: ✅ Upbit, Binance, Bybit 모두 정상 수집
- **BTC 실시간 데이터**: 161,272,000원 → 161,273,000원 변화 확인됨

#### 2. 프론트엔드 데이터 흐름 진단
4단계 디버깅 방법론 적용:
```
Backend WebSocket → usePriceData → CoinTable → CoinRow → PriceCell/PremiumCell
```

**발견된 문제**: CoinTable에서는 새 데이터 처리하지만 CoinRow로 전달되지 않음
```javascript
// CoinTable: 새 데이터 수신 ✅
💰 [usePriceData] BTC 수신: 161273000 KRW
🔍 [CoinTable] BTC 최종 객체 생성: domestic_price=161273000

// CoinRow: 이전 데이터만 수신 ❌
🎯 [CoinRow] BTC: 161272000  // 여전히 이전 값!
🔍 [PriceCell] 렌더링: price=161272000, prev=161272000  // 변화 없음
```

#### 3. React 최적화 문제 해결
- **React.memo 제거**: CoinRow에서 메모이제이션 완전 비활성화
- **강제 리렌더링**: _renderKey로 고유 키 생성
- **디버그 로깅**: 각 단계별 상세 추적 로그 추가

### Current Status
- ✅ **백엔드**: 실시간 데이터 수집 및 브로드캐스팅 정상
- ✅ **PriceCell/PremiumCell**: 직접 DOM 조작 애니메이션 로직 완성
- ❌ **데이터 전달**: CoinTable → CoinRow 간 props 업데이트 누락
- 🔍 **진행 중**: React 컴포넌트 리렌더링 문제 해결

### Technical Lessons Learned
- **Direct DOM Manipulation**: React 최적화를 우회한 실시간 애니메이션 해결책
- **WebSocket 디버깅**: 4단계 데이터 흐름 추적 방법론
- **성능 vs 실시간성**: 메모이제이션과 실시간 업데이트 간의 트레이드오프
- **컴포넌트 분리**: PriceCell과 PremiumCell의 독립적 애니메이션 로직