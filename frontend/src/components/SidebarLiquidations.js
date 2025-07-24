import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { useLiquidations } from '../hooks/useLiquidations';

const SidebarLiquidations = () => {
  const { trend, error, lastUpdate } = useLiquidations(5);

  return (
    <aside className="relative w-80 px-4 py-3 text-base text-white mx-auto">
      {/* 헤더 */}
      <header className="mb-4">
        <h2 className="font-semibold text-cyan-300 text-center">실시간 청산 데이터</h2>
        <p className="text-xs opacity-70 text-center mt-1">
          {lastUpdate ? `업데이트: ${lastUpdate.toLocaleTimeString('ko-KR')}` : '데이터 로딩 중...'}
        </p>
      </header>
      
      {/* 에러 표시 */}
      {error && (
        <div className="text-xs text-orange-400 mb-3 text-center">
          ⚠️ {error}
        </div>
      )}

      {/* 5분 차트 */}
      <section className="mb-4">
        <p className="mb-2 text-xs font-medium text-center text-zinc-300">
          5분 거래소별 청산 (M USD)
        </p>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart
            data={trend.map(item => ({
              ...item,
              exchange: item.exchange.startsWith('Hyperl') ? 'HL' : item.exchange
            }))}
            layout="vertical"
            barCategoryGap={6}
            margin={{ top: 2, right: 15, left: 15, bottom: 2 }}
          >
            <XAxis 
              type="number" 
              hide 
              domain={[0, 'dataMax + 1']} 
            />
            <YAxis
              type="category"
              dataKey="exchange"
              width={60}
              tick={{ fontSize: 10, fill: '#ccc' }}
              axisLine={false}
              tickLine={false}
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

      {/* 1시간 차트 */}
      <section>
        <p className="mb-2 text-xs font-medium text-center text-zinc-300">
          1시간 거래소별 청산 (M USD)
        </p>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart
            data={trend.map(item => ({
              ...item,
              exchange: item.exchange.startsWith('Hyperl') ? 'HL' : item.exchange,
              long: item.long * 12, // 1시간 = 12 x 5분 (시뮬레이션)
              short: item.short * 12
            }))}
            layout="vertical"
            barCategoryGap={6}
            margin={{ top: 2, right: 15, left: 15, bottom: 2 }}
          >
            <XAxis 
              type="number" 
              hide 
              domain={[0, 'dataMax + 1']} 
            />
            <YAxis
              type="category"
              dataKey="exchange"
              width={60}
              tick={{ fontSize: 10, fill: '#ccc' }}
              axisLine={false}
              tickLine={false}
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