// frontend/src/components/PremiumCell.js
import React, { useEffect, useRef } from 'react';
import { formatPercent } from '../utils/formatters';

const PremiumCell = ({ premium }) => {
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