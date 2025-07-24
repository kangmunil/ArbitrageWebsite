/**
 * 청산 데이터 차트 컴포넌트.
 * 
 * 여러 거래소의 청산 데이터를 Stacked Column 형태로 시각화합니다.
 * Long(녹색)과 Short(빨강)를 분리하여 1분 버킷마다 표시합니다.
 * 
 * @returns {JSX.Element} 청산 차트 UI
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

function LiquidationChart() {
  const [chartData, setChartData] = useState(null); // Chart.js에 사용될 차트 데이터
  const [loading, setLoading] = useState(true); // 데이터 로딩 상태
  const [error, setError] = useState(null); // 에러 상태
  const [selectedExchanges, setSelectedExchanges] = useState({
    binance: true,
    bybit: true,
    okx: true,
    bitmex: true,
    bitget: true,
    hyperliquid: true
  }); // 표시할 거래소 선택 상태
  const [recentLiquidations, setRecentLiquidations] = useState([]); // 최근 청산 스트림 (최근 20개)
  const [timelineData, setTimelineData] = useState([]); // 5분 간격 누적 데이터 (최근 2시간)
  
  // 거래소별 색상 설정
  const exchangeColors = {
    binance: { long: '#10B981', short: '#EF4444' }, // 초록/빨강
    bybit: { long: '#34D399', short: '#F87171' },
    okx: { long: '#6EE7B7', short: '#FCA5A5' },
    bitmex: { long: '#A7F3D0', short: '#FEB2B2' },
    bitget: { long: '#D1FAE5', short: '#FECACA' },
    hyperliquid: { long: '#059669', short: '#DC2626' }
  };

  useEffect(() => {
    const cleanupWs = connectWebSocket();
    
    // 5분마다 타임라인 데이터 정리 (오래된 데이터 제거)
    const cleanupInterval = setInterval(() => {
      const twoHoursAgo = Date.now() - (2 * 60 * 60 * 1000);
      setTimelineData(prev => prev.filter(item => item.timestamp >= twoHoursAgo));
    }, 5 * 60 * 1000); // 5분마다
    
    return () => {
      cleanupWs();
      clearInterval(cleanupInterval);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  useEffect(() => {
    // 선택된 거래소가 변경되면 차트 데이터 업데이트
    if (chartData) {
      processTimelineChart();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedExchanges, timelineData]);

  /**
   * WebSocket 연결을 설정하여 실시간 청산 데이터를 수신합니다.
   */
  const connectWebSocket = () => {
    let ws;
    
    const connect = () => {
      // Firefox 전용 처리 - 먼저 127.0.0.1 시도
      const isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;
      let wsUrl = isFirefox ? 'ws://127.0.0.1:8000/ws/liquidations' : 'ws://localhost:8000/ws/liquidations';
      console.log(`Connecting to liquidation WebSocket: ${wsUrl} (Firefox: ${isFirefox})`);
      
      ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('청산 데이터 WebSocket 연결됨');
        setError(null);
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === 'liquidation_initial' && message.data) {
            // 초기 데이터 로드
            console.log('초기 청산 데이터 수신:', message.data.length, '개 아이템');
            message.data.forEach(item => updateTimelineData(item));
            setLoading(false);
          } else if (message.type === 'liquidation_update' && message.data) {
            // 실시간 업데이트
            console.log('실시간 청산 데이터 업데이트:', message.data);
            updateChartWithNewData(message.data);
          }
        } catch (err) {
          console.error('WebSocket 메시지 파싱 오류:', err);
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket 오류:', error);
        setError('WebSocket 연결 오류. 데이터를 가져올 수 없습니다.');
      };
      
      ws.onclose = () => {
        console.log('청산 데이터 WebSocket 연결 끄어짐. 3초 후 재연결 시도...');
        setTimeout(connect, 3000);
      };
    };
    
    connect();
    
    // cleanup 함수 반환
    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  };
  
  /**
   * 새로운 청산 데이터 처리 (실시간 스트림 + 타임라인 업데이트)
   */
  const updateChartWithNewData = (newDataPoint) => {
    if (!newDataPoint || !newDataPoint.exchanges) return;
    
    // 1. 실시간 청산 스트림에 추가 (최근 20개만 유지)
    if (newDataPoint.exchanges) {
      Object.entries(newDataPoint.exchanges).forEach(([exchange, data]) => {
        if (data && (data.long_volume > 0 || data.short_volume > 0)) {
          const liquidationEvent = {
            id: Date.now() + Math.random(),
            timestamp: newDataPoint.timestamp || Date.now(),
            exchange,
            longVolume: data.long_volume || 0,
            shortVolume: data.short_volume || 0,
            longCount: data.long_count || 0,
            shortCount: data.short_count || 0
          };
          
          setRecentLiquidations(prev => {
            const updated = [liquidationEvent, ...prev];
            return updated.slice(0, 20); // 최근 20개만 유지
          });
        }
      });
    }
    
    // 2. 5분 간격 타임라인 데이터 업데이트
    updateTimelineData(newDataPoint);
  };

  /**
   * 5분 간격 타임라인 데이터 업데이트
   */
  const updateTimelineData = (newDataPoint) => {
    const timestamp = newDataPoint.timestamp || Date.now();
    // 5분 간격으로 반올림 (예: 14:32 -> 14:30, 14:37 -> 14:35)
    const fiveMinuteSlot = Math.floor(timestamp / (5 * 60 * 1000)) * (5 * 60 * 1000);
    
    setTimelineData(prev => {
      const existingSlotIndex = prev.findIndex(item => item.timestamp === fiveMinuteSlot);
      
      if (existingSlotIndex >= 0) {
        // 기존 슬롯 업데이트
        const updated = [...prev];
        const slot = { ...updated[existingSlotIndex] };
        
        Object.entries(newDataPoint.exchanges).forEach(([exchange, data]) => {
          if (!slot.exchanges[exchange]) {
            slot.exchanges[exchange] = { long: 0, short: 0, count: 0 };
          }
          slot.exchanges[exchange].long += data.long_volume || 0;
          slot.exchanges[exchange].short += data.short_volume || 0;
          slot.exchanges[exchange].count += (data.long_count || 0) + (data.short_count || 0);
        });
        
        updated[existingSlotIndex] = slot;
        return updated;
      } else {
        // 새로운 슬롯 생성
        const newSlot = {
          timestamp: fiveMinuteSlot,
          exchanges: {}
        };
        
        Object.entries(newDataPoint.exchanges).forEach(([exchange, data]) => {
          newSlot.exchanges[exchange] = {
            long: data.long_volume || 0,
            short: data.short_volume || 0,
            count: (data.long_count || 0) + (data.short_count || 0)
          };
        });
        
        const updated = [...prev, newSlot];
        // 시간순 정렬 및 최근 2시간만 유지
        const twoHoursAgo = Date.now() - (2 * 60 * 60 * 1000);
        return updated
          .filter(item => item.timestamp >= twoHoursAgo)
          .sort((a, b) => a.timestamp - b.timestamp);
      }
    });
    
    // 차트 업데이트
    processTimelineChart();
  };
  
  /**
   * 데모 청산 데이터를 생성합니다.
   */
  const generateDemoData = () => {
    const demoData = [];
    const now = Date.now();
    const exchanges = ['binance', 'bybit', 'okx', 'bitmex', 'bitget', 'hyperliquid'];
    
    for (let i = 59; i >= 0; i--) {
      const timestamp = now - (i * 60 * 1000); // 1분씩 뒤로
      const exchangesData = {};
      
      exchanges.forEach(exchange => {
        exchangesData[exchange] = {
          long_volume: Math.random() * 1000000 + 100000, // 10만 ~ 110만 USDT
          short_volume: Math.random() * 1000000 + 100000,
          long_count: Math.floor(Math.random() * 50) + 5,
          short_count: Math.floor(Math.random() * 50) + 5
        };
      });
      
      demoData.push({
        timestamp,
        exchanges: exchangesData,
        total_long: Object.values(exchangesData).reduce((sum, ex) => sum + ex.long_volume, 0),
        total_short: Object.values(exchangesData).reduce((sum, ex) => sum + ex.short_volume, 0)
      });
    }
    
    return demoData;
  };

  /**
   * 타임라인 차트 처리 (5분 간격 누적 차트)
   */
  const processTimelineChart = () => {
    if (timelineData.length === 0) return;

    // 시간 라벨 생성 (HH:MM 형식)
    const labels = timelineData.map(item => {
      const date = new Date(item.timestamp);
      return date.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
      });
    });

    const exchanges = ['binance', 'bybit', 'okx', 'bitmex', 'bitget', 'hyperliquid'];
    const datasets = [];

    // 거래소별 Long 데이터셋
    exchanges.forEach(exchange => {
      if (!selectedExchanges[exchange]) return;
      
      datasets.push(
        // Long 포지션
        {
          label: `${exchange.toUpperCase()} Long`,
          data: timelineData.map(item => {
            const exchangeData = item.exchanges[exchange];
            return exchangeData ? exchangeData.long / 1000 : 0; // K 단위
          }),
          backgroundColor: exchangeColors[exchange].long,
          borderColor: exchangeColors[exchange].long,
          borderWidth: 1,
          stack: 'positive',
        },
        // Short 포지션 (음수)
        {
          label: `${exchange.toUpperCase()} Short`,
          data: timelineData.map(item => {
            const exchangeData = item.exchanges[exchange];
            return exchangeData ? -(exchangeData.short / 1000) : 0; // K 단위, 음수
          }),
          backgroundColor: exchangeColors[exchange].short,
          borderColor: exchangeColors[exchange].short,
          borderWidth: 1,
          stack: 'negative',
        }
      );
    });

    setChartData({
      labels,
      datasets
    });
  };

  /**
   * 거래소 선택 토글 핸들러
   */
  const handleExchangeToggle = (exchange) => {
    setSelectedExchanges(prev => ({
      ...prev,
      [exchange]: !prev[exchange]
    }));
  };

  // 차트 옵션 설정 (누적 바 차트)
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          filter: (legendItem, data) => {
            // Long/Short 구분을 위해 범례 필터링
            return legendItem.text.includes('Long') || legendItem.text.includes('Short');
          }
        }
      },
      title: {
        display: true,
        text: '5분 간격 누적 청산량 (최근 2시간)',
        font: {
          size: 16,
          weight: 'bold'
        }
      },
      tooltip: {
        callbacks: {
          title: (tooltipItems) => {
            return `시간: ${tooltipItems[0].label}`;
          },
          label: (context) => {
            const value = Math.abs(context.parsed.y);
            const label = context.dataset.label;
            return `${label}: ${value.toLocaleString()}K USDT`;
          }
        }
      }
    },
    scales: {
      x: {
        stacked: true,
        title: {
          display: true,
          text: '시간'
        }
      },
      y: {
        stacked: true,
        title: {
          display: true,
          text: '청산량 (K USDT)'
        },
        ticks: {
          callback: function(value) {
            return Math.abs(value).toLocaleString() + 'K';
          }
        }
      }
    }
  };

  if (loading && !chartData) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>청산 데이터 로딩 중...</p>
      </div>
    );
  }

  if (error && !chartData) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: 'red' }}>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '15px', border: '1px solid #333', borderRadius: '8px', backgroundColor: '#1a1a1a', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 상단: 실시간 청산 스트림 */}
      <div style={{ flex: 1, minHeight: '200px', maxHeight: '300px', overflowY: 'auto', border: '1px solid #444', borderRadius: '6px', padding: '10px', backgroundColor: '#2a2a2a' }}>
        <h3 style={{ color: 'white', marginBottom: '10px', textAlign: 'center' }}>실시간 청산 스트림 (최근 20개)</h3>
        {recentLiquidations.length === 0 ? (
          <p style={{ color: '#888', textAlign: 'center' }}>실시간 청산 데이터 대기 중...</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column-reverse' }}> {/* 최신 데이터가 아래로 오도록 */}
            {recentLiquidations.map((event) => (
              <div key={event.id} style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center', 
                padding: '8px', 
                borderBottom: '1px solid #333',
                backgroundColor: event.longVolume > event.shortVolume ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', // Long/Short에 따라 배경색
                animation: 'fadeIn 0.5s ease-out'
              }}>
                <span style={{ color: '#bbb', fontSize: '12px', flex: 1 }}>
                  {new Date(event.timestamp).toLocaleTimeString('ko-KR')}
                </span>
                <span style={{ color: '#fff', fontWeight: 'bold', flex: 1 }}>
                  {event.exchange.toUpperCase()}
                </span>
                <span style={{ color: '#10B981', flex: 1, textAlign: 'right' }}>
                  L: {event.longVolume > 0 ? `${(event.longVolume / 1000).toFixed(1)}K` : '-'}
                </span>
                <span style={{ color: '#EF4444', flex: 1, textAlign: 'right' }}>
                  S: {event.shortVolume > 0 ? `${(event.shortVolume / 1000).toFixed(1)}K` : '-'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 하단: 5분 간격 누적 바 차트 */}
      <div style={{ flex: 2, height: '400px', position: 'relative' }}>
        {chartData && <Bar data={chartData} options={options} />}
      </div>
      
      {/* 거래소 선택 체크박스 */}
      <div style={{ marginTop: '15px' }}>
        <div style={{ color: 'white', fontSize: '14px', marginBottom: '8px', fontWeight: 'bold' }}>
          거래소 선택:
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          {Object.keys(selectedExchanges).map(exchange => (
            <label key={exchange} style={{ color: 'white', fontSize: '13px', display: 'flex', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={selectedExchanges[exchange]}
                onChange={() => handleExchangeToggle(exchange)}
                style={{ marginRight: '5px' }}
              />
              {exchange.toUpperCase()}
            </label>
          ))}
        </div>
      </div>
      
      {error && (
        <div style={{ marginTop: '10px', fontSize: '12px', color: '#FFA500' }}>
          ⚠️ 실시간 데이터 연결 실패. 데모 데이터를 표시합니다.
        </div>
      )}
    </div>
  );
}

export default LiquidationChart;
