/**
 * 롱숏 비율 표시 섹션 컴포넌트
 * 주요 5개 코인의 실시간 롱숏 비율을 표시합니다.
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react';
import ProgressBar from './ProgressBar';

const SYMBOL_DISPLAY_NAMES = {
  'BTCUSDT': 'BTC',
  'ETHUSDT': 'ETH', 
  'SOLUSDT': 'SOL',
  'DOGEUSDT': 'DOGE',
  'ADAUSDT': 'ADA'
};

const LongShortSection = ({ data, loading, error, onRefresh }) => {
  // 로딩 상태
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 mb-4 border border-gray-600">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center">
            <TrendingUp className="w-4 h-4 mr-2 text-blue-400" />
            롱숏 비율
          </h3>
          <div className="animate-spin">
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </div>
        </div>
        
        <div className="space-y-3">
          {Object.keys(SYMBOL_DISPLAY_NAMES).map((symbol) => (
            <div key={symbol} className="animate-pulse">
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs font-medium text-gray-300">
                  {SYMBOL_DISPLAY_NAMES[symbol]}
                </span>
                <div className="w-16 h-3 bg-gray-600 rounded"></div>
              </div>
              <div className="w-full h-3 bg-gray-600 rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 에러 상태
  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 mb-4 border-l-4 border-red-500 border border-gray-600">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center">
            <TrendingUp className="w-4 h-4 mr-2 text-red-400" />
            롱숏 비율
          </h3>
          <button 
            onClick={onRefresh}
            className="p-1 hover:bg-gray-700 rounded"
            title="새로고침"
          >
            <RefreshCw className="w-4 h-4 text-gray-300" />
          </button>
        </div>
        <p className="text-xs text-red-400">데이터를 불러올 수 없습니다: {error}</p>
      </div>
    );
  }

  // 데이터가 없는 경우
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 mb-4 border border-gray-600">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center">
            <TrendingUp className="w-4 h-4 mr-2 text-gray-400" />
            롱숏 비율
          </h3>
          <button 
            onClick={onRefresh}
            className="p-1 hover:bg-gray-700 rounded"
            title="새로고침"
          >
            <RefreshCw className="w-4 h-4 text-gray-300" />
          </button>
        </div>
        <p className="text-xs text-gray-400">데이터가 없습니다.</p>
      </div>
    );
  }

  // 트렌드 아이콘 결정
  const getTrendIcon = (longRatio) => {
    if (longRatio > 0.6) {
      return <TrendingUp className="w-3 h-3 text-green-600" />;
    } else if (longRatio < 0.4) {
      return <TrendingDown className="w-3 h-3 text-red-600" />;
    }
    return <Minus className="w-3 h-3 text-yellow-600" />;
  };

  // 색상 결정
  const getColors = (longRatio) => {
    if (longRatio > 0.6) {
      return { longColor: 'bg-green-500', shortColor: 'bg-green-200' };
    } else if (longRatio < 0.4) {
      return { longColor: 'bg-red-200', shortColor: 'bg-red-500' };
    }
    return { longColor: 'bg-yellow-400', shortColor: 'bg-yellow-200' };
  };

  return (
    <div className="bg-gray-800 rounded-lg p-3 mb-3 shadow-sm border border-gray-600">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-200 flex items-center">
          <TrendingUp className="w-4 h-4 mr-2 text-blue-400" />
          롱숏 비율
        </h3>
        <button 
          onClick={onRefresh}
          className="p-1 hover:bg-gray-700 rounded transition-colors"
          title="새로고침"
        >
          <RefreshCw className="w-4 h-4 text-gray-300" />
        </button>
      </div>

      {/* 롱숏 비율 리스트 */}
      <div className="space-y-2">
        {Object.entries(SYMBOL_DISPLAY_NAMES).map(([symbol, displayName]) => {
          const symbolData = data[symbol];
          
          if (!symbolData || !symbolData.binance) {
            return (
              <div key={symbol} className="opacity-50">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs font-medium text-gray-300">
                    {displayName}
                  </span>
                  <span className="text-xs text-gray-500">데이터 없음</span>
                </div>
                <div className="w-full h-3 bg-gray-700 rounded"></div>
              </div>
            );
          }

          const binanceData = symbolData.binance;
          const longRatio = binanceData.long_ratio;
          const shortRatio = binanceData.short_ratio;
          const longPercent = Math.round(longRatio * 100);
          const shortPercent = Math.round(shortRatio * 100);
          const colors = getColors(longRatio);

          return (
            <div key={symbol}>
              {/* 심볼과 비율 표시 */}
              <div className="flex justify-between items-center mb-1">
                <div className="flex items-center">
                  <span className="text-xs font-medium text-gray-200 mr-1">
                    {displayName}
                  </span>
                  {getTrendIcon(longRatio)}
                </div>
                <div className="text-xs text-gray-300">
                  <span className="text-green-600 font-medium">{longPercent}%</span>
                  <span className="text-gray-400 mx-1">:</span>
                  <span className="text-red-600 font-medium">{shortPercent}%</span>
                </div>
              </div>

              {/* 프로그레스 바 */}
              <ProgressBar
                longValue={longPercent}
                shortValue={shortPercent}
                showPercentage={false}
                height="h-2"
                longColor={colors.longColor}
                shortColor={colors.shortColor}
                animate={true}
              />
            </div>
          );
        })}
      </div>

      {/* 마지막 업데이트 시간 */}
      <div className="mt-3 pt-2 border-t border-gray-600">
        <p className="text-xs text-gray-400 text-center">
          마지막 업데이트: {new Date().toLocaleTimeString('ko-KR')}
        </p>
      </div>
    </div>
  );
};

export default LongShortSection;