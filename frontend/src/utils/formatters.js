/**
 * 공통 데이터 포맷팅 유틸리티
 * 
 * 가격, 거래량, 시간, 프리미엄 등의 표시용 포맷팅 함수들을 제공합니다.
 */

/**
 * 가격 포맷팅 (동적 소수점)
 */
export const formatPrice = (price, currency = '₩') => {
  if (price === null || price === undefined || isNaN(price)) {
    return `${currency}0`;
  }

  const numPrice = Number(price);
  
  if (numPrice < 0.01) {
    return `${currency}${numPrice.toFixed(6)}`;      // 소수 6자리 (SHIB, BONK 등)
  }
  if (numPrice < 1) {
    return `${currency}${numPrice.toFixed(4)}`;      // 소수 4자리  
  }
  if (numPrice < 100) {
    return `${currency}${numPrice.toFixed(2)}`;      // 소수 2자리
  }
  
  return `${currency}${Math.round(numPrice).toLocaleString()}`;  // 정수 + 천단위 구분
};

/**
 * USD 가격 포맷팅
 */
export const formatUsdPrice = (price) => {
  return formatPrice(price, '$');
};

/**
 * 거래량 포맷팅
 */
export const formatVolume = (volume, currency = 'KRW') => {
  if (volume === null || volume === undefined || isNaN(volume)) {
    return currency === 'KRW' ? '0억원' : '$0M';
  }

  const numVolume = Number(volume);
  
  if (currency === 'KRW') {
    // KRW: 억원 단위로 표시
    return `${(numVolume / 100_000_000).toFixed(0)}억원`;
  } else {
    // USD: 백만달러 단위로 표시
    return `$${(numVolume / 1_000_000).toFixed(1)}M`;
  }
};

/**
 * 퍼센트 포맷팅 (변화율, 프리미엄)
 */
export const formatPercent = (percent, decimalPlaces = 2) => {
  if (percent === null || percent === undefined || isNaN(percent)) {
    return '0.00%';
  }

  const numPercent = Number(percent);
  const sign = numPercent >= 0 ? '+' : '';
  return `${sign}${numPercent.toFixed(decimalPlaces)}%`;
};

/**
 * 프리미엄 포맷팅 (색상 클래스 포함)
 */
export const formatPremium = (premium) => {
  const formatted = formatPercent(premium);
  const numPremium = Number(premium);
  
  let colorClass = 'text-gray-500';
  if (numPremium > 0) {
    colorClass = 'text-red-500';  // 양수: 빨간색
  } else if (numPremium < 0) {
    colorClass = 'text-blue-500'; // 음수: 파란색
  }
  
  return { formatted, colorClass };
};

/**
 * 시간 포맷팅
 */
export const formatTime = (timestamp, format = 'relative') => {
  if (!timestamp) return '-';
  
  const date = new Date(timestamp);
  
  switch (format) {
    case 'relative':
      return formatRelativeTime(date);
    case 'short':
      return date.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    case 'full':
      return date.toLocaleString('ko-KR');
    case 'date':
      return date.toLocaleDateString('ko-KR');
    default:
      return date.toLocaleString('ko-KR');
  }
};

/**
 * 상대 시간 포맷팅 (몇 초 전, 몇 분 전 등)
 */
export const formatRelativeTime = (date) => {
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);
  
  if (diffSec < 60) {
    return `${diffSec}초 전`;
  } else if (diffMin < 60) {
    return `${diffMin}분 전`;
  } else if (diffHour < 24) {
    return `${diffHour}시간 전`;
  } else if (diffDay < 7) {
    return `${diffDay}일 전`;
  } else {
    return date.toLocaleDateString('ko-KR');
  }
};

/**
 * 숫자를 간단한 형태로 포맷팅 (K, M, B 단위)
 */
