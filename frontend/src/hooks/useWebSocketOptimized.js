import { useState, useEffect, useRef, useCallback } from 'react';

const useWebSocket = (endpoints) => {
  const [data, setData] = useState({});
  const [status, setStatus] = useState({});
  const socketsRef = useRef({});

  const connect = useCallback((endpoint) => {
    console.log(`[WebSocket] Connecting to ${endpoint}...`);
    if (socketsRef.current[endpoint] && (socketsRef.current[endpoint].readyState === WebSocket.OPEN || socketsRef.current[endpoint].readyState === WebSocket.CONNECTING)) {
      console.log(`[WebSocket] Already open or connecting to ${endpoint}. Skipping.`);
      return;
    }

    const socket = new WebSocket(endpoint);
    socketsRef.current[endpoint] = socket;

    socket.onopen = () => {
      console.log(`[WebSocket] Connected to ${endpoint}`);
      setStatus(prev => ({ ...prev, [endpoint]: 'connected' }));
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setData(prev => ({ ...prev, [endpoint]: message }));
      } catch (error) {
        console.error(`[WebSocket] Error parsing message from ${endpoint}:`, error);
      }
    };

    socket.onerror = (error) => {
      console.error(`[WebSocket] Error on ${endpoint}:`, error, `(readyState: ${socket.readyState})`);
      setStatus(prev => ({ ...prev, [endpoint]: 'error' }));
    };

    socket.onclose = (event) => {
      console.log(`[WebSocket] Disconnected from ${endpoint}. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`);
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