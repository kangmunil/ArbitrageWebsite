import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import useWebSocket from './useWebSocketOptimized';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const useLiquidations = (windowMin = 5) => {
  const [summary, setSummary] = useState([]);
  const [trend, setTrend] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const cacheRef = useRef(null);
  const intervalRef = useRef(null);

  const liquidationWsEndpoint = 'ws://localhost:8000/ws/liquidations';
  const { data: wsData } = useWebSocket([liquidationWsEndpoint]);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const summaryResponse = await axios.get(
        `${API_BASE}/api/liquidations/aggregated?limit=${windowMin * 12}`,
        { timeout: 10000 }
      );

      // This part remains the same as it processes the fetched data
      const exchangeSummary = {};
      if (Array.isArray(summaryResponse.data)) {
        summaryResponse.data.forEach(item => {
          if (item.exchanges) {
            Object.entries(item.exchanges).forEach(([exchange, exchangeData]) => {
              if (!exchangeSummary[exchange]) {
                exchangeSummary[exchange] = { long: 0, short: 0 };
              }
              exchangeSummary[exchange].long += exchangeData.long_volume || 0;
              exchangeSummary[exchange].short += exchangeData.short_volume || 0;
            });
          }
        });
      }

      const fixedOrderExchanges = ['Binance', 'Bybit', 'Okx', 'Bitget', 'Bitmex', 'Hyperliquid'];
      const summaryData = fixedOrderExchanges.map(exchange => {
        const lowerExchange = exchange.toLowerCase();
        const data = exchangeSummary[lowerExchange] || { long: 0, short: 0 };
        return { exchange, long: data.long, short: data.short };
      });

      const trendData = summaryData.map(item => ({
        exchange: item.exchange,
        long: item.long / 1000000, // M a 단위
        short: item.short / 1000000,
      }));

      cacheRef.current = { summary: summaryData, trend: trendData, timestamp: Date.now() };
      setSummary(summaryData);
      setTrend(trendData);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Liquidation data fetch error:', err);
      if (cacheRef.current && (Date.now() - cacheRef.current.timestamp < 5 * 60 * 1000)) {
        setSummary(cacheRef.current.summary);
        setTrend(cacheRef.current.trend);
        setError('Network error - using cached data');
      } else {
        setError('Failed to load data');
      }
    } finally {
      setLoading(false);
    }
  }, [windowMin]);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 60000);
    return () => clearInterval(intervalRef.current);
  }, [fetchData]);

  useEffect(() => {
    if (wsData[liquidationWsEndpoint]) {
      // Trigger a refetch when new WebSocket data arrives
      fetchData();
    }
  }, [wsData, fetchData, liquidationWsEndpoint]);

  return { summary, trend, loading, error, refetch: fetchData, lastUpdate };
};