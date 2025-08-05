
FROM python:3.12-slim

# Force rebuild to apply latest code changes

WORKDIR /app

RUN apt-get update && apt-get install -y gcc python3-dev curl

COPY requirements-common.txt .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app
COPY ./shared /app/shared
COPY ./core /app/core
COPY ./services /app/services

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-ping-interval", "30", "--ws-ping-timeout", "30", "--reload"]
