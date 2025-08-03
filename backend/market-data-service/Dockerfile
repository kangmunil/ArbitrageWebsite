FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements-common.txt .
COPY market-data-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY market-data-service/ .
COPY shared /app/shared

# 로그 디렉토리 생성
RUN mkdir -p /app/logs

# 포트 노출
EXPOSE 8001

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# 애플리케이션 실행
CMD ["python", "main.py"]