import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

/**
 * 비트코인 과거 가격 차트 컴포넌트.
 * 
 * Binance API를 통해 BTC의 과거 30일 가격 데이터를 가져와
 * Chart.js로 선 그래프로 시각화합니다.
 * 
 * @returns {JSX.Element} 가격 차트 UI
 */
function PriceChart() {
  const [chartData, setChartData] = useState(null); // Chart.js에 사용될 차트 데이터
  const [loading, setLoading] = useState(true); // 데이터 로딩 상태
  const [error, setError] = useState(null); // 에러 상태

  useEffect(() => {
    const fetchHistoricalData = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/historical_prices/btc');
        const data = response.data;

        const labels = data.map(item => new Date(item.timestamp).toLocaleDateString());
        const prices = data.map(item => item.close);

        setChartData({
          labels: labels,
          datasets: [
            {
              label: 'BTC Price (USD)',
              data: prices,
              borderColor: 'rgb(75, 192, 192)',
              tension: 0.1,
            },
          ],
        });
        setLoading(false);
      } catch (err) {
        console.error("Failed to fetch historical data:", err);
        setError("Failed to fetch historical data.");
        setLoading(false);
      }
    };

    fetchHistoricalData();
  }, []);

  if (loading) {
    return <p>Loading chart data...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Bitcoin Historical Price',
      },
    },
  };

  return (
    <div>
      {chartData && <Line data={chartData} options={options} />}
    </div>
  );
}

export default PriceChart;