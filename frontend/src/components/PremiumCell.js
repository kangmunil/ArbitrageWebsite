import React, { useState, useEffect, useRef } from 'react';

/**
 * 김프 변화를 시각적으로 표시하는 셀 컴포넌트
 */
const PremiumCell = ({ premium }) => {
  const [isFlashing, setIsFlashing] = useState(false);
  const [premiumChange, setPremiumChange] = useState(null);
  const prevPremiumRef = useRef(premium);
  
  useEffect(() => {
    if (prevPremiumRef.current !== premium && prevPremiumRef.current !== null) {
      const change = premium > prevPremiumRef.current ? 'up' : 'down';
      setPremiumChange(change);
      setIsFlashing(true);
      
      // 플래시 효과 제거
      const timer = setTimeout(() => {
        setIsFlashing(false);
        setPremiumChange(null);
      }, 1200);
      
      prevPremiumRef.current = premium;
      return () => clearTimeout(timer);
    }
    prevPremiumRef.current = premium;
  }, [premium]);
  
  const getFlashClass = () => {
    if (!isFlashing) return '';
    return premiumChange === 'up' 
      ? 'bg-emerald-500/20 border border-emerald-500/50' 
      : 'bg-red-500/20 border border-red-500/50';
  };
  
  const getPremiumChangeIcon = () => {
    if (!premiumChange) return null;
    return premiumChange === 'up' ? '📈' : '📉';
  };
  
  const getPremiumColor = () => {
    if (premium > 0) return 'text-emerald-400';
    if (premium < 0) return 'text-red-400';
    return 'text-gray-400';
  };
  
  const getIntensityIcon = () => {
    if (premium === null) return '';
    const abs = Math.abs(premium);
    if (abs > 5) return '🔥';
    if (abs > 2) return '⚡';
    if (abs > 1) return '💫';
    return '';
  };
  
  return (
    <span className={`transition-all duration-1200 px-1 rounded ${getFlashClass()} ${getPremiumColor()}`}>
      {premium !== null ? `${premium > 0 ? '+' : ''}${premium.toFixed(2)}%` : 'N/A'}
      {getPremiumChangeIcon() && (
        <span className="ml-1 text-xs opacity-75">
          {getPremiumChangeIcon()}
        </span>
      )}
      {getIntensityIcon() && (
        <span className="ml-1 text-xs opacity-60">
          {getIntensityIcon()}
        </span>
      )}
    </span>
  );
};

export default PremiumCell;