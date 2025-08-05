/**
 * 청산 현황 표시 섹션 컴포넌트
 * 24시간 청산 데이터를 실시간으로 표시합니다.
 */

import React, { useState } from 'react';
import { Activity, Zap, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import ProgressBar from './ProgressBar';

const LiquidationSection = ({ 
  data, 
  loading, 
  error, 
  wsConnected, 
  lastUpdate, 
  onRefresh 
}) => {
  const [sortBy, setSortBy] = useState('total_usd'); // 'total_usd' or 'events'

  // 포맷터 함수들
  const formatUSD = (value) => {
    if (value >= 1000000) {
      return `$${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}K`;
    }
    return `$${value.toFixed(0)}`;
  };

  const formatSymbol = (symbol) => {
    return symbol.replace('USDT', '').toUpperCase();
  };

  const getRelativeTime = (timestamp) => {
    if (!timestamp) return '';
    const now = new Date();
    const diff = now - new Date(timestamp);
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return '방금 전';
    if (minutes < 60) return `${minutes}분 전`;
    return `${Math.floor(minutes / 60)}시간 전`;
  };

  // 정렬된 데이터 (BTC, ETH, SOL 상위 고정)
  const sortedData = React.useMemo(() => {
    if (!data || !Array.isArray(data)) return [];
    
    const prioritySymbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
    
    // 우선순위 심볼과 나머지 심볼 분리
    const priorityData = data.filter(item => prioritySymbols.includes(item.symbol));
    const otherData = data.filter(item => !prioritySymbols.includes(item.symbol));
    
    // 우선순위 심볼을 지정된 순서로 정렬 (없는 경우 더미 데이터 생성)
    const sortedPriorityData = prioritySymbols.map(symbol => {
      const existingData = priorityData.find(item => item.symbol === symbol);
      if (existingData) {
        return existingData;
      }
      // 더미 데이터 생성 (데이터 수집 대기 중)
      return {
        symbol,
        total_liquidation_usd: 0,
        long_liquidation_usd: 0,
        short_liquidation_usd: 0,
        long_percentage: 0,
        short_percentage: 0,
        total_events: 0,
        long_events: 0,
        short_events: 0,
        timestamp: new Date().toISOString(),
        isPlaceholder: true // 더미 데이터 표시용
      };
    });
    
    // 나머지 데이터 정렬
    const sortedOtherData = [...otherData].sort((a, b) => {
      if (sortBy === 'total_usd') {
        return (b.total_liquidation_usd || 0) - (a.total_liquidation_usd || 0);
      } else {
        return (b.total_events || 0) - (a.total_events || 0);
      }
    });
    
    // 우선순위 데이터 + 나머지 데이터 결합 (더 많은 데이터 표시)
    return [...sortedPriorityData, ...sortedOtherData].slice(0, 15);
  }, [data, sortBy]);

  // 로딩 상태
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-600">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-red-400" />
            24시간 청산 현황
          </h3>
          <div className="animate-spin">
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </div>
        </div>
        
        <div className="space-y-3">
          {[...Array(5)].map((_, index) => (
            <div key={index} className="animate-pulse">
              <div className="flex justify-between items-center mb-2">
                <div className="w-16 h-4 bg-gray-600 rounded"></div>
                <div className="w-20 h-4 bg-gray-600 rounded"></div>
              </div>
              <div className="w-full h-2 bg-gray-600 rounded mb-1"></div>
              <div className="flex justify-between">
                <div className="w-12 h-3 bg-gray-600 rounded"></div>
                <div className="w-12 h-3 bg-gray-600 rounded"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 에러 상태
  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 shadow-sm border border-red-500">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-red-400" />
            24시간 청산 현황
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
  if (!sortedData || sortedData.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-600">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-gray-400" />
            24시간 청산 현황
          </h3>
          <div className="flex items-center space-x-2">
            {wsConnected ? (
              <Wifi className="w-4 h-4 text-green-400" title="실시간 연결" />
            ) : (
              <WifiOff className="w-4 h-4 text-red-400" title="연결 끊김" />
            )}
            <button 
              onClick={onRefresh}
              className="p-1 hover:bg-gray-700 rounded"
              title="새로고침"
            >
              <RefreshCw className="w-4 h-4 text-gray-300" />
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-400">청산 데이터가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-3 shadow-sm border border-gray-600">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-200 flex items-center">
          <Activity className="w-4 h-4 mr-2 text-red-400" />
          24시간 청산 현황
        </h3>
        <div className="flex items-center space-x-2">
          {/* 실시간 연결 상태 */}
          {wsConnected ? (
            <div className="flex items-center">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mr-1"></div>
              <Wifi className="w-4 h-4 text-green-400" title="실시간 연결" />
            </div>
          ) : (
            <WifiOff className="w-4 h-4 text-red-400" title="연결 끊김" />
          )}
          
          {/* 새로고침 버튼 */}
          <button 
            onClick={onRefresh}
            className="p-1 hover:bg-gray-700 rounded transition-colors"
            title="새로고침"
          >
            <RefreshCw className="w-4 h-4 text-gray-300" />
          </button>
        </div>
      </div>

      {/* 정렬 옵션 */}
      <div className="flex space-x-2 mb-3">
        <button
          onClick={() => setSortBy('total_usd')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            sortBy === 'total_usd' 
              ? 'bg-red-600 text-white font-medium' 
              : 'bg-gray-600 text-gray-200 hover:bg-gray-500'
          }`}
        >
          청산액순
        </button>
        <button
          onClick={() => setSortBy('events')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            sortBy === 'events' 
              ? 'bg-red-600 text-white font-medium' 
              : 'bg-gray-600 text-gray-200 hover:bg-gray-500'
          }`}
        >
          이벤트순
        </button>
      </div>

      {/* 청산 데이터 리스트 */}
      <div className="space-y-2">
        {sortedData.map((item, index) => {
          const symbol = formatSymbol(item.symbol);
          const totalUsd = item.total_liquidation_usd || 0;
          const longPercent = item.long_percentage || 0;
          const shortPercent = item.short_percentage || 0;
          const totalEvents = item.total_events || 0;
          
          // 청산 강도에 따른 색상 결정 (다크 테마)
          const getIntensityColor = (usd, isPlaceholder) => {
            if (isPlaceholder) return 'border-l-gray-600 bg-gray-800/30';
            if (usd > 100000) return 'border-l-red-500 bg-red-900/20';
            if (usd > 50000) return 'border-l-orange-500 bg-orange-900/20';
            if (usd > 10000) return 'border-l-yellow-500 bg-yellow-900/20';
            return 'border-l-gray-500 bg-gray-700/50';
          };

          return (
            <div 
              key={item.symbol} 
              className={`p-2 rounded border-l-4 ${getIntensityColor(totalUsd, item.isPlaceholder)} transition-colors`}
            >
              {/* 심볼과 청산액 */}
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center">
                  <span className={`text-sm font-semibold mr-2 ${
                    item.isPlaceholder ? 'text-gray-400' : 'text-gray-200'
                  }`}>
                    {symbol}
                  </span>
                  {index < 3 && !item.isPlaceholder && <Zap className="w-3 h-3 text-yellow-500" />}
                  {item.isPlaceholder && (
                    <span className="text-xs text-gray-500 italic">대기중</span>
                  )}
                </div>
                <div className="text-right">
                  <div className={`text-sm font-bold ${
                    item.isPlaceholder ? 'text-gray-500' : 'text-red-400'
                  }`}>
                    {formatUSD(totalUsd)}
                  </div>
                  <div className="text-xs text-gray-400">
                    {totalEvents}건
                  </div>
                </div>
              </div>

              {/* 롱/숏 청산 비율 */}
              <ProgressBar
                longValue={longPercent}
                shortValue={shortPercent}
                showPercentage={!item.isPlaceholder}
                height="h-2"
                longColor={item.isPlaceholder ? "bg-gray-600" : "bg-blue-500"}
                shortColor={item.isPlaceholder ? "bg-gray-600" : "bg-red-500"}
                animate={!item.isPlaceholder}
              />

              {/* 마지막 업데이트 시간 또는 상태 메시지 */}
              {item.isPlaceholder ? (
                <div className="text-xs text-gray-500 mt-1 text-right italic">
                  청산 데이터 수집 중...
                </div>
              ) : item.timestamp && (
                <div className="text-xs text-gray-500 mt-1 text-right">
                  {getRelativeTime(item.timestamp)}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 푸터 정보 */}
      <div className="mt-3 pt-2 border-t border-gray-600">
        <div className="flex justify-between items-center text-xs text-gray-400">
          <span>실시간 Binance 데이터</span>
          {lastUpdate && (
            <span>
              업데이트: {getRelativeTime(lastUpdate)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default LiquidationSection;