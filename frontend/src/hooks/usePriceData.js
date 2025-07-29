import { useState, useEffect, useCallback } from 'react';
import { useWebSocket, WS_STATUS } from './useWebSocketManager';
import { coinApi } from '../utils/apiClient';

const usePriceData = () => {
  const [data, setData] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('loading');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);

  // 통합 WebSocket 관리자 사용
  const priceWs = useWebSocket('/ws/prices', {
    reconnectAttempts: 3,
    reconnectInterval: 2000,
    enableLogging: true
  });

  const loadInitialData = useCallback(async () => {
    try {
      setConnectionStatus('loading');
      const result = await coinApi.getLatest(false); // 캐시 사용 안함
      
      if (result.success) {
        setData(result.data);
        setLastUpdate(new Date());
        setConnectionStatus('loaded');
        setError(null);
      } else {
        throw new Error(result.error);
      }
    } catch (err) {
      console.error('Failed to load initial data:', err);
      setError(err.message);
      setConnectionStatus('failed');
    }
  }, []);

  useEffect(() => {
    // WebSocket 상태에 따른 연결 상태 업데이트
    switch (priceWs.status) {
      case WS_STATUS.CONNECTED:
        setConnectionStatus('connected');
        setError(null);
        break;
      case WS_STATUS.CONNECTING:
      case WS_STATUS.RECONNECTING:
        setConnectionStatus('connecting');
        break;
      case WS_STATUS.ERROR:
        setConnectionStatus('error');
        setError(priceWs.error);
        // WebSocket 오류 시 초기 데이터 로드 시도
        loadInitialData();
        break;
      case WS_STATUS.DISCONNECTED:
        setConnectionStatus('disconnected');
        // 연결 끊김 시 초기 데이터 로드 시도
        loadInitialData();
        break;
      default:
        setConnectionStatus('loading');
    }
  }, [priceWs.status, priceWs.error, loadInitialData]);

  useEffect(() => {
    // WebSocket 데이터 업데이트
    if (priceWs.data) {
      // 새로운 WebSocket 매니저의 표준 메시지 형식 처리
      const messageData = priceWs.data.data || priceWs.data;
      
      if (Array.isArray(messageData)) {
        setData(messageData);
        setLastUpdate(new Date());
        console.log('🔍 [usePriceData] WebSocket 데이터 업데이트:', messageData.length, '개 코인');
      }
    }
  }, [priceWs.data]);

  return {
    data,
    connectionStatus,
    lastUpdate,
    error,
    reconnect: priceWs.reconnect, // WebSocket 재연결 함수 사용
    refresh: loadInitialData,
    wsStats: priceWs.stats // WebSocket 통계 정보 추가
  };
};

export default usePriceData;