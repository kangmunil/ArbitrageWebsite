#!/usr/bin/env python3
"""
업비트 API로부터 코인 한글명을 가져와서 데이터베이스에 동기화하는 스크립트

Usage:
    python sync_coin_names.py
"""

import requests
import logging
from typing import Optional
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from .database import get_db
from .models import Cryptocurrency

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 업비트에 없는 코인들을 위한 하드코딩 매핑 테이블
HARDCODED_KOREAN_NAMES = {
    'BTC': '비트코인',
    'ETH': '이더리움',
    'XRP': '엑스알피(리플)',
    'SOL': '솔라나',
    'ADA': '에이다',
    'DOT': '폴카닷', 
    'LINK': '체인링크',
    'UNI': '유니스왑',
    'AVAX': '아발란체',
    'MATIC': '폴리곤',
    'ATOM': '코스모스',
    'NEAR': '니어프로토콜',
    'FTM': '팬텀',
    'ALGO': '알고랜드',
    'VET': '비체인',
    'ICP': '인터넷컴퓨터',
    'FIL': '파일코인',
    'TRX': '트론',
    'ETC': '이더리움클래식',
    'XLM': '스텔라루멘',
    'HBAR': '헤데라',
    'FLOW': '플로우',
    'THETA': '세타토큰',
    'XTZ': '테조스',
    'ENJ': '엔진코인',
    'CHZ': '칠리즈',
    'MANA': '디센트럴랜드',
    'SAND': '더샌드박스',
    'CRV': '커브다오토큰',
    'ZIL': '질리카',
    'SXP': '스와이프',
    'BAT': '베이직어텐션토큰',
    'ICX': '아이콘',
    'ONT': '온톨로지',
    'ZRX': '제로엑스',
    'OMG': '오미세고',
    'LRC': '루프링',
    'REP': '어거',
    'KNC': '카이버네트워크',
    'COMP': '컴파운드',
    'MKR': '메이커',
    'SNX': '신세틱스',
    'YFI': '연파이낸스',
    '1INCH': '1인치네트워크',
    'SUSHI': '스시스왑',
    'AAVE': '에이브',
    'GRT': '더그래프',
    'FTT': 'FTX토큰',
    'DOGE': '도지코인',
    'SHIB': '시바이누',
    'BONK': '봉크',
    'PEPE': '페페',
    'XEC': '이캐시',
    'FLOKI': '플로키',
    'WIF': '도그위드햇',
}

def fetch_upbit_korean_names():
    """업비트 API에서 모든 KRW 마켓 코인의 한글명을 가져옵니다.

    업비트의 `market/all` 엔드포인트를 호출하여 KRW 마켓에 상장된 코인들의
    심볼과 한글명 매핑 딕셔너리를 생성하여 반환합니다.

    Returns:
        dict: 코인 심볼(예: 'BTC')을 키로 하고 한글명(예: '비트코인')을 값으로 하는 딕셔너리.
              API 호출 실패 시 빈 딕셔너리를 반환합니다.
    """
    try:
        url = "https://api.upbit.com/v1/market/all"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        korean_names = {}
        for item in data:
            # KRW 마켓만 처리
            if item['market'].startswith('KRW-'):
                symbol = item['market'].split('-')[1]
                korean_names[symbol] = item['korean_name']
        
        logger.info(f"업비트에서 {len(korean_names)}개 코인의 한글명을 가져왔습니다.")
        return korean_names
        
    except requests.exceptions.RequestException as e:
        logger.error(f"업비트 API 호출 오류: {e}")
        return {}

def sync_cryptocurrency_names():
    """
    업비트 API와 하드코딩 테이블의 데이터를 데이터베이스와 동기화합니다.
    """
    # 업비트 API에서 한글명 가져오기
    upbit_names = fetch_upbit_korean_names()
    
    # 하드코딩 테이블과 합치기 (업비트 데이터가 우선)
    all_names = HARDCODED_KOREAN_NAMES.copy()
    all_names.update(upbit_names)
    
    logger.info(f"총 {len(all_names)}개 코인의 한글명을 동기화합니다.")
    
    # 데이터베이스 세션 생성
    db = next(get_db())
    
    try:
        updated_count = 0
        created_count = 0
        
        for symbol, korean_name in all_names.items():
            # 기존 데이터 확인
            existing_crypto: Optional[Cryptocurrency] = db.query(Cryptocurrency).filter(
                Cryptocurrency.symbol == symbol
            ).first()
            
            if existing_crypto is not None:  # type: ignore
                # 기존 데이터 업데이트
                if str(existing_crypto.name_ko) != korean_name:
                    setattr(existing_crypto, 'name_ko', korean_name)
                    updated_count += 1
                    logger.info(f"업데이트: {symbol} -> {korean_name}")
            else:
                # 새 데이터 생성
                new_crypto = Cryptocurrency(
                    crypto_id=f"crypto_{symbol.lower()}",
                    symbol=symbol,
                    name_ko=korean_name,
                    name_en=symbol,  # 영문명은 일단 심볼로 설정
                    is_active=True
                )
                db.add(new_crypto)
                created_count += 1
                logger.info(f"생성: {symbol} -> {korean_name}")
        
        # 변경사항 커밋
        db.commit()
        
        logger.info(f"동기화 완료: {created_count}개 생성, {updated_count}개 업데이트")
        
    except Exception as e:
        db.rollback()
        logger.error(f"데이터베이스 동기화 오류: {e}")
        raise
    finally:
        db.close()

def main():
    """코인 한글명 동기화 프로세스의 메인 진입점입니다.

    `sync_cryptocurrency_names` 함수를 호출하여 데이터베이스와 코인 한글명을 동기화하고,
    시작 및 완료 로그를 출력합니다.
    """
    logger.info("코인 한글명 동기화를 시작합니다...")
    sync_cryptocurrency_names()
    logger.info("동기화가 완료되었습니다.")

if __name__ == "__main__":
    main()