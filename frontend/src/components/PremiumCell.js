import { useRef, useEffect, useCallback } from 'react';

/**
 * 김프 변화를 시각적으로 표시하는 셀 컴포넌트 (직접 DOM 조작 방식)
 */
const PremiumCell = ({ premium }) => {
  const spanRef = useRef(null);
  const prevPremiumRef = useRef(null);
  const animationTimeoutRef = useRef(null);
  
  // 컴포넌트 호출 추적 제거 (너무 많은 로그)
  
  // 프리미엄 색상 결정 함수
  const getPremiumColor = useCallback((premiumValue) => {
    if (premiumValue > 0) return 'text-emerald-400';
    if (premiumValue < 0) return 'text-red-400';
    return 'text-gray-400';
  }, []);
  
  useEffect(() => {
    if (!spanRef.current) return;
    
    const currentPremium = premium;
    const prevPremium = prevPremiumRef.current;
    
    // 렌더링 로그 제거 (스팸 방지)
    
    // 첫 번째 렌더링이거나 프리미엄이 null인 경우
    if (prevPremium === null || currentPremium === null) {
      prevPremiumRef.current = currentPremium;
      spanRef.current.textContent = currentPremium !== null ? `${currentPremium > 0 ? '+' : ''}${currentPremium.toFixed(2)}%` : 'N/A';
      // 초기 색상 설정
      if (currentPremium !== null) {
        spanRef.current.className = `premium-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md ${getPremiumColor(currentPremium)}`;
      }
      return;
    }
    
    // 프리미엄 변화가 있는 경우
    if (prevPremium !== currentPremium) {
      const change = currentPremium > prevPremium ? 'up' : 'down';
      
      console.log(`📈 [PremiumCell] 김프 변화: ${prevPremium.toFixed(2)}% → ${currentPremium.toFixed(2)}% (${change === 'up' ? '상승' : '하락'})`);
      
      // 즉시 DOM 업데이트
      spanRef.current.textContent = `${currentPremium > 0 ? '+' : ''}${currentPremium.toFixed(2)}%`;
      
      // 기존 애니메이션 클래스 제거
      const baseClass = `premium-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md ${getPremiumColor(currentPremium)}`;
      spanRef.current.className = baseClass;
      
      // 애니메이션 클래스 추가
      const flashClass = change === 'up' 
        ? 'premium-cell-flash-up bg-emerald-400/60 border-2 border-emerald-300 shadow-xl shadow-emerald-400/50 scale-105 text-white font-bold'
        : 'premium-cell-flash-down bg-red-400/60 border-2 border-red-300 shadow-xl shadow-red-400/50 scale-105 text-white font-bold';
      
      setTimeout(() => {
        if (spanRef.current) {
          spanRef.current.className = `premium-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md ${flashClass}`;
        }
      }, 10);
      
      // 기존 타이머 클리어
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
      
      // 1.5초 후 원래 상태로 복구
      animationTimeoutRef.current = setTimeout(() => {
        if (spanRef.current) {
          spanRef.current.className = baseClass;
        }
      }, 1500);
      
      prevPremiumRef.current = currentPremium;
    } else {
      // 프리미엄 변화가 없어도 텍스트 업데이트
      spanRef.current.textContent = `${currentPremium > 0 ? '+' : ''}${currentPremium.toFixed(2)}%`;
    }
  }, [premium, getPremiumColor]);
  
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
      className="premium-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md text-gray-400"
    >
      {premium !== null ? `${premium > 0 ? '+' : ''}${premium.toFixed(2)}%` : 'N/A'}
    </span>
  );
};

export default PremiumCell;