# Codebase Understanding: ArbitrageWebsite

## Project Overview
The ArbitrageWebsite project is designed for real-time cryptocurrency arbitrage monitoring. It displays live coin prices, calculates the "kimchi premium" (price difference between Korean and international exchanges), and provides liquidation data.

## Technologies and Frameworks
*   **Backend:** FastAPI (Python)
*   **Frontend:** React (JavaScript)
*   **Database:** MySQL (managed via Docker Compose)
*   **Containerization:** Docker, Docker Compose
*   **Real-time Communication:** WebSockets
*   **Data Caching:** Redis

## Key Components and Data Flow

### 1. Orchestration Layer: Docker Compose (`docker-compose.yml`)
Orchestrates the various microservices:
*   `api-gateway`: The main FastAPI application that serves as the entry point for the frontend. It aggregates data from other services.
*   `market-data-service`: A dedicated service for fetching real-time market data (prices, volumes) from various exchanges.
*   `liquidation-service`: A dedicated service for collecting and processing liquidation data.
*   `frontend`: The React application.
*   `db`: The MySQL database.
*   `redis`: Redis instance for caching and real-time data sharing between services.

### 2. Backend Microservices

#### `api-gateway` (`backend/app/`)
*   **Main Application Entry Point:** Initializes the FastAPI application that the frontend connects to.
*   **WebSocket Management:** Uses a `WebSocketConnectionManager` to handle multiple client WebSocket connections for prices and liquidations.
*   **Data Aggregation:**
    *   Does not collect data directly from exchanges.
    *   Periodically fetches combined market data from `market-data-service` via HTTP requests.
    *   Fetches aggregated liquidation data from `liquidation-service`.
*   **Dynamic Broadcasting Strategy:**
    *   Implements a hybrid update system to enhance real-time experience and reduce data overhead.
    *   **Dynamic Prioritization:** Coins are dynamically classified as "major" or "minor".
        *   **Major Coins:** Top 20 coins by Korean exchange (Upbit, Bithumb) trading volume, updated every 5 minutes. Users can also temporarily "watch" a coin, promoting it to major status for 5 minutes.
        *   **Minor Coins:** All other coins.
    *   **Broadcasting Method:**
        *   Major coin updates are sent individually and immediately (with a 50ms throttle per coin) via the `/ws/prices` WebSocket.
        *   Minor coin updates are buffered and sent in batches every 100ms to reduce client-side load.
*   **REST APIs:** Provides a rich set of endpoints for the frontend.
    *   **Core:** `/api/coins/latest` (initial data load), `/api/fear_greed_index`, and proxies for other services.
    *   **Health:** `/health` for service status monitoring.
    *   **Coin Metadata:** A suite of endpoints to query detailed coin information from the database, including `/api/coin-names`, `/api/coin-images`, `/api/coin-metadata/{symbol}`, `/api/categories`, and `/api/coins/top-marketcap`.
    *   **Dynamic Watchlist:** `/api/watch-coin/{symbol}` and `/api/watched-coins` to manage the user-driven priority list.

#### `market-data-service` (`backend/market-data-service/`)
*   **Responsibility:** Solely responsible for collecting real-time market data from all supported exchanges (Upbit, Binance, Bybit, Bithumb).
*   **`market_collector.py`:** Contains the core logic for connecting to exchange WebSockets (for Upbit, Binance) and polling REST APIs (for Bybit, Bithumb) to gather ticker data.
*   **`shared_data.py`:** Manages the collected data. It stores the data in both an in-memory dictionary and a Redis cache for fast access and persistence.
*   **API:** Exposes a comprehensive set of REST endpoints.
    *   **Primary:** `/api/market/combined` for the `api-gateway` to fetch the latest, processed market data.
    *   **Granular Data:** `/api/market/prices`, `/api/market/volumes`, `/api/market/premiums`, and `/api/market/exchange-rate`.
    *   **Health & Debug:** `/health` for service status, and `/api/debug/collectors` for monitoring internal collector stats.
*   **WebSocket Endpoint:** Includes a `/ws/market` endpoint for broadcasting raw combined data, likely for debugging or internal service communication.

#### `liquidation-service` (`backend/liquidation_service/`)
*   **Responsibility:** Collects and processes liquidation data from various exchanges.
*   **`liquidation_stats_collector.py`:**
    *   Fetches 24-hour trading volume statistics from exchanges.
    *   Calculates liquidation volumes based on changes in total volume, applying a realistic long/short ratio. This is a statistical approach rather than tracking individual liquidation events.
