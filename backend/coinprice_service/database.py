
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@db/kimchiscan")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """데이터베이스 세션을 생성하고 자동으로 정리하는 제너레이터.
    
    FastAPI의 Depends에서 사용되어 엔드포인트에 데이터베이스 세션을 주입합니다.
    요청 완료 후 자동으로 세션을 닫어 리소스 누수를 방지합니다.
    
    Yields:
        Session: SQLAlchemy 데이터베이스 세션
        
    Example:
        @app.get("/exchanges")
        def get_exchanges(db: Session = Depends(get_db)):
            return db.query(Exchange).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
