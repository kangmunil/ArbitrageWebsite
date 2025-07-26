/**
 * 코인 가격 데이터 관리 훅 - 빠른 초기 로드 + 실시간 업데이트
 * 
 * 작동 방식:
 * 1. REST API로 즉시 초기 데이터 로드
 * 2. WebSocket으로 실시간 업데이트 수신
 * 3. 데이터 병합 및 상태 관리
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const usePriceData = () => {
  const [data, setData] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('loading');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const dataRef = useRef([]);
  
  // 1. REST API로 초기 데이터 빠르게 로드
  const loadInitialData = useCallback(async () => {
    try {
      console.log('🚀 Loading initial data via REST API...');
      setConnectionStatus('loading');
      
      const response = await fetch('http://localhost:8002/api/coins/latest');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log(`✅ Initial data loaded: ${result.count} coins`);
      console.log('📊 Sample coin:', result.data[0]);
      
      setData(result.data);
      dataRef.current = result.data;
      setLastUpdate(new Date());
      setConnectionStatus('loaded');
      setError(null);
      
      // 초기 데이터 로드 후 WebSocket 연결 시작
      connectWebSocket();
      
    } catch (err) {
      console.error('❌ Failed to load initial data:', err);
      setError(err.message);
      setConnectionStatus('error');
      
      // 3초 후 재시도
      setTimeout(loadInitialData, 3000);
    }
  }, []);
  
  // 2. WebSocket 실시간 업데이트
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }
    
    try {
      console.log('🔄 Connecting to WebSocket for real-time updates...');
      wsRef.current = new WebSocket('ws://localhost:8002/ws/prices');
      
      wsRef.current.onopen = () => {
        console.log('✅ WebSocket connected for real-time updates');
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          // 연결 확인 메시지는 무시
          if (message.message) {
            console.log('📡 WebSocket connection confirmed');
            return;
          }
          
          // 실제 코인 데이터 배열인 경우 업데이트
          if (Array.isArray(message) && message.length > 0) {
            console.log(`🔄 Real-time update: ${message.length} coins`);
            console.log('💰 Price change sample:', {
              symbol: message[0].symbol,
              price: message[0].upbit_price,
              time: new Date().toLocaleTimeString()
            });
            
            // 기존 데이터와 비교하여 실제 변경이 있는지 확인
            const hasChanges = !dataRef.current.length || 
              message.some((coin, index) => {
                const oldCoin = dataRef.current[index];
                return !oldCoin || coin.upbit_price !== oldCoin.upbit_price;
              });
            
            if (hasChanges) {
              console.log('✨ Data has changed, updating UI');
              setData([...message]); // 새 배열 참조로 강제 리렌더링
              dataRef.current = message;
              setLastUpdate(new Date());
              setError(null);
            } else {
              console.log('⏭️ No price changes detected');
            }
          }
          
        } catch (err) {
          console.error('WebSocket message parsing error:', err);
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
      };
      
      wsRef.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code);
        setConnectionStatus('disconnected');
        
        // 자동 재연결 (최대 10회)
        if (reconnectAttemptsRef.current < 10) {
          reconnectAttemptsRef.current++;
          console.log(`Reconnecting WebSocket... (${reconnectAttemptsRef.current}/10)`);
          setTimeout(connectWebSocket, 3000);
        } else {
          console.error('Max WebSocket reconnect attempts reached');
          setConnectionStatus('failed');
        }
      };
      
    } catch (err) {
      console.error('WebSocket connection failed:', err);
      setConnectionStatus('error');
    }
  }, []);
  
  // 수동 재연결
  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    loadInitialData();
  }, [loadInitialData]);
  
  // 컴포넌트 마운트 시 초기 데이터 로드
  useEffect(() => {
    loadInitialData();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [loadInitialData]);
  
  return {
    data,
    connectionStatus,
    lastUpdate,
    error,
    reconnect,
    refresh: loadInitialData
  };
};

export default usePriceData;