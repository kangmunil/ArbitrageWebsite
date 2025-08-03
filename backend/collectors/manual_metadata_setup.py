#!/usr/bin/env python3
"""
수동 메타데이터 설정
주요 코인들의 메타데이터를 수동으로 추가
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db_manager, CoinMaster, BithumbListing

def add_priority_metadata():
    """우선순위 코인 메타데이터 수동 추가"""
    
    # 주요 코인들 메타데이터 (CoinGecko에서 미리 수집한 데이터)
    priority_coins = [
        # 메이저 코인들
        {
            'coingecko_id': 'bitcoin',
            'symbol': 'BTC',
            'name_en': 'Bitcoin',
            'name_ko': '비트코인',
            'image_url': 'https://assets.coingecko.com/coins/images/1/large/bitcoin.png',
            'market_cap_rank': 1,
            'description': 'Bitcoin is the world\'s first cryptocurrency.',
            'homepage_url': 'https://bitcoin.org/',
            'is_active': True
        },
        {
            'coingecko_id': 'ethereum',
            'symbol': 'ETH',
            'name_en': 'Ethereum',
            'name_ko': '이더리움',
            'image_url': 'https://assets.coingecko.com/coins/images/279/large/ethereum.png',
            'market_cap_rank': 2,
            'description': 'Ethereum is a decentralized platform for smart contracts.',
            'homepage_url': 'https://ethereum.org/',
            'is_active': True
        },
        {
            'coingecko_id': 'ripple',
            'symbol': 'XRP',
            'name_en': 'XRP',
            'name_ko': '리플',
            'image_url': 'https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png',
            'market_cap_rank': 6,
            'description': 'XRP is a digital asset built for payments.',
            'homepage_url': 'https://ripple.com/xrp/',
            'is_active': True
        },
        {
            'coingecko_id': 'solana',
            'symbol': 'SOL',
            'name_en': 'Solana',
            'name_ko': '솔라나',
            'image_url': 'https://assets.coingecko.com/coins/images/4128/large/solana.png',
            'market_cap_rank': 5,
            'description': 'Solana is a high-performance blockchain supporting builders.',
            'homepage_url': 'https://solana.com/',
            'is_active': True
        },
        {
            'coingecko_id': 'dogecoin',
            'symbol': 'DOGE',
            'name_en': 'Dogecoin',
            'name_ko': '도지코인',
            'image_url': 'https://assets.coingecko.com/coins/images/5/large/dogecoin.png',
            'market_cap_rank': 8,
            'description': 'Dogecoin is a cryptocurrency featuring a Shiba Inu.',
            'homepage_url': 'https://dogecoin.com/',
            'is_active': True
        },
        {
            'coingecko_id': 'cardano',
            'symbol': 'ADA',
            'name_en': 'Cardano',
            'name_ko': '에이다',
            'image_url': 'https://assets.coingecko.com/coins/images/975/large/cardano.png',
            'market_cap_rank': 9,
            'description': 'Cardano is a research-driven blockchain platform.',
            'homepage_url': 'https://cardano.org/',
            'is_active': True
        },
        {
            'coingecko_id': 'chainlink',
            'symbol': 'LINK',
            'name_en': 'Chainlink',
            'name_ko': '체인링크',
            'image_url': 'https://assets.coingecko.com/coins/images/877/large/chainlink-new-logo.png',
            'market_cap_rank': 16,
            'description': 'Chainlink provides reliable data feeds for blockchains.',
            'homepage_url': 'https://chain.link/',
            'is_active': True
        },
        {
            'coingecko_id': 'polygon-pos',
            'symbol': 'MATIC',
            'name_en': 'Polygon',
            'name_ko': '폴리곤',
            'image_url': 'https://assets.coingecko.com/coins/images/4713/large/matic-token-icon.png',
            'market_cap_rank': 15,
            'description': 'Polygon is an Ethereum scaling solution.',
            'homepage_url': 'https://polygon.technology/',
            'is_active': True
        },
        {
            'coingecko_id': 'litecoin',
            'symbol': 'LTC',
            'name_en': 'Litecoin',
            'name_ko': '라이트코인',
            'image_url': 'https://assets.coingecko.com/coins/images/2/large/litecoin.png',
            'market_cap_rank': 20,
            'description': 'Litecoin is a peer-to-peer cryptocurrency.',
            'homepage_url': 'https://litecoin.org/',
            'is_active': True
        },
        {
            'coingecko_id': 'bitcoin-cash',
            'symbol': 'BCH',
            'name_en': 'Bitcoin Cash',
            'name_ko': '비트코인캐시',
            'image_url': 'https://assets.coingecko.com/coins/images/780/large/bitcoin-cash-circle.png',
            'market_cap_rank': 19,
            'description': 'Bitcoin Cash is a cryptocurrency.',
            'homepage_url': 'https://bitcoincash.org/',
            'is_active': True
        },
        {
            'coingecko_id': 'ethereum-classic',
            'symbol': 'ETC',
            'name_en': 'Ethereum Classic',
            'name_ko': '이더리움클래식',
            'image_url': 'https://assets.coingecko.com/coins/images/453/large/ethereum-classic-logo.png',
            'market_cap_rank': 32,
            'description': 'Ethereum Classic is the original Ethereum blockchain.',
            'homepage_url': 'https://ethereumclassic.org/',
            'is_active': True
        },
        {
            'coingecko_id': 'stellar',
            'symbol': 'XLM',
            'name_en': 'Stellar',
            'name_ko': '스텔라',
            'image_url': 'https://assets.coingecko.com/coins/images/100/large/Stellar_symbol_black_RGB.png',
            'market_cap_rank': 28,
            'description': 'Stellar is an open network for moving money.',
            'homepage_url': 'https://stellar.org/',
            'is_active': True
        },
        {
            'coingecko_id': 'tron',
            'symbol': 'TRX',
            'name_en': 'TRON',
            'name_ko': '트론',
            'image_url': 'https://assets.coingecko.com/coins/images/1094/large/tron-logo.png',
            'market_cap_rank': 24,
            'description': 'TRON is a decentralized blockchain platform.',
            'homepage_url': 'https://tron.network/',
            'is_active': True
        },
        {
            'coingecko_id': 'tether',
            'symbol': 'USDT',
            'name_en': 'Tether',
            'name_ko': '테더',
            'image_url': 'https://assets.coingecko.com/coins/images/325/large/Tether.png',
            'market_cap_rank': 3,
            'description': 'Tether is a stablecoin pegged to the US Dollar.',
            'homepage_url': 'https://tether.to/',
            'is_active': True
        },
        {
            'coingecko_id': 'usd-coin',
            'symbol': 'USDC',
            'name_en': 'USD Coin',
            'name_ko': 'USD코인',
            'image_url': 'https://assets.coingecko.com/coins/images/6319/large/USD_Coin_icon.png',
            'market_cap_rank': 4,
            'description': 'USD Coin is a fully collateralized US dollar stablecoin.',
            'homepage_url': 'https://www.centre.io/',
            'is_active': True
        },
        {
            'coingecko_id': 'shiba-inu',
            'symbol': 'SHIB',
            'name_en': 'Shiba Inu',
            'name_ko': '시바이누',
            'image_url': 'https://assets.coingecko.com/coins/images/11939/large/shiba.png',
            'market_cap_rank': 13,
            'description': 'Shiba Inu is a decentralized meme token.',
            'homepage_url': 'https://shibatoken.com/',
            'is_active': True
        }
    ]
    
    saved_count = 0
    updated_count = 0
    
    with db_manager.get_session_context() as session:
        for coin_data in priority_coins:
            try:
                # 기존 레코드 확인
                existing = session.query(CoinMaster).filter_by(
                    coingecko_id=coin_data['coingecko_id']
                ).first()
                
                if existing:
                    # 업데이트
                    for key, value in coin_data.items():
                        setattr(existing, key, value)
                    updated_count += 1
                    print(f"🔄 업데이트: {existing.symbol}({existing.name_ko})")
                else:
                    # 신규 추가
                    new_coin = CoinMaster(**coin_data)
                    session.add(new_coin)
                    saved_count += 1
                    print(f"🆕 신규 추가: {new_coin.symbol}({new_coin.name_ko})")
                
            except Exception as e:
                print(f"❌ {coin_data['symbol']} 처리 실패: {e}")
        
        session.commit()
    
    print(f"\n✅ 우선순위 메타데이터 처리 완료:")
    print(f"   신규 추가: {saved_count}개")
    print(f"   업데이트: {updated_count}개")
    
    return saved_count + updated_count

def update_bithumb_korean_names():
    """빗썸 코인들에 한글명 매핑"""
    print("\n🏪 빗썸 코인 한글명 매핑...")
    
    updated_count = 0
    
    with db_manager.get_session_context() as session:
        # 한글명이 없는 빗썸 코인들 조회
        bithumb_coins = session.query(BithumbListing).filter(
            BithumbListing.is_active == True,
            BithumbListing.korean_name.is_(None)
        ).all()
        
        for bithumb_coin in bithumb_coins:
            # coin_master에서 해당 심볼의 한글명 찾기
            coin_master = session.query(CoinMaster).filter_by(
                symbol=bithumb_coin.symbol,
                is_active=True
            ).first()
            
            if coin_master and coin_master.name_ko:
                bithumb_coin.korean_name = coin_master.name_ko
                bithumb_coin.coingecko_id = coin_master.coingecko_id
                updated_count += 1
                print(f"🔄 {bithumb_coin.symbol} → {coin_master.name_ko}")
        
        session.commit()
    
    print(f"✅ 빗썸 {updated_count}개 코인 한글명 매핑 완료")
    return updated_count

def get_metadata_summary():
    """메타데이터 현황 요약"""
    with db_manager.get_session_context() as session:
        # coin_master 통계
        total_coins = session.query(CoinMaster).filter_by(is_active=True).count()
        coins_with_korean = session.query(CoinMaster).filter(
            CoinMaster.is_active == True,
            CoinMaster.name_ko.isnot(None)
        ).count()
        coins_with_icons = session.query(CoinMaster).filter(
            CoinMaster.is_active == True,
            CoinMaster.image_url.isnot(None)
        ).count()
        
        # 빗썸 한글명 커버리지
        bithumb_total = session.query(BithumbListing).filter_by(is_active=True).count()
        bithumb_with_korean = session.query(BithumbListing).filter(
            BithumbListing.is_active == True,
            BithumbListing.korean_name.isnot(None)
        ).count()
        
        return {
            "coin_master": {
                "total_coins": total_coins,
                "korean_names": coins_with_korean,
                "korean_coverage": f"{(coins_with_korean/total_coins*100):.1f}%" if total_coins > 0 else "0%",
                "icons": coins_with_icons,
                "icon_coverage": f"{(coins_with_icons/total_coins*100):.1f}%" if total_coins > 0 else "0%"
            },
            "bithumb": {
                "total_coins": bithumb_total,
                "korean_names": bithumb_with_korean,
                "korean_coverage": f"{(bithumb_with_korean/bithumb_total*100):.1f}%" if bithumb_total > 0 else "0%"
            }
        }

def main():
    """메인 함수"""
    print("🚀 수동 메타데이터 설정 시작")
    
    try:
        # 1. 우선순위 코인 메타데이터 추가
        metadata_count = add_priority_metadata()
        
        # 2. 빗썸 한글명 매핑
        bithumb_count = update_bithumb_korean_names()
        
        # 3. 현황 요약
        summary = get_metadata_summary()
        
        print(f"\n📈 메타데이터 현황 요약:")
        print(f"   🌍 글로벌 코인: {summary['coin_master']['total_coins']}개")
        print(f"   🇰🇷 한글명: {summary['coin_master']['korean_names']}개 ({summary['coin_master']['korean_coverage']})")
        print(f"   🖼️ 아이콘: {summary['coin_master']['icons']}개 ({summary['coin_master']['icon_coverage']})")
        print(f"   🏪 빗썸 한글명: {summary['bithumb']['korean_names']}개 ({summary['bithumb']['korean_coverage']})")
        
        print(f"\n🎉 메타데이터 설정 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 메타데이터 설정 실패: {e}")
        return False

if __name__ == "__main__":
    main()