*   **Data Storage:** Stores aggregated liquidation data in an in-memory deque.
*   **API:** Provides a set of REST endpoints for data consumption and debugging.
    *   **Primary:** `/api/liquidations/aggregated` for the `api-gateway`.
    *   **Health & Debug:** `/health` for service status, `/api/liquidations/debug` for internal bucket data, and `/api/liquidations/raw` for unfiltered data.
    *   **Summaries:** `/api/exchanges/stats` and `/api/liquidations/summary` for high-level overviews.

#### Shared Components (`backend/shared/`)
*   **`websocket_manager.py`:** A common module used by both `api-gateway` and `market-data-service` to manage WebSocket connections.
*   **`redis_manager.py`:** A standardized helper for connecting to and interacting with the Redis cache.
*   **`health_checker.py`:** Provides a common framework for creating health check endpoints for each service, typically exposed at the `/health` route.

### 3. Frontend (`frontend/`)
*   The frontend remains largely the same, connecting to the `api-gateway`'s WebSocket endpoints (`/ws/prices`, `/ws/liquidations`) to receive and display real-time data.
*   It fetches initial data via REST calls to the `api-gateway`.

## System Architecture Summary
The system employs a modern, containerized microservices architecture.

### 1. Orchestration Layer: Docker Compose
The entire system is managed by `docker-compose.yml`. This acts as the central control plane, defining and launching all the individual services (`api-gateway`, `market-data-service`, `liquidation-service`, `frontend`, `db`, `redis`) and placing them in a shared network for easy communication.

### 2. Backend: A FastAPI-based Microservices Hub
The backend is split into specialized, independent services:

*   **API Gateway (`api-gateway`):** This is the central hub that the frontend directly communicates with. It acts as a reverse proxy and aggregator. It does not perform data collection itself.
*   **Market Data Service (`market-data-service`):** Connects directly to cryptocurrency exchanges to fetch raw price ticker data. It processes this data and makes it available to the API Gateway via a REST API and Redis.
*   **Liquidation Service (`liquidation-service`):** Connects to exchanges to fetch data for calculating liquidation statistics. It provides this data to the API Gateway.
*   **Database (`db`):** A MySQL database for persistent data (e.g., coin names).
*   **Cache (`redis`):** A Redis instance used for caching frequently accessed data and for inter-service communication, reducing the load on individual services.

### 3. Frontend: React Single Page Application (SPA)
*   The React application runs in the user's browser and communicates exclusively with the `api-gateway`. It receives real-time updates via WebSockets and fetches initial data via REST.

### Data Flow Summary
1.  **Collection:** `market-data-service` and `liquidation-service` continuously fetch raw data from external exchanges.
2.  **Storage & Caching:** `market-data-service` stores its collected data in Redis for persistence and inter-service access. `liquidation-service` holds its data in memory.
3.  **Aggregation:** The `api-gateway` requests the latest processed data from `market-data-service` and `liquidation-service` via their internal REST APIs.
4.  **Dynamic Broadcast:** The `api-gateway` processes the aggregated data and sends it to clients using a dynamic, hybrid strategy. High-priority "major" coins are sent instantly, while "minor" coins are batched and sent periodically via the `/ws/prices` WebSocket.
5.  **Display:** The React frontend receives the data and dynamically updates the UI, providing a responsive experience for major coins while efficiently handling updates for others.

## Local Development
For developers who want to run services individually without Docker Compose, follow these instructions.

### Backend Services
Each backend service is a standalone FastAPI application.

1.  **Navigate to the service directory:**
    ```bash
    # For the main gateway
    cd backend/app

    # For the market data service
    cd backend/market-data-service

    # For the liquidation service
    cd backend/liquidation_service
    ```

2.  **Install dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Run the service:**
    ```bash
    uvicorn main:app --reload --port <port_number>
    ```
    *   `api-gateway`: port `8000`
    *   `market-data-service`: port `8001`
    *   `liquidation-service`: port `8002`

### Frontend Service
The frontend is a React application.

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

3.  **Start the development server:**
    ```bash
    npm run start
    ```
    The application will be available at `http://localhost:3000`.

## Build and Run Instructions
(The build and run instructions remain the same as they rely on Docker Compose, which handles the multi-service setup.)

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
3.  **Access the application:**
    *   **Frontend:** `http://localhost:3000`
    *   **API Gateway (Docs):** `http://localhost:8000/docs`