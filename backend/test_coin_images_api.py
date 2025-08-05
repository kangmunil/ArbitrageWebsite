#!/usr/bin/env python3
"""
코인 이미지 API 엔드포인트 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import get_db, CoinMaster

def test_coin_images_api():
    """coin-images API 로직 테스트"""
    print("=== /api/coin-images API 로직 테스트 ===")
    
    # 데이터베이스 세션 가져오기
    db = next(get_db())
    
    try:
        # Query coins with image URLs
        coins = db.query(CoinMaster).filter(
            CoinMaster.image_url.isnot(None),
            CoinMaster.image_url != ''
        ).all()
        
        # Create symbol -> image URL mapping
        coin_images = {}
        for coin in coins:
            coin_images[coin.symbol] = coin.image_url
        
        print(f"이미지 URL 매핑: {len(coin_images)}개")
        
        print("\n=== 주요 코인 이미지 URL ===")
        major_coins = ['BTC', 'ETH', 'XRP', 'ADA', 'SOL', 'LINK', 'DOGE']
        for coin in major_coins:
            if coin in coin_images:
                print(f"{coin}: {coin_images[coin]}")
            else:
                print(f"{coin}: 없음")
        
        print("\n=== 모든 이미지 URL ===")
        for symbol, url in coin_images.items():
            print(f"{symbol}: {url}")
            
        return coin_images
        
    except Exception as e:
        print(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_coin_images_api()