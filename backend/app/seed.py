
import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# models.py에서 정의한 모델과 Base를 임포트해야 합니다.
# 하지만 이 스크립트는 src 폴더 내에 있으므로 상대 경로 임포트를 사용합니다.
from .models import Base, Exchange, Cryptocurrency

# 데이터베이스 연결 설정
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@db/kimchiscan")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db():
    """데이터베이스 세션 컨텍스트 매니저"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def seed_exchanges(db_session):
    """exchanges.csv 파일에서 거래소 데이터를 읽어 DB에 삽입합니다."""
    # CSV 파일은 backend 폴더에 위치해야 합니다.
    with open('/app/data/exchanges.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 중복 체크
            exists = db_session.query(Exchange).filter_by(exchange_id=row['exchange_id']).first()
            if not exists:
                exchange = Exchange(
                    exchange_id=row['exchange_id'],
                    name=row['name'],
                    country=row['country'],
                    is_korean=row['is_korean'].upper() == 'TRUE',
                    site_url=row['site_url'],
                    api_url=row['api_url'],
                    logo_url=row['logo_url'],
                    is_active=row['is_active'].upper() == 'TRUE'
                )
                db_session.add(exchange)
        db_session.commit()
    print("Exchanges seeded successfully.")

def seed_cryptocurrencies(db_session):
    """cryptocurrencies.csv 파일에서 암호화폐 데이터를 읽어 DB에 삽입합니다."""
    with open('/app/data/cryptocurrencies.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 중복 체크
            exists = db_session.query(Cryptocurrency).filter_by(crypto_id=row['crypto_id']).first()
            if not exists:
                crypto = Cryptocurrency(
                    crypto_id=row['crypto_id'],
                    symbol=row['symbol'],
                    name_ko=row['name_ko'],
                    name_en=row['name_en'],
                    logo_url=row['logo_url'],
                    is_active=row['is_active'].upper() == 'TRUE'
                )
                db_session.add(crypto)
        db_session.commit()
    print("Cryptocurrencies seeded successfully.")

if __name__ == "__main__":
    # 테이블이 없으면 생성
    Base.metadata.create_all(bind=engine)
    
    with get_db() as db:
        print("Seeding initial data...")
        seed_exchanges(db)
        seed_cryptocurrencies(db)
        print("Data seeding finished.")
