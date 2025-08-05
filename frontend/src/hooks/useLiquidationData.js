/**
 * 청산 데이터 관리 훅
 * 청산 서비스(포트 8002)에서 실시간 청산 데이터를 가져옵니다.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const LIQUIDATION_SERVICE_URL = process.env.REACT_APP_LIQUIDATION_SERVICE_URL || 'http://localhost:8002';
const WS_URL = LIQUIDATION_SERVICE_URL.replace('http', 'ws');

export const useLiquidationData = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const ws = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  // 초기 데이터 로드
  const fetchInitialData = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch(`${LIQUIDATION_SERVICE_URL}/api/liquidations/24h`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      
      if (result.success && result.data) {
        // 데이터를 배열로 변환하고 청산액 순으로 정렬
        const liquidationArray = Object.entries(result.data).map(([symbol, summary]) => ({
          symbol,
          ...summary
        })).sort((a, b) => b.total_liquidation_usd - a.total_liquidation_usd);
        
        console.log('Liquidation data loaded:', liquidationArray.length, 'items');
        console.log('Sample data:', liquidationArray.slice(0, 3));
        
        setData(liquidationArray);
        setLastUpdate(new Date());
      } else {
        console.warn('Invalid liquidation API response:', result);
      }
    } catch (error) {
      console.error('Error fetching initial liquidation data:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // WebSocket 연결
  const connectWebSocket = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      ws.current = new WebSocket(`${WS_URL}/ws/liquidations`);
      
      ws.current.onopen = () => {
        console.log('Liquidation WebSocket connected');
        setWsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        
        // Keep-alive 메시지 전송 (5초마다)
        const keepAliveInterval = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send('ping');
          } else {
            clearInterval(keepAliveInterval);
          }
        }, 5000);
      };

      ws.current.onmessage = (event) => {
        try {
          const messageData = JSON.parse(event.data);
          console.log('WebSocket message received:', messageData.type, messageData);
          
          // 청산 데이터 업데이트
          if (messageData.type === 'liquidation_update' && messageData.data) {
            const liquidationArray = Object.entries(messageData.data).map(([symbol, summary]) => ({
              symbol,
              ...summary
            })).sort((a, b) => b.total_liquidation_usd - a.total_liquidation_usd);
            
            console.log('WebSocket data updated:', liquidationArray.length, 'items');
            
            setData(liquidationArray);
            setLastUpdate(new Date());
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.current.onclose = (event) => {
        console.log('Liquidation WebSocket disconnected:', event.code, event.reason);
        setWsConnected(false);
        
        // 자동 재연결 (정상 종료가 아닌 경우)
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            console.log(`Attempting to reconnect... (${reconnectAttempts.current}/${maxReconnectAttempts})`);
            connectWebSocket();
          }, delay);
        }
      };

      ws.current.onerror = (error) => {
        console.error('Liquidation WebSocket error:', error);
        setError('WebSocket connection failed');
      };

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      setError(error.message);
    }
  }, []);

  // WebSocket 연결 해제
  const disconnectWebSocket = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (ws.current) {
      ws.current.close(1000, 'Component unmounting');
      ws.current = null;
    }
    
    setWsConnected(false);
  }, []);

  useEffect(() => {
    // 초기 데이터 로드
    fetchInitialData();
    
    // WebSocket 연결
    connectWebSocket();

    return () => {
      disconnectWebSocket();
    };
  }, [fetchInitialData, connectWebSocket, disconnectWebSocket]);

  // 수동 새로고침
  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchInitialData();
  }, [fetchInitialData]);

  // 특정 심볼의 데이터 가져오기
  const getSymbolData = useCallback((symbol) => {
    return data.find(item => item.symbol === symbol) || null;
  }, [data]);

  // 상위 N개 청산 데이터 가져오기
  const getTopLiquidations = useCallback((limit = 10) => {
    return data.slice(0, limit);
  }, [data]);

  // 총 청산액 계산
  const getTotalLiquidationUsd = useCallback(() => {
    return data.reduce((total, item) => total + (item.total_liquidation_usd || 0), 0);
  }, [data]);

  // 롱 청산 비율 계산
  const getTotalLongPercentage = useCallback(() => {
    const totalUsd = getTotalLiquidationUsd();
    if (totalUsd === 0) return 0;
    
    const totalLongUsd = data.reduce((total, item) => total + (item.long_liquidation_usd || 0), 0);
    return Math.round((totalLongUsd / totalUsd) * 100);
  }, [data, getTotalLiquidationUsd]);

  return {
    data,
    loading,
    error,
    wsConnected,
    lastUpdate,
    refresh,
    getSymbolData,
    getTopLiquidations,
    getTotalLiquidationUsd,
    getTotalLongPercentage,
    hasData: data.length > 0
  };
};

export default useLiquidationData;