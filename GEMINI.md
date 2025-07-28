# Codebase Understanding: ArbitrageWebsite

## Project Overview
The ArbitrageWebsite project is designed for real-time cryptocurrency arbitrage monitoring. It displays live coin prices, calculates the "kimchi premium" (price difference between Korean and international exchanges), and provides liquidation data.

## Technologies and Frameworks
*   **Backend:** FastAPI (Python)
*   **Frontend:** React (JavaScript)
*   **Database:** MySQL (managed via Docker Compose)
*   **Containerization:** Docker, Docker Compose
*   **Real-time Communication:** WebSockets

## Key Components and Data Flow

### 1. Orchestration Layer: Docker Compose (`docker-compose.yml`)
Orchestrates the various services:
*   `backend`: The FastAPI application.
*   `frontend`: The React application.
*   `coinprice_service`: A separate service responsible for fetching raw coin data from various exchanges.
*   `liquidation_service`: A separate service responsible for fetching liquidation data.
*   `db`: The MySQL database.
*   **Enhancements**: `backend` service now includes a `healthcheck` to ensure it's ready before `frontend` starts. `frontend`'s `depends_on` condition was updated to `service_healthy` for robust startup order. `backend` service's port mapping was explicitly set to `0.0.0.0:8000:8000` to ensure accessibility from all network interfaces.

### 2. Backend (`backend/`)

#### `backend/app/main.py`
*   **Main Application Entry Point:** Initializes the FastAPI application.
*   **WebSocket Management:** Uses a `ConnectionManager` class to handle multiple client WebSocket connections.
*   **Background Tasks (`startup_event`):**
    *   Starts WebSocket clients for Upbit, Binance, and Bybit (`services.upbit_websocket_client`, `services.binance_websocket_client`, `services.bybit_websocket_client`).
    *   Initiates periodic fetching of USD/KRW and USDT/KRW exchange rates (`services.fetch_exchange_rate_periodically`, `services.fetch_usdt_krw_rate_periodically`).
    *   Starts the `price_aggregator` task.
    *   Starts the liquidation data collection (`liquidation_services.start_liquidation_collection`).
*   **`price_aggregator`:** A periodic asynchronous task that:
    *   Reads real-time ticker data and exchange rates from `services.shared_data`.
    *   Processes the data, including calculating kimchi premium and converting Binance/Bybit volumes to KRW equivalent.
    *   Broadcasts the aggregated coin data to all connected WebSocket clients via `/ws/prices`.
    *   **Enhancements**: Added debug logging to monitor data broadcast just before sending to clients.

#### Backend Endpoints

*   **WebSocket Endpoints:**
    *   `/ws/prices`: Streams real-time coin price and premium data.
    *   `/ws/liquidations`: Streams real-time liquidation data.
*   **REST API Endpoints:**
    *   `/`: Basic message indicating API is running.
    *   `/api/fear_greed_index`: Fetches the Fear & Greed Index.
    *   `/api/liquidations/aggregated`: Provides aggregated liquidation data.
    *   `/api/liquidations/debug`: Debug endpoint for in-memory liquidation data.
    *   `/api/coins/latest`: Returns the latest aggregated coin data (used for initial frontend load).
    *   `/api/coin-names`: Returns a mapping of coin symbols to Korean names.

#### `backend/app/services.py`
*   **`shared_data`:** A global dictionary acting as a central store for all real-time data collected from various sources (Upbit, Binance, Bybit tickers, exchange rates).
*   **WebSocket Client Functions:**
    *   `upbit_websocket_client()`: **Refactored to use `EnhancedWebSocketClient`** for robust connection management, subscribes to KRW markets, and updates `shared_data['upbit_tickers']`.
    *   `binance_websocket_client()`: **Refactored to use `EnhancedWebSocketClient`** for robust connection management, subscribes to USDT pairs, and updates `shared_data['binance_tickers']`.
    *   `bybit_websocket_client()`: Connects to Bybit WebSocket, subscribes to USDT pairs, and updates `shared_data['bybit_tickers']`.
