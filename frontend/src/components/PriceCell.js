// frontend/src/components/PriceCell.js
import React, { useState, useEffect, useRef, memo } from 'react';
import './PriceCell.css';

const PriceCell = ({ price, currency, formatPrice }) => {
  // 이전 가격을 기억하기 위한 ref
  const prevPriceRef = useRef(price);
  // 깜빡임 효과를 위한 CSS 클래스를 관리하는 state
  const [flashClass, setFlashClass] = useState('');

  useEffect(() => {
    // 컴포넌트가 처음 마운트될 때 prevPriceRef.current를 초기 price로 설정
    // 이렇게 하면 첫 렌더링 시에는 애니메이션이 발생하지 않음
    if (prevPriceRef.current === undefined) {
      prevPriceRef.current = price;
      return; // 첫 렌더링에서는 애니메이션 스킵
    }

    const prevPrice = prevPriceRef.current;

    // 이전 가격과 현재 가격을 비교하여 CSS 클래스 설정
    // price가 null이 아닌 경우에만 비교 및 애니메이션 적용
    if (price !== null && prevPrice !== null && price !== prevPrice) {
      if (price > prevPrice) {
        setFlashClass('flash-up'); // 가격 상승
      } else if (price < prevPrice) {
        setFlashClass('flash-down'); // 가격 하락
      }
      // 0.5초 후에 깜빡임 효과 클래스를 제거
      const timer = setTimeout(() => {
        setFlashClass('');
      }, 500);
      return () => clearTimeout(timer); // 타이머 정리
    }

    // 다음 비교를 위해 현재 가격을 ref에 저장 (null 값도 저장하여 다음 비교에 사용)
    prevPriceRef.current = price;

  }, [price]); // 'price' prop이 변경될 때마다 이 effect를 실행

  return (
    // 적용된 flashClass에 따라 배경색이 변함
    <span className={`price-cell ${flashClass}`}>
      {formatPrice(price, currency)}
    </span>
  );
};

export default memo(PriceCell);