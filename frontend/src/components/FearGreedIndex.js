import React, { useState, useEffect } from 'react';
import GaugeChart from 'react-gauge-chart';

/**
 * 암호화폐 공포/탐욕 지수 컴포넌트.
 * 
 * Alternative.me API를 통해 암호화폐 시장의 감정 지수를 가져와
 * 게이지 차트로 시각화합니다. 0~100 점수로 표시됩니다.
 * 
 * @returns {JSX.Element} 공포탐욕 지수 게이지 UI
 */
function FearGreedIndex() {
  const [indexData, setIndexData] = useState(null); // 공포탐욕 지수 데이터
  const [loading, setLoading] = useState(true); // 데이터 로딩 상태
  const [error, setError] = useState(null); // 에러 상태

  useEffect(() => {
    const fetchFearGreedIndex = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/fear_greed_index');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setIndexData(data);
      } catch (e) {
        console.error("Failed to fetch Fear & Greed Index:", e);
        setError(e);
      } finally {
        setLoading(false);
      }
    };

    fetchFearGreedIndex();
  }, []);

  if (loading) {
    return <p>Loading Fear & Greed Index...</p>;
  }

  if (error) {
    return <p>Error loading Fear & Greed Index: {error.message}</p>;
  }
  if (!indexData) {
    return <p>No Fear & Greed Index data available.</p>;
  }

  // Gauge Chart 설정
  const gaugeChartProps = {
    id: "gauge-chart",
    nrOfLevels: 5, // 5단계 (Extreme Fear, Fear, Neutral, Greed, Extreme Greed)
    arcsLength: [0.2, 0.2, 0.2, 0.2, 0.2], // 각 구간의 비율 (총합 1)
    colors: ['#FF0000', '#FFA500', '#FFFF00', '#90EE90', '#008000'], // 빨강, 주황, 노랑, 연두, 초록
    // colors: ['#EA4228', '#F5CD19', '#5BE12C'], // 예시 색상
    arcWidth: 0.3,
    percent: indexData.value / 100, // 0-100 값을 0-1로 변환
    textColor: '#FFFFFF', // 텍스트 색상
    needleColor: '#FFFFFF', // 바늘 색상
    needleBaseColor: '#FFFFFF', // 바늘 베이스 색상
    hideText: false, // 값 텍스트 표시
    formatTextValue: value => `${value}%`,
    animate: false, // 애니메이션 비활성화
  };

  return (
    <div style={{ padding: '15px', border: '1px solid #333', borderRadius: '8px', backgroundColor: '#1a1a1a' }}>
      <h3>Fear & Greed Index</h3>
      <GaugeChart {...gaugeChartProps} />
      <p>{new Date(parseInt(indexData.timestamp) * 1000).toLocaleDateString('ko-KR', { year: 'numeric', month: 'numeric', day: 'numeric' })}</p>
    </div>
  );
}

export default FearGreedIndex;
