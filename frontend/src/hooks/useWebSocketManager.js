/**
 * 통합 WebSocket 관리 훅
 * 
 * 모든 WebSocket 연결을 중앙에서 관리하고,
 * 재연결, 오류 처리, 상태 모니터링을 제공합니다.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getWebSocketUrl } from '../utils/apiClient';

// 연결 상태 정의
export const WS_STATUS = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  ERROR: 'error',
  RECONNECTING: 'reconnecting'
};

// 기본 설정
const DEFAULT_OPTIONS = {
  reconnectAttempts: 5,
  reconnectInterval: 3000,
  pingInterval: 30000,
  connectionTimeout: 10000,
  enableLogging: process.env.NODE_ENV === 'development'
};

/**
 * 단일 WebSocket 연결 관리 훅
 */
export const useWebSocket = (endpoint, options = {}) => {
  const config = { ...DEFAULT_OPTIONS, ...options };
  const socketRef = useRef(null);
  const reconnectCountRef = useRef(0);
  const pingIntervalRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const connectionTimeoutRef = useRef(null);
  
  const [status, setStatus] = useState(WS_STATUS.DISCONNECTED);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [lastMessageTime, setLastMessageTime] = useState(null);
  
  const log = useCallback((message, level = 'info') => {
    if (config.enableLogging) {
      console[level](`[WebSocket:${endpoint}] ${message}`);
    }
  }, [endpoint, config.enableLogging]);
  
  // 연결 함수
  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      log('이미 연결되어 있습니다');
      return;
    }
    
    setStatus(WS_STATUS.CONNECTING);
    setError(null);
    
    try {
      const wsUrl = getWebSocketUrl(endpoint);
      socketRef.current = new WebSocket(wsUrl);
      
      // 연결 타임아웃 설정
      connectionTimeoutRef.current = setTimeout(() => {
        if (socketRef.current?.readyState === WebSocket.CONNECTING) {
          log('연결 타임아웃', 'warn');
          socketRef.current.close();
          setStatus(WS_STATUS.ERROR);
          setError('연결 타임아웃');
        }
      }, config.connectionTimeout);
      
      socketRef.current.onopen = () => {
        log('연결 성공');
        clearTimeout(connectionTimeoutRef.current);
        setStatus(WS_STATUS.CONNECTED);
        setError(null);
        reconnectCountRef.current = 0;
        
        // Ping 시작
        startPing();
      };
      
      socketRef.current.onmessage = (event) => {
        try {
          // Pong 메시지 처리
          if (event.data === 'pong') {
            log('Pong 수신');
            return;
          }
          
          const message = JSON.parse(event.data);
          setData(message);
          setLastMessageTime(new Date());
          
          log(`메시지 수신: ${JSON.stringify(message).substring(0, 100)}...`);
        } catch (err) {
          log(`메시지 파싱 오류: ${err.message}`, 'error');
        }
      };
      
      socketRef.current.onerror = (err) => {
        log(`연결 오류: ${err}`, 'error');
        setStatus(WS_STATUS.ERROR);
        setError('연결 오류가 발생했습니다');
        clearTimeout(connectionTimeoutRef.current);
      };
      
      socketRef.current.onclose = (event) => {
        log(`연결 종료: Code ${event.code}, Reason: ${event.reason}`);
        clearTimeout(connectionTimeoutRef.current);
        stopPing();
        
        if (event.code !== 1000) { // 정상 종료가 아닌 경우
          setStatus(WS_STATUS.DISCONNECTED);
          attemptReconnect();
        } else {
          setStatus(WS_STATUS.DISCONNECTED);
        }
      };
      
    } catch (err) {
      log(`연결 시도 실패: ${err.message}`, 'error');
      setStatus(WS_STATUS.ERROR);
      setError(err.message);
    }
  }, [endpoint, config, log]);
  
  // 재연결 시도
  const attemptReconnect = useCallback(() => {
    if (reconnectCountRef.current >= config.reconnectAttempts) {
      log('최대 재연결 시도 횟수 초과', 'error');
      setStatus(WS_STATUS.ERROR);
      setError('재연결에 실패했습니다');
      return;
    }
    
    reconnectCountRef.current++;
    setStatus(WS_STATUS.RECONNECTING);
    
    const delay = config.reconnectInterval * Math.pow(1.5, reconnectCountRef.current - 1);
    log(`${delay}ms 후 재연결 시도 (${reconnectCountRef.current}/${config.reconnectAttempts})`);
    
    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [config.reconnectAttempts, config.reconnectInterval, connect, log]);
  
  // Ping 시작
  const startPing = useCallback(() => {
    if (config.pingInterval <= 0 || pingIntervalRef.current) return;
    
    pingIntervalRef.current = setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send('ping');
        log('Ping 전송');
      }
    }, config.pingInterval);
  }, [config.pingInterval, log]);
  
  // Ping 중지
  const stopPing = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);
  
  // 연결 해제
  const disconnect = useCallback(() => {
    log('연결 해제 요청');
    
    // 재연결 중단
    clearTimeout(reconnectTimeoutRef.current);
    clearTimeout(connectionTimeoutRef.current);
    reconnectCountRef.current = config.reconnectAttempts; // 재연결 방지
    
    stopPing();
    
    if (socketRef.current) {
      socketRef.current.close(1000, '사용자 요청');
      socketRef.current = null;
    }
    
    setStatus(WS_STATUS.DISCONNECTED);
  }, [config.reconnectAttempts, log, stopPing]);
  
  // 메시지 전송
  const sendMessage = useCallback((message) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
      socketRef.current.send(messageStr);
      log(`메시지 전송: ${messageStr.substring(0, 100)}...`);
      return true;
    } else {
      log('연결되지 않은 상태에서 메시지 전송 시도', 'warn');
      return false;
    }
  }, [log]);
  
  // 수동 재연결
  const reconnect = useCallback(() => {
    log('수동 재연결 시도');
    disconnect();
    setTimeout(() => {
      reconnectCountRef.current = 0;
      connect();
    }, 1000);
  }, [connect, disconnect, log]);
  
  // 초기 연결
  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);
  
  // 연결 상태 반환
  return {
    status,
    data,
    error,
    lastMessageTime,
    sendMessage,
    reconnect,
    disconnect,
    stats: {
      reconnectCount: reconnectCountRef.current,
      maxReconnects: config.reconnectAttempts,
      isConnected: status === WS_STATUS.CONNECTED,
      hasError: status === WS_STATUS.ERROR,
      isReconnecting: status === WS_STATUS.RECONNECTING
    }
  };
};

