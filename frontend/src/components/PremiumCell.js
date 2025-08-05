import React from 'react';
import { formatPercent } from '../utils/formatters';

/**
 * 프리미엄 정보를 표시하는 셀 컴포넌트입니다.
 * 프리미엄 값에 따라 색상을 변경합니다.
 * @param {{premium: number}} props - 컴포넌트 props
 * @returns {JSX.Element} PremiumCell 컴포넌트
 */
const PremiumCell = ({ premium }) => {
  /**
   * 프리미엄 값에 따라 기본 색상을 반환합니다.
   * @returns {string} Tailwind CSS 색상 클래스
   */
  const getBasePremiumColor = () => {
    if (premium > 0) return 'text-green-400';
    if (premium < 0) return 'text-red-400';
    return 'text-gray-400';
  };

  return (
    <span className={`transition-colors duration-300 ${getBasePremiumColor()}`}>
      {formatPercent(premium)}
    </span>
  );
};

export default PremiumCell;
