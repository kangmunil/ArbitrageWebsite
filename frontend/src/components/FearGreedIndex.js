import React, { useState, useEffect, useMemo, useCallback } from 'react';
import GaugeChart from 'react-gauge-chart';

/**
 * 암호화폐 공포/탐욕 지수 컴포넌트.
 * 
 * Alternative.me API를 통해 암호화폐 시장의 감정 지수를 가져와
 * 게이지 차트로 시각화합니다. 0~100 점수로 표시됩니다.
 * 
 * @returns {JSX.Element} 공포탐욕 지수 게이지 UI
 */
const FearGreedIndex = React.memo(() => {
  const [indexData, setIndexData] = useState(null); // 공포탐욕 지수 데이터
  const [loading, setLoading] = useState(true); // 데이터 로딩 상태
  const [error, setError] = useState(null); // 에러 상태

  const fetchFearGreedIndex = useCallback(async () => {
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
  }, []);

  // Gauge Chart 설정 - useMemo로 메모이제이션하여 불필요한 재렌더링 방지
  const gaugeChartProps = useMemo(() => {
    const fixedValue = indexData ? indexData.value : 50; // 기본값 50으로 고정
    return {
      id: "fear-greed-gauge-stable",
      nrOfLevels: 5, // 5단계 (Extreme Fear, Fear, Neutral, Greed, Extreme Greed)
      arcsLength: [0.2, 0.2, 0.2, 0.2, 0.2], // 각 구간의 비율 (총합 1)
      colors: ['#FF0000', '#FFA500', '#FFFF00', '#90EE90', '#008000'], // 빨강, 주황, 노랑, 연두, 초록
      arcWidth: 0.3,
      percent: fixedValue / 100, // 0-100 값을 0-1로 변환
      textColor: '#FFFFFF', // 텍스트 색상
      needleColor: '#FFFFFF', // 바늘 색상
      needleBaseColor: '#FFFFFF', // 바늘 베이스 색상
      hideText: false, // 값 텍스트 표시
      formatTextValue: () => `${Math.round(fixedValue)}%`, // 고정된 값 사용
      animate: false, // 애니메이션 비활성화
      animateDuration: 0, // 애니메이션 시간 0으로 설정
      animDelay: 0, // 애니메이션 지연 시간 0
      cornerRadius: 0, // 모서리 둥글기 제거로 렌더링 안정화
      style: { 
        width: '240px', 
        height: '140px'
      } // 크기 고정
    };
  }, [indexData]);

  useEffect(() => {
    // 초기 로드
    fetchFearGreedIndex();
    
    // 12시간마다 업데이트 (43200000ms = 12시간)
    const interval = setInterval(fetchFearGreedIndex, 43200000);
    
    return () => clearInterval(interval);
  }, [fetchFearGreedIndex]);

  if (loading) {
    return <p>Loading Fear & Greed Index...</p>;
  }

  if (error) {
    return <p>Error loading Fear & Greed Index: {error.message}</p>;
  }
  if (!indexData) {
    return <p>No Fear & Greed Index data available.</p>;
  }

  return (
    <div style={{ 
      width: '100%', // App-section의 전체 너비 사용
      maxWidth: '320px', // 최대 너비 320px로 제한
      margin: '0 auto', // 중앙 정렬
      padding: '0', // App-section에서 이미 padding 적용되므로 제거
      border: 'none', // App-section에서 이미 border 적용되므로 제거
      borderRadius: '0', // App-section에서 이미 적용되므로 제거
      backgroundColor: 'transparent', // App-section에서 이미 배경색 적용되므로 투명
      height: '100%', // App-section의 높이에 맞춤
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'space-between'
    }}>
      <h3 style={{ margin: '0 0 10px 0' }}>Fear & Greed Index</h3>
      <div style={{ 
        width: '240px', 
        height: '140px', // 게이지 높이에 맞춰 축소
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        minWidth: '240px', // 최소 너비 고정
        minHeight: '140px', // 최소 높이 고정
        maxWidth: '240px', // 최대 너비 고정
        maxHeight: '140px', // 최대 높이 고정
        overflow: 'hidden', // 넘침 방지
        position: 'relative' // 위치 고정
      }}>
        <div style={{
          width: '100%',
          height: '100%',
          position: 'absolute',
          top: 0,
          left: 0
        }}>
          <GaugeChart key="fear-greed-gauge-stable" {...gaugeChartProps} />
        </div>
      </div>
      <p style={{ margin: '5px 0 0 0', fontSize: '12px', opacity: '0.8' }}>
        {new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'numeric', day: 'numeric' })}
      </p>
    </div>
  );
});

FearGreedIndex.displayName = 'FearGreedIndex';

export default FearGreedIndex;
