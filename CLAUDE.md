# Project Guide: Cryptocurrency Arbitrage Monitor

This document provides guidance for working with the code in this repository.

## Project Overview

This is a cryptocurrency arbitrage monitoring website that displays price differences between Korean exchanges (Upbit, Bithumb) and overseas exchanges (Binance, Bybit). The application calculates the "Kimchi Premium," which is the price difference for cryptocurrencies between Korean and international exchanges.

## Development Commands

### Backend (FastAPI)

  * **Start backend locally**: `cd backend && source venv/bin/activate && uvicorn app.main:app --reload`
  * **Install dependencies**: `cd backend && source venv/bin/activate && pip install -r requirements.txt`
  * **Database setup**: `cd backend && source venv/bin/activate && python scripts/db_management/create_db_tables.py`
  * **Seed database**: `cd backend && source venv/bin/activate && python scripts/db_management/seed.py`
  * **Activate virtual environment**: `cd backend && source venv/bin/activate`

### Frontend (React)

  * **Start frontend locally**: `cd frontend && npm start`
  * **Install dependencies**: `cd frontend && npm install`
  * **Build for production**: `cd frontend && npm run build`
  * **Run tests**: `cd frontend && npm test`

### Docker Development

  * **Start entire stack**: `docker-compose up --build`
  * **Microservices stack**: `docker-compose -f docker-compose-microservices.yml up --build`
  * **Backend only**: `docker-compose up api-gateway db redis`
  * **Market service only**: `docker-compose up market-service redis`
  * **Stop services**: `docker-compose down`
  * **View logs**: `docker-compose logs -f api-gateway`
  * **Log viewer**: Access Dozzle at `http://localhost:8080`

## Architecture

The project utilizes a 3-service microservices architecture, supported by a React frontend and several infrastructure services.

### End-to-End Data Flow

```
Exchange APIs → Market Data Service → Redis Cache → API Gateway → Integrated WebSocket Manager → Optimized Frontend Hook → Memoized Components → UI
```

### Backend Microservices

The backend consists of three main services that communicate via HTTP and share data through a Redis cache.

#### 1\. API Gateway (Port 8000)

  * **Role**: Main API server and frontend entry point.
  * **Technology**: FastAPI.
  * **Responsibilities**:
      * Manages HTTP API, WebSocket connections, and CORS for the frontend.
      * Aggregates data from the Market and Liquidation services.
      * Broadcasts real-time price data for 559 coins every second via WebSockets.
      * Integrates with a MySQL database for metadata, such as coin name mappings.
      * Includes a health check system to monitor the status of all other microservices.

#### 2\. Market Data Service (Port 8001)

  * **Role**: Dedicated market data collection.
  * **Technology**: FastAPI.
  * **Responsibilities**:
      * Establishes real-time data connections with Upbit, Binance, Bybit, and Bithumb.
      * Normalizes and processes exchange-specific data. A key fix was standardizing all volume data to **trading amounts** (e.g., `acc_trade_price_24h` for KRW, `ticker['q']` for USDT) instead of inconsistent trade counts.
      * Shares collected data with other services via a Redis cache.
      * Provides REST API endpoints for integrated market data (`/api/market/combined`).

#### 3\. Liquidation Service (Port 8002)

  * **Role**: Specialized liquidation data collection and processing.
  * **Technology**: FastAPI.
  * **Responsibilities**:
      * Collects real-time liquidation data from Binance (`!forceOrder@arr` stream) and simulates data for five other exchanges. Initially, data was filtered for BTC, but this was removed to process all available coin liquidations.
      * Stores the last 24 hours of liquidation statistics in memory for high-performance access.
      * Aggregates and processes statistics based on exchange and time.
      * Exposes data through a REST API (`/api/liquidations/aggregated`).

#### Shared Backend Modules

  * **`shared/websocket_manager.py`**: Standardized WebSocket connection management.
  * **`shared/health_checker.py`**: A common system for service health checks.
  * **`shared/data_validator.py`**: Contains classes for data validation, normalization, and premium calculation.
  * **`shared/redis_manager.py`**: Manages Redis connections and error handling.

