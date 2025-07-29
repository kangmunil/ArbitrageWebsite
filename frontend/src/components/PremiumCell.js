// frontend/src/components/PremiumCell.js
import React, { useRef, memo } from 'react';
import { formatPercent } from '../utils/formatters';

const PremiumCell = ({ premium }) => {
  const prevPremiumRef = useRef(premium);

  // 프리미엄 변동 방향에 따른 색상 클래스 계산
  const getPremiumChangeClass = () => {
    const prevPremium = prevPremiumRef.current;
    
    if (premium !== null && prevPremium !== null && premium !== prevPremium) {
      if (premium > prevPremium) {
        prevPremiumRef.current = premium;
        return 'price-up'; // 상승: 초록색
      } else if (premium < prevPremium) {
        prevPremiumRef.current = premium;
        return 'price-down'; // 하락: 빨간색
      }
    }
    
    // 첫 렌더링이거나 변화가 없으면 이전 값 저장 후 기본 클래스
    prevPremiumRef.current = premium;
    return '';
  };

  // 프리미엄 절대값에 따른 기본 색상 (양수/음수)
  const getBasePremiumClass = () => {
    if (premium > 0) return 'premium-positive';
    if (premium < 0) return 'premium-negative';
    return 'premium-neutral';
  };

  const changeClass = getPremiumChangeClass();
  const baseClass = getBasePremiumClass();

  return (
    <span className={`premium-cell ${baseClass} ${changeClass}`}>
      {formatPercent(premium)}
    </span>
  );
};

export default memo(PremiumCell); // React.memo 추가