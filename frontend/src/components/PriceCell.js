import { useRef, useEffect } from 'react';

/**
 * 가격 변화를 시각적으로 표시하는 셀 컴포넌트 (직접 DOM 조작 방식)
 */
const PriceCell = ({ price, currency = '₩', formatPrice }) => {
  const spanRef = useRef(null);
  const prevPriceRef = useRef(null);
  const animationTimeoutRef = useRef(null);
  
  useEffect(() => {
    if (!spanRef.current) return;
    
    const currentPrice = price;
    const prevPrice = prevPriceRef.current;
    
    // 디버그: 모든 렌더링 추적
    console.log(`🔍 [PriceCell] 렌더링: price=${currentPrice}, prev=${prevPrice}, currency=${currency}`);
    
    // 첫 번째 렌더링이거나 가격이 null인 경우
    if (prevPrice === null || currentPrice === null) {
      console.log(`🔍 [PriceCell] 초기 설정: ${currentPrice} ${currency}`);
      prevPriceRef.current = currentPrice;
      spanRef.current.textContent = currentPrice ? formatPrice(currentPrice, currency) : 'N/A';
      return;
    }
    
    // 가격 변화가 있는 경우
    if (prevPrice !== currentPrice) {
      const change = currentPrice > prevPrice ? 'up' : 'down';
      
      console.log(`💰 [PriceCell] ${currency === '₩' ? '국내' : '해외'} 가격 변화: ${prevPrice} → ${currentPrice} (${change === 'up' ? '상승' : '하락'})`);
      
      // 즉시 DOM 업데이트
      spanRef.current.textContent = formatPrice(currentPrice, currency);
      
      // 기존 애니메이션 클래스 제거
      spanRef.current.className = 'price-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md';
      
      // 애니메이션 클래스 추가
      const flashClass = change === 'up' 
        ? 'price-cell-flash-up bg-green-400/60 border-2 border-green-300 shadow-xl shadow-green-400/50 scale-105 text-white font-bold'
        : 'price-cell-flash-down bg-red-400/60 border-2 border-red-300 shadow-xl shadow-red-400/50 scale-105 text-white font-bold';
      
      setTimeout(() => {
        spanRef.current.className = `price-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md ${flashClass}`;
      }, 10);
      
      // 기존 타이머 클리어
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
      
      // 1.5초 후 원래 상태로 복구
      animationTimeoutRef.current = setTimeout(() => {
        if (spanRef.current) {
          spanRef.current.className = 'price-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md';
        }
      }, 1500);
      
      prevPriceRef.current = currentPrice;
    } else {
      // 가격 변화가 없어도 텍스트 업데이트
      spanRef.current.textContent = formatPrice(currentPrice, currency);
    }
  }, [price, currency, formatPrice]);
  
  // 컴포넌트 언마운트 시 타이머 정리
  useEffect(() => {
    return () => {
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
    };
  }, []);
  
  return (
    <span 
      ref={spanRef}
      className="price-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md"
    >
      {price ? formatPrice(price, currency) : 'N/A'}
    </span>
  );
};

export default PriceCell;