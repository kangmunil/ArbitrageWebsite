import React from 'react';

/**
 * 가격 정보 표시 컴포넌트.
 * 
 * 여러 거래소의 가격과 김치 프리미엄, 환율 정보를 표시합니다.
 * 현재는 사용되지 않는 레거시 컴포넌트입니다.
 * 
 * @param {Object} props - 컴포넌트 props
 * @param {Object} props.priceInfo - 가격 정보 객체
 * @param {number} props.priceInfo.upbit_price - Upbit 가격 (KRW)
 * @param {number} props.priceInfo.bithumb_price - Bithumb 가격 (KRW)
 * @param {number} props.priceInfo.binance_price - Binance 가격 (USD)
 * @param {number} props.priceInfo.premium - 김치 프리미엄 (%)
 * @param {number} props.priceInfo.usdt_krw_rate - USDT/KRW 환율
 * @param {number} props.priceInfo.exchange_rate - USD/KRW 환율
 * @returns {JSX.Element} 가격 정보 표시 UI
 */
function PriceDisplay({ priceInfo }) {
  if (!priceInfo) {
    return <p>Connecting to real-time price feed...</p>;
  }

  return (
    <div>
      <p>Upbit: {priceInfo.upbit_price.toLocaleString()} KRW</p>
      <p>Bithumb: {priceInfo.bithumb_price.toLocaleString()} KRW</p>
      <p>Bybit: ${priceInfo.bybit_price.toLocaleString()}</p>
      <p>OKX: ${priceInfo.okx_price.toLocaleString()}</p>
      <p>Gate.io: ${priceInfo.gateio_price.toLocaleString()}</p>
      <p>MEXC: ${priceInfo.mexc_price.toLocaleString()}</p>
      <p>Binance: ${priceInfo.binance_price.toLocaleString()}</p>
      <p className={priceInfo.premium > 0 ? 'premium-plus' : 'premium-minus'}>
        Kimchi Premium: {priceInfo.premium}%
      </p>
      <p>USDT-KRW Rate (Upbit): {priceInfo.usdt_krw_rate.toLocaleString()} KRW</p>
      {priceInfo.exchange_rate && (
        <p>KRW/USD Rate (Naver): {priceInfo.exchange_rate.toLocaleString()} KRW</p>
      )}
    </div>
  );
}

export default PriceDisplay;
