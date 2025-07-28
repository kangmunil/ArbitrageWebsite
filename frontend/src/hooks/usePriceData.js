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
  
  useEffect(() => {
    dataRef.current = data; // data 상태가 변경될 때 dataRef.current 업데이트
  }, [data]);
  
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
    // 기존 WebSocket 연결이 있다면 정리
    if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
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
              
              // 실제 변화하는 코인들의 데이터 확인 (백엔드 로그에서 확인된 코인들)
              const changingCoins = ['XRP', 'ENS', 'NEWT', 'SIGN', 'UNI'];
              const changingData = message.filter(coin => changingCoins.includes(coin.symbol));
              if (changingData.length > 0) {
                changingData.forEach(coin => {
                  console.log(`💰 [usePriceData] ${coin.symbol} 수신: Upbit=${coin.upbit_price} KRW, Binance=${coin.binance_price} USD`);
                });
              }
            }
            
            // 1. 새로운 데이터를 Symbol을 키로 하는 Map으로 변환 (빠른 조회를 위해) - 현재 사용되지 않음
            // const newMessageMap = new Map(message.map(coin => [coin.symbol, coin]));

            // 2. 이전 데이터를 Map으로 변환
            const oldDataMap = new Map(dataRef.current.map(coin => [coin.symbol, coin]));

            // 3. 실제 변경 감지 로직 개선
            const PRICE_CHANGE_THRESHOLD = 0.000001; // 가격 변화 감지 임계값 (예: 0.0001%)

            const hasChanges = message.length !== dataRef.current.length || message.some(newCoin => {
              const oldCoin = oldDataMap.get(newCoin.symbol);
              if (!oldCoin) return true; // 새로운 코인인 경우

              // 가격 변화를 임계값 기준으로 감지
              const upbitPriceChanged = newCoin.upbit_price !== null && oldCoin.upbit_price !== null && Math.abs(newCoin.upbit_price - oldCoin.upbit_price) > (oldCoin.upbit_price * PRICE_CHANGE_THRESHOLD || 0.000001); // 0으로 나누는 것 방지
              const binancePriceChanged = newCoin.binance_price !== null && oldCoin.binance_price !== null && Math.abs(newCoin.binance_price - oldCoin.binance_price) > (oldCoin.binance_price * PRICE_CHANGE_THRESHOLD || 0.000001);
              const bybitPriceChanged = newCoin.bybit_price !== null && oldCoin.bybit_price !== null && Math.abs(newCoin.bybit_price - oldCoin.bybit_price) > (oldCoin.bybit_price * PRICE_CHANGE_THRESHOLD || 0.000001);

              return upbitPriceChanged || binancePriceChanged || bybitPriceChanged;
            });

            if (hasChanges) {
              if (process.env.NODE_ENV === 'development') {
                logOnce('data-changed', '✨ Data has changed, updating UI', console.log, 60000);
                
                // 1단계 디버깅: setState 직후 새 데이터 확인
                const xrpData = message.find(coin => coin.symbol === 'XRP');
                if (xrpData) {
                  console.log(`🔍 [usePriceData 1단계] XRP setState 직후: upbit_price=${xrpData.upbit_price}, 배열길이=${message.length}`);
                }
              }
              setData([...message]); // 새 배열 참조로 강제 리렌더링
              // dataRef.current는 setData가 완료된 후에 업데이트
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
        
        // 자동 재연결 (무한)
        reconnectAttemptsRef.current++;
        if (process.env.NODE_ENV === 'development') {
            logOnce(`ws-reconnect-${reconnectAttemptsRef.current}`, `Reconnecting WebSocket... (attempt ${reconnectAttemptsRef.current})`, console.log, 3000);
        }
        setTimeout(connectWebSocket, 3000);
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