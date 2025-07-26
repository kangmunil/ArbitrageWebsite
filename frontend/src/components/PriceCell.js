import React, { useState, useEffect, useRef } from 'react';

/**
 * 가격 변화를 시각적으로 표시하는 셀 컴포넌트
 */
const PriceCell = ({ price, currency = '₩', formatPrice }) => {
  const [isFlashing, setIsFlashing] = useState(false);
  const [priceChange, setPriceChange] = useState(null);
  const prevPriceRef = useRef(price);
  
  useEffect(() => {
    if (prevPriceRef.current !== price && prevPriceRef.current !== null) {
      const change = price > prevPriceRef.current ? 'up' : 'down';
      setPriceChange(change);
      setIsFlashing(true);
      
      // 플래시 효과 제거
      const timer = setTimeout(() => {
        setIsFlashing(false);
        setPriceChange(null);
      }, 1000);
      
      prevPriceRef.current = price;
      return () => clearTimeout(timer);
    }
    prevPriceRef.current = price;
  }, [price]);
  
  const getFlashClass = () => {
    if (!isFlashing) return '';
    return priceChange === 'up' 
      ? 'bg-green-500/20 border border-green-500/50' 
      : 'bg-red-500/20 border border-red-500/50';
  };
  
  const getPriceChangeIcon = () => {
    if (!priceChange) return null;
    return priceChange === 'up' ? '↗️' : '↘️';
  };
  
  return (
    <span className={`transition-all duration-1000 px-1 rounded ${getFlashClass()}`}>
      {price ? formatPrice(price, currency) : 'N/A'}
      {getPriceChangeIcon() && (
        <span className="ml-1 text-xs opacity-75">
          {getPriceChangeIcon()}
        </span>
      )}
    </span>
  );
};

export default PriceCell;