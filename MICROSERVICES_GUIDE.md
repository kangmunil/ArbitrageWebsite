# 🚀 마이크로서비스 실행 가이드

## 📋 개요

이 프로젝트는 다음과 같은 마이크로서비스 구조로 분리되었습니다:

- **🎯 API Gateway** (포트 8000): 메인 API 서버, 프론트엔드 진입점
- **📊 Market Data Service** (포트 8001): 가격, 거래량, 환율 데이터 수집
- **⚡ Liquidation Service** (포트 8002): 청산 데이터 수집 및 처리
- **🗄️ MySQL** (포트 3306): 데이터베이스
- **🔴 Redis** (포트 6379): 서비스 간 데이터 공유

## 🚀 실행 방법

### 1. 기본 실행
```bash
# 마이크로서비스 구조로 실행
docker-compose up --build

# 백그라운드 실행
docker-compose up --build -d
```

### 2. 로그 모니터링 포함 실행
```bash
# Dozzle 로그 뷰어 포함 (http://localhost:8080)
docker-compose --profile monitoring up --build
```

### 3. 기존 방식 (백업용)
```bash
# 기존 통합 구조 (문제 발생 시 롤백용)
docker-compose -f docker-compose-legacy.yml up --build
```

## 🔍 서비스 상태 확인

### Health Check 엔드포인트들
```bash
# API Gateway 상태
curl http://localhost:8000/health

# Market Data Service 상태  
curl http://localhost:8001/health

# Liquidation Service 상태
curl http://localhost:8002/health
```

### 개별 서비스 로그 확인
```bash
# 전체 로그
docker-compose logs -f

# API Gateway 로그
docker-compose logs -f api-gateway

# Market Data Service 로그
docker-compose logs -f market-service

# Liquidation Service 로그
docker-compose logs -f liquidation-service
```

## 📊 API 엔드포인트

### API Gateway (포트 8000)
- `GET /` - 서비스 상태
- `GET /health` - 헬스체크 (모든 서비스 상태 포함)
- `GET /api/coins/latest` - 통합 코인 데이터
- `GET /api/coin-names` - 코인 한글명
- `GET /api/fear_greed_index` - 공포탐욕지수
- `WebSocket /ws/prices` - 실시간 가격 데이터
- `WebSocket /ws/liquidations` - 실시간 청산 데이터

### Market Data Service (포트 8001)
- `GET /health` - 서비스 상태
- `GET /api/market/prices` - 가격 데이터만
- `GET /api/market/volumes` - 거래량 데이터만  
- `GET /api/market/premiums` - 김치 프리미엄 데이터
- `GET /api/market/exchange-rate` - 환율 정보
- `GET /api/market/combined` - 통합 시장 데이터
- `WebSocket /ws/market` - 실시간 시장 데이터

### Liquidation Service (포트 8002)
- `GET /health` - 서비스 상태
- `GET /api/liquidations/aggregated` - 집계된 청산 데이터
- `GET /api/liquidations/debug` - 디버그 정보
- `GET /api/liquidations/summary` - 청산 요약
- `GET /api/liquidations/raw` - 원시 청산 데이터

## 🔧 개발 및 디버깅

### 1. 개별 서비스 개발
```bash
# Market Data Service만 실행 (개발용)
cd backend/market-data-service
python main.py

# Liquidation Service만 실행 (개발용)  
cd backend/liquidation_service
python main.py
```

### 2. 로그 파일 위치
```
logs/
├── api-gateway/          # API Gateway 로그
├── market-service/       # Market Data Service 로그
└── liquidation-service/  # Liquidation Service 로그
```

### 3. Redis 데이터 확인
```bash
# Redis CLI 접속
docker exec -it arbitrage-microservices-redis-1 redis-cli

# 시장 데이터 확인
HGETALL market:upbit
HGETALL market:binance
HGETALL market:rates
```

## 🚨 문제 해결

### 1. 서비스 시작 순서 문제
```bash
# 의존성 순서: Redis → DB → Market/Liquidation Services → API Gateway
# Docker Compose가 자동으로 관리하지만, 수동 재시작 시:

docker-compose up redis db
# 잠시 대기 후
docker-compose up market-service liquidation-service  
# 잠시 대기 후
docker-compose up api-gateway frontend
```

### 2. 데이터 수집 확인
```bash
# Market Data Service 디버그
curl http://localhost:8001/api/debug/collectors

# Liquidation Service 디버그  
curl http://localhost:8002/api/liquidations/debug

# 원시 거래소 데이터 확인
curl http://localhost:8001/api/debug/raw-data/upbit
curl http://localhost:8001/api/debug/raw-data/binance
```

### 3. 서비스 간 통신 문제
```bash
# API Gateway에서 다른 서비스 상태 확인
curl http://localhost:8000/health

# 개별 서비스 직접 테스트
curl http://localhost:8001/api/market/combined
curl http://localhost:8002/api/liquidations/aggregated
```

## 🔄 롤백 방법

문제 발생 시 기존 통합 구조로 롤백:

```bash
# 새 구조 중지
docker-compose down

# 기존 구조로 실행 (레거시)
docker-compose -f docker-compose-legacy.yml up --build
```

## 📈 성능 모니터링

### 1. 로그 모니터링 (Dozzle)
- URL: http://localhost:8080
- 모든 컨테이너 로그를 실시간으로 확인

### 2. 서비스 메트릭
```bash
# 컨테이너 리소스 사용량
docker stats

# 개별 서비스 상태
curl http://localhost:8000/health | jq
curl http://localhost:8001/health | jq  
curl http://localhost:8002/health | jq
```

## 🎯 장점 확인

### 1. 로그 분리 확인
- 각 서비스별 독립적인 로그 스트림
- 문제 발생 시 해당 서비스만 집중 분석 가능

### 2. 독립적인 확장
```bash
# Market Data Service만 스케일링
docker-compose up --scale market-service=2

# Liquidation Service만 재시작
docker-compose restart liquidation-service
```

### 3. 장애 격리
- 한 서비스 다운 시에도 다른 서비스는 정상 동작
- API Gateway가 실패한 서비스는 우아하게 처리

## 📝 참고사항

- **프론트엔드**: 기존과 동일하게 `http://localhost:8000` 사용
- **데이터베이스**: 기존 구조 유지, 호환성 보장  
- **WebSocket**: 기존 클라이언트 코드 수정 불필요
- **API**: 기존 REST API 엔드포인트 모두 유지