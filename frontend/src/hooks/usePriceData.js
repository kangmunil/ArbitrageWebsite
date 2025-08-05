import { useState, useEffect, useCallback } from 'react';
import { useWebSocket, WS_STATUS } from './useWebSocketManager';
import { coinApi } from '../utils/apiClient';

/**
 * 가격 데이터를 관리하는 커스텀 훅.
 * @returns {{data: Array, connectionStatus: string, lastUpdate: Date, error: string, reconnect: Function, refresh: Function, wsStats: Object}}
 */
const usePriceData = () => {
  const [data, setData] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('loading');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);

  // 통합 WebSocket 관리자 사용 - 재연결 빈도 최적화
  const priceWs = useWebSocket('/ws/prices', {
    reconnectAttempts: 2,
    reconnectInterval: 20000, // 20초로 증가
    connectionTimeout: 30000, // 30초로 증가
    enableLogging: false // 운영 모드로 전환
  });

  /**
   * 초기 데이터를 로드합니다.
   */
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
    // 하이브리드 WebSocket 데이터 업데이트 처리
    if (priceWs.data) {
      const messageType = priceWs.data.type || 'price_update';
      const messageData = priceWs.data.data || priceWs.data;
      
      if (messageType === 'major_update') {
        // Major 코인 즉시 업데이트: 기존 데이터에서 해당 코인만 업데이트
        if (Array.isArray(messageData)) {
          setData(prevData => {
            // prevData가 배열이 아닌 경우 안전하게 처리
            if (!Array.isArray(prevData)) {
              console.warn('prevData is not an array, initializing with messageData');
              return messageData;
            }
            
            const updatedData = [...prevData];
            messageData.forEach(newCoin => {
              const index = updatedData.findIndex(coin => coin.symbol === newCoin.symbol);
              if (index !== -1) {
                updatedData[index] = { ...updatedData[index], ...newCoin };
              }
            });
            return updatedData;
          });
          console.log(`⚡ Major 코인 즉시 업데이트: ${messageData.map(c => c.symbol).join(', ')}`);
        }
      } else if (messageType === 'minor_batch') {
        // Minor 코인 배치 업데이트: 기존 데이터에서 해당 코인들만 업데이트
        if (Array.isArray(messageData)) {
          setData(prevData => {
            // prevData가 배열이 아닌 경우 안전하게 처리
            if (!Array.isArray(prevData)) {
              console.warn('prevData is not an array, initializing with messageData');
              return messageData;
            }
            
            const updatedData = [...prevData];
            messageData.forEach(newCoin => {
              const index = updatedData.findIndex(coin => coin.symbol === newCoin.symbol);
              if (index !== -1) {
                updatedData[index] = { ...updatedData[index], ...newCoin };
              }
            });
            return updatedData;
          });
          console.log(`📦 Minor 코인 배치 업데이트: ${messageData.length}개`);
        }
      } else {
        // 기존 방식 (호환성 유지): 전체 데이터 교체
        if (Array.isArray(messageData)) {
          console.log(`💰 전체 가격 데이터 업데이트: ${messageData.length}개 코인`);
          setData(messageData);
        } else {
          console.warn('⚠️ 예상치 못한 데이터 형식:', typeof messageData);
        }
      }
      
      setLastUpdate(new Date());
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