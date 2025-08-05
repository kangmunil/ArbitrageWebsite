FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드 및 의존성 설치
RUN pip install --upgrade pip setuptools wheel

# 의존성 설치
COPY requirements-common.txt .
COPY liquidation_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements-common.txt && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY liquidation_service/ .
COPY shared /app/shared

# 로그 디렉토리 생성
RUN mkdir -p /app/logs

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# 서비스 실행 (개발환경에서는 --reload, 운영환경에서는 제거)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]