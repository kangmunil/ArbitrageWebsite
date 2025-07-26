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
*   **WebSocket Endpoints:**
    *   `/ws/prices`: Streams real-time coin price and premium data.
    *   `/ws/liquidations`: Streams real-time liquidation data.
*   **REST API Endpoints:** Includes basic endpoints like `/`, `/api/fear_greed_index`, and `/api/liquidations/aggregated`.

#### `backend/app/services.py`
*   **`shared_data`:** A global dictionary acting as a central store for all real-time data collected from various sources (Upbit, Binance, Bybit tickers, exchange rates).
*   **WebSocket Client Functions:**
    *   `upbit_websocket_client()`: Connects to Upbit WebSocket, subscribes to KRW markets, and updates `shared_data['upbit_tickers']`.
    *   `binance_websocket_client()`: Connects to Binance WebSocket, subscribes to USDT pairs, and updates `shared_data['binance_tickers']`.
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

### 3. Frontend (`frontend/`)

#### `frontend/public/index.html`
*   Contains the root `div` (`<div id="root"></div>`) where the React application is mounted.

#### `frontend/src/index.js`
*   The main entry point for the React application.
*   Uses `ReactDOM.createRoot().render()` to render the `<App />` component into the `id="root"` element.

#### `frontend/src/App.js`
*   **Main React Component:** The top-level component of the user interface.
*   **WebSocket Connection:** Establishes a WebSocket connection to `ws://localhost:8000/ws/prices` to receive real-time coin data.
*   **`ws.onmessage` Handler:** Parses incoming JSON messages. If the data is an array (expected for coin data), it updates the `allCoinsData` state.
*   **State Management:** Manages `allCoinsData`, `selectedDomesticExchange`, and `selectedGlobalExchange` states.
*   **Component Rendering:** Renders `Header`, `CoinTable`, `FearGreedIndex`, and `SidebarLiquidations` components.
*   **Layout:** Uses CSS classes like `App-layout-container`, `App-sidebar`, `App-content`, and `App-section` for structural layout.

#### `frontend/src/components/CoinTable.js`
*   **Coin Price Comparison Table:** Displays the real-time coin data.
*   **Props:** Receives `allCoinsData`, `selectedDomesticExchange`, `setSelectedDomesticExchange`, `selectedGlobalExchange`, `setSelectedGlobalExchange`.
*   **Data Processing:** Uses `useMemo` to filter, sort, and prepare `displayData` from `allCoinsData`.
*   **UI Features:** Provides exchange selection dropdowns, a search input, and sortable columns.
*   **Volume Display:**
    *   Backend now sends Binance and Bybit volumes converted to KRW equivalent.
    *   Frontend displays KRW volume in "백만 원" units (no decimals).
    *   Frontend displays USD volume in "K $" units (no decimals).
*   **Styling:** Uses Tailwind CSS classes for layout and appearance, along with `CoinTable.css`.

#### `frontend/src/components/Header.js`
*   Displays the website header with logo and navigation.

#### `frontend/src/components/FearGreedIndex.js`
*   Displays the Fear & Greed Index.

#### `frontend/src/components/SidebarLiquidations.js`
*   Displays real-time liquidation data, including charts.
*   **Styling:** Recently adjusted to ensure consistent background color with `App-section` and correct centering.

#### `frontend/src/hooks/useLiquidations.js`
*   A custom React hook for fetching and managing liquidation data.

#### `frontend/src/App.css`
*   Contains global CSS styles for the application layout and general elements.
*   Recently updated to use `display: flex` and `flex-direction: column` for `App-section` to improve layout stability.

#### `frontend/src/components/CoinTable.css`
*   Contains specific CSS rules for the `CoinTable` component, such as padding for select elements and background color.

## Current Status and Recent Changes
*   **Backend Volume Conversion:** `backend/app/main.py` was modified to convert Binance and Bybit volumes to KRW equivalent before broadcasting to the frontend.
*   **Frontend Volume Formatting:** `frontend/src/components/CoinTable.js` was updated to display KRW volume in "백만 원" units and USD volume in "K $" units, both without decimals.
*   **Frontend Layout/Styling:**
    *   `CoinTable.js`: Dropdown and search input alignment, font size adjustments.
    *   `CoinTable.css`: Added for `CoinTable` specific styles.
    *   `App.js`: Added a max-width wrapper (`mx-auto max-w-screen-2xl`) for the main content.
    *   `App.css`: `App-section` updated to use flexbox for better internal layout.
    *   `SidebarLiquidations.js`: Adjusted styling for centering and consistent background color.
*   **Frontend JSX Error:** The previous JSX syntax error in `CoinTable.js` has been fixed by the user.

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