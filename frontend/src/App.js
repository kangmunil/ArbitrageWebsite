
import React, { useState, useEffect } from 'react';
import './App.css';
import Header from './components/Header';
import CoinTable from './components/CoinTable';
import PriceChart from './components/PriceChart';
import FearGreedIndex from './components/FearGreedIndex';

function App() {
  const [allCoinsData, setAllCoinsData] = useState(null);
  const [selectedDomesticExchange, setSelectedDomesticExchange] = useState('upbit'); // 기본값 Upbit
  const [selectedGlobalExchange, setSelectedGlobalExchange] = useState('binance'); // 기본값 Binance

  useEffect(() => {
    let ws;
    const connectWebSocket = () => {
      ws = new WebSocket(`ws://localhost:8000/ws/prices`);

      ws.onopen = () => {
        console.log("WebSocket connected");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setAllCoinsData(data); // Update state with new data
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
