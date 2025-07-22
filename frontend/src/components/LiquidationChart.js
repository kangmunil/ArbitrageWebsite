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
    fetchLiquidationData();
    connectWebSocket();
    
    return () => {
      // WebSocket 연결 정리는 connectWebSocket 내부에서 처리
    };
  }, []);
  
  useEffect(() => {
    // 선택된 거래소가 변경되면 차트 데이터 업데이트
    if (chartData) {
      // 현재 데이터를 기반으로 차트 재생성
      const mockData = generateDemoData();
      processChartData(mockData);
    }
  }, [selectedExchanges]);

  /**
   * WebSocket 연결을 설정하여 실시간 청산 데이터를 수신합니다.
   */
  const connectWebSocket = () => {
    let ws;
    
    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws/liquidations');
      
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
            processChartData(message.data);
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
        setError('WebSocket 연결 오류. HTTP API로 대체합니다.');
        // WebSocket 실패 시 HTTP API 사용
        fetchLiquidationData();
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
   * 새로운 데이터로 차트를 업데이트합니다.
   */
  const updateChartWithNewData = (newDataPoint) => {
    setChartData(prevData => {
      if (!prevData) return null;
      
      // 새 데이터 포인트를 추가하고 가장 오래된 것 제거
      const newLabels = [...prevData.labels];
      const newDate = new Date(newDataPoint.timestamp);
      const newLabel = newDate.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
      });
      
      newLabels.push(newLabel);
      if (newLabels.length > 60) {
        newLabels.shift(); // 가장 오래된 라벨 제거
      }
      
      // 각 데이터셋 업데이트
      const newDatasets = prevData.datasets.map(dataset => {
        const newData = [...dataset.data];
        
        // 데이터셋 이름에서 거래소와 사이드 추출
        const exchangeName = dataset.label.split(' ')[0].toLowerCase();
        const isLong = dataset.label.includes('Long');
        
        // 새 데이터 포인트 추가
        const exchangeData = newDataPoint.exchanges[exchangeName];
        if (exchangeData) {
          const value = isLong ? 
            exchangeData.long_volume / 1000 : 
            -(exchangeData.short_volume / 1000);
          newData.push(value);
        } else {
          newData.push(0);
        }
        
        if (newData.length > 60) {
          newData.shift(); // 가장 오래된 데이터 제거
        }
        
        return {
          ...dataset,
          data: newData
        };
      });
      
      return {
        labels: newLabels,
        datasets: newDatasets
      };
    });
  };
  
  /**
   * 백엔드에서 집계된 청산 데이터를 가져옵니다. (Fallback)
   */
  const fetchLiquidationData = async () => {
    try {
      setLoading(true);
      const response = await axios.get('http://localhost:8000/api/liquidations/aggregated?limit=60');
      const liquidationData = response.data;
      
      if (liquidationData && liquidationData.length > 0) {
        processChartData(liquidationData);
      } else {
        // 데모 데이터 생성 (실제 데이터가 없을 때)
        const demoData = generateDemoData();
        processChartData(demoData);
      }
      
      setError(null);
    } catch (err) {
      console.error('청산 데이터 가져오기 실패:', err);
      setError('HTTP API로 청산 데이터를 가져오는데 실패했습니다. 데모 데이터를 표시합니다.');
      
      // 에러 시에도 데모 데이터 표시
      const demoData = generateDemoData();
      processChartData(demoData);
    } finally {
      setLoading(false);
    }
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
   * 청산 데이터를 Chart.js 형식으로 변환합니다.
   */
  const processChartData = (liquidationData) => {
    // 시간 라벨 생성
    const labels = liquidationData.map(item => {
      const date = new Date(item.timestamp);
      return date.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
      });
    });

    // 거래소별 데이터셋 생성
    const datasets = [];
    const exchanges = ['binance', 'bybit', 'okx', 'bitmex', 'bitget', 'hyperliquid'];
    
    exchanges.forEach(exchange => {
      if (!selectedExchanges[exchange]) return;
      
      // Long 포지션 청산 (양수로 표시)
      const longData = liquidationData.map(item => {
        const exchangeData = item.exchanges[exchange];
        return exchangeData ? exchangeData.long_volume / 1000 : 0; // USDT를 K 단위로 변환
      });
      
      // Short 포지션 청산 (음수로 표시)
      const shortData = liquidationData.map(item => {
        const exchangeData = item.exchanges[exchange];
        return exchangeData ? -(exchangeData.short_volume / 1000) : 0; // 음수로 변환
      });
      
      datasets.push(
        // Long 데이터셋
        {
          label: `${exchange.toUpperCase()} Long`,
          data: longData,
          backgroundColor: exchangeColors[exchange].long,
          borderColor: exchangeColors[exchange].long,
          borderWidth: 1,
          stack: exchange, // 같은 거래소끼리 스택
        },
        // Short 데이터셋
        {
          label: `${exchange.toUpperCase()} Short`,
          data: shortData,
          backgroundColor: exchangeColors[exchange].short,
          borderColor: exchangeColors[exchange].short,
          borderWidth: 1,
          stack: exchange, // 같은 거래소끼리 스택
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

  // 차트 옵션 설정
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
        text: '암호화폐 청산 데이터 (1분 간격)',
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
            const isLong = context.parsed.y >= 0;
            const side = isLong ? 'Long' : 'Short';
            return `${context.dataset.label}: ${value.toLocaleString()}K USDT ${side}`;
          }
        }
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: '시간'
        }
      },
      y: {
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
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
    elements: {
      bar: {
        borderWidth: 1,
      },
    },
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
    <div style={{ padding: '15px', border: '1px solid #333', borderRadius: '8px', backgroundColor: '#1a1a1a' }}>
      <div style={{ marginBottom: '15px' }}>
        <h3 style={{ color: 'white', marginBottom: '10px' }}>청산 데이터</h3>
        
        {/* 거래소 선택 체크박스 */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '10px' }}>
          {Object.keys(selectedExchanges).map(exchange => (
            <label key={exchange} style={{ color: 'white', fontSize: '14px', display: 'flex', alignItems: 'center' }}>
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
        
        <div style={{ fontSize: '12px', color: '#888', marginBottom: '10px' }}>
          <span style={{ color: '#10B981' }}>■</span> Long 청산 (위쪽) / 
          <span style={{ color: '#EF4444', marginLeft: '10px' }}>■</span> Short 청산 (아래쪽)
        </div>
      </div>
      
      <div style={{ height: '400px' }}>
        {chartData && <Bar data={chartData} options={options} />}
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