#!/usr/bin/env python3
"""
데이터베이스 연결 및 세션 관리
SQLAlchemy 기반 DB 연결, 세션 관리, 트랜잭션 처리
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional, Any

from sqlalchemy import create_engine, MetaData, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from .config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """데이터베이스 연결 및 세션 관리"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """SQLAlchemy 엔진 초기화"""
        try:
            self.engine = create_engine(
                settings.database.url,
                poolclass=QueuePool,
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.max_overflow,
                pool_pre_ping=True,  # 연결 상태 확인
                pool_recycle=3600,   # 1시간마다 연결 재생성
                echo=settings.is_development,  # 개발 환경에서만 SQL 로깅
                connect_args={
                    "charset": "utf8mb4",
                    "use_unicode": True,
                    "autocommit": False
                }
            )
            
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info(f"데이터베이스 엔진 초기화 완료: {settings.database.host}:{settings.database.port}")
            
        except Exception as e:
            logger.error(f"데이터베이스 엔진 초기화 실패: {e}")
            raise
    
    def get_session(self) -> Session:
        """새로운 세션 반환"""
        try:
            if self.SessionLocal is None:
                raise Exception("세션 팩토리가 초기화되지 않음")
            return self.SessionLocal()
        except Exception as e:
            logger.error(f"세션 생성 실패: {e}")
            raise
    
    @contextmanager
    def get_session_context(self) -> Generator[Session, None, None]:
        """컨텍스트 매니저로 세션 관리"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"데이터베이스 트랜잭션 실패: {e}")
            raise
        finally:
            session.close()
    
    @contextmanager  
    def get_batch_session(self, batch_size: int = 1000) -> Generator[Session, None, None]:
        """배치 처리용 세션 (대용량 데이터 처리)"""
        session = self.get_session()
        try:
            # 배치 처리 최적화 설정
            session.execute(text("SET autocommit=0"))
            session.execute(text("SET unique_checks=0"))
            session.execute(text("SET foreign_key_checks=0"))
            
            yield session
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"배치 처리 실패: {e}")
            raise
        finally:
            # 설정 복원
            session.execute(text("SET unique_checks=1"))
            session.execute(text("SET foreign_key_checks=1"))
            session.execute(text("SET autocommit=1"))
            session.close()
    
    def test_connection(self) -> bool:
        """연결 상태 테스트"""
        try:
            with self.get_session_context() as session:
                session.execute(text("SELECT 1"))
                logger.info("데이터베이스 연결 테스트 성공")
                return True
        except Exception as e:
            logger.error(f"데이터베이스 연결 테스트 실패: {e}")
            return False
    
    def get_table_info(self) -> dict:
        """테이블 정보 조회"""
        try:
            inspector = inspect(self.engine)
            if inspector is None:
                logger.error("Inspector is None")
                return {}
            tables = {}
            
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                tables[table_name] = {
                    "columns": len(columns),
                    "column_names": [col["name"] for col in columns]
                }
            
            return tables
        except Exception as e:
            logger.error(f"테이블 정보 조회 실패: {e}")
            return {}
    
    def execute_raw_sql(self, sql: str, params: Optional[dict] = None) -> Any:
        """Raw SQL 실행"""
        try:
            with self.get_session_context() as session:
                result = session.execute(text(sql), params or {})
                if sql.strip().upper().startswith("SELECT"):
                    return result.fetchall()
                return getattr(result, 'rowcount', 0)
        except Exception as e:
            logger.error(f"Raw SQL 실행 실패: {sql[:100]}... Error: {e}")
            raise
    
    def close(self):
        """엔진 및 연결 정리"""
        if self.engine:
            self.engine.dispose()
            logger.info("데이터베이스 연결 정리 완료")

# 글로벌 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()

# Legacy compatibility exports
engine = db_manager.engine
SessionLocal = db_manager.SessionLocal

# FastAPI Dependency용 함수들
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: 일반 세션"""
    with db_manager.get_session_context() as session:
        yield session

def get_batch_db(batch_size: int = 1000) -> Generator[Session, None, None]:
    """FastAPI dependency: 배치 세션"""
    with db_manager.get_batch_session(batch_size) as session:
        yield session

# 편의 함수들
def execute_sql(sql: str, params: Optional[dict] = None) -> Any:
    """간단한 SQL 실행"""
    return db_manager.execute_raw_sql(sql, params)

def test_db_connection() -> bool:
    """DB 연결 테스트"""
    return db_manager.test_connection()

def get_db_info() -> dict:
    """DB 정보 조회"""
    info = {
        "connection_url": f"{settings.database.host}:{settings.database.port}/{settings.database.database}",
        "pool_size": settings.database.pool_size,
        "max_overflow": settings.database.max_overflow,
        "tables": db_manager.get_table_info()
    }
    return info

# 헬스체크용 함수
async def health_check() -> dict:
    """비동기 헬스체크"""
    try:
        is_healthy = db_manager.test_connection()
        return {
            "database": "healthy" if is_healthy else "unhealthy",
            "connection_pool": {
                "size": getattr(db_manager.engine.pool, 'size', lambda: 0)() if db_manager.engine else 0,
                "checked_out": getattr(db_manager.engine.pool, 'checkedout', lambda: 0)() if db_manager.engine else 0
            }
        }
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        return {
            "database": "unhealthy",
            "error": str(e)
        }

# 데이터베이스 정리 함수 (애플리케이션 종료 시 호출)
def cleanup_database():
    """애플리케이션 종료 시 데이터베이스 정리"""
    db_manager.close()

# 시작 시 연결 테스트
if __name__ == "__main__":
    # 간단한 테스트
    print("🔗 데이터베이스 연결 테스트...")
    
    if test_db_connection():
        print("✅ 데이터베이스 연결 성공")
        
        # 테이블 정보 출력
        info = get_db_info()
        print(f"📊 테이블 수: {len(info['tables'])}")
        for table_name, table_info in info['tables'].items():
            print(f"   - {table_name}: {table_info['columns']}개 컬럼")
    else:
        print("❌ 데이터베이스 연결 실패")
        
    cleanup_database()