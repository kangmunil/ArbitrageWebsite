# 암호화폐 거래소 데이터 수집 시스템

이 디렉토리는 9개 거래소(한국 2개, 해외 7개)에서 실시간 가격 데이터를 수집하고 김치프리미엄을 계산하는 시스템입니다.

## 📁 파일 구조

```
collectors/
├── README.md                           # 이 파일
├── requirements.txt                    # Python 의존성
├── korean_exchange_collector.py        # 한국 거래소 (업비트, 빗썸) 수집
├── coingecko_metadata_collector.py     # CoinGecko 메타데이터 수집
├── manual_metadata_setup.py           # 수동 메타데이터 설정
├── ccxt_price_collector.py            # CCXT 기반 9개 거래소 가격 수집 ⭐
├── kimchi_premium_calculator.py       # 김치프리미엄 계산기 ⭐
├── setup_exchange_registry.py         # 거래소 등록 정보 설정
├── test_complete_system.py            # 전체 시스템 통합 테스트 ⭐
└── test_metadata_collection.py        # 메타데이터 수집 테스트
```

## 🚀 주요 기능

### 1. 거래소 데이터 수집
- **한국 거래소**: 업비트, 빗썸 (KRW 기준)
- **해외 거래소**: Binance, Bybit, OKX, Gate.io, Bitget, MEXC, Coinbase (USD/USDT 기준)
- **수집 데이터**: 실시간 가격, 24시간 거래량, 가격 변화율

### 2. 메타데이터 관리
- **코인 정보**: CoinGecko ID, 심볼, 영문명, 한글명
- **아이콘**: CoinGecko에서 코인 아이콘 URL 자동 수집
- **한글명**: 업비트 API 직접 수집, 빗썸은 CoinGecko 매핑

### 3. 김치프리미엄 계산
- **실시간 계산**: 국내 평균가 vs 해외 평균가 비교
- **환율 반영**: USD/KRW 환율 실시간 조회 및 적용
- **데이터 검증**: 비정상적인 프리미엄 필터링

## 📊 데이터베이스 스키마

### 핵심 테이블
- `coin_master`: 코인 메타데이터 (CoinGecko ID 기준)
- `upbit_listings`: 업비트 상장 코인 (한글명 포함)
- `bithumb_listings`: 빗썸 상장 코인
- `exchange_registry`: 거래소 등록 정보
- `price_snapshots`: 실시간 가격 데이터
- `kimchi_premium`: 김치프리미엄 계산 결과
- `exchange_rates`: 환율 정보

## 🔧 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r collectors/requirements.txt
```

### 2. 환경 설정
```bash
# core/config.py에서 데이터베이스 설정 확인
# MySQL 데이터베이스 준비
# CoinGecko API 키 설정 (선택사항)
```

### 3. 단계별 실행

#### 3.1 거래소 등록 설정
```bash
cd collectors
python setup_exchange_registry.py
```

#### 3.2 한국 거래소 데이터 수집
```bash
python korean_exchange_collector.py
```

#### 3.3 메타데이터 설정
```bash
python manual_metadata_setup.py
```

#### 3.4 CCXT 가격 수집
```bash
python ccxt_price_collector.py
```

#### 3.5 김치프리미엄 계산
```bash
python kimchi_premium_calculator.py
```

### 4. 전체 시스템 테스트
```bash
python test_complete_system.py
```

## 📋 사용 예시

### CCXT 가격 수집기 사용
```python
import asyncio
from ccxt_price_collector import CCXTPriceCollector

async def collect_prices():
    async with CCXTPriceCollector() as collector:
        result = await collector.run_collection_cycle()
        print(f"수집된 가격: {result['total_prices']}개")

asyncio.run(collect_prices())
```

### 김치프리미엄 계산기 사용
```python
import asyncio
from kimchi_premium_calculator import KimchiPremiumCalculator

async def calculate_premium():
    async with KimchiPremiumCalculator() as calculator:
        result = await calculator.run_calculation_cycle()
        print(f"계산된 프리미엄: {result['total_calculations']}개")

asyncio.run(calculate_premium())
```

## ⚙️ 설정 옵션

### CCXT 설정
```python
# ccxt_price_collector.py 내부
exchange_configs = {
    "binance": {"ccxt_id": "binance", "region": "global", "base_currency": "USDT"},
    "upbit": {"ccxt_id": "upbit", "region": "korea", "base_currency": "KRW"},
    # ...
}
```

### 김치프리미엄 계산 설정
```python
# kimchi_premium_calculator.py 내부
korean_exchanges = ["upbit", "bithumb"]
global_exchanges = ["binance", "bybit", "okx", "gateio", "bitget", "mexc", "coinbase"]
```

## 🔍 모니터링 및 로깅

### 로그 레벨 설정
```python
import logging
logging.basicConfig(level=logging.INFO)
```

### 통계 확인
```python
# 수집 통계
collector.print_collection_summary()

# 계산 통계  
calculator.print_calculation_summary()
```

## 🚨 에러 처리

### 일반적인 문제들

1. **CCXT 연결 실패**
   - 네트워크 연결 확인
   - 거래소 API 상태 확인
   - Rate Limit 설정 조정

2. **환율 조회 실패**
   - 백업 API 자동 사용
   - DB에서 최근 환율 fallback

3. **데이터베이스 연결 오류**
   - MySQL 서버 상태 확인
   - 연결 설정 확인

### 에러 로그 예시
```
❌ binance BTC/USDT 조회 실패: Request timeout
⚠️ Rate limit, 대기...
✅ 환율 조회 성공: 1 USD = 1340.50 KRW
```

## 📈 성능 최적화

### 배치 처리
- 가격 수집: 10개 코인씩 배치 처리
- Rate Limit 준수: 거래소별 1초 대기

### 캐싱 전략
- 심볼 매핑: 메모리 캐시
- 환율 정보: 30초 TTL
- 가격 데이터: 5분 윈도우

## 🔄 스케줄링

### 권장 실행 주기
- **가격 수집**: 1분마다
- **김치프리미엄 계산**: 1분마다 (가격 수집 후)
- **메타데이터 업데이트**: 1일 1회
- **거래소 목록 업데이트**: 1주일 1회

### Cron 설정 예시
```bash
# 매분 가격 수집
* * * * * cd /path/to/backend/collectors && python ccxt_price_collector.py

# 매분 김치프리미엄 계산 (30초 후)
* * * * * sleep 30 && cd /path/to/backend/collectors && python kimchi_premium_calculator.py

# 매일 오전 6시 메타데이터 업데이트
0 6 * * * cd /path/to/backend/collectors && python manual_metadata_setup.py
```

## 🛠️ 개발 가이드

### 새로운 거래소 추가
1. `ccxt_price_collector.py`의 `exchange_configs`에 추가
2. `setup_exchange_registry.py`에 거래소 정보 추가
3. 심볼 매핑 확인 및 수동 오버라이드 설정

### 새로운 계산 로직 추가
1. `kimchi_premium_calculator.py`에 계산 함수 추가
2. 결과 저장을 위한 DB 스키마 확장
3. 테스트 케이스 추가

## 📞 지원

문제가 발생하거나 개선 사항이 있으면 이슈를 등록해 주세요.

---

💡 **Tip**: 전체 시스템 테스트(`test_complete_system.py`)를 먼저 실행해서 모든 구성 요소가 정상 작동하는지 확인하세요!