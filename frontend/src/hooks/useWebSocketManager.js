/**
 * 통합 WebSocket 관리 훅
 * 
 * 모든 WebSocket 연결을 중앙에서 관리하고,
 * 재연결, 오류 처리, 상태 모니터링을 제공합니다.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { getWebSocketUrl } from '../utils/apiClient';

// 연결 상태 정의
export const WS_STATUS = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  ERROR: 'error',
  RECONNECTING: 'reconnecting'
};

// 기본 설정 - 서버 부하 방지를 위한 최적화
const DEFAULT_OPTIONS = {
  reconnectAttempts: 2,
  reconnectInterval: 15000, // 15초로 증가
  pingInterval: 60000, // 1분으로 증가
  connectionTimeout: 30000, // 30초로 증가
  enableLogging: true // 디버깅을 위해 임시 활성화
};

/**
 * 단일 WebSocket 연결 관리 훅
 * @param {string} endpoint - WebSocket 엔드포인트
 * @param {Object} options - 연결 옵션
 * @returns {{status: string, data: any, error: string, lastMessageTime: Date, sendMessage: Function, reconnect: Function, disconnect: Function, stats: Object}}
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
  
  /**
   * 로그를 출력합니다.
   * @param {string} message - 로그 메시지
   * @param {string} level - 로그 레벨 (info, warn, error)
   */
  const log = useCallback((message, level = 'info') => {
    if (config.enableLogging) {
      console[level](`[WebSocket:${endpoint}] ${message}`);
    }
  }, [endpoint, config.enableLogging]);
  
  /**
   * WebSocket에 연결합니다.
   */
  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      log('이미 연결되어 있습니다');
      return;
    }
    
    setStatus(WS_STATUS.CONNECTING);
    setError(null);
    
    try {
      const wsUrl = getWebSocketUrl(endpoint);
      
      // Firefox 호환성을 위한 WebSocket 옵션 설정
      if (navigator.userAgent.includes('Firefox')) {
        // Firefox에서는 서브프로토콜 없이 연결 시도
        socketRef.current = new WebSocket(wsUrl);
      } else {
        socketRef.current = new WebSocket(wsUrl);
      }
      
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
          
          // 빈 메시지나 잘못된 데이터 체크
          if (!event.data || typeof event.data !== 'string') {
            log('빈 메시지 또는 잘못된 데이터 형식', 'warn');
            return;
          }
          
          const message = JSON.parse(event.data);
          
          // 메시지 유효성 검사 및 타입별 처리
          if (message && typeof message === 'object') {
            // 하이브리드 업데이트 시스템: 메시지 타입에 따라 분기 처리
            const messageType = message.type || 'price_update';
            
            if (messageType === 'major_update') {
              // Major 코인 즉시 업데이트: 개별 데이터이므로 배열로 래핑하여 전달
              setData({
                type: 'major_update',
                data: message.data || message,
                timestamp: new Date()
              });
              log(`Major 코인 즉시 업데이트: ${message.data?.[0]?.symbol || 'unknown'}`);
            } else if (messageType === 'minor_batch') {
              // Minor 코인 배치 업데이트
              setData({
                type: 'minor_batch', 
                data: message.data || message,
                timestamp: new Date()
              });
              log(`Minor 코인 배치 업데이트: ${(message.data || []).length}개`);
            } else {
              // 기존 방식 (호환성 유지)
              setData({
                type: 'price_update',
                data: message.data || message,
                timestamp: new Date()
              });
              log(`기본 가격 업데이트: ${JSON.stringify(message).substring(0, 100)}...`);
            }
            
            setLastMessageTime(new Date());
          } else {
            log('잘못된 메시지 형식', 'warn');
          }
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
        
        // 정상 종료(1000)이거나 사용자 요청(1001) 종료인 경우만 재연결하지 않음
        if (event.code === 1000 || event.code === 1001) {
          setStatus(WS_STATUS.DISCONNECTED);
        } else {
          setStatus(WS_STATUS.DISCONNECTED);
          // 짧은 지연 후 재연결 시도 (서버 부하 방지)
          setTimeout(() => {
            attemptReconnect();
          }, 2000);
        }
      };
      
    } catch (err) {
      log(`연결 시도 실패: ${err.message}`, 'error');
      setStatus(WS_STATUS.ERROR);
      setError(err.message);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, config.connectionTimeout, config.pingInterval, log]);
  
  /**
   * 재연결을 시도합니다.
   */
  const attemptReconnect = useCallback(() => {
    if (reconnectCountRef.current >= config.reconnectAttempts) {
      log('최대 재연결 시도 횟수 초과', 'warn');
      setStatus(WS_STATUS.ERROR);
      setError('재연결에 실패했습니다');
      return;
    }
    
    reconnectCountRef.current++;
    setStatus(WS_STATUS.RECONNECTING);
    
    // 지수적 백오프로 재연결 간격 증가 (서버 부하 방지)
    const delay = Math.min(config.reconnectInterval * Math.pow(2, reconnectCountRef.current - 1), 60000);
    log(`${delay}ms 후 재연결 시도 (${reconnectCountRef.current}/${config.reconnectAttempts})`);
    
    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [config.reconnectAttempts, config.reconnectInterval, connect, log]);
  
  /**
   * Ping을 시작합니다.
   */
  const startPing = useCallback(() => {
    if (config.pingInterval <= 0 || pingIntervalRef.current) return;
    
    pingIntervalRef.current = setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send('ping');
        log('Ping 전송');
      }
    }, config.pingInterval);
  }, [config.pingInterval, log]);
  
  /**
   * Ping을 중지합니다.
   */
  const stopPing = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);
  
  /**
   * WebSocket 연결을 해제합니다.
   */
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
  
  /**
   * WebSocket으로 메시지를 전송합니다.
   * @param {any} message - 전송할 메시지
   * @returns {boolean} 전송 성공 여부
   */
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
  
  /**
   * 수동으로 재연결을 시도합니다.
   */
  const reconnect = useCallback(() => {
    log('수동 재연결 시도');
    
    // 기존 연결 정리
    if (socketRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      clearTimeout(connectionTimeoutRef.current);
      stopPing();
      
      if (socketRef.current.readyState === WebSocket.OPEN || 
          socketRef.current.readyState === WebSocket.CONNECTING) {
        socketRef.current.close(1000, '수동 재연결');
      }
      socketRef.current = null;
    }
    
    setTimeout(() => {
      reconnectCountRef.current = 0;
      connect();
    }, 1000);
  }, [connect, log, stopPing]);
  
  // 초기 연결 - 순환 의존성 제거
  useEffect(() => {
    connect();
    
    return () => {
      // cleanup에서는 직접 처리하여 순환 의존성 방지
      if (socketRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        clearTimeout(connectionTimeoutRef.current);
        
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        
        if (socketRef.current.readyState === WebSocket.OPEN || 
            socketRef.current.readyState === WebSocket.CONNECTING) {
          socketRef.current.close(1000, '컴포넌트 언마운트');
        }
        socketRef.current = null;
      }
      setStatus(WS_STATUS.DISCONNECTED);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
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
 * @param {Array<string>} endpoints - WebSocket 엔드포인트 목록
 * @param {Object} options - 연결 옵션
 * @returns {{connections: Object, globalStatus: string, disconnectAll: Function, reconnectAll: Function, getConnection: Function, getAllData: Function, getStats: Function}}
 */
export const useMultipleWebSockets = (endpoints, options = {}) => {
  const [connections, setConnections] = useState({});
  const [globalStatus, setGlobalStatus] = useState('disconnected');
  
  // React Hook 규칙 준수: 조건문이나 반복문 내에서 Hook을 호출할 수 없음
  // 이 함수는 현재 사용되지 않으므로 단순화된 구현으로 변경
  const sockets = useMemo(() => ({}), []);
  
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
    // 빈 객체이므로 의존성 배열에서 제거
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  /**
   * 모든 WebSocket 연결을 해제합니다.
   */
  const disconnectAll = useCallback(() => {
    Object.values(sockets).forEach(socket => {
      socket.disconnect();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  /**
   * 모든 WebSocket 연결을 재시도합니다.
   */
  const reconnectAll = useCallback(() => {
    Object.values(sockets).forEach(socket => {
      socket.reconnect();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
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
