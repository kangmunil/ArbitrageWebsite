FROM python:3.12-slim

WORKDIR /app

# 의존성 설치
COPY requirements-common.txt .
COPY liquidation_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY liquidation_service/ .
COPY shared /app/shared

# 서비스 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]