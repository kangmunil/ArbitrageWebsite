import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * 여러 WebSocket 엔드포인트에 대한 연결을 관리하는 커스텀 훅입니다.
 * @param {Array<string>} endpoints - 연결할 WebSocket 엔드포인트 목록
 * @returns {{data: Object, status: Object}} 각 엔드포인트의 데이터 및 연결 상태
 */
const useWebSocket = (endpoints) => {
  const [data, setData] = useState({});
  const [status, setStatus] = useState({});
  const socketsRef = useRef({});

  /**
   * 지정된 엔드포인트에 WebSocket 연결을 설정합니다.
   * @param {string} endpoint - 연결할 WebSocket 엔드포인트
   */
  const connect = useCallback((endpoint) => {
    if (socketsRef.current[endpoint] && (socketsRef.current[endpoint].readyState === WebSocket.OPEN || socketsRef.current[endpoint].readyState === WebSocket.CONNECTING)) {
      return;
    }

    const socket = new WebSocket(endpoint);
    socketsRef.current[endpoint] = socket;

    socket.onopen = () => {
      setStatus(prev => ({ ...prev, [endpoint]: 'connected' }));
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setData(prev => ({ ...prev, [endpoint]: message }));
      } catch (error) {
        console.error(`WebSocket parse error:`, error);
      }
    };

    socket.onerror = (error) => {
      console.error(`WebSocket error on ${endpoint}:`, error);
      setStatus(prev => ({ ...prev, [endpoint]: 'error' }));
    };

    socket.onclose = () => {
      setStatus(prev => ({ ...prev, [endpoint]: 'disconnected' }));
    };
  }, []);

  // endpoints 배열이 변경될 때만 effect가 실행되도록 수정
  const endpointsKey = JSON.stringify(endpoints.sort());

  useEffect(() => {
    const currentEndpoints = JSON.parse(endpointsKey);
    currentEndpoints.forEach(endpoint => {
      connect(endpoint);
    });

    const sockets = socketsRef.current;
    return () => {
      Object.values(sockets).forEach(socket => {
        socket.close();
      });
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpointsKey, connect]);

  return { data, status };
};

export default useWebSocket;