*   **Periodic Data Fetching Functions:**
    *   `fetch_exchange_rate_periodically()`: Fetches USD/KRW exchange rate from Naver Finance.
    *   `fetch_usdt_krw_rate_periodically()`: Fetches USDT/KRW rate from Upbit.
*   **Helper Functions:** `get_upbit_krw_markets()`, `get_binance_supported_symbols()`, `get_bybit_supported_symbols()`.
*   **`get_fear_greed_index()`:** Fetches the Fear & Greed Index from Alternative.me.

#### `backend/app/liquidation_services.py`
*   Handles the collection, processing, and aggregation of liquidation data.
*   `start_liquidation_collection()`: A background task that collects liquidation data.
*   `set_websocket_manager()`: Allows the liquidation service to use the same `ConnectionManager` instance as the main application for broadcasting.
*   `get_aggregated_liquidation_data()`: Provides aggregated liquidation data, used for initial data load and potentially for broadcasting.

#### `backend/app/enhanced_websocket.py`
*   **Enhanced WebSocket Client Management:** Defines the `EnhancedWebSocketClient` class for robust WebSocket client connections.
*   **Features:** Includes exponential backoff for reconnection, error handling, connection state monitoring, and callback mechanisms for various events.
*   **Purpose:** Provides a reusable and resilient WebSocket client implementation for various data collection services.
*   **Enhancements**: `__init__` method now accepts and stores `ping_interval` and `ping_timeout` parameters. The `run_with_retry` method was modified to attempt **infinite reconnections** (removed `max_retries` limit).

### Database Models and Schemas

#### `backend/app/models.py` (SQLAlchemy ORM Models)
Defines the database table structures:
*   **`Exchange`**: Stores information about cryptocurrency exchanges (e.g., name, country, Korean status).
*   **`Cryptocurrency`**: Stores metadata about cryptocurrencies (e.g., symbol, Korean/English names).
*   **`CoinPrice`**: Stores historical coin price data for specific cryptocurrencies on specific exchanges.
*   **`PremiumHistory`**: Stores historical kimchi premium data, including prices from Korean and foreign exchanges.

#### `backend/app/schemas.py` (Pydantic Schemas)
Defines Pydantic schemas for data validation and serialization, used for FastAPI's request and response models. Each model typically has a `Base` schema for input/creation and a full schema (inheriting from `Base`) for output/response, which includes the `id` field.
*   **`ExchangeBase`, `Exchange`**: Exchange data schemas.
*   **`CryptocurrencyBase`, `Cryptocurrency`**: Cryptocurrency data schemas.
*   **`CoinPriceBase`, `CoinPrice`**: Coin price data schemas.
*   **`PremiumHistoryBase`, `PremiumHistory`**: Premium history data schemas.

### 3. Frontend (`frontend/`)

#### `frontend/public/index.html`
*   Contains the root `div` (`<div id="root"></div>`) where the React application is mounted.

#### `frontend/src/index.js`
*   The main entry point for the React application.
*   Uses `ReactDOM.createRoot().render()` to render the `<App />` component into the `id="root"` element.

#### `frontend/src/App.js`
*   **Main React Component:** The top-level component of the user interface, responsible for overall layout and data flow.
*   **WebSocket Connection:** Establishes a WebSocket connection to `ws://localhost:8000/ws/prices` via `usePriceData` hook to receive real-time coin data.
*   **State Management:** Manages `allCoinsData`, `selectedDomesticExchange`, `selectedGlobalExchange`, and connection status.
*   **Component Rendering:** Renders `Header`, `CoinTable`, `FearGreedIndex`, and `SidebarLiquidations` components.
*   **Code Splitting:** Uses `React.lazy` and `React.Suspense` for dynamic imports of `CoinTable`, `FearGreedIndex`, and `SidebarLiquidations` to optimize loading performance.
*   **Layout:** Uses CSS classes like `App-layout-container`, `App-sidebar`, `App-content`, and `App-section` for structural layout, along with Tailwind CSS for styling.

