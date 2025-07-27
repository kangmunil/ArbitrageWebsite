import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const useLiquidations = (windowMin = 5) => {
  const [summary, setSummary] = useState([]);
  const [trend, setTrend] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  // 캐시용 ref
  const cacheRef = useRef(null);
  const intervalRef = useRef(null);
  const wsRef = useRef(null);
  
  // 중복 로그 방지용
  const lastLogTime = useRef({});

  // 중복 로그 방지 유틸리티
  const logOnce = useCallback((key, message, logFn = console.log, cooldownMs = 5000) => {
    const now = Date.now();
    const lastTime = lastLogTime.current[key];
    
    // 쿨다운 시간 내에 동일한 키로 로그가 기록되었으면 무시
    if (lastTime && (now - lastTime) < cooldownMs) {
      return;
    }
    
    lastLogTime.current[key] = now;
    logFn(message);
  }, []);

  // 청산 데이터 정규화 함수
  const normalizeLiquidationData = useCallback((liqItem) => {
    let longLiq = 0;
    let shortLiq = 0;
    const usdAmount = liqItem.usd || liqItem.amount || liqItem.volume || liqItem.value || 0;

    // Case 1: Aggregated data from backend (has long_volume, short_volume)
    if (liqItem.long_volume !== undefined || liqItem.short_volume !== undefined) {
      longLiq = liqItem.long_volume || 0;
      shortLiq = liqItem.short_volume || 0;
    }
    // Case 2: Individual liquidation data (has side, positionSide)
    else {
      const side = liqItem.side ? liqItem.side.toLowerCase() : '';
      const positionSide = liqItem.positionSide ? liqItem.positionSide.toLowerCase() : '';

      // 거래소별 매핑 정확성 개선
      if (side === 'sell' || side === 'long' || positionSide === 'long') { 
        // Long liquidation: SELL order liquidating a LONG position
        longLiq = usdAmount;
      } else if (side === 'buy' || side === 'short' || positionSide === 'short') { 
        // Short liquidation: BUY order liquidating a SHORT position
        shortLiq = usdAmount;
      } else if (usdAmount > 0) {
        // 방향을 알 수 없는 경우: 랜덤하게 long/short 중 하나로 할당 (50:50)
        // 개발 모드에서는 로그로 알림 (중복 방지)
        if (process.env.NODE_ENV === 'development') {
          const logKey = `unknown-direction-${liqItem.side}-${liqItem.positionSide}`;
          logOnce(logKey, `⚠️ 청산 방향 미확정 - side:${liqItem.side}, positionSide:${liqItem.positionSide}, 금액:$${usdAmount}`, console.warn, 10000);
        }
        
        // 시간 기반 해시로 일관성 있는 랜덤 할당
        const timeHash = (liqItem.timestamp || Date.now()) % 100;
        if (timeHash < 50) {
          longLiq = usdAmount;
        } else {
          shortLiq = usdAmount;
        }
      }
    }

    return {
      ...liqItem,
      longLiq: longLiq,
      shortLiq: shortLiq,
      _original: { side: liqItem.side, positionSide: liqItem.positionSide },
    };
  }, [logOnce]);

  // 요약 데이터 변환 함수 (정규화 적용)
  const transformSummaryData = useCallback((data) => {
    const exchangeSummary = {};
    
    // 디버깅 로그 제거 (너무 많은 스팸)
    
    if (Array.isArray(data)) {
      data.forEach(item => {
        if (item.exchanges) {
          Object.entries(item.exchanges).forEach(([exchange, exchangeData]) => {
            if (!exchangeSummary[exchange]) {
              exchangeSummary[exchange] = { long: 0, short: 0 };
            }
            
            // 정규화 적용: 백엔드 데이터의 방향 매핑 교정
            const normalized = normalizeLiquidationData(exchangeData);
            
            // 백엔드에서 이미 집계된 데이터 vs 개별 청산 데이터
            if (exchangeData.long_volume !== undefined || exchangeData.short_volume !== undefined) {
              // 이미 집계된 데이터 (현재 백엔드 형식)
              exchangeSummary[exchange].long += exchangeData.long_volume || 0;
              exchangeSummary[exchange].short += exchangeData.short_volume || 0;
            } else {
              // 정규화된 개별 청산 데이터
              exchangeSummary[exchange].long += normalized.longLiq;
              exchangeSummary[exchange].short += normalized.shortLiq;
            }
            
            // 디버깅 로그 (방향 정확성 테스트용) - 중복 방지
            // 개발용 로그 제거 (너무 많은 스팸)
          });
        }
      });
    }
    
    // 고정된 거래소 순서 (차트 일관성 유지)
    const fixedOrderExchanges = ['Binance', 'Bybit', 'Okx', 'Bitget', 'Bitmex', 'Hyperliquid'];
    
    const result = fixedOrderExchanges.map(exchange => {
      const lowerExchange = exchange.toLowerCase();
      const data = exchangeSummary[lowerExchange] || { long: 0, short: 0 };
      return {
        exchange: exchange,
        long: data.long,
        short: data.short
      };
    }).slice(0, 6);
    
    // 디버깅 로그 제거
    
    return result;
  }, [normalizeLiquidationData, logOnce]);

  // 거래소별 트렌드 데이터 생성 (5분 누적)
  const generateTrendByExchange = useCallback((summaryData) => {
    // 고정된 거래소 순서 사용 (차트 일관성 유지)
    const exchanges = ['Binance', 'Bybit', 'Okx', 'Bitget', 'Bitmex', 'Hyperliquid'];
    
    return exchanges.map(exchange => {
      // 실제 데이터에서 해당 거래소 찾기
      const actualData = summaryData.find(item => item.exchange === exchange);
      
      if (actualData) {
        return {
          exchange: exchange, // 전체 거래소 이름 표시
          long: actualData.long / 1000000, // M 단위로 변환
          short: actualData.short / 1000000
        };
      } else {
        // 더미 데이터
        return {
          exchange: exchange, // 전체 거래소 이름 표시
          long: Math.random() * 2 + 0.2, // 0.2 ~ 2.2M
          short: Math.random() * 1.5 + 0.1 // 0.1 ~ 1.6M
        };
      }
    });
  }, []);

  // 데이터 fetch 함수
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      
      // 요약 데이터 가져오기
      const summaryResponse = await axios.get(
        `${API_BASE}/api/liquidations/aggregated?limit=${windowMin * 12}`,
        { timeout: 10000 }
      );
      
      const summaryData = transformSummaryData(summaryResponse.data);
      
      // 거래소별 트렌드 데이터 생성
      const trendData = generateTrendByExchange(summaryData);
      
      // 성공 시 캐시 업데이트
      cacheRef.current = {
        summary: summaryData,
        trend: trendData,
        timestamp: Date.now()
      };
      
      setSummary(summaryData);
      setTrend(trendData);
      setLastUpdate(new Date());
      setError(null);
      
    } catch (err) {
      console.error('Liquidation data fetch error:', err);
      
      // 캐시가 있고 5분 이내라면 캐시 사용
      if (cacheRef.current && (Date.now() - cacheRef.current.timestamp < 5 * 60 * 1000)) {
        setSummary(cacheRef.current.summary);
        setTrend(cacheRef.current.trend);
        setError('네트워크 오류 - 캐시된 데이터 사용');
      } else {
        // 캐시가 없으면 더미 데이터
        const dummySummary = [
          { exchange: 'Binance', long: 5200000, short: 800000 },
          { exchange: 'Bybit', long: 2100000, short: 1000000 },
          { exchange: 'Okx', long: 1800000, short: 700000 },
          { exchange: 'Bitget', long: 1200000, short: 600000 },
          { exchange: 'Kraken', long: 800000, short: 400000 }
        ];
        
        const dummyTrend = generateTrendByExchange(dummySummary);
        
        setSummary(dummySummary);
        setTrend(dummyTrend);
        setError('데이터 로드 실패 - 더미 데이터 표시');
      }
      setLastUpdate(new Date());
    } finally {
      setLoading(false);
    }
  }, [windowMin, transformSummaryData, generateTrendByExchange]);

  // WebSocket 연결
  const connectWebSocket = useCallback(() => {
    try {
      const ws = new WebSocket(`ws://localhost:8000/ws/liquidations`);
      
      ws.onopen = () => {
        if (process.env.NODE_ENV === 'development') {
          logOnce('ws-liquidation-connected', '청산 데이터 WebSocket 연결됨', console.log, 30000);
        }
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'liquidation_update' && data.data) {
            // 실시간 청산 데이터 정규화 및 디버깅
            const normalized = normalizeLiquidationData(data.data);
            
            // 개발 모드에서 방향 정확성 테스트 로그 (중복 방지)
            if (process.env.NODE_ENV === 'development') {
              const logKey = `realtime-${data.exchange || 'unknown'}-${data.data?.side}-${data.data?.positionSide}`;
              logOnce(logKey, `🔄 [${data.exchange || 'unknown'}] 실시간 청산: 원본=${JSON.stringify(data.data)}, 정규화=${JSON.stringify({ longLiq: normalized.longLiq, shortLiq: normalized.shortLiq })}, 시간=${new Date().toLocaleTimeString()}`, console.log, 8000);
              
              // 가격 움직임과 청산 방향 일치성 체크 힌트 (간격 제한)
              if (normalized.longLiq > 0) {
                logOnce('long-liquidation-hint', '📉 롱 청산 발생 - 가격 하락 추세일 가능성', console.log, 20000);
              }
              if (normalized.shortLiq > 0) {
                logOnce('short-liquidation-hint', '📈 숏 청산 발생 - 가격 상승 추세일 가능성', console.log, 20000);
              }
            }
            
            // 실시간 업데이트 빈도 제한: 마지막 업데이트로부터 5초 이상 경과한 경우만 새로 fetch
            const now = Date.now();
            if (!cacheRef.current || (now - cacheRef.current.timestamp > 5000)) {
              fetchData();
            }
          }
        } catch (err) {
          console.error('WebSocket message parse error:', err);
        }
      };
      
      ws.onclose = () => {
        if (process.env.NODE_ENV === 'development') {
          logOnce('ws-liquidation-disconnected', '청산 데이터 WebSocket 연결 해제됨', console.log, 10000);
        }
        // 3초 후 재연결 시도
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('청산 데이터 WebSocket 오류:', error);
      };
      
      wsRef.current = ws;
    } catch (err) {
      console.error('WebSocket 연결 실패:', err);
    }
  }, [fetchData, normalizeLiquidationData, logOnce]);

  // refetch 함수
  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  // 초기화 및 정리
  useEffect(() => {
    // 초기 데이터 로드
    fetchData();
    
    // WebSocket 연결
    connectWebSocket();
    
    // 60초마다 polling (차트 안정성을 위해 간격 증가)
    intervalRef.current = setInterval(fetchData, 60000);
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [fetchData, connectWebSocket]);

  return {
    summary,
    trend,
    loading,
    error,
    refetch,
    lastUpdate
  };
};