#!/usr/bin/env python3
"""
선택적 코인 이미지 URL 업데이트 스크립트
DB에 존재하지만 image_url이 null인 코인들만 순차적으로 업데이트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from datetime import datetime
from core import db_manager, CoinMaster
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 추가할 코인 이미지 URL 목록 (DB에 있지만 image_url이 null인 것들)
ADDITIONAL_COIN_IMAGES = {
    # 업비트/빗썸 주요 코인들 중 누락된 것들
    'AAVE': 'https://coin-images.coingecko.com/coins/images/12645/large/aave-token-round.png',
    'AGLD': 'https://coin-images.coingecko.com/coins/images/18125/large/lpgblc4h_400x400.jpg',
    'AHT': 'https://coin-images.coingecko.com/coins/images/12158/large/2022_ahatoken.jpg',
    'AIOZ': 'https://coin-images.coingecko.com/coins/images/14631/large/aioz-logo-200.png',
    'AKT': 'https://coin-images.coingecko.com/coins/images/12785/large/akash-logo.png',
    'ALGO': 'https://coin-images.coingecko.com/coins/images/4380/large/download.png',
    'ALICE': 'https://coin-images.coingecko.com/coins/images/14375/large/alice_logo.jpg',
    'ALT': 'https://coin-images.coingecko.com/coins/images/33077/large/altlayer.jpeg',
    'ANKR': 'https://coin-images.coingecko.com/coins/images/12866/large/ankr.jpg',
    'ANT': 'https://coin-images.coingecko.com/coins/images/681/large/JelZ58cv_400x400.png',
    'APE': 'https://coin-images.coingecko.com/coins/images/24383/large/apecoin.jpg',
    'API3': 'https://coin-images.coingecko.com/coins/images/13256/large/api3.jpg',
    'APT': 'https://coin-images.coingecko.com/coins/images/26455/large/aptos_round.png',
    'ARB': 'https://coin-images.coingecko.com/coins/images/16547/large/arb.jpg',
    'ARKM': 'https://coin-images.coingecko.com/coins/images/30929/large/Arkham_Logo_CG.png',
    'ARPA': 'https://coin-images.coingecko.com/coins/images/8506/large/9u0a23XY_400x400.jpg',
    'ASTR': 'https://coin-images.coingecko.com/coins/images/17233/large/astar-logo.png',
    'ATOM': 'https://coin-images.coingecko.com/coins/images/1481/large/cosmos_hub.png',
    'AURORA': 'https://coin-images.coingecko.com/coins/images/20582/large/aurora.jpeg',
    'AVAX': 'https://coin-images.coingecko.com/coins/images/12559/large/Avalanche_Circle_RedWhite_Trans.png',
    'AXS': 'https://coin-images.coingecko.com/coins/images/13029/large/axie_infinity_logo.png',
    'BAL': 'https://coin-images.coingecko.com/coins/images/11683/large/Balancer.png',
    'BAT': 'https://coin-images.coingecko.com/coins/images/677/large/basic-attention-token.png',
    'BORA': 'https://coin-images.coingecko.com/coins/images/7646/large/bora.png',
    'BSV': 'https://coin-images.coingecko.com/coins/images/6799/large/BSV.png',
    'BNB': 'https://coin-images.coingecko.com/coins/images/825/large/bnb-icon2_2x.png',
    'BLUR': 'https://coin-images.coingecko.com/coins/images/28453/large/blur.png',
    'CAKE': 'https://coin-images.coingecko.com/coins/images/12632/large/pancakeswap-cake-logo_.png',
    'CELR': 'https://coin-images.coingecko.com/coins/images/4379/large/Celr.png',
    'CHZ': 'https://coin-images.coingecko.com/coins/images/8834/large/Chiliz.png',
    'CKB': 'https://coin-images.coingecko.com/coins/images/9566/large/nervos.png',
    'COMP': 'https://coin-images.coingecko.com/coins/images/10775/large/COMP.png',
    'COTI': 'https://coin-images.coingecko.com/coins/images/8382/large/coti.png',
    'CRO': 'https://coin-images.coingecko.com/coins/images/7310/large/cro_token_logo.png',
    'CRV': 'https://coin-images.coingecko.com/coins/images/12124/large/Curve.png',
    'CVX': 'https://coin-images.coingecko.com/coins/images/15585/large/convex.png',
    'DAI': 'https://coin-images.coingecko.com/coins/images/9956/large/4943.png',
    'DASH': 'https://coin-images.coingecko.com/coins/images/19/large/dash-logo.png',
    'DENT': 'https://coin-images.coingecko.com/coins/images/1152/large/gLCBBlS__400x400.jpg',
    'DGB': 'https://coin-images.coingecko.com/coins/images/63/large/digibyte.png',
    'DOT': 'https://coin-images.coingecko.com/coins/images/12171/large/polkadot.png',
    'DYDX': 'https://coin-images.coingecko.com/coins/images/17500/large/hjnIm9bV.jpg',
    'EGLD': 'https://coin-images.coingecko.com/coins/images/12335/large/EGLD_symbol.png',
    'ENJ': 'https://coin-images.coingecko.com/coins/images/1102/large/enjin-coin-logo.png',
    'ENS': 'https://coin-images.coingecko.com/coins/images/19785/large/acatxTm8_400x400.jpg',
    'EOS': 'https://coin-images.coingecko.com/coins/images/738/large/eos-eos-logo.png',
    'FET': 'https://coin-images.coingecko.com/coins/images/5681/large/Fetch.jpg',
    'FIL': 'https://coin-images.coingecko.com/coins/images/12817/large/filecoin.png',
    'FLOW': 'https://coin-images.coingecko.com/coins/images/13446/large/5f6294c0c7a8cda55cb1c936_Flow_Wordmark.png',
    'GALA': 'https://coin-images.coingecko.com/coins/images/17014/large/GALA-COINGECKO.png',
    'GLM': 'https://coin-images.coingecko.com/coins/images/542/large/Golem_Submark_Positive_RGB.png',
    'GMX': 'https://coin-images.coingecko.com/coins/images/18323/large/arbit.png',
    'GRT': 'https://coin-images.coingecko.com/coins/images/13397/large/Graph_Token.png',
    'GAS': 'https://coin-images.coingecko.com/coins/images/4480/large/gas.png',
    'HBAR': 'https://coin-images.coingecko.com/coins/images/3688/large/hbar.png',
    'HIVE': 'https://coin-images.coingecko.com/coins/images/10840/large/logo_transparent.png',
    'ICP': 'https://coin-images.coingecko.com/coins/images/14495/large/Internet_Computer_logo.png',
    'ICX': 'https://coin-images.coingecko.com/coins/images/1060/large/iconfoundation-logo-1200x1200.png',
    'INJ': 'https://coin-images.coingecko.com/coins/images/12882/large/Secondary_Symbol.png',
    'IOST': 'https://coin-images.coingecko.com/coins/images/2468/large/IOST.png',
    'IOTA': 'https://coin-images.coingecko.com/coins/images/692/large/IOTA_Swirl.png',
    'JST': 'https://coin-images.coingecko.com/coins/images/11095/large/JUST_icon.png',
    'KAVA': 'https://coin-images.coingecko.com/coins/images/9761/large/kava.png',
    'KLAY': 'https://coin-images.coingecko.com/coins/images/9672/large/klaytn.png',
    'KNC': 'https://coin-images.coingecko.com/coins/images/14899/large/RwdVsGcw_400x400.jpg',
    'KSM': 'https://coin-images.coingecko.com/coins/images/12747/large/kusama.png',
    'LDO': 'https://coin-images.coingecko.com/coins/images/13573/large/Lido_DAO.png',
    'LPT': 'https://coin-images.coingecko.com/coins/images/7137/large/logo-circle-green.png',
    'LRC': 'https://coin-images.coingecko.com/coins/images/913/large/LRC.png',
    'LSK': 'https://coin-images.coingecko.com/coins/images/385/large/Lisk_Symbol_-_Blue.png',
    'LUNA': 'https://coin-images.coingecko.com/coins/images/25767/large/01_Luna_color.png',
    'MANA': 'https://coin-images.coingecko.com/coins/images/878/large/decentraland-mana.png',
    'MASK': 'https://coin-images.coingecko.com/coins/images/14051/large/Mask_Network.jpg',
    'MINA': 'https://coin-images.coingecko.com/coins/images/15628/large/JM4_vQ34_400x400.png',
    'MKR': 'https://coin-images.coingecko.com/coins/images/1364/large/Mark_Maker.png',
    'MTL': 'https://coin-images.coingecko.com/coins/images/763/large/Metal.png',
    'NEAR': 'https://coin-images.coingecko.com/coins/images/10365/large/near_icon.png',
    'NEO': 'https://coin-images.coingecko.com/coins/images/480/large/NEO_512_512.png',
    'NU': 'https://coin-images.coingecko.com/coins/images/3318/large/photo1198982838879365035.jpg',
    'OGN': 'https://coin-images.coingecko.com/coins/images/3296/large/op.jpg',
    'OMG': 'https://coin-images.coingecko.com/coins/images/776/large/OMG_Network.jpg',
    'ONT': 'https://coin-images.coingecko.com/coins/images/3447/large/ONT.png',
    'OP': 'https://coin-images.coingecko.com/coins/images/25244/large/Optimism.png',
    'ORBS': 'https://coin-images.coingecko.com/coins/images/4630/large/Orbs.jpg',
    'PAXG': 'https://coin-images.coingecko.com/coins/images/9519/large/paxgold.png',
    'PENDLE': 'https://coin-images.coingecko.com/coins/images/15069/large/Pendle_Logo_Normal-03.png',
    'PLA': 'https://coin-images.coingecko.com/coins/images/14316/large/54023228.png',
    'POLYX': 'https://coin-images.coingecko.com/coins/images/17537/large/POLYX.png',
    'POWR': 'https://coin-images.coingecko.com/coins/images/1104/large/power-ledger.png',
    'PYTH': 'https://coin-images.coingecko.com/coins/images/31557/large/pyth.png',
    'QNT': 'https://coin-images.coingecko.com/coins/images/3370/large/5ZOu7brX_400x400.jpg',
    'QTUM': 'https://coin-images.coingecko.com/coins/images/684/large/qtum.png',
    'REN': 'https://coin-images.coingecko.com/coins/images/3139/large/REN.png',
    'REP': 'https://coin-images.coingecko.com/coins/images/309/large/REP.png',
    'RLC': 'https://coin-images.coingecko.com/coins/images/646/large/pL1VuXm.png',
    'RSR': 'https://coin-images.coingecko.com/coins/images/8365/large/rsr.png',
    'SAND': 'https://coin-images.coingecko.com/coins/images/12129/large/sandbox_logo.jpg',
    'SEI': 'https://coin-images.coingecko.com/coins/images/28205/large/Sei_Logo_-_Transparent.png',
    'SKL': 'https://coin-images.coingecko.com/coins/images/13245/large/SKALE_token_300x300.png',
    'SNT': 'https://coin-images.coingecko.com/coins/images/779/large/status.png',
    'SNX': 'https://coin-images.coingecko.com/coins/images/3406/large/SNX.png',
    'SRM': 'https://coin-images.coingecko.com/coins/images/11970/large/serum-logo.png',
    'STEEM': 'https://coin-images.coingecko.com/coins/images/487/large/steem.png',
    'STORJ': 'https://coin-images.coingecko.com/coins/images/949/large/storj.png',
    'SUI': 'https://coin-images.coingecko.com/coins/images/26375/large/sui_asset.jpeg',
    'SUSHI': 'https://coin-images.coingecko.com/coins/images/12271/large/512x512_Logo_no_chop.png',
    'SXP': 'https://coin-images.coingecko.com/coins/images/11794/large/SwipeToken.png',
    'TFUEL': 'https://coin-images.coingecko.com/coins/images/8029/large/1_0YusgngOrriVg4yYfsC-bg.png',
    'THETA': 'https://coin-images.coingecko.com/coins/images/2538/large/theta-token-logo.png',
    'TIA': 'https://coin-images.coingecko.com/coins/images/31967/large/tia.jpg',
    'TON': 'https://coin-images.coingecko.com/coins/images/17980/large/ton_symbol.png',
    'TRB': 'https://coin-images.coingecko.com/coins/images/9644/large/Blk_icon_current.png',
    'UMA': 'https://coin-images.coingecko.com/coins/images/10951/large/UMA.png',
    'UNI': 'https://coin-images.coingecko.com/coins/images/12504/large/uni.jpg',
    'VET': 'https://coin-images.coingecko.com/coins/images/1077/large/VeChain-Logo-768x725.png',
    'WAXP': 'https://coin-images.coingecko.com/coins/images/10481/large/WAX_Coin.png',
    'WEMIX': 'https://coin-images.coingecko.com/coins/images/12998/large/wemixcoin_symbol_color.png',
    'XEC': 'https://coin-images.coingecko.com/coins/images/16646/large/Logo_final-04.png',
    'XEM': 'https://coin-images.coingecko.com/coins/images/242/large/NEM_WC_Logo.png',
    'XTZ': 'https://coin-images.coingecko.com/coins/images/976/large/Tezos-logo.png',
    'YFI': 'https://coin-images.coingecko.com/coins/images/11849/large/yearn.jpg',
    'ZEC': 'https://coin-images.coingecko.com/coins/images/486/large/circle-zcash-color.png',
    'ZIL': 'https://coin-images.coingecko.com/coins/images/2687/large/Zilliqa-logo.png',
    'ZRX': 'https://coin-images.coingecko.com/coins/images/863/large/0x.png'
}

def get_coins_missing_images():
    """이미지 URL이 null인 코인들 조회"""
    logger.info("🔍 이미지 URL이 없는 코인들 조회...")
    
    with db_manager.get_session_context() as session:
        # CoinMaster에서 image_url이 null이거나 빈 문자열인 코인들
        missing_coins = session.query(CoinMaster).filter(
            CoinMaster.is_active == True,
            (CoinMaster.image_url.is_(None) | (CoinMaster.image_url == ''))
        ).all()
        
        missing_symbols = [coin.symbol for coin in missing_coins]
        logger.info(f"📊 이미지 URL이 필요한 코인: {len(missing_symbols)}개")
        logger.info(f"📋 처음 10개: {missing_symbols[:10]}")
        
        return missing_symbols

def selective_update_images():
    """DB에 존재하지만 image_url이 null인 코인들만 선택적으로 업데이트"""
    logger.info("🎯 선택적 이미지 URL 업데이트 시작...")
    
    # 1. 누락된 코인들 조회
    missing_symbols = get_coins_missing_images()
    
    if not missing_symbols:
        logger.info("✅ 모든 코인이 이미지 URL을 가지고 있습니다!")
        return 0
    
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
    with db_manager.get_session_context() as session:
        for symbol in missing_symbols:
            try:
                # 추가할 이미지 URL이 있는지 확인
                if symbol in ADDITIONAL_COIN_IMAGES:
                    image_url = ADDITIONAL_COIN_IMAGES[symbol]
                    
                    # 기존 레코드 찾기
                    existing_coin = session.query(CoinMaster).filter_by(
                        symbol=symbol,
                        is_active=True
                    ).first()
                    
                    if existing_coin:
                        # image_url이 null이거나 빈 문자열인 경우만 업데이트
                        if not existing_coin.image_url or existing_coin.image_url.strip() == '':
                            existing_coin.image_url = image_url
                            existing_coin.updated_at = datetime.now()
                            updated_count += 1
                            logger.info(f"✅ {symbol}: 이미지 URL 업데이트 완료")
                        else:
                            skipped_count += 1
                            logger.info(f"⏭️ {symbol}: 이미지 URL 이미 존재, 건너뜀")
                    else:
                        logger.warning(f"⚠️ {symbol}: DB에 레코드가 없음")
                        failed_count += 1
                else:
                    logger.info(f"📝 {symbol}: 추가할 이미지 URL이 준비되지 않음")
                    skipped_count += 1
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ {symbol} 처리 실패: {e}")
                continue
        
        # 변경사항 커밋
        session.commit()
    
    logger.info(f"\\n✅ 선택적 이미지 URL 업데이트 완료:")
    logger.info(f"   🔄 업데이트: {updated_count}개")
    logger.info(f"   ⏭️ 건너뜀: {skipped_count}개")
    logger.info(f"   ❌ 실패: {failed_count}개")
    
    return updated_count

def verify_final_results():
    """최종 결과 검증"""
    logger.info("🔍 최종 결과 검증...")
    
    with db_manager.get_session_context() as session:
        # 전체 활성 코인 수
        total_coins = session.query(CoinMaster).filter_by(is_active=True).count()
        
        # 이미지 URL이 있는 코인 수
        coins_with_images = session.query(CoinMaster).filter(
            CoinMaster.image_url.isnot(None),
            CoinMaster.image_url != '',
            CoinMaster.is_active == True
        ).count()
        
        # 업비트/빗썸 코인 중 이미지가 있는 것들
        upbit_bithumb_with_images = session.execute(text('''
            SELECT COUNT(DISTINCT cm.symbol)
            FROM coin_master cm
            WHERE cm.is_active = true 
            AND cm.image_url IS NOT NULL 
            AND cm.image_url != ''
            AND cm.symbol IN (
                SELECT u.symbol FROM upbit_listings u WHERE u.is_active = true
                UNION
                SELECT b.symbol FROM bithumb_listings b WHERE b.is_active = true
            )
        ''')).scalar()
        
        # 업비트/빗썸 전체 코인 수
        total_upbit_bithumb = session.execute(text('''
            SELECT COUNT(DISTINCT symbol)
            FROM (
                SELECT u.symbol FROM upbit_listings u WHERE u.is_active = true
                UNION
                SELECT b.symbol FROM bithumb_listings b WHERE b.is_active = true
            ) AS all_coins
        ''')).scalar()
        
        logger.info(f"\\n📊 최종 결과:")
        logger.info(f"   전체 활성 코인: {total_coins}개")
        logger.info(f"   이미지 URL 보유: {coins_with_images}개")
        logger.info(f"   전체 커버리지: {coins_with_images/total_coins*100:.1f}%")
        logger.info(f"\\n🎯 업비트/빗썸 코인:")
        logger.info(f"   전체 코인: {total_upbit_bithumb}개")
        logger.info(f"   이미지 보유: {upbit_bithumb_with_images}개")
        logger.info(f"   커버리지: {upbit_bithumb_with_images/total_upbit_bithumb*100:.1f}%")

def main():
    """메인 실행 함수"""
    try:
        logger.info("🚀 선택적 코인 이미지 URL 업데이트 시작")
        
        # 선택적 업데이트 실행
        updated_count = selective_update_images()
        
        # 최종 결과 검증
        verify_final_results()
        
        logger.info(f"🎉 완료! {updated_count}개 코인 이미지 URL 업데이트됨")
        return True
        
    except Exception as e:
        logger.error(f"❌ 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()