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

  // 청산 데이터 정규화 함수
  const normalizeLiquidationData = useCallback((liqItem) => {
    // CEX API 필드 매핑 오류 교정
    // side: 'sell'/'buy', positionSide: 'long'/'short' 또는 다른 형식들
    
    let isLongLiquidation = false;
    let isShortLiquidation = false;
    
    if (liqItem.side && liqItem.positionSide) {
      // Binance 스타일: side + positionSide 조합
      isLongLiquidation = liqItem.side === 'sell' && liqItem.positionSide === 'long';
      isShortLiquidation = liqItem.side === 'buy' && liqItem.positionSide === 'short';
    } else if (liqItem.side) {
      // 단순 side 필드만 있는 경우의 추론 로직
      // 일반적으로 'long' = 롱 청산, 'short' = 숏 청산
      isLongLiquidation = liqItem.side === 'long' || liqItem.side === 'sell';
      isShortLiquidation = liqItem.side === 'short' || liqItem.side === 'buy';
    } else {
      // 백엔드에서 이미 정규화된 데이터인 경우
      isLongLiquidation = Boolean(liqItem.long_volume || liqItem.longVolume);
      isShortLiquidation = Boolean(liqItem.short_volume || liqItem.shortVolume);
    }
    
    const usdAmount = liqItem.usd || liqItem.amount || liqItem.volume || 0;
    
    return {
      ...liqItem,
      longLiq: isLongLiquidation ? usdAmount : 0,
      shortLiq: isShortLiquidation ? usdAmount : 0,
      // 디버깅용 필드
      _original: { side: liqItem.side, positionSide: liqItem.positionSide }
    };
  }, []);

  // 요약 데이터 변환 함수 (정규화 적용)
  const transformSummaryData = useCallback((data) => {
    const exchangeSummary = {};
    
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
            
            // 디버깅 로그 (방향 정확성 테스트용)
            if (process.env.NODE_ENV === 'development' && normalized._original) {
              console.log(`[${exchange}] 원본:`, normalized._original, '→ 정규화:', {
                longLiq: normalized.longLiq,
                shortLiq: normalized.shortLiq
              });
            }
          });
        }
      });
    }
    
    return Object.entries(exchangeSummary)
      .map(([exchange, data]) => ({
        exchange: exchange.charAt(0).toUpperCase() + exchange.slice(1).toLowerCase(),
        long: data.long,
        short: data.short
      }))
      .sort((a, b) => (b.long + b.short) - (a.long + a.short))
      .slice(0, 5);
  }, [normalizeLiquidationData]);

  // 거래소별 트렌드 데이터 생성 (5분 누적)
  const generateTrendByExchange = useCallback((summaryData) => {
    // 실제 요약 데이터가 있으면 그것을 기반으로, 없으면 더미 데이터
    const exchanges = summaryData.length > 0 
      ? summaryData.slice(0, 5).map(item => item.exchange)
      : ['Binance', 'Bybit', 'Okx', 'Bitget', 'Bitmex'];
    
    return exchanges.map(exchange => {
      // 실제 데이터에서 해당 거래소 찾기
      const actualData = summaryData.find(item => item.exchange === exchange);
      
      if (actualData) {
        return {
          exchange: exchange.length > 6 ? exchange.slice(0, 6) : exchange, // 6자 제한
          long: actualData.long / 1000000, // M 단위로 변환
          short: actualData.short / 1000000
        };
      } else {
        // 더미 데이터
        return {
          exchange: exchange.length > 6 ? exchange.slice(0, 6) : exchange,
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
        console.log('청산 데이터 WebSocket 연결됨');
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'liquidation_update' && data.data) {
            // 실시간 청산 데이터 정규화 및 디버깅
            const normalized = normalizeLiquidationData(data.data);
            
            // 개발 모드에서 방향 정확성 테스트 로그
            if (process.env.NODE_ENV === 'development') {
              console.log(`🔄 [${data.exchange}] 실시간 청산:`, {
                원본: data.data,
                정규화: { longLiq: normalized.longLiq, shortLiq: normalized.shortLiq },
                시간: new Date().toLocaleTimeString()
              });
              
              // 가격 움직임과 청산 방향 일치성 체크 힌트
              if (normalized.longLiq > 0) {
                console.log('📉 롱 청산 발생 - 가격 하락 추세일 가능성');
              }
              if (normalized.shortLiq > 0) {
                console.log('📈 숏 청산 발생 - 가격 상승 추세일 가능성');
              }
            }
            
            // 실시간 업데이트 (전체 데이터 다시 fetch)
            fetchData();
          }
        } catch (err) {
          console.error('WebSocket message parse error:', err);
        }
      };
      
      ws.onclose = () => {
        console.log('청산 데이터 WebSocket 연결 해제됨');
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
  }, [fetchData, normalizeLiquidationData]);

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
    
    // 15초마다 polling
    intervalRef.current = setInterval(fetchData, 15000);
    
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