#### `frontend/src/components/CoinTable.js`
*   **Coin Price Comparison Table:** Displays real-time coin data, calculates kimchi premium, and provides user interaction features like search, sort, and exchange selection.
*   **Props:** Receives `allCoinsData`, selected exchange states, and connection status from `App.js`.
*   **State Management:** Manages local states for search term, sort column/direction, display limit, and fetched Korean coin names.
*   **Data Processing:** Uses `useMemo` to process `allCoinsData`, extracting relevant prices/volumes for selected exchanges, calculating kimchi premium (using USDT/KRW rate), and applying search filters and sorting.
*   **Helper Functions:** Utilizes `optimizedFilter`, `optimizedSort`, `createDebouncedSearch` for performance, `cacheManager` for caching Korean coin names, and `formatVolume`/`formatPrice` for display formatting.
*   **Sub-components:** Renders memoized `CoinRow` components for each coin, and uses `PriceCell` and `PremiumCell` for specific data display.
*   **UI Features:** Provides dropdowns for domestic/global exchange selection, a search input, sortable table columns, and a "Show More" button.
*   **Performance Optimization:** Extensively uses `memo`, `useMemo`, `useCallback`, debouncing, and caching to minimize re-renders and optimize performance.
*   **Styling:** Uses Tailwind CSS classes and `CoinTable.css` for layout and appearance.
*   **Enhancements**: Ensures stable `key` props for `CoinRow` components.

#### `frontend/src/components/Header.js`
*   Displays the website header with logo and navigation.

#### `frontend/src/components/FearGreedIndex.js`
*   Displays the Fear & Greed Index.

#### `frontend/src/components/SidebarLiquidations.js`
*   **Liquidation Data Display:** Displays real-time liquidation data in the form of bar charts, categorized by exchange and liquidation side (long/short).
*   **Data Source:** Utilizes the `useLiquidations` custom hook to fetch and manage aggregated liquidation data.
*   **Chart Data Preparation:** Uses `useMemo` to prepare data for 5-minute and simulated 1-hour liquidation charts, including exchange name abbreviation.
*   **Charting Library:** Employs `recharts` for rendering interactive bar charts.
*   **UI Features:** Shows a header with last update time, error messages, and two distinct bar charts for different timeframes.
*   **Styling:** Uses inline styles and Tailwind CSS for visual presentation.

#### `frontend/src/hooks/useLiquidations.js`
*   **Custom Hook for Liquidation Data:** Fetches, processes, and manages real-time liquidation data for the frontend.
*   **Data Sources:** Retrieves data from the backend via both REST API (`/api/liquidations/aggregated` for initial load and polling) and WebSocket (`/ws/liquidations` for real-time updates).
*   **Data Processing:** Includes `normalizeLiquidationData` for standardizing individual liquidation events and `transformSummaryData`/`generateTrendByExchange` for aggregating and preparing data for charts.
*   **State Management:** Manages `summary`, `trend`, `loading`, `error`, and `lastUpdate` states.
*   **Error Handling & Caching:** Implements fallback to cached data or dummy data on fetch errors and attempts WebSocket reconnection.
*   **Performance Optimization:** Utilizes `useCallback`, `useMemo`, and `useRef` for memoization and efficient resource management.
*   **Lifecycle Management:** Sets up initial data fetching, WebSocket connection, and periodic polling, with proper cleanup on unmount.

