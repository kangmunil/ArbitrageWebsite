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
- `models.py`: SQLAlchemy database models
- `database.py`: Database connection and session management

### Frontend Structure  
- **React 18** with functional components and hooks
- **WebSocket client** connects to backend for real-time price updates
- **Chart.js** for price charts and gauges
- **Axios** for REST API calls

### Key Frontend Components
- `CoinTable.js`: Main price comparison table with exchange selection
- `PriceChart.js`: Bitcoin historical price chart using Binance API
- `FearGreedIndex.js`: Crypto Fear & Greed Index gauge
- `Header.js`: Application header and navigation

### Data Flow
1. Backend fetches prices from multiple exchange APIs every second
2. Calculates Kimchi Premium using Upbit vs Binance prices + USD/KRW rate
3. Broadcasts data via WebSocket to all connected frontend clients
4. Frontend displays real-time updates in table format

### Database Schema
- **exchanges**: Exchange information (Upbit, Binance, etc.)
- **cryptocurrencies**: Supported crypto symbols and metadata  
- **coin_prices**: Historical price data storage
- **premium_histories**: Historical premium calculation records

## Key Dependencies
- **Backend**: fastapi, uvicorn, sqlalchemy, pymysql, requests, websockets, beautifulsoup4
- **Frontend**: react, axios, chart.js, react-chartjs-2, react-gauge-chart

## Development Notes
- Frontend connects to backend WebSocket at `ws://localhost:8000/ws/prices`
- Backend fetches USD/KRW exchange rate from Naver Finance via web scraping
- Supported cryptocurrencies are limited to BTC, ETH, XRP for performance
- Some global exchanges (OKX, Gate.io, MEXC) are commented out in the code
- Database credentials are hardcoded in docker-compose.yml for development