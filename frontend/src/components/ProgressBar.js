/**
 * 재사용 가능한 프로그레스 바 컴포넌트
 * 롱/숏 비율과 청산 비율 표시에 사용됩니다.
 */

import React from 'react';

const ProgressBar = ({ 
  longValue, 
  shortValue, 
  showPercentage = true, 
  height = 'h-3', 
  className = '',
  longColor = 'bg-green-500',
  shortColor = 'bg-red-500',
  animate = true
}) => {
  // 값 검증 및 기본값 설정
  const longPercent = Math.max(0, Math.min(100, longValue || 0));
  const shortPercent = Math.max(0, Math.min(100, shortValue || 0));
  
  // 총합이 100%가 되도록 정규화
  const total = longPercent + shortPercent;
  const normalizedLong = total > 0 ? (longPercent / total) * 100 : 50;
  const normalizedShort = total > 0 ? (shortPercent / total) * 100 : 50;

  // 애니메이션 클래스
  const animationClass = animate ? 'transition-all duration-500 ease-in-out' : '';

  return (
    <div className={`w-full ${className}`}>
      {/* 프로그레스 바 */}
      <div className={`w-full ${height} bg-gray-200 rounded-full overflow-hidden relative`}>
        {/* 롱 섹션 */}
        <div 
          className={`${longColor} ${height} ${animationClass} absolute left-0 top-0`}
          style={{ width: `${normalizedLong}%` }}
        />
        
        {/* 숏 섹션 */}
        <div 
          className={`${shortColor} ${height} ${animationClass} absolute right-0 top-0`}
          style={{ width: `${normalizedShort}%` }}
        />
      </div>

      {/* 퍼센트 라벨 */}
      {showPercentage && (
        <div className="flex justify-between text-xs text-gray-600 mt-1">
          <span className="flex items-center">
            <div className={`w-2 h-2 ${longColor} rounded-full mr-1`}></div>
            Long {Math.round(normalizedLong)}%
          </span>
          <span className="flex items-center">
            <div className={`w-2 h-2 ${shortColor} rounded-full mr-1`}></div>
            Short {Math.round(normalizedShort)}%
          </span>
        </div>
      )}
    </div>
  );
};

export default ProgressBar;