#### Core Backend Modules (Newly Organized)

  * **`core/`**: Essential database, models, and configuration management
    * **`core/config.py`**: Centralized configuration with environment-based settings
    * **`core/database.py`**: Database connection and session management
    * **`core/models.py`**: SQLAlchemy ORM models for all tables
    * **`core/minimal_schema.py`**: Database schema creation scripts
  
  * **`collectors/`**: Specialized data collection modules
    * **`collectors/working_exchange_collector.py`**: Collects data from 7 working exchanges (Binance, Bybit, OKX, Gate.io, Coinbase)
    * **`collectors/korean_exchange_collector.py`**: Dedicated Korean exchange (Upbit, Bithumb) data collection
    * **`collectors/coingecko_metadata_collector.py`**: CoinGecko metadata and Korean name collection
    * **`collectors/manual_metadata_setup.py`**: Manual metadata setup for priority coins

  * **`services/`**: Business logic and API services
    * **`services/exchange_service.py`**: Exchange-related business logic
    * **`services/premium_service.py`**: Kimchi premium calculation and market data aggregation

  * **`scripts/`**: Database management and maintenance
    * **`scripts/db_management/`**: Database creation, seeding, and migration scripts
    * **`scripts/maintenance/`**: System maintenance and cleanup scripts

#### Infrastructure Services

  * **Redis Cache (Port 6379)**: Used for inter-service data sharing and performance caching.
  * **MySQL Database (Port 3306)**: Stores coin metadata and Korean name mappings.
  * **Docker Health Checks**: Implemented to manage dependency ordering and ensure service resilience.

### Frontend Architecture

  * **Framework**: React 18 with functional components and hooks.
  * **Key Features**:
      * **Modular Structure**: Organized into reusable components, hooks, and utilities.
      * **Centralized WebSocket Management**: The `useWebSocketManager.js` hook handles WebSocket connections, state, and auto-reconnection.
      * **Standardized API Client**: `apiClient.js` provides a centralized interface for API calls with built-in caching and error handling.
      * **Integrated Utility System**: `formatters.js` contains a comprehensive set of functions for formatting prices, volumes, and other data consistently across the application.
      * **Real-time Animations**: Components like `PriceCell` use a `useState` and `useEffect` pattern to provide visual feedback (flashing colors) when prices change.

### Frontend Directory Structure

```
frontend/src/
├── styles/
│   └── common.css
├── utils/
│   ├── formatters.js
│   ├── apiClient.js
│   └── ...
├── hooks/
│   ├── useWebSocketManager.js
│   ├── usePriceData.js
│   └── useLiquidations.js
└── components/
    ├── PriceCell.js
    ├── PriceCell.css
    ├── PremiumCell.js
    ├── CoinTable.js
    ├── LiquidationChart.js
    └── ...
```

## Real-Time Animation and Performance

### Price Change Animation

The `PriceCell` component provides visual feedback when a price changes. The implementation evolved from direct DOM manipulation to a more stable and simplified React pattern.

**Current `PriceCell.js` Implementation:**

```javascript
const PriceCell = ({ price, currency = '₩' }) => {
  const [flashStyle, setFlashStyle] = useState('');
  const prevPriceRef = useRef(price);

  useEffect(() => {
    const currentPrice = price;
    const prevPrice = prevPriceRef.current;

    if (currentPrice !== null && prevPrice !== null && currentPrice !== prevPrice) {
      // Use CSS animation classes
      const style = currentPrice > prevPrice ? 'price-up' : 'price-down';
      setFlashStyle(style);

      // Reset the style after the animation duration
      const timer = setTimeout(() => {
        setFlashStyle('');
      }, 800);

      prevPriceRef.current = currentPrice;
      return () => clearTimeout(timer);
    } else {
      prevPriceRef.current = currentPrice;
    }
  }, [price]);

  return (
    <span className={`price-cell transition-all duration-300 ${flashStyle}`}>
      {formatPrice(price, currency)}
    </span>
  );
};
```

