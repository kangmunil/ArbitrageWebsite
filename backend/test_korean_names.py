#!/usr/bin/env python3
"""
업비트/빗썸 한글명 API 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager
from sqlalchemy import text

def test_korean_names():
    """한글명 데이터베이스 확인"""
    print("=== 업비트/빗썸 한글명 확인 ===")
    
    with db_manager.get_session_context() as session:
        # 업비트 한글명 확인
        upbit_result = session.execute(text('''
            SELECT symbol, korean_name 
            FROM upbit_listings 
            WHERE is_active = true 
            AND korean_name IS NOT NULL 
            AND korean_name != ''
            LIMIT 10
        ''')).fetchall()
        
        print(f"업비트 한글명: {len(upbit_result)}개")
        for symbol, korean_name in upbit_result:
            print(f"  {symbol}: {korean_name}")
        
        # 빗썸 한글명 확인
        bithumb_result = session.execute(text('''
            SELECT symbol, korean_name 
            FROM bithumb_listings 
            WHERE is_active = true 
            AND korean_name IS NOT NULL 
            AND korean_name != ''
            LIMIT 10
        ''')).fetchall()
        
        print(f"\n빗썸 한글명: {len(bithumb_result)}개")
        for symbol, korean_name in bithumb_result:
            print(f"  {symbol}: {korean_name}")
            
        # 전체 통계
        upbit_total = session.execute(text('''
            SELECT COUNT(*) FROM upbit_listings 
            WHERE is_active = true 
            AND korean_name IS NOT NULL 
            AND korean_name != ''
        ''')).scalar()
        
        bithumb_total = session.execute(text('''
            SELECT COUNT(*) FROM bithumb_listings 
            WHERE is_active = true 
            AND korean_name IS NOT NULL 
            AND korean_name != ''
        ''')).scalar()
        
        print(f"\n=== 전체 통계 ===")
        print(f"업비트 한글명 보유: {upbit_total}개")
        print(f"빗썸 한글명 보유: {bithumb_total}개")

if __name__ == "__main__":
    test_korean_names()