#### `frontend/src/hooks/usePriceData.js`
*   **Coin Price Data Management Hook:** Manages fetching and updating real-time coin price data for the frontend.
*   **Data Flow:** Initiates with a fast initial load via REST API (`/api/coins/latest`) and then transitions to real-time updates via WebSocket (`/ws/prices`).
*   **State Management:** Controls `data` (coin price array), `connectionStatus` (e.g., 'loading', 'connected', 'failed'), `lastUpdate` timestamp, and `error` messages.
*   **Key Functions:** `loadInitialData` (for REST fetch), `connectWebSocket` (for WebSocket connection and message handling), `reconnect`, and `refresh`.
*   **Error Handling & Reconnection:** Implements automatic reconnection logic for WebSockets with exponential backoff and handles REST API fetch errors.
*   **Performance Optimization:** Uses `useCallback`, `useMemo`, and `useRef` for memoization, efficient data comparison (`dataRef`), and controlled logging (`logOnce`) to prevent unnecessary re-renders and console spam.
*   **Lifecycle Management:** Handles initial data loading and WebSocket connection setup on component mount, and ensures proper cleanup on unmount.
*   **Enhancements**: `connectWebSocket` now explicitly cleans up previous WebSocket event listeners and closes old connections before establishing a new one. `PRICE_CHANGE_THRESHOLD` was introduced in `hasChanges` logic for more accurate price change detection, mitigating floating-point comparison issues. `dataRef.current` updates are now synchronized with `data` state changes via a dedicated `useEffect`.

#### `frontend/src/App.css`
*   Contains global CSS styles for the application layout and general elements.
*   Recently updated to use `display: flex` and `flex-direction: column` for `App-section` to improve layout stability.

#### `frontend/src/components/CoinTable.css`
*   Contains specific CSS rules for the `CoinTable` component, such as padding for select elements and background color.

#### `frontend/src/components/PriceCell.css`
*   **New File**: Contains specific CSS rules for the `PriceCell` component, defining price change animation styles.

## Current Status and Recent Changes
*   **Frontend Rendering & Data Flow Improvements**:
    *   `PriceCell.js` refactored for purely declarative, state-based rendering and animation, removing direct DOM manipulation. A dedicated `PriceCell.css` was introduced for styling.
    *   `CoinTable.js` ensures stable `key` props for `CoinRow` components and uses `useMemo` for optimized data processing.
    *   `usePriceData.js` now includes robust WebSocket event listener cleanup, infinite reconnection logic, and a `PRICE_CHANGE_THRESHOLD` for more accurate price change detection, mitigating floating-point comparison issues. `dataRef.current` updates are now synchronized with `data` state changes via `useEffect`.
*   **Backend WebSocket Stability & Data Collection**:
    *   `EnhancedWebSocketClient` (`backend/app/enhanced_websocket.py`) now explicitly handles `ping_interval` and `ping_timeout` for improved connection stability. Its `run_with_retry` method was modified to attempt infinite reconnections.
    *   `upbit_websocket_client()` and `binance_websocket_client()` in `backend/app/services.py` have been refactored to utilize the `EnhancedWebSocketClient` for consistent and resilient WebSocket management.
    *   Added debug logging in `backend/app/main.py`'s `price_aggregator` to monitor data broadcast.
*   **Containerization & Deployment Enhancements**:
    *   `docker-compose.yml` updated: `backend` service now includes a `healthcheck` to ensure it's ready before `frontend` starts. `frontend`'s `depends_on` condition was updated to `service_healthy`. `backend` service's port mapping was explicitly set to `0.0.0.0:8000:8000` to ensure accessibility from the host. `frontend`'s `REACT_APP_BACKEND_URL` environment variable was changed to `http://backend:8000` to leverage Docker's internal networking.
    *   `backend/Dockerfile` was modified to include `curl` installation for health checks and a comment was added to force Docker cache invalidation for rebuilds.
    *   `frontend/Dockerfile` was modified with a comment to force `npm install` during rebuilds.
*   **CORS Configuration**: `backend/app/main.py`'s `CORSMiddleware` `allow_origins` was temporarily set to `*` for debugging purposes to resolve cross-origin request blocking.

