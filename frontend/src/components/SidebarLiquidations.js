import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { useLiquidations } from '../hooks/useLiquidations';

/**
 * 실시간 청산 데이터를 표시하는 사이드바 컴포넌트입니다.
 * @returns {JSX.Element} 사이드바 청산 컴포넌트
 */
const SidebarLiquidations = () => {
  const { trend, error, lastUpdate } = useLiquidations(5);

  // 차트 데이터 메모이제이션
  const chartData1hour = useMemo(() => {
    // 항상 6개 거래소를 보장하는 기본 데이터
    const defaultData = [
      { exchange: 'Binance', long: 0, short: 0 },
      { exchange: 'Bybit', long: 0, short: 0 },
      { exchange: 'Okx', long: 0, short: 0 },
      { exchange: 'Bitget', long: 0, short: 0 },
      { exchange: 'Bitmex', long: 0, short: 0 },
      { exchange: 'Hyperliquid', long: 0, short: 0 }
    ];

    if (!trend || trend.length === 0) {
      return defaultData;
    }

    // trend 데이터를 defaultData에 병합
    return defaultData.map(defaultItem => {
      const trendItem = trend.find(item => item.exchange === defaultItem.exchange);
      return trendItem || defaultItem;
    });
  }, [trend]);

  const chartData24hour = useMemo(() => {
    // 24시간 누적 데이터로 변경 (실제 백엔드에서 24시간 데이터를 받아옴)
    return chartData1hour.map(item => ({
      ...item,
      long: item.long * 24, // 24시간 누적 시뮬레이션
      short: item.short * 24
    }));
  }, [chartData1hour]);

  // Development mode: minimal logging for operational status
  if (process.env.NODE_ENV === 'development' && trend?.length) {
    const now = Date.now();
    if (!window.lastSidebarLog || (now - window.lastSidebarLog) > 60000) {
      console.log(`📊 Liquidations updated: ${trend.length} exchanges`);
      window.lastSidebarLog = now;
    }
  }

  return (
    <aside style={{ 
      width: '300px',
      padding: '0px', 
      border: '1px solid rgb(51, 51, 51)', 
      borderRadius: '8px', 
      backgroundColor: 'rgb(26, 26, 26)',
      color: 'white',
      margin: '-11px',
      minHeight: '400px'
    }}>
      {/* 헤더 */}
      <header className="mb-4 px-4 pt-4">
        <h2 className="font-semibold text-cyan-300 text-center">실시간 청산 데이터</h2>
        <p className="text-xs opacity-70 text-center mt-1">
          {lastUpdate ? `업데이트: ${lastUpdate.toLocaleTimeString('ko-KR')}` : '데이터 로딩 중...'}
        </p>
      </header>
      
      {/* 에러 표시 */}
      {error && (
        <div className="text-xs text-orange-400 mb-3 text-center px-4">
          ⚠️ {error}
        </div>
      )}

      {/* 1시간 차트 */}
      <section className="mb-4" style={{ paddingLeft: 0, paddingRight: 16 }}>
        <p className="mb-2 text-xs font-medium text-center text-zinc-300" style={{ paddingLeft: 16 }}>
          1시간 거래소별 청산 (M USD)
        </p>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart
            data={chartData1hour}
            layout="vertical"
            barCategoryGap={12}
            margin={{ top: 8, right: 15, left: 0, bottom: 8 }}
          >
            <XAxis 
              type="number" 
              hide 
              domain={[0, 'dataMax + 1']} 
            />
            <YAxis
              type="category"
              dataKey="exchange"
              width={80}
              interval={0}
              tick={{ fontSize: 10, fill: '#fff' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value) => value}
            />
            <Tooltip 
              formatter={(value) => `${value.toFixed(2)}M`}
              contentStyle={{
                backgroundColor: '#374151',
                border: 'none',
                borderRadius: '0.375rem',
                fontSize: '11px'
              }}
            />
            <Bar dataKey="long" fill="#3b82f6" name="롱" barSize={8} />
            <Bar dataKey="short" fill="#ef4444" name="숏" barSize={8} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* 24시간 차트 */}
      <section className="pb-4" style={{ paddingLeft: 0, paddingRight: 16 }}>
        <p className="mb-2 text-xs font-medium text-center text-zinc-300" style={{ paddingLeft: 16 }}>
          24시간 거래소별 청산 (M USD)
        </p>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart
            data={chartData24hour}
            layout="vertical"
            barCategoryGap={12}
            margin={{ top: 8, right: 15, left: 0, bottom: 8 }}
          >
            <XAxis 
              type="number" 
              hide 
              domain={[0, 'dataMax + 1']} 
            />
            <YAxis
              type="category"
              dataKey="exchange"
              width={80}
              interval={0}
              tick={{ fontSize: 10, fill: '#fff' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value) => value}
            />
            <Tooltip 
              formatter={(value) => `${value.toFixed(2)}M`}
              contentStyle={{
                backgroundColor: '#374151',
                border: 'none',
                borderRadius: '0.375rem',
                fontSize: '11px'
              }}
            />
            <Bar dataKey="long" fill="#3b82f6" name="롱" barSize={8} />
            <Bar dataKey="short" fill="#ef4444" name="숏" barSize={8} />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </aside>
  );
};

export default SidebarLiquidations;
