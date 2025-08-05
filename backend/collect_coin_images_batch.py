#!/usr/bin/env python3
"""
업비트/빗썸 코인 이미지 URL 배치 수집 스크립트
Rate limit을 고려한 효율적인 수집
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import db_manager, CoinMaster
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 우선 수집할 주요 코인들 (업비트/빗썸에서 인기 있는 코인들)
PRIORITY_COINS = [
    '1INCH', 'AAVE', 'ADA', 'AGLD', 'AHT', 'AIOZ', 'AKT', 'ALGO', 'ALICE', 'ALT',
    'ANKR', 'ANT', 'APE', 'API3', 'APT', 'ARB', 'ARKM', 'ARPA', 'ASTR', 'ATOM',
    'AURORA', 'AVAX', 'AXS', 'BAL', 'BAT', 'BORA', 'BSV', 'BNB', 'BLUR', 'CAKE',
    'CELR', 'CHZ', 'CKB', 'COMP', 'COTI', 'CRO', 'CRV', 'CVX', 'CTC', 'DAI',
    'DASH', 'DENT', 'DGB', 'DKA', 'DOT', 'DYDX', 'EGLD', 'ENJ', 'ENS', 'EOS',
    'ETC', 'ETHW', 'FCT2', 'FET', 'FIDA', 'FIL', 'FLOW', 'FLZ', 'FORTH', 'GALA',
    'GLM', 'GMX', 'GRT', 'GAS', 'HBAR', 'HIVE', 'HOOK', 'ICP', 'ICX', 'IMX',
    'INJ', 'IOST', 'IOTA', 'JST', 'KAVA', 'KLAY', 'KNC', 'KSM', 'LBRY', 'LDO',
    'LINK', 'LPT', 'LRC', 'LSK', 'LTC', 'LUNA', 'MANA', 'MASK', 'MATIC', 'MBL',
    'MINA', 'MKR', 'MLK', 'MOC', 'MTL', 'NEAR', 'NEO', 'NFT', 'NU', 'OGN',
    'OMG', 'ONT', 'OP', 'ORBS', 'OXT', 'PAXG', 'PENDLE', 'PLA', 'POLYX', 'POWR',
    'PYTH', 'QNT', 'QTUM', 'RDNT', 'REI', 'REN', 'REP', 'RLC', 'RSR', 'SAND',
    'SEI', 'SHIB', 'SIX', 'SKL', 'SNT', 'SNX', 'SOL', 'SRM', 'STEEM', 'STORJ',
    'STRK', 'STX', 'SUI', 'SUSHI', 'SXP', 'T', 'TFUEL', 'THETA', 'TIA', 'TON',
    'TRB', 'TRX', 'UMA', 'UNI', 'USDC', 'USDT', 'VET', 'WAXP', 'WEMIX', 'XEC',
    'XEM', 'XLM', 'XRP', 'XTZ', 'YFI', 'ZEC', 'ZIL', 'ZRX'
]

class FastCoinImageCollector:
    """빠른 코인 이미지 수집기"""
    
    def __init__(self):
        self.session = None
        
        # 직접 매핑된 주요 코인들의 CoinGecko ID
        self.known_mappings = {
            '1INCH': '1inch',
            'AAVE': 'aave',
            'ADA': 'cardano',
            'AGLD': 'adventure-gold',
            'AHT': 'ahatoken',
            'AIOZ': 'aioz-network',
            'AKT': 'akash-network',
            'ALGO': 'algorand',
            'ALICE': 'alice',
            'ALT': 'altbase',
            'ANKR': 'ankr',
            'ANT': 'aragon',
            'APE': 'apecoin',
            'API3': 'api3',
            'APT': 'aptos',
            'ARB': 'arbitrum',
            'ARKM': 'arkham',
            'ARPA': 'arpa-chain',
            'ASTR': 'astar',
            'ATOM': 'cosmos',
            'AURORA': 'aurora-near',
            'AVAX': 'avalanche-2',
            'AXS': 'axie-infinity',
            'BAL': 'balancer',
            'BAT': 'basic-attention-token',
            'BORA': 'bora',
            'BSV': 'bitcoin-cash-sv',
            'BNB': 'binancecoin',
            'BLUR': 'blur',
            'CAKE': 'pancakeswap-token',
            'CELR': 'celer-network',
            'CHZ': 'chiliz',
            'CKB': 'nervos-network',
            'COMP': 'compound-governance-token',
            'COTI': 'coti',
            'CRO': 'crypto-com-chain',
            'CRV': 'curve-dao-token',
            'CVX': 'convex-finance',
            'DAI': 'dai',
            'DASH': 'dash',
            'DENT': 'dent',
            'DGB': 'digibyte',
            'DOT': 'polkadot',
            'DYDX': 'dydx',
            'EGLD': 'elrond-erd-2',
            'ENJ': 'enjincoin',
            'ENS': 'ethereum-name-service',
            'EOS': 'eos',
            'ETC': 'ethereum-classic',
            'FET': 'fetch-ai',
            'FIL': 'filecoin',
            'FLOW': 'flow',
            'GALA': 'gala',
            'GLM': 'golem',
            'GMX': 'gmx',
            'GRT': 'the-graph',
            'GAS': 'gas',
            'HBAR': 'hedera-hashgraph',
            'HIVE': 'hive',
            'ICP': 'internet-computer',
            'ICX': 'icon',
            'IMX': 'immutable-x',
            'INJ': 'injective-protocol',
            'IOST': 'iostoken',
            'IOTA': 'iota',
            'JST': 'just',
            'KAVA': 'kava',
            'KLAY': 'klaytn',
            'KNC': 'kyber-network-crystal',
            'KSM': 'kusama',
            'LDO': 'lido-dao',
            'LINK': 'chainlink',
            'LPT': 'livepeer',
            'LRC': 'loopring',
            'LSK': 'lisk',
            'LTC': 'litecoin',
            'LUNA': 'terra-luna-2',
            'MANA': 'decentraland',
            'MASK': 'mask-network',
            'MATIC': 'matic-network',
            'MINA': 'mina-protocol',
            'MKR': 'maker',
            'MTL': 'metal',
            'NEAR': 'near',
            'NEO': 'neo',
            'NU': 'nucypher',
            'OGN': 'origin-protocol',
            'OMG': 'omisego',
            'ONT': 'ontology',
            'OP': 'optimism',
            'ORBS': 'orbs',
            'PAXG': 'pax-gold',
            'PENDLE': 'pendle',
            'PLA': 'playdapp',
            'POLYX': 'polymesh',
            'POWR': 'power-ledger',
            'PYTH': 'pyth-network',
            'QNT': 'quant-network',
            'QTUM': 'qtum',
            'REN': 'republic-protocol',
            'REP': 'augur',
            'RLC': 'iexec-rlc',
            'RSR': 'reserve-rights-token',
            'SAND': 'the-sandbox',
            'SEI': 'sei-network',
            'SHIB': 'shiba-inu',
            'SKL': 'skale',
            'SNT': 'status',
            'SNX': 'havven',
            'SOL': 'solana',
            'SRM': 'serum',
            'STEEM': 'steem',
            'STORJ': 'storj',
            'STX': 'blockstack',
            'SUI': 'sui',
            'SUSHI': 'sushi',
            'SXP': 'swipe',
            'TFUEL': 'theta-fuel',
            'THETA': 'theta-token',
            'TIA': 'celestia',
            'TON': 'the-open-network',
            'TRB': 'tellor',
            'TRX': 'tron',
            'UMA': 'uma',
            'UNI': 'uniswap',
            'USDC': 'usd-coin',
            'USDT': 'tether',
            'VET': 'vechain',
            'WAXP': 'wax',
            'WEMIX': 'wemix-token',
            'XEC': 'ecash',
            'XEM': 'nem',
            'XLM': 'stellar',
            'XRP': 'ripple',
            'XTZ': 'tezos',
            'YFI': 'yearn-finance',
            'ZEC': 'zcash',
            'ZIL': 'zilliqa',
            'ZRX': '0x'
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "ArbitrageWebsite-FastImageCollector/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def get_coin_details_batch(self, coin_ids: list):
        """여러 코인의 상세 정보를 배치로 조회"""
        logger.info(f"🎯 {len(coin_ids)}개 코인 상세 정보 조회...")
        
        coin_details = []
        
        for coin_id in coin_ids:
            try:
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                async with self.session.get(url) as response:
                    if response.status == 200:
                        coin_data = await response.json()
                        details = {
                            'id': coin_data['id'],
                            'symbol': coin_data['symbol'].upper(),
                            'name': coin_data['name'],
                            'image_url': coin_data.get('image', {}).get('large', ''),
                            'market_cap_rank': coin_data.get('market_cap_rank'),
                            'description': coin_data.get('description', {}).get('en', '')[:500] if coin_data.get('description', {}).get('en') else ''
                        }
                        
                        if details['image_url']:
                            coin_details.append(details)
                            logger.info(f"✅ {details['symbol']}: {details['image_url']}")
                        else:
                            logger.warning(f"⚠️ {details['symbol']}: 이미지 URL 없음")
                            
                    elif response.status == 429:
                        logger.warning(f"⏸️ Rate limit reached for {coin_id}")
                        await asyncio.sleep(5)
                    else:
                        logger.warning(f"⚠️ {coin_id} 조회 실패: {response.status}")
                
                # Rate limiting 방지
                await asyncio.sleep(1.2)  # 1.2초 대기
                
            except Exception as e:
                logger.warning(f"⚠️ {coin_id} 조회 오류: {e}")
                continue
        
        return coin_details
    
    def save_coin_images(self, coin_details: list):
        """코인 이미지를 데이터베이스에 저장"""
        logger.info(f"💾 {len(coin_details)}개 코인 이미지 저장...")
        
        saved_count = 0
        updated_count = 0
        failed_count = 0
        
        with db_manager.get_session_context() as session:
            for coin in coin_details:
                try:
                    # 기존 레코드 확인
                    existing_coin = session.query(CoinMaster).filter_by(
                        symbol=coin['symbol'],
                        is_active=True
                    ).first()
                    
                    if existing_coin:
                        # 기존 레코드 업데이트
                        if not existing_coin.image_url or existing_coin.image_url != coin['image_url']:
                            existing_coin.image_url = coin['image_url']
                            existing_coin.updated_at = datetime.now()
                            updated_count += 1
                            logger.info(f"🔄 {coin['symbol']}: 이미지 URL 업데이트")
                    else:
                        # 새 레코드 생성
                        new_coin = CoinMaster(
                            coingecko_id=coin['id'],
                            symbol=coin['symbol'],
                            name_en=coin['name'],
                            image_url=coin['image_url'],
                            market_cap_rank=coin['market_cap_rank'],
                            description=coin['description'],
                            is_active=True,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        session.add(new_coin)
                        saved_count += 1
                        logger.info(f"💾 {coin['symbol']}: 새 레코드 생성")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ {coin['symbol']} 저장 실패: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"✅ 저장 완료: {saved_count}개 신규, {updated_count}개 업데이트, {failed_count}개 실패")
        return saved_count + updated_count

async def main():
    """메인 실행 함수"""
    try:
        logger.info("🚀 빠른 코인 이미지 수집 시작")
        start_time = time.time()
        
        async with FastCoinImageCollector() as collector:
            # 우선순위 코인들의 CoinGecko ID 수집
            priority_coin_ids = []
            for symbol in PRIORITY_COINS:
                if symbol in collector.known_mappings:
                    priority_coin_ids.append(collector.known_mappings[symbol])
            
            logger.info(f"📋 우선 수집 대상: {len(priority_coin_ids)}개 코인")
            
            # 배치로 코인 정보 수집
            coin_details = await collector.get_coin_details_batch(priority_coin_ids)
            
            if coin_details:
                # 데이터베이스에 저장
                saved_count = collector.save_coin_images(coin_details)
                
                elapsed_time = time.time() - start_time
                logger.info(f"🎉 완료! {saved_count}개 코인 이미지 수집 (소요시간: {elapsed_time:.1f}초)")
                return True
            else:
                logger.warning("⚠️ 수집된 코인 이미지가 없습니다.")
                return False
                
    except Exception as e:
        logger.error(f"❌ 코인 이미지 수집 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(main())