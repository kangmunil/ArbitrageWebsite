
import React, { useState, useEffect } from 'react';
import './App.css';
import Header from './components/Header';
import CoinTable from './components/CoinTable';
import FearGreedIndex from './components/FearGreedIndex';
import SidebarLiquidations from './components/SidebarLiquidations';

/**
 * 암호화폐 차익거래 모니터링 웹사이트의 메인 애플리케이션 컴포넌트.
 * 
 * WebSocket을 통해 실시간 가격 데이터를 받아오고,
 * 한국과 해외 거래소 간의 가격 차이(김치 프리미엄)를 모니터링합니다.
 * 
 * @returns {JSX.Element} 메인 애플리케이션 UI
 */
function App() {
  const [allCoinsData, setAllCoinsData] = useState(null); // 모든 코인의 실시간 가격 데이터
  const [selectedDomesticExchange, setSelectedDomesticExchange] = useState('upbit'); // 선택된 국내 거래소 (기본: Upbit)
  const [selectedGlobalExchange, setSelectedGlobalExchange] = useState('binance'); // 선택된 해외 거래소 (기본: Binance)

  useEffect(() => {
    let ws;
    const connectWebSocket = () => {
      // Firefox 호환성을 위한 WebSocket 연결 개선
      try {
        // 모든 브라우저에 대해 localhost를 시도한 다음 127.0.0.1을 시도
        let wsUrl = `ws://localhost:8000/ws/prices`;
        console.log(`Connecting to WebSocket: ${wsUrl}`);
        ws = new WebSocket(wsUrl);
      } catch (error) {
        console.error("WebSocket creation failed:", error);
        // 실패 시 127.0.0.1로 재시도
        try {
          let wsUrl = `ws://127.0.0.1:8000/ws/prices`;
          console.log(`Retrying with 127.0.0.1: ${wsUrl}`);
          ws = new WebSocket(wsUrl);
        } catch (retryError) {
          console.error("WebSocket retry failed:", retryError);
          setTimeout(connectWebSocket, 3000);
          return;
        }
      }

      ws.onopen = () => {
        console.log("WebSocket connected");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        // 배열 데이터인 경우에만 코인 데이터 업데이트 (가격 데이터)
        if (Array.isArray(data)) {
          console.log(`WebSocket received ${data.length} coins at ${new Date().toLocaleTimeString()}`);
          setAllCoinsData(data);
        } else {
          console.log('Non-array data received:', data);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };

      ws.onclose = (event) => {
        console.log("WebSocket disconnected. Code:", event.code, "Reason:", event.reason);
        console.log("Attempting to reconnect...");
        // Firefox에서 더 안정적인 재연결을 위해 지연 시간 조정
        setTimeout(connectWebSocket, 5000); 
      };
    };

    connectWebSocket(); // Initial connection

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []);

  return (
    <div className="App">
      <div className="mx-auto max-w-screen-2xl px-4 lg:px-6">
      <Header />
      <main className="App-main">
        <div className="App-layout-container">
          <div className="App-sidebar items-center">
            <section className="App-section">
              <FearGreedIndex />
            </section>
            <section id="liquidation-widget-section" className="App-section">
              <SidebarLiquidations />
            </section>
            <section className="App-section">
              {/* 광고 자리 */}
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
            </section>
          </div>
          <div className="App-content">
            <section className="App-section">
              <CoinTable
                allCoinsData={allCoinsData}
                selectedDomesticExchange={selectedDomesticExchange}
                setSelectedDomesticExchange={setSelectedDomesticExchange}
                selectedGlobalExchange={selectedGlobalExchange}
                setSelectedGlobalExchange={setSelectedGlobalExchange}
              />
            </section>
          </div>
        </div>
      </main>
      </div>
    </div>
  );
}

export default App;
