
import React, { useState, useCallback, useMemo, Suspense, lazy } from 'react';
import './App.css';
import Header from './components/Header';
import useWebSocketOptimized from './hooks/useWebSocketOptimized';

// 코드 스플리팅을 위한 동적 임포트
const CoinTable = lazy(() => import('./components/CoinTable'));
const FearGreedIndex = lazy(() => import('./components/FearGreedIndex'));
const SidebarLiquidations = lazy(() => import('./components/SidebarLiquidations'));

/**
 * 암호화폐 차익거래 모니터링 웹사이트의 메인 애플리케이션 컴포넌트.
 * 
 * WebSocket을 통해 실시간 가격 데이터를 받아오고,
 * 한국과 해외 거래소 간의 가격 차이(김치 프리미엄)를 모니터링합니다.
 * 
 * @returns {JSX.Element} 메인 애플리케이션 UI
 */
function App() {
  const [selectedDomesticExchange, setSelectedDomesticExchange] = useState('upbit'); // 선택된 국내 거래소 (기본: Upbit)
  const [selectedGlobalExchange, setSelectedGlobalExchange] = useState('binance'); // 선택된 해외 거래소 (기본: Binance)
  
  // 최적화된 WebSocket 연결
  const { 
    data: allCoinsData, 
    connectionStatus, 
    lastUpdate,
    reconnect 
  } = useWebSocketOptimized('ws://localhost:8002/ws/prices', {
    batchInterval: 100,        // 100ms 배치 처리
    maxBatchSize: 30,         // 최대 30개 배치
    enableDeltaCompression: false, // 임시로 비활성화하여 초기 데이터 로드 확인
    reconnectInterval: 3000,   // 3초 재연결 간격
    maxReconnectAttempts: 15   // 15회 최대 재연결
  });
  
  // 거래소 선택 핸들러 메모이제이션
  const handleDomesticExchangeChange = useCallback((exchange) => {
    setSelectedDomesticExchange(exchange);
  }, []);
  
  const handleGlobalExchangeChange = useCallback((exchange) => {
    setSelectedGlobalExchange(exchange);
  }, []);
  
  // 데이터 로딩 상태 메모이제이션
  const isDataLoaded = useMemo(() => {
    console.log('🏠 App.js - allCoinsData status:', {
      length: allCoinsData?.length || 0,
      connectionStatus,
      lastUpdate: lastUpdate?.toLocaleTimeString(),
      firstCoinPrice: allCoinsData?.[0]?.upbit_price,
      dataReference: allCoinsData // 객체 참조 확인
    });
    return allCoinsData && allCoinsData.length > 0;
  }, [allCoinsData, connectionStatus, lastUpdate]);
  
  // 연결 상태 표시
  const getConnectionStatusColor = (status) => {
    switch (status) {
      case 'connected': return '#10b981'; // green
      case 'connecting': return '#f59e0b'; // yellow  
      case 'disconnected': return '#ef4444'; // red
      case 'error': return '#dc2626'; // dark red
      case 'failed': return '#7f1d1d'; // very dark red
      default: return '#6b7280'; // gray
    }
  };


  return (
    <div className="App">
      <div className="mx-auto max-w-screen-2xl px-4 lg:px-6">
      <Header />
      <main className="App-main">
        <div className="App-layout-container">
          <div className="App-sidebar">
            <section className="App-section sidebar-fixed">
              {/* CoinTable 데이터가 로드된 후에만 FearGreedIndex 표시 */}
              {isDataLoaded ? (
                <Suspense fallback={
                  <div style={{
                    width: '100%',
                    height: '200px',
                    borderRadius: '8px',
                    backgroundColor: '#1a1a1a',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: '1px solid #333'
                  }}>
                    <div style={{ textAlign: 'center', color: '#666' }}>
                      <p style={{ fontSize: '14px', margin: '0' }}>공포/탐욕 지수 로드 중...</p>
                    </div>
                  </div>
                }>
                  <FearGreedIndex />
                </Suspense>
              ) : (
                <div style={{
                  width: '100%',
                  height: '200px',
                  borderRadius: '8px',
                  backgroundColor: '#1a1a1a',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid #333'
                }}>
                  <div style={{ textAlign: 'center', color: '#666' }}>
                    <p style={{ fontSize: '14px', margin: '0 0 4px 0' }}>공포/탐욕 지수 준비 중...</p>
                    <p style={{ fontSize: '12px', margin: '0' }}>메인 데이터 로드를 기다리고 있습니다</p>
                  </div>
                </div>
              )}
            </section>
            <section id="liquidation-widget-section" className="App-section">
              {/* CoinTable 데이터가 로드된 후에만 SidebarLiquidations 표시 */}
              {isDataLoaded ? (
                <Suspense fallback={
                  <div style={{
                    width: '100%',
                    height: '400px',
                    borderRadius: '8px',
                    backgroundColor: '#1a1a1a',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: '1px solid #333'
                  }}>
                    <div style={{ textAlign: 'center', color: '#666' }}>
                      <p style={{ fontSize: '14px', margin: '0' }}>청산 데이터 로드 중...</p>
                    </div>
                  </div>
                }>
                  <SidebarLiquidations />
                </Suspense>
              ) : (
                <div style={{
                  width: '100%',
                  height: '400px',
                  borderRadius: '8px',
                  backgroundColor: '#1a1a1a',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid #333'
                }}>
                  <div style={{ textAlign: 'center', color: '#666' }}>
                    <p style={{ fontSize: '14px', margin: '0 0 4px 0' }}>청산 데이터 준비 중...</p>
                    <p style={{ fontSize: '12px', margin: '0' }}>코인 데이터 로드를 기다리고 있습니다</p>
                  </div>
                </div>
              )}
            </section>
            <section className="App-section">
              {/* CoinTable 데이터가 로드된 후에만 광고 섹션 표시 */}
              {isDataLoaded ? (
                <div className="advertisement-placeholder">
                  <p style={{ 
                    textAlign: 'center', 
                    color: '#666', 
                    padding: '40px 20px',
                    border: '2px dashed #333',
                    borderRadius: '8px',
                    backgroundColor: '#1a1a1a'
                  }}>
                    광고 공간
                  </p>
                </div>
              ) : (
                <div style={{
                  width: '100%',
                  height: '150px',
                  borderRadius: '8px',
                  backgroundColor: '#1a1a1a',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid #333'
                }}>
                  <div style={{ textAlign: 'center', color: '#666' }}>
                    <p style={{ fontSize: '12px', margin: '0' }}>광고 준비 중...</p>
                  </div>
                </div>
              )}
            </section>
          </div>
          <div className="App-content">
            <section className="App-section">
              <Suspense fallback={
                <div className="w-full max-w-[960px] rounded-md bg-gray-900 text-[14px] text-gray-200 p-8">
                  <div className="text-center">
                    <p className="text-lg">코인 테이블 로드 중...</p>
                    <p className="text-sm text-gray-400 mt-2">잠시만 기다려주세요.</p>
                  </div>
                </div>
              }>
                <CoinTable
                  allCoinsData={allCoinsData}
                  selectedDomesticExchange={selectedDomesticExchange}
                  setSelectedDomesticExchange={handleDomesticExchangeChange}
                  selectedGlobalExchange={selectedGlobalExchange}
                  setSelectedGlobalExchange={handleGlobalExchangeChange}
                  connectionStatus={connectionStatus}
                  lastUpdate={lastUpdate}
                  getConnectionStatusColor={getConnectionStatusColor}
                  reconnect={reconnect}
                />
              </Suspense>
            </section>
          </div>
        </div>
      </main>
      </div>
    </div>
  );
}

export default App;
