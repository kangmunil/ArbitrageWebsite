// frontend/src/components/PremiumCell.js
import React, { useState, useEffect, useCallback, useRef, memo } from 'react';
// PremiumCell.css 파일이 있다면 import
// import './PremiumCell.css'; 

const PremiumCell = ({ premium }) => {
  const prevPremiumRef = useRef(premium); // 이전 premium 값을 추적
  const [flashClass, setFlashClass] = useState(''); // 애니메이션 클래스 상태
  const animationTimeoutRef = useRef(null); // 타이머 ID 저장

  // 프리미엄 색상 결정 함수
  const getPremiumColor = useCallback((premiumValue) => {
    if (premiumValue > 0) return 'text-emerald-400';
    if (premiumValue < 0) return 'text-red-400';
    return 'text-gray-400';
  }, []);

  useEffect(() => {
    // 컴포넌트가 처음 마운트될 때 prevPremiumRef.current를 초기 premium으로 설정
    if (prevPremiumRef.current === undefined) {
      prevPremiumRef.current = premium;
      return; // 첫 렌더링에서는 애니메이션 스킵
    }

    const currentPremium = premium;
    const prevPremium = prevPremiumRef.current;

    // premium 값이 유효하고, 이전 값과 다를 때만 애니메이션 적용
    if (currentPremium !== null && prevPremium !== null && currentPremium !== prevPremium) {
      const change = currentPremium > prevPremium ? 'up' : 'down';

      console.log(`📈 [PremiumCell] 김프 변화: ${prevPremium.toFixed(2)}% → ${currentPremium.toFixed(2)}% (${change === 'up' ? '상승' : '하락'})`);

      // 애니메이션 클래스 설정
      const newFlashClass = change === 'up'
        ? 'premium-cell-flash-up bg-emerald-400/60 border-2 border-emerald-300 shadow-xl shadow-emerald-400/50 scale-105 text-white font-bold'
        : 'premium-cell-flash-down bg-red-400/60 border-2 border-red-300 shadow-xl shadow-red-400/50 scale-105 text-white font-bold';

      setFlashClass(newFlashClass);

      // 기존 타이머 클리어
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }

      // 1.5초 후 원래 상태로 복구
      animationTimeoutRef.current = setTimeout(() => {
        setFlashClass(''); // 클래스 제거
      }, 1500);
    }
    
    // 다음 비교를 위해 현재 premium 값을 ref에 저장 (null 값도 저장)
    prevPremiumRef.current = currentPremium;

    // 컴포넌트 언마운트 시 타이머 정리
    return () => {
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
    };
  }, [premium]); // premium prop이 변경될 때마다 이 effect를 실행

  // 렌더링될 텍스트와 기본 클래스 결정
  const displayPremium = premium !== null ? `${premium > 0 ? '+' : ''}${premium.toFixed(2)}%` : 'N/A';
  const baseColorClass = getPremiumColor(premium); // 현재 premium 값에 따른 기본 색상

  return (
    <span
      // flashClass가 있다면 적용하고, 없다면 기본 클래스만 적용
      className={`premium-cell transition-all duration-300 ease-in-out px-2 py-1 rounded-md ${baseColorClass} ${flashClass}`}
    >
      {displayPremium}
    </span>
  );
};

export default memo(PremiumCell); // React.memo 추가