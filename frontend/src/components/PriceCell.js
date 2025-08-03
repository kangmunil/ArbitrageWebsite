// frontend/src/components/PriceCell.js
import React, { useState, useEffect, useRef } from 'react';
import { formatPrice } from '../utils/formatters';
import './PriceCell.css';

/**
 * 가격 정보를 표시하는 셀 컴포넌트입니다.
 * 가격 변동 시 깜빡이는 효과를 줍니다.
 * @param {{price: number, currency: string}} props - 컴포넌트 props
 * @returns {JSX.Element} PriceCell 컴포넌트
 */
const PriceCell = ({ price, currency = '₩' }) => {
  const [flashStyle, setFlashStyle] = useState('');
  const prevPriceRef = useRef(null); // null로 초기화해서 첫 번째 가격도 감지
  const timerRef = useRef(null);

  useEffect(() => {
    const currentPrice = price;
    const prevPrice = prevPriceRef.current;

    // 이전 타이머 클리어
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    // 가격 변화 감지 (첫 번째 가격은 건너뛰고, 두 번째부터 비교)
    if (prevPrice !== null && currentPrice !== null && currentPrice !== prevPrice) {
      const style = currentPrice > prevPrice ? 'price-up' : 'price-down';
      setFlashStyle(style);

      timerRef.current = setTimeout(() => {
        setFlashStyle('');
        timerRef.current = null;
      }, 300);
    }
    
    // 이전 가격 업데이트
    prevPriceRef.current = currentPrice;

    // Cleanup function
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [price]);

  return (
    <span className={`price-cell ${flashStyle}`}>
      {formatPrice(price, currency)}
    </span>
  );
};

export default PriceCell;
