/**
 * 롱숏 비율 데이터 관리 훅
 * 청산 서비스(포트 8002)에서 실시간 롱숏 비율 데이터를 가져옵니다.
 */

import { useState, useEffect, useCallback } from 'react';

const LIQUIDATION_SERVICE_URL = process.env.REACT_APP_LIQUIDATION_SERVICE_URL || 'http://localhost:8002';
const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'ADAUSDT'];

export const useLongShortData = () => {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchLongShortData = useCallback(async () => {
    try {
      setError(null);
      
      // 모든 심볼의 롱숏 비율 데이터를 병렬로 가져오기
      const promises = SYMBOLS.map(async (symbol) => {
        try {
          const response = await fetch(`${LIQUIDATION_SERVICE_URL}/api/long-short/${symbol}`);
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
          const result = await response.json();
          return { symbol, data: result.data };
        } catch (error) {
          console.warn(`Failed to fetch long/short data for ${symbol}:`, error);
          return { symbol, data: null };
        }
      });

      const results = await Promise.all(promises);
      
      // 결과를 객체로 변환
      const longShortData = {};
      results.forEach(({ symbol, data }) => {
        if (data) {
          longShortData[symbol] = data;
        }
      });

      setData(longShortData);
      setLastUpdate(new Date());
      
    } catch (error) {
      console.error('Error fetching long/short data:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // 초기 데이터 로드
    fetchLongShortData();

    // 5분마다 업데이트
    const interval = setInterval(fetchLongShortData, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [fetchLongShortData]);

  // 수동 새로고침 함수
  const refresh = useCallback(() => {
    setLoading(true);
    fetchLongShortData();
  }, [fetchLongShortData]);

  // 특정 심볼의 데이터 가져오기
  const getSymbolData = useCallback((symbol) => {
    return data[symbol] || null;
  }, [data]);

  // 롱 우세 여부 판단
  const isLongDominant = useCallback((symbol) => {
    const symbolData = getSymbolData(symbol);
    if (!symbolData || !symbolData.binance) return null;
    return symbolData.binance.long_ratio > 0.6;
  }, [getSymbolData]);

  // 숏 우세 여부 판단
  const isShortDominant = useCallback((symbol) => {
    const symbolData = getSymbolData(symbol);
    if (!symbolData || !symbolData.binance) return null;
    return symbolData.binance.long_ratio < 0.4;
  }, [getSymbolData]);

  // 균형 상태 여부 판단
  const isBalanced = useCallback((symbol) => {
    const symbolData = getSymbolData(symbol);
    if (!symbolData || !symbolData.binance) return null;
    return symbolData.binance.long_ratio >= 0.4 && symbolData.binance.long_ratio <= 0.6;
  }, [getSymbolData]);

  return {
    data,
    loading,
    error,
    lastUpdate,
    refresh,
    getSymbolData,
    isLongDominant,
    isShortDominant,
    isBalanced,
    hasData: Object.keys(data).length > 0
  };
};

export default useLongShortData;