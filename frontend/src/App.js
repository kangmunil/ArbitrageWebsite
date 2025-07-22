
import React, { useState, useEffect } from 'react';
import './App.css';
import Header from './components/Header';
import CoinTable from './components/CoinTable';
import PriceChart from './components/PriceChart';
import FearGreedIndex from './components/FearGreedIndex';
import LiquidationChart from './components/LiquidationChart';

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
      ws = new WebSocket(`ws://localhost:8000/ws/prices`);

      ws.onopen = () => {
        console.log("WebSocket connected");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // 백엔드에서 배열 형태로 데이터를 전송하므로 그대로 사용
        console.log('Received WebSocket data:', data);
        if (Array.isArray(data)) {
          setAllCoinsData(data);
        } else {
          console.error('Received data is not an array:', data);
          setAllCoinsData([]);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected. Attempting to reconnect...");
        // Reconnect after a short delay
        setTimeout(connectWebSocket, 3000); 
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
      <Header />
      <main className="App-main">
        <div className="App-layout-container">
          <div className="App-sidebar">
            <section className="App-section">
              <FearGreedIndex />
            </section>
            <section id="chart-section" className="App-section">
              <LiquidationChart />
            </section>
            <section className="App-section">
              <h2>Bitcoin Price Chart</h2>
              <PriceChart />
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
  );
}

export default App;