**Associated `PriceCell.css`:**

```css
.price-up {
  color: #ef4444 !important; /* Red for price up */
  font-weight: bold !important;
  transition: color 0.3s ease !important;
}

.price-down {
  color: #3b82f6 !important; /* Blue for price down */
  font-weight: bold !important;
  transition: color 0.3s ease !important;
}
```

### Proposed Rendering Optimizations

To handle the high frequency of updates (559 coins per second), the following optimizations are recommended:

1.  **Memoize Components**: Use `React.memo` on the `CoinRow` component with a custom comparison function to prevent re-rendering if its core data hasn't changed.
2.  **Use Centralized Formatters**: Avoid creating inline functions in the render method by using the already implemented `formatters.js` utility.
3.  **Memoize Expensive Computations**: Move static objects, like coin icon mappings, outside the component to prevent re-creation on every render.
4.  **Introduce Virtual Scrolling**: For long-term scalability, implement virtual scrolling using a library like `react-window` to only render the visible rows.

## Database Schema (Updated)

### New Core Tables
  * **`coin_master`**: Master table for all cryptocurrency metadata with Korean names and icon URLs
  * **`upbit_listings`**: Specific to Upbit exchange listings with Korean names from API
  * **`bithumb_listings`**: Specific to Bithumb exchange listings 
  * **`exchange_registry`**: Registry of all supported exchanges with status tracking
  * **`binance_listings`**, **`bybit_listings`**, etc.: Individual exchange tables for 7 working exchanges

### Legacy Tables (Preserved)
  * **`exchanges`**: Original exchange information table
  * **`cryptocurrencies`**: Original cryptocurrency metadata
  * **`coin_prices`**: Historical price data storage
  * **`premium_histories`**: Kimchi Premium calculation logs

## Known Issues & Development Notes

  * **API Environment**: Use virtual environment for all Python operations: `source venv/bin/activate`
  * **IDE Configuration**: Set Python interpreter to `/Users/kangmunil/Project/ArbitrageWebsite/backend/venv/bin/python3` to resolve import errors
  * **Working Exchanges**: 7 out of 9 exchanges are fully functional (Bitget and MEXC have API issues)
  * **Production Settings**: Security settings, such as hardcoded database credentials in `docker-compose.yml`, must be changed for a production environment.
  * **Code Structure**: Main API Gateway simplified from 1,100+ lines to 230 lines, complex functionality moved to `app/legacy/`

## Recent Development Activity Summary

### Major Code Restructuring (Latest)
- **Directory Structure Overhaul**: Implemented improved backend organization superior to want.txt proposal
- **API Gateway Simplification**: Reduced main.py from 1,100+ lines to 230 lines (80% reduction)
- **Modular Architecture**: Separated concerns into `core/`, `collectors/`, `services/`, `scripts/`, `shared/`
- **Legacy Preservation**: Moved complex code to `app/legacy/` for safety and reference
- **Virtual Environment**: All dependencies properly installed and configured

### Database Infrastructure
- **New Schema Implementation**: Separated Korean exchanges (Upbit, Bithumb) with dedicated tables
- **Exchange Coverage**: 7 working exchanges with individual tracking tables
- **Metadata Integration**: 16 priority coins with Korean names and icon URLs from CoinGecko
- **Data Quality**: Null value handling and name change detection implemented

### WebSocket Connection Status  
- WebSocket connections to `/ws/prices` functioning correctly with automatic reconnection
- Real-time data flow: 559 coins updated every second via simplified aggregator
- Connection recovery working properly (Code 1001 reconnection observed)

### Data Processing Flow
**Simplified flow in new architecture:**
```
Exchange APIs → collectors/ → core/models → services/premium_service → app/main.py → WebSocket broadcast
```

### Performance Metrics
- **Code Complexity**: 80% reduction in main API Gateway code
- **Maintainability**: Clear separation of concerns across modules
- **WebSocket Performance**: ~500ms intervals, 559 coins per update
- **Memory Usage**: Stable with no memory leaks observed
