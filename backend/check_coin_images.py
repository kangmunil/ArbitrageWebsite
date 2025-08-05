#!/usr/bin/env python3
"""
코인 이미지 URL 확인 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager, CoinMaster

def check_coin_images():
    """데이터베이스의 코인 이미지 URL 확인"""
    print("=== 데이터베이스 이미지 URL 확인 ===")
    
    with db_manager.get_session_context() as session:
        # CoinMaster 테이블에서 이미지 URL 있는 코인들 확인
        coins_with_images = session.query(CoinMaster).filter(
            CoinMaster.image_url.isnot(None),
            CoinMaster.image_url != '',
            CoinMaster.is_active == True
        ).all()
        
        print(f"이미지 URL 보유 코인: {len(coins_with_images)}개")
        
        print("\n=== 이미지 URL 예시 ===")
        for i, coin in enumerate(coins_with_images[:10]):
            print(f"{i+1}. {coin.symbol}: {coin.image_url}")
        
        # 주요 코인들의 이미지 URL 확인
        print("\n=== 주요 코인 이미지 URL ===")
        major_coins = ['BTC', 'ETH', 'XRP', 'ADA', 'SOL', 'LINK', 'DOGE']
        for symbol in major_coins:
            coin = session.query(CoinMaster).filter_by(symbol=symbol, is_active=True).first()
            if coin and coin.image_url:
                print(f"{symbol}: {coin.image_url}")
            else:
                print(f"{symbol}: 이미지 URL 없음")
        
        # 전체 통계
        total_coins = session.query(CoinMaster).filter_by(is_active=True).count()
        print(f"\n=== 통계 ===")
        print(f"전체 활성 코인: {total_coins}개")
        print(f"이미지 URL 보유: {len(coins_with_images)}개")
        print(f"이미지 커버리지: {len(coins_with_images)/total_coins*100:.1f}%")

if __name__ == "__main__":
    check_coin_images()