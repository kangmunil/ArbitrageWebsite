// frontend/src/components/PriceCell.js
import React, { useRef, memo } from 'react';
import { formatPrice } from '../utils/formatters';
import './PriceCell.css';

const PriceCell = ({ price, currency = '₩' }) => {
  // 이전 가격을 기억하기 위한 ref
  const prevPriceRef = useRef(price);
  
  // 가격 변동 방향 계산
  const getPriceChangeClass = () => {
    const prevPrice = prevPriceRef.current;
    
    if (price !== null && prevPrice !== null && price !== prevPrice) {
      if (price > prevPrice) {
        prevPriceRef.current = price;
        return 'price-up'; // 상승: 초록색
      } else if (price < prevPrice) {
        prevPriceRef.current = price;
        return 'price-down'; // 하락: 빨간색
      }
    }
    
    // 첫 렌더링이거나 변화가 없으면 이전 가격 저장 후 기본 클래스
    prevPriceRef.current = price;
    return '';
  };

  return (
    <span className={`price-cell ${getPriceChangeClass()}`}>
      {formatPrice(price, currency)}
    </span>
  );
};

export default memo(PriceCell);