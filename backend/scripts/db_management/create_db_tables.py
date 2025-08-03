"""
데이터베이스 테이블 생성 스크립트

이 스크립트는 models.py에 정의된 모든 SQLAlchemy 모델을 기반으로
데이터베이스에 테이블을 생성합니다.
"""

from sqlalchemy import create_engine
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@db/kimchiscan")
engine = create_engine(DATABASE_URL)

if __name__ == "__main__":
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")