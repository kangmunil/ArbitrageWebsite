#!/usr/bin/env python3
"""
거래소 등록 정보 설정
9개 거래소의 기본 정보를 exchange_registry 테이블에 설정
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db_manager, ExchangeRegistry

def setup_exchange_registry():
    """거래소 등록 정보 설정"""
    print("🏦 거래소 등록 정보 설정...")
    
    # 9개 거래소 정보 
    exchanges_data = [
        # 해외 거래소 (7개)
        {
            "exchange_id": "binance",
            "exchange_name": "Binance",
            "region": "global",
            "base_currency": "USDT",
            "api_enabled": True,
            "rate_limit_per_minute": 1200,
            "priority_order": 1,
            "ccxt_id": "binance",
            "is_active": True
        },
        {
            "exchange_id": "bybit",
            "exchange_name": "Bybit",
            "region": "global",
            "base_currency": "USDT",
            "api_enabled": True,
            "rate_limit_per_minute": 600,
            "priority_order": 2,
            "ccxt_id": "bybit",
            "is_active": True
        },
        {
            "exchange_id": "okx",
            "exchange_name": "OKX",
            "region": "global",
            "base_currency": "USDT",
            "api_enabled": True,
            "rate_limit_per_minute": 600,
            "priority_order": 3,
            "ccxt_id": "okx",
            "is_active": True
        },
        {
            "exchange_id": "gateio",
            "exchange_name": "Gate.io",
            "region": "global",
            "base_currency": "USDT",
            "api_enabled": True,
            "rate_limit_per_minute": 600,
            "priority_order": 4,
            "ccxt_id": "gateio",
            "is_active": True
        },
        {
            "exchange_id": "bitget",
            "exchange_name": "Bitget",
            "region": "global",
            "base_currency": "USDT",
            "api_enabled": True,
            "rate_limit_per_minute": 600,
            "priority_order": 5,
            "ccxt_id": "bitget",
            "is_active": True
        },
        {
            "exchange_id": "mexc",
            "exchange_name": "MEXC",
            "region": "global",
            "base_currency": "USDT",
            "api_enabled": True,
            "rate_limit_per_minute": 600,
            "priority_order": 6,
            "ccxt_id": "mexc",
            "is_active": True
        },
        {
            "exchange_id": "coinbase",
            "exchange_name": "Coinbase Pro",
            "region": "global",
            "base_currency": "USD",
            "api_enabled": True,
            "rate_limit_per_minute": 300,
            "priority_order": 7,
            "ccxt_id": "coinbasepro",
            "is_active": True
        },
        
        # 국내 거래소 (2개)
        {
            "exchange_id": "upbit",
            "exchange_name": "업비트",
            "region": "korea",
            "base_currency": "KRW",
            "api_enabled": True,
            "rate_limit_per_minute": 600,
            "priority_order": 10,
            "ccxt_id": "upbit",
            "is_active": True
        },
        {
            "exchange_id": "bithumb",
            "exchange_name": "빗썸",
            "region": "korea",
            "base_currency": "KRW",
            "api_enabled": True,
            "rate_limit_per_minute": 300,
            "priority_order": 11,
            "ccxt_id": "bithumb",
            "is_active": True
        }
    ]
    
    saved_count = 0
    updated_count = 0
    
    with db_manager.get_session_context() as session:
        for exchange_data in exchanges_data:
            try:
                # 기존 레코드 확인
                existing = session.query(ExchangeRegistry).filter_by(
                    exchange_id=exchange_data['exchange_id']
                ).first()
                
                if existing:
                    # 업데이트
                    for key, value in exchange_data.items():
                        setattr(existing, key, value)
                    updated_count += 1
                    print(f"🔄 업데이트: {existing.exchange_name}")
                else:
                    # 신규 추가
                    new_exchange = ExchangeRegistry(**exchange_data)
                    session.add(new_exchange)
                    saved_count += 1
                    print(f"🆕 신규 추가: {new_exchange.exchange_name}")
                
            except Exception as e:
                print(f"❌ {exchange_data['exchange_id']} 처리 실패: {e}")
        
        session.commit()
    
    print(f"\n✅ 거래소 등록 정보 설정 완료:")
    print(f"   신규 추가: {saved_count}개")
    print(f"   업데이트: {updated_count}개")
    
    return saved_count + updated_count

def get_exchange_summary():
    """거래소 등록 현황 요약"""
    with db_manager.get_session_context() as session:
        total_exchanges = session.query(ExchangeRegistry).count()
        active_exchanges = session.query(ExchangeRegistry).filter_by(is_active=True).count()
        
        # 지역별 통계
        global_exchanges = session.query(ExchangeRegistry).filter_by(
            region="global", is_active=True
        ).count()
        korea_exchanges = session.query(ExchangeRegistry).filter_by(
            region="korea", is_active=True
        ).count()
        
        return {
            "total_exchanges": total_exchanges,
            "active_exchanges": active_exchanges,
            "global_exchanges": global_exchanges,
            "korea_exchanges": korea_exchanges
        }

def main():
    """메인 함수"""
    print("🚀 거래소 등록 정보 설정 시작")
    
    try:
        # 1. 거래소 등록 정보 설정
        setup_count = setup_exchange_registry()
        
        # 2. 현황 요약
        summary = get_exchange_summary()
        
        print(f"\n📈 거래소 등록 현황:")
        print(f"   🌍 전체 거래소: {summary['total_exchanges']}개")
        print(f"   ✅ 활성 거래소: {summary['active_exchanges']}개")
        print(f"   🌐 해외 거래소: {summary['global_exchanges']}개")
        print(f"   🇰🇷 국내 거래소: {summary['korea_exchanges']}개")
        
        print(f"\n🎉 거래소 등록 설정 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 거래소 등록 설정 실패: {e}")
        return False

if __name__ == "__main__":
    main()