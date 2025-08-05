#!/usr/bin/env python3
"""
한글명 API 엔드포인트 테스트
"""

import requests
import time
import subprocess
import sys
import signal
import os

def test_api():
    """API 테스트"""
    print("=== API 테스트: /api/coin-names ===")
    
    try:
        response = requests.get('http://localhost:8000/api/coin-names', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"총 코인 수: {len(data)}개")
            
            print("\n=== 업비트/빗썸 한글명 확인 ===")
            test_coins = ['BTC', 'ETH', 'XRP', 'ADA', 'DOT', 'LINK', 'SOL', 'QTUM', 'ICX', 'TRX', '1INCH', 'GAS', 'GALA']
            
            found_count = 0
            for coin in test_coins:
                if coin in data:
                    print(f"  {coin}: {data[coin]}")
                    found_count += 1
                else:
                    print(f"  {coin}: 없음")
            
            print(f"\n=== 처음 20개 코인 ===")
            for i, (symbol, name) in enumerate(list(data.items())[:20]):
                print(f"  {symbol}: {name}")
                
            print(f"\n테스트 결과: {found_count}/{len(test_coins)}개 한글명 확인")
            return True
            
        else:
            print(f"API 호출 실패: {response.status_code}")
            print(f"응답: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"API 호출 오류: {e}")
        return False

def main():
    """메인 함수"""
    print("🚀 API 서버 시작...")
    
    # API 서버 시작
    try:
        # 기존 프로세스 종료
        os.system("pkill -f 'uvicorn app.main:app'")
        time.sleep(1)
        
        # 새 서버 시작
        server_process = subprocess.Popen(
            ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            cwd="/Users/kangmunil/Project/ArbitrageWebsite/backend",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 서버 시작 대기
        print("서버 시작 대기 중...")
        time.sleep(5)
        
        # API 테스트
        success = test_api()
        
        if success:
            print("✅ API 테스트 성공!")
        else:
            print("❌ API 테스트 실패!")
        
        # 서버 종료
        server_process.terminate()
        server_process.wait()
        
        return success
        
    except KeyboardInterrupt:
        print("\n테스트 중단됨")
        if 'server_process' in locals():
            server_process.terminate()
        return False
    except Exception as e:
        print(f"테스트 오류: {e}")
        if 'server_process' in locals():
            server_process.terminate()
        return False

if __name__ == "__main__":
    main()