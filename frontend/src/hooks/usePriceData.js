import { useState, useEffect, useCallback } from 'react';
import useWebSocket from './useWebSocketOptimized';

const usePriceData = () => {
  const [data, setData] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('loading');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
  const priceWsEndpoint = `${backendUrl.replace('http', 'ws')}/ws/prices`;
  const { data: wsData, status: wsStatus } = useWebSocket([priceWsEndpoint]);

  const loadInitialData = useCallback(async () => {
    try {
      setConnectionStatus('loading');
      const response = await fetch(`${backendUrl}/api/coins/latest`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const result = await response.json();
      setData(result.data);
      setLastUpdate(new Date());
      setConnectionStatus('loaded');
      setError(null);
    } catch (err) {
      console.error('Failed to load initial data:', err);
      setError(err.message);
      setConnectionStatus('failed');
    }
  }, [backendUrl]);

  useEffect(() => {
    // 초기 상태 설정
    setConnectionStatus('loading');

    // 웹소켓 연결 상태를 추적
    const currentWsStatus = wsStatus[priceWsEndpoint];
    if (currentWsStatus) {
      setConnectionStatus(currentWsStatus);
    }

    // 웹소켓 데이터가 있으면 업데이트
    if (wsData[priceWsEndpoint]) {
      const newData = wsData[priceWsEndpoint];
      setData(newData);
      setLastUpdate(new Date());
      console.log('🔍 [usePriceData] 웹소켓 데이터 업데이트됨. 첫 번째 코인:', newData[0]?.symbol, newData[0]?.upbit_price);
    } else if (currentWsStatus === 'disconnected' || currentWsStatus === 'error') {
      // 웹소켓 연결이 끊기거나 오류 발생 시에만 초기 데이터 로딩 시도
      loadInitialData();
    }
  }, [wsData, wsStatus, priceWsEndpoint, loadInitialData]);

  return {
    data,
    connectionStatus,
    lastUpdate,
    error,
    reconnect: loadInitialData, // Reconnect is now just reloading initial data
    refresh: loadInitialData,
  };
};

export default usePriceData;