## System Architecture Summary
The system employs a modern, containerized microservices architecture.

### 1. Orchestration Layer: Docker Compose
The entire system is managed by `docker-compose.yml`. This acts as the central control plane, defining and launching all the individual services (`backend`, `frontend`, data collectors, database) and placing them in a shared network so they can communicate with each other easily.

### 2. Backend: A FastAPI-based Microservices Hub
The backend is not a single application but is split into several specialized services:

*   **Main Backend API (`backend`):** This is the central hub that the frontend directly communicates with. Its key responsibilities are:
    *   **WebSocket Server:** Manages real-time connections with users' browsers to stream data.
    *   **Data Aggregator:** It doesn't fetch data from exchanges itself. Instead, it collects data from the other backend services (`coinprice_service`, `liquidation_service`) and external APIs (for fiat exchange rates).
    *   **Processing & Business Logic:** It calculates the kimchi premium, converts currency volumes, and aggregates data before broadcasting it.
    *   **Serving REST APIs:** Provides standard endpoints for non-real-time data like the Fear & Greed Index.

*   **Data Collection Services (`coinprice_service`, `liquidation_service`):** These are specialized, independent workers.
    *   `coinprice_service`: Connects directly to cryptocurrency exchanges (Upbit, Binance, Bybit) to fetch raw price ticker data.
    *   `liquidation_service`: Connects to exchanges to fetch raw liquidation data.
    *   This separation of concerns means that the main backend doesn't have to worry about the complexities of connecting to third-party sources.

*   **Database (`db`):** A MySQL database running in its own container, used for data persistence.

### 3. Frontend: React Single Page Application (SPA)
*   **User Interface (`frontend`):** A standard React application that runs entirely in the user's browser.
*   **Real-time Updates:** It establishes a persistent WebSocket connection to the main backend's `/ws/prices` and `/ws/liquidations` endpoints. This allows the UI to update in real-time as new data is broadcast from the server, without needing to constantly poll for changes.
*   **Component-Based UI:** The interface is built from modular components like `CoinTable`, `SidebarLiquidations`, and `FearGreedIndex`, each responsible for a specific part of the display.

### Data Flow Summary
The end-to-end data flow is a key part of the architecture:

1.  **Collection:** The `coinprice_service` and `liquidation_service` continuously fetch raw data from external exchanges.
2.  **Aggregation:** The main `backend` service gathers this raw data, fetches supplementary data like KRW exchange rates, and processes it into a clean, unified format.
3.  **Broadcast:** The main `backend` sends this processed data over WebSockets to all connected frontend clients.
4.  **Display:** The React frontend receives the data and dynamically updates the relevant components on the user's screen.

## Build and Run Instructions

This project uses Docker Compose for easy setup and execution of all services.

### Prerequisites
*   Docker Desktop (or Docker Engine and Docker Compose) installed on your system.

### Steps to Build and Run
1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd ArbitrageWebsite
    ```
2.  **Build and start the services:**
    Navigate to the root directory of the project (where `docker-compose.yml` is located) and run:
    ```bash
    docker-compose up --build -d
    ```
    *   `--build`: This flag ensures that Docker images for the services are built from their respective Dockerfiles. You only need to use this flag when you make changes to the Dockerfiles or for the initial build.
    *   `-d`: This flag runs the services in detached mode, meaning they will run in the background.

3.  **Verify services are running:**
    You can check the status of your running containers with:
    ```bash
    docker-compose ps
    ```

4.  **Access the application:**
    *   **Frontend:** Open your web browser and navigate to `http://localhost:3000`
    *   **Backend API (FastAPI):** The API documentation (Swagger UI) can be accessed at `http://localhost:8000/docs`

### Stopping the services
To stop all running services and remove their containers, networks, and volumes (if not explicitly defined as external):
```bash
docker-compose down
```
To stop services but keep their containers running:
```bash
docker-compose stop
```