// frontend/src/components/PriceCell.js
import React, { useState, useEffect, useRef } from 'react';
import { formatPrice } from '../utils/formatters';

const PriceCell = ({ price, currency = '₩' }) => {
  const [flashStyle, setFlashStyle] = useState('');
  const prevPriceRef = useRef(price);

  useEffect(() => {
    const currentPrice = price;
    const prevPrice = prevPriceRef.current;

    if (currentPrice !== null && prevPrice !== null && currentPrice !== prevPrice) {
      const style = currentPrice > prevPrice ? 'text-red-500 font-bold' : 'text-blue-500 font-bold';
      setFlashStyle(style);

      const timer = setTimeout(() => {
        setFlashStyle('');
      }, 500); // 500ms 후 스타일 제거

      prevPriceRef.current = currentPrice;
      return () => clearTimeout(timer);
    } else {
      prevPriceRef.current = currentPrice;
    }
  }, [price]);

  return (
    <span className={`transition-all duration-300 ${flashStyle}`}>
      {formatPrice(price, currency)}
    </span>
  );
};

export default PriceCell;