/**
 * 다중 WebSocket 연결 관리 훅
 */
export const useMultipleWebSockets = (endpoints, options = {}) => {
  const [connections, setConnections] = useState({});
  const [globalStatus, setGlobalStatus] = useState('disconnected');
  
  // 개별 WebSocket 훅들
  const sockets = {};
  endpoints.forEach(endpoint => {
    sockets[endpoint] = useWebSocket(endpoint, options);
  });
  
  // 연결 상태 업데이트
  useEffect(() => {
    const newConnections = {};
    const statuses = [];
    
    Object.entries(sockets).forEach(([endpoint, socket]) => {
      newConnections[endpoint] = {
        status: socket.status,
        data: socket.data,
        error: socket.error,
        lastMessageTime: socket.lastMessageTime,
        sendMessage: socket.sendMessage,
        reconnect: socket.reconnect,
        disconnect: socket.disconnect,
        stats: socket.stats
      };
      
      statuses.push(socket.status);
    });
    
    setConnections(newConnections);
    
    // 전체 상태 계산
    if (statuses.includes(WS_STATUS.CONNECTED)) {
      setGlobalStatus('connected');
    } else if (statuses.includes(WS_STATUS.CONNECTING) || statuses.includes(WS_STATUS.RECONNECTING)) {
      setGlobalStatus('connecting');
    } else if (statuses.every(status => status === WS_STATUS.ERROR)) {
      setGlobalStatus('error');
    } else {
      setGlobalStatus('disconnected');
    }
  }, [sockets]);
  
  // 모든 연결 해제
  const disconnectAll = useCallback(() => {
    Object.values(sockets).forEach(socket => {
      socket.disconnect();
    });
  }, [sockets]);
  
  // 모든 연결 재시도
  const reconnectAll = useCallback(() => {
    Object.values(sockets).forEach(socket => {
      socket.reconnect();
    });
  }, [sockets]);
  
  return {
    connections,
    globalStatus,
    disconnectAll,
    reconnectAll,
    getConnection: (endpoint) => connections[endpoint],
    getAllData: () => {
      const allData = {};
      Object.entries(connections).forEach(([endpoint, conn]) => {
        if (conn.data) {
          allData[endpoint] = conn.data;
        }
      });
      return allData;
    },
    getStats: () => {
      const stats = {
        total: endpoints.length,
        connected: 0,
        connecting: 0,
        disconnected: 0,
        error: 0,
        totalReconnects: 0
      };
      
      Object.values(connections).forEach(conn => {
        switch (conn.status) {
          case WS_STATUS.CONNECTED:
            stats.connected++;
            break;
          case WS_STATUS.CONNECTING:
          case WS_STATUS.RECONNECTING:
            stats.connecting++;
            break;
          case WS_STATUS.ERROR:
            stats.error++;
            break;
          default:
            stats.disconnected++;
        }
        
        if (conn.stats) {
          stats.totalReconnects += conn.stats.reconnectCount;
        }
      });
      
      return stats;
    }
  };
};

export default useWebSocket;