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