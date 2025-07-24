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
- `CoinTable.js`: Main price comparison table with exchange selection
- `PriceChart.js`: Bitcoin historical price chart using Binance API
- `FearGreedIndex.js`: Crypto Fear & Greed Index gauge
- `LiquidationChart.js`: Real-time liquidation data visualization
- `PriceDisplay.js`: Price display component
- `Header.js`: Application header and navigation
- `Header.css`: Header component styling

### Detailed Data Flow Architecture

#### 1. Real-Time Price Data Flow
```
External APIs → Backend Services → Background Task → WebSocket → Frontend
```

**Price Update Process (`main.py`)**:
1. `price_updater()` background task runs every 1 second
2. Fetches from Korean exchanges: Upbit, Bithumb (KRW markets)
3. Fetches from International exchanges: Binance, Bybit (USDT markets)
4. Retrieves USD/KRW exchange rate from Naver Finance via web scraping
5. Calculates Kimchi Premium: `((upbit_price - binance_price_krw) / binance_price_krw) * 100`
6. Broadcasts JSON array to all WebSocket clients via `ConnectionManager`
7. Frontend `App.js` receives updates and updates `allCoinsData` state
8. `CoinTable.js` dynamically recalculates premiums based on selected exchanges

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