import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { useWebSocket, WS_STATUS } from './useWebSocketManager';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * 청산 데이터를 관리하는 커스텀 훅.
 * @param {number} windowMin - 데이터를 가져올 시간(분)
 * @returns {{summary: Array, trend: Array, loading: boolean, error: string, refetch: Function, lastUpdate: Date}}
 */
export const useLiquidations = (windowMin = 5) => {
  const [summary, setSummary] = useState([]);
  const [trend, setTrend] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const cacheRef = useRef(null);
  const intervalRef = useRef(null);

  // 통합 WebSocket 매니저 사용 - 중복 연결 방지
  const liquidationWs = useWebSocket('/ws/liquidations', {
    reconnectAttempts: 2,
    reconnectInterval: 15000, // 15초로 증가
    enableLogging: false
  });

  /**
   * 청산 데이터를 가져옵니다.
   */
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
    // 통합 WebSocket 매니저의 데이터 처리
    if (liquidationWs.data && liquidationWs.status === WS_STATUS.CONNECTED) {
      // WebSocket 데이터 수신 시 새로운 데이터 가져오기
      fetchData();
    }
  }, [liquidationWs.data, liquidationWs.status, fetchData]);

  return { summary, trend, loading, error, refetch: fetchData, lastUpdate };
};
