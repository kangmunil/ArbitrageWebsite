/**
 * 최적화된 WebSocket 훅
 * 
 * 주요 최적화 기능:
 * 1. 배치 업데이트 (여러 메시지를 한 번에 처리)
 * 2. 디바운싱 (과도한 업데이트 방지)
 * 3. 델타 압축 (변경된 데이터만 업데이트)
 * 4. 연결 상태 관리
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const useWebSocketOptimized = (url, options = {}) => {
  const {
    batchInterval = 100, // 배치 업데이트 간격 (ms)
    maxBatchSize = 50,   // 최대 배치 크기
    enableDeltaCompression = true, // 델타 압축 활성화
    reconnectInterval = 5000, // 재연결 간격 (ms)
    maxReconnectAttempts = 10 // 최대 재연결 시도 횟수
  } = options;

  const [data, setData] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const wsRef = useRef(null);
  const batchQueueRef = useRef([]);
  const batchTimeoutRef = useRef(null);
  const lastDataRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  
  // 배치 처리 함수
  const processBatch = useCallback(() => {
    if (batchQueueRef.current.length === 0) {
      console.log('⚠️ Batch queue is empty, skipping processing');
      return;
    }
    
    console.log(`🎯 Processing batch: ${batchQueueRef.current.length} messages in queue`);
    
    const batchData = [...batchQueueRef.current];
    batchQueueRef.current = [];
    
    // 최신 데이터만 추출 (같은 심볼의 경우 마지막 데이터만 사용)
    const latestDataMap = new Map();
    
    batchData.forEach((message, index) => {
      console.log(`📦 Processing message ${index + 1}:`, Array.isArray(message) ? `${message.length} coins` : 'non-array');
      if (Array.isArray(message)) {
        message.forEach(coin => {
          latestDataMap.set(coin.symbol, coin);
        });
      }
    });
    
    const processedData = Array.from(latestDataMap.values()).map(coin => ({ ...coin }));
    console.log(`🔧 Processed ${processedData.length} unique coins from batch`);
    
    // 델타 압축: 변경된 데이터만 업데이트 (임시로 비활성화)
    if (enableDeltaCompression && lastDataRef.current && lastDataRef.current.length > 0) {
      console.log('🔍 Delta compression is enabled but temporarily bypassed for debugging');
      // 임시로 모든 데이터를 통과시킴
    }
    
    console.log('📤 Updating React state with processed data');
    
    console.log('DEBUG: processedData before setData:', processedData[0]?.symbol, processedData[0]?.upbit_price, new Date().toLocaleTimeString());
    lastDataRef.current = processedData;
    setData(processedData);
    setLastUpdate(new Date());
    
    console.log(`🚀 Batch processed: ${processedData.length} coins updated at ${new Date().toLocaleTimeString()}`);
    if (processedData.length > 0) {
      console.log('📊 Sample coin data:', processedData[0]);
    }
  }, [enableDeltaCompression]);
  
  // 배치 타이머 설정
  const scheduleBatchProcess = useCallback(() => {
    if (batchTimeoutRef.current) {
      clearTimeout(batchTimeoutRef.current);
    }
    
    batchTimeoutRef.current = setTimeout(processBatch, batchInterval);
  }, [processBatch, batchInterval]);
  
  // 메시지 핸들러
  const handleMessage = useCallback((event) => {
    try {
      const message = JSON.parse(event.data);
      console.log('WebSocket raw message:', message);
      
      if (Array.isArray(message) && message.length > 0) {
        console.log(`✅ Received ${message.length} coins data`);
        console.log('📊 First coin sample:', message[0]);
        batchQueueRef.current.push(message);
        
        // 배치 크기가 임계값에 도달하면 즉시 처리
        if (batchQueueRef.current.length >= maxBatchSize) {
          if (batchTimeoutRef.current) {
            clearTimeout(batchTimeoutRef.current);
          }
          processBatch();
        } else {
          scheduleBatchProcess();
        }
      } else {
        console.log('Non-array or empty data received:', message);
      }
    } catch (error) {
      console.error('WebSocket message parsing error:', error, event.data);
    }
  }, [maxBatchSize, processBatch, scheduleBatchProcess]);
  
  // WebSocket 연결 함수
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected, skipping');
      return;
    }
    
    try {
      setConnectionStatus('connecting');
      console.log(`🔄 Connecting to WebSocket: ${url}`);
      
      wsRef.current = new WebSocket(url);
      
      wsRef.current.onopen = () => {
        console.log(`✅ WebSocket connected to: ${url}`);
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
      };
      
      wsRef.current.onmessage = handleMessage;
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
      };
      
      wsRef.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setConnectionStatus('disconnected');
        
        // 자동 재연결
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          console.log(`Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
          setTimeout(connect, reconnectInterval);
        } else {
          console.error('Max reconnect attempts reached');
          setConnectionStatus('failed');
        }
      };
      
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      setConnectionStatus('error');
      
      // 재연결 시도
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current++;
        setTimeout(connect, reconnectInterval);
      }
    }
  }, [url, handleMessage, reconnectInterval, maxReconnectAttempts]);
  
  // 연결 해제 함수
  const disconnect = useCallback(() => {
    if (batchTimeoutRef.current) {
      clearTimeout(batchTimeoutRef.current);
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setConnectionStatus('disconnected');
  }, []);
  
  // 수동 재연결 함수
  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttemptsRef.current = 0;
    setTimeout(connect, 1000);
  }, [connect, disconnect]);
  
  // 컴포넌트 마운트/언마운트 처리
  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);
  
  // 배치 처리 통계
  const getBatchStats = useCallback(() => {
    return {
      queueSize: batchQueueRef.current.length,
      lastUpdate,
      connectionStatus,
      reconnectAttempts: reconnectAttemptsRef.current
    };
  }, [lastUpdate, connectionStatus]);
  
  return {
    data,
    connectionStatus,
    lastUpdate,
    reconnect,
    disconnect,
    getBatchStats
  };
};

export default useWebSocketOptimized;