/**
 * 통합 청산 & 롱숏 비율 위젯
 * 사이드바에 표시되는 실시간 암호화폐 데이터 위젯입니다.
 */

import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import LongShortSection from './LongShortSection';
import LiquidationSection from './LiquidationSection';
import { useLongShortData } from '../hooks/useLongShortData';
import { useLiquidationData } from '../hooks/useLiquidationData';

const LiquidationWidget = () => {
  const [widgetError, setWidgetError] = useState(null);

  // 커스텀 훅 사용
  const {
    data: longShortData,
    loading: lsLoading,
    error: lsError,
    lastUpdate: lsLastUpdate,
    refresh: refreshLongShort,
    hasData: hasLsData
  } = useLongShortData();

  const {
    data: liquidationData,
    loading: liqLoading,
    error: liqError,
    wsConnected,
    lastUpdate: liqLastUpdate,
    refresh: refreshLiquidation,
    hasData: hasLiqData
  } = useLiquidationData();

  // 전체 위젯 에러 상태 관리
  useEffect(() => {
    if (lsError && liqError) {
      setWidgetError('청산 서비스에 연결할 수 없습니다.');
    } else {
      setWidgetError(null);
    }
  }, [lsError, liqError]);

  // 전체 새로고침 함수
  const handleRefreshAll = () => {
    refreshLongShort();
    refreshLiquidation();
  };

  // 전체 위젯 에러 상태
  if (widgetError && !hasLsData && !hasLiqData) {
    return (
      <div className="w-full bg-gray-900 rounded-lg shadow-lg p-4 border-l-4 border-red-500 border border-gray-700">
        <div className="flex items-center mb-3">
          <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
          <h2 className="text-lg font-semibold text-gray-200">연결 오류</h2>
        </div>
        <p className="text-sm text-gray-300 mb-3">
          청산 서비스(포트 8002)에 연결할 수 없습니다.
        </p>
        <button 
          onClick={handleRefreshAll}
          className="w-full px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
        >
          다시 시도
        </button>
        <div className="mt-3 p-2 bg-gray-800 rounded text-xs text-gray-300">
          <p>확인사항:</p>
          <ul className="list-disc list-inside mt-1 space-y-1">
            <li>청산 서비스가 실행 중인지 확인</li>
            <li>포트 8002가 열려있는지 확인</li>
            <li>네트워크 연결 상태 확인</li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-gray-900 rounded-lg shadow-lg overflow-hidden border border-gray-700">
      {/* 위젯 헤더 */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-3 py-2">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold">실시간 시장 데이터</h2>
            <p className="text-blue-100 text-xs">롱숏 비율 & 청산 현황</p>
          </div>
          <div className="flex items-center space-x-2">
            {/* 연결 상태 표시 */}
            <div className="flex flex-col items-end">
              <div className="flex items-center">
                <div className={`w-2 h-2 rounded-full mr-1 ${
                  wsConnected ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
                }`}></div>
                <span className="text-xs">
                  {wsConnected ? '실시간' : '연결끊김'}
                </span>
              </div>
              {(lsLastUpdate || liqLastUpdate) && (
                <span className="text-xs text-blue-100 mt-1">
                  {new Date().toLocaleTimeString('ko-KR', { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                  })}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 위젯 콘텐츠 */}
      <div className="p-3 space-y-3 max-h-[500px] overflow-y-auto">
        {/* 롱숏 비율 섹션 (상단 40%) */}
        <LongShortSection
          data={longShortData}
          loading={lsLoading}
          error={lsError}
          onRefresh={refreshLongShort}
        />

        {/* 청산 현황 섹션 (하단 60%) */}
        <LiquidationSection
          data={liquidationData}
          loading={liqLoading}
          error={liqError}
          wsConnected={wsConnected}
          lastUpdate={liqLastUpdate}
          onRefresh={refreshLiquidation}
        />
      </div>

      {/* 위젯 푸터 */}
      <div className="bg-gray-800 px-3 py-2 border-t border-gray-700">
        <div className="flex justify-between items-center text-xs text-gray-300">
          <span>Binance 데이터 기준</span>
          <button 
            onClick={handleRefreshAll}
            className="text-blue-400 hover:text-blue-300 font-medium"
          >
            전체 새로고침
          </button>
        </div>
      </div>
    </div>
  );
};

export default LiquidationWidget;