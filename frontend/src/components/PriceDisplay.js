import React from 'react';

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
