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
  
  // 중복 로그 방지용
  const lastLogTime = useRef({});
  
  // 중복 로그 방지 유틸리티
  const logOnce = useCallback((key, message, logFn = console.log, cooldownMs = 5000) => {
    const now = Date.now();
    const lastTime = lastLogTime.current[key];
    
    if (lastTime && (now - lastTime) < cooldownMs) {
      return;
    }
    
    lastLogTime.current[key] = now;
    logFn(message);
  }, []);
  
  // 1. REST API로 초기 데이터 빠르게 로드
  const loadInitialData = useCallback(async () => {
    try {
      if (process.env.NODE_ENV === 'development') {
        logOnce('initial-load', '🚀 Loading initial data via REST API...', console.log, 30000);
      }
      setConnectionStatus('loading');
      
      const response = await fetch('http://localhost:8000/api/coins/latest');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      if (process.env.NODE_ENV === 'development') {
        logOnce('initial-loaded', `✅ Initial data loaded: ${result.count} coins`, console.log, 30000);
        logOnce('sample-coin', `📊 Sample coin: ${JSON.stringify(result.data[0])}`, console.log, 60000);
      }
      
      setData(result.data);
      dataRef.current = result.data;
      setLastUpdate(new Date());
      setConnectionStatus('loaded');
      setError(null);
      
    } catch (err) {
      console.error('❌ Failed to load initial data:', err);
      setError(err.message);
      setConnectionStatus('error');
      
      // 3초 후 재시도
      setTimeout(loadInitialData, 3000);
    }
  }, [logOnce]);
  
  // 2. WebSocket 실시간 업데이트
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('⚠️ [usePriceData] WebSocket already connected');
      return;
    }
    
    try {
      if (process.env.NODE_ENV === 'development') {
        logOnce('ws-connecting', '🔄 Connecting to WebSocket for real-time updates...', console.log, 15000);
      }
      wsRef.current = new WebSocket('ws://localhost:8000/ws/prices');
      
      wsRef.current.onopen = () => {
        if (process.env.NODE_ENV === 'development') {
          logOnce('ws-connected', '✅ WebSocket connected for real-time updates', console.log, 30000);
        }
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          // 연결 확인 메시지는 무시
          if (message.message) {
            if (process.env.NODE_ENV === 'development') {
              logOnce('ws-ping-confirmed', '📡 WebSocket connection confirmed', console.log, 60000);
            }
            return;
          }
          
          // 실제 코인 데이터 배열인 경우 업데이트
          if (Array.isArray(message) && message.length > 0) {
            if (process.env.NODE_ENV === 'development') {
              logOnce('realtime-update', `🔄 Real-time update: ${message.length} coins`, console.log, 60000);
              
              // BTC 데이터 확인용 로그
              const btcData = message.find(coin => coin.symbol === 'BTC');
              if (btcData) {
                console.log(`💰 [usePriceData] BTC 수신: ${btcData.upbit_price} KRW / ${btcData.binance_price} USD`);
              }
            }
            
            // 기존 데이터와 비교하여 실제 변경이 있는지 확인
            const hasChanges = !dataRef.current.length || 
              message.some((coin, index) => {
                const oldCoin = dataRef.current[index];
                return !oldCoin || coin.upbit_price !== oldCoin.upbit_price;
              });
            
            if (hasChanges) {
              if (process.env.NODE_ENV === 'development') {
                logOnce('data-changed', '✨ Data has changed, updating UI', console.log, 60000);
              }
              setData([...message]); // 새 배열 참조로 강제 리렌더링
              dataRef.current = message;
              setLastUpdate(new Date());
              setError(null);
            }
          }
          
        } catch (err) {
          console.error('WebSocket message parsing error:', err);
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('❌ [usePriceData] WebSocket error:', error);
        setConnectionStatus('error');
      };
      
      wsRef.current.onclose = (event) => {
        if (process.env.NODE_ENV === 'development') {
          logOnce('ws-disconnected', `🔌 WebSocket disconnected: ${event.code} - ${event.reason}`, console.log, 5000);
        }
        setConnectionStatus('disconnected');
        
        // 자동 재연결 (최대 10회)
        if (reconnectAttemptsRef.current < 10) {
          reconnectAttemptsRef.current++;
          if (process.env.NODE_ENV === 'development') {
            logOnce(`ws-reconnect-${reconnectAttemptsRef.current}`, `Reconnecting WebSocket... (${reconnectAttemptsRef.current}/10)`, console.log, 3000);
          }
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
  }, [logOnce]);
  
  // 수동 재연결
  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    loadInitialData();
  }, [loadInitialData]);
  
  // 컴포넌트 마운트 시 초기 데이터 로드
  useEffect(() => {
    const init = async () => {
      await loadInitialData();
      connectWebSocket();
    };
    
    init();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [loadInitialData, connectWebSocket]);
  
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