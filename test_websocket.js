const WebSocket = require('ws');

console.log('🔄 WebSocket 연결 테스트 시작...');

const ws = new WebSocket('ws://localhost:8000/ws/prices');

ws.on('open', () => {
  console.log('✅ WebSocket 연결 성공!');
  
  // 연결 확인 메시지 전송
  ws.send('ping');
});

ws.on('message', (data) => {
  try {
    const message = JSON.parse(data);
    
    if (Array.isArray(message) && message.length > 0) {
      console.log(`📊 실시간 데이터 수신: ${message.length}개 코인`);
      console.log(`💰 첫 번째 코인: ${message[0].symbol} - 업비트: ${message[0].upbit_price}, 바이낸스: ${message[0].binance_price}, 김프: ${message[0].premium}%`);
    } else {
      console.log('📡 연결 확인 메시지:', message);
    }
  } catch (err) {
    console.log('📝 원본 메시지:', data.toString().substring(0, 200) + '...');
  }
});

ws.on('error', (error) => {
  console.error('❌ WebSocket 오류:', error);
});

ws.on('close', () => {
  console.log('🔚 WebSocket 연결 종료');
  process.exit(0);
});

// 10초 후 자동 종료
setTimeout(() => {
  console.log('⏰ 테스트 완료 - 연결 종료');
  ws.close();
}, 10000);