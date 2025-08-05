#!/usr/bin/env python3
"""
get_coin_names 함수 직접 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import get_db, CoinMaster
from sqlalchemy import text

def test_coin_names_function():
    """get_coin_names 함수 로직 테스트"""
    print("=== get_coin_names 함수 로직 테스트 ===")
    
    # 데이터베이스 세션 가져오기
    db = next(get_db())
    
    try:
        coin_names = {}
        
        print("1. CoinMaster 테이블에서 기본 한글명 가져오기...")
        coins = db.query(CoinMaster).all()
        print(f"   CoinMaster 레코드 수: {len(coins)}")
        
        for coin in coins:
            korean_name = getattr(coin, 'name_ko', None)
            if korean_name and korean_name.strip():
                coin_names[coin.symbol] = korean_name
            else:
                coin_names[coin.symbol] = coin.symbol
        
        print(f"   CoinMaster에서 추가된 이름: {len(coin_names)}개")
        
        print("2. 업비트 테이블에서 한글명 가져오기...")
        try:
            upbit_result = db.execute(text("""
                SELECT symbol, korean_name 
                FROM upbit_listings 
                WHERE is_active = true 
                AND korean_name IS NOT NULL 
                AND korean_name != ''
            """)).fetchall()
            
            for symbol, korean_name in upbit_result:
                if korean_name and korean_name.strip():
                    coin_names[symbol] = korean_name.strip()
            
            print(f"   업비트에서 추가/업데이트된 이름: {len(upbit_result)}개")
        except Exception as e:
            print(f"   업비트 쿼리 실패: {e}")
        
        print("3. 빗썸 테이블에서 한글명 가져오기...")
        try:
            bithumb_result = db.execute(text("""
                SELECT symbol, korean_name 
                FROM bithumb_listings 
                WHERE is_active = true 
                AND korean_name IS NOT NULL 
                AND korean_name != ''
            """)).fetchall()
            
            for symbol, korean_name in bithumb_result:
                if korean_name and korean_name.strip():
                    coin_names[symbol] = korean_name.strip()
            
            print(f"   빗썸에서 추가/업데이트된 이름: {len(bithumb_result)}개")
        except Exception as e:
            print(f"   빗썸 쿼리 실패: {e}")
        
        print(f"\n=== 최종 결과 ===")
        print(f"총 코인명: {len(coin_names)}개")
        
        # 샘플 출력
        print("\n주요 코인들:")
        test_coins = ['BTC', 'ETH', 'XRP', 'ADA', '1INCH', 'GAS', 'GALA']
        for coin in test_coins:
            if coin in coin_names:
                print(f"  {coin}: {coin_names[coin]}")
        
        print("\n처음 10개 코인:")
        for i, (symbol, name) in enumerate(list(coin_names.items())[:10]):
            print(f"  {symbol}: {name}")
            
        return coin_names
        
    except Exception as e:
        print(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_coin_names_function()