export const formatCompactNumber = (num) => {
  if (num === null || num === undefined || isNaN(num)) {
    return '0';
  }

  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  
  if (absNum >= 1e9) {
    return `${sign}${(absNum / 1e9).toFixed(1)}B`;
  } else if (absNum >= 1e6) {
    return `${sign}${(absNum / 1e6).toFixed(1)}M`;
  } else if (absNum >= 1e3) {
    return `${sign}${(absNum / 1e3).toFixed(1)}K`;
  } else {
    return `${sign}${absNum.toString()}`;
  }
};

/**
 * 암호화폐 심볼 표준화
 */
export const formatSymbol = (symbol) => {
  if (!symbol || typeof symbol !== 'string') {
    return '';
  }
  return symbol.toUpperCase().trim();
};

/**
 * 소수점 자릿수 동적 결정
 */
export const getDynamicDecimalPlaces = (price) => {
  const numPrice = Number(price);
  if (numPrice < 0.01) return 6;
  if (numPrice < 1) return 4;
  if (numPrice < 100) return 2;
  return 0;
};

/**
 * 애니메이션을 위한 가격 변화 방향 계산
 */
export const getPriceChangeDirection = (currentPrice, previousPrice) => {
  if (!currentPrice || !previousPrice) return 'neutral';
  
  const current = Number(currentPrice);
  const previous = Number(previousPrice);
  
  if (current > previous) return 'up';
  if (current < previous) return 'down';
  return 'neutral';
};

/**
 * 가격 변화량 계산
 */
export const calculatePriceChange = (currentPrice, previousPrice) => {
  if (!currentPrice || !previousPrice) return { amount: 0, percent: 0 };
  
  const current = Number(currentPrice);
  const previous = Number(previousPrice);
  
  const amount = current - previous;
  const percent = previous !== 0 ? (amount / previous) * 100 : 0;
  
  return { amount, percent };
};

/**
 * 가격 차이 및 프리미엄 계산
 */
export const calculatePremium = (domesticPrice, globalPrice, exchangeRate = 1300) => {
  if (!domesticPrice || !globalPrice || !exchangeRate) {
    return { premium: 0, difference: 0 };
  }
  
  const domestic = Number(domesticPrice);
  const global = Number(globalPrice);
  const rate = Number(exchangeRate);
  
  const globalInKRW = global * rate;
  const difference = domestic - globalInKRW;
  const premium = globalInKRW !== 0 ? (difference / globalInKRW) * 100 : 0;
  
  return { premium, difference };
};

/**
 * 안전한 숫자 변환
 */
export const safeNumber = (value, defaultValue = 0) => {
  if (value === null || value === undefined) return defaultValue;
  const num = Number(value);
  return isNaN(num) ? defaultValue : num;
};

/**
 * 정확도 검사 (소수점 오차 보정)
 */
export const roundToPrecision = (num, precision = 8) => {
  return Math.round(num * Math.pow(10, precision)) / Math.pow(10, precision);
};

/**
 * 가격 애니메이션을 위한 CSS 클래스 생성
 */
export const getPriceAnimationClass = (direction) => {
  switch (direction) {
    case 'up':
      return 'price-up';
    case 'down':
      return 'price-down';
    default:
      return '';
  }
};

/**
 * 청산 데이터 포맷팅
 */
export const formatLiquidation = (amount, currency = 'USD') => {
  const numAmount = safeNumber(amount);
  
  if (currency === 'USD') {
    if (numAmount >= 1_000_000) {
      return `$${(numAmount / 1_000_000).toFixed(2)}M`;
    } else if (numAmount >= 1_000) {
      return `$${(numAmount / 1_000).toFixed(1)}K`;
    } else {
      return `$${numAmount.toFixed(0)}`;
    }
  } else {
    return formatPrice(numAmount, currency);
  }
};

// 기본 내보내기
const formatters = {
  formatPrice,
  formatUsdPrice,
  formatVolume,
  formatPercent,
  formatPremium,
  formatTime,
  formatRelativeTime,
  formatCompactNumber,
  formatSymbol,
  formatLiquidation,
  getDynamicDecimalPlaces,
  getPriceChangeDirection,
  calculatePriceChange,
  calculatePremium,
  safeNumber,
  roundToPrecision,
  getPriceAnimationClass
};

export default formatters;