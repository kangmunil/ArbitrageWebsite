#!/usr/bin/env python3
"""
데이터베이스 테이블 생성, 마이그레이션 및 초기 데이터 세팅 스크립트
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DECIMAL, DATETIME, ForeignKey, text
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
import os

# 데이터베이스 연결
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@db/kimchiscan")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 모델 정의
class Exchange(Base):
    """거래소 정보를 저장하는 모델"""
    __tablename__ = 'exchanges'
    id = Column(Integer, primary_key=True, autoincrement=True)
    exchange_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    country = Column(String(255))
    is_korean = Column(Boolean)
    site_url = Column(String(255))
    api_url = Column(String(255))
    logo_url = Column(String(255))
    is_active = Column(Boolean, default=True)

class Cryptocurrency(Base):
    """암호화폐 정보를 저장하는 모델"""
    __tablename__ = 'cryptocurrencies'
    id = Column(Integer, primary_key=True, autoincrement=True)
    crypto_id = Column(String(255), unique=True, nullable=False)
    symbol = Column(String(255), nullable=False)
    name_ko = Column(String(255))
    name_en = Column(String(255))
    logo_url = Column(String(255))
    is_active = Column(Boolean, default=True)

class CoinPrice(Base):
    """코인 가격 정보를 저장하는 모델"""
    __tablename__ = 'coin_prices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    crypto_id = Column(Integer, ForeignKey('cryptocurrencies.id'))
    exchange_id = Column(Integer, ForeignKey('exchanges.id'))
    price_krw = Column(DECIMAL(20, 8))
    price_usd = Column(DECIMAL(20, 8))
    last_updated = Column(DATETIME)
    cryptocurrency = relationship("Cryptocurrency")
    exchange = relationship("Exchange")

class PremiumHistory(Base):
    """프리미엄 이력을 저장하는 모델"""
    __tablename__ = 'premium_histories'
    id = Column(Integer, primary_key=True, autoincrement=True)
    crypto_id = Column(Integer, ForeignKey('cryptocurrencies.id'))
    premium = Column(DECIMAL(10, 4))
    gap = Column(DECIMAL(20, 8))
    korean_price = Column(DECIMAL(20, 8))
    foreign_price = Column(DECIMAL(20, 8))
    reference_exchange_kor = Column(Integer, ForeignKey('exchanges.id'))
    reference_exchange_for = Column(Integer, ForeignKey('exchanges.id'))
    timestamp = Column(DATETIME)
    cryptocurrency = relationship("Cryptocurrency")
    kor_exchange = relationship("Exchange", foreign_keys=[reference_exchange_kor])
    for_exchange = relationship("Exchange", foreign_keys=[reference_exchange_for])

def create_tables():
    """
    데이터베이스에 모든 테이블을 생성합니다.

    Base.metadata에 정의된 모든 테이블을 생성합니다.
    """
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully.")

def seed_initial_data():
    """
    초기 데이터를 데이터베이스에 삽입합니다.

    거래소 및 주요 암호화폐에 대한 초기 데이터를 추가합니다.
    """
    print("Seeding initial data...")
    
    db = SessionLocal()
    try:
        # 거래소 데이터
        exchanges = [
            Exchange(exchange_id='upbit', name='Upbit', country='Korea', is_korean=True, is_active=True),
            Exchange(exchange_id='bithumb', name='Bithumb', country='Korea', is_korean=True, is_active=True),
            Exchange(exchange_id='binance', name='Binance', country='Global', is_korean=False, is_active=True),
            Exchange(exchange_id='bybit', name='Bybit', country='Global', is_korean=False, is_active=True),
        ]
        
        for exchange in exchanges:
            existing = db.query(Exchange).filter(Exchange.exchange_id == exchange.exchange_id).first()
            if not existing:
                db.add(exchange)
        
        # 주요 암호화폐 데이터 (한글명 포함)
        cryptocurrencies = [
            Cryptocurrency(crypto_id='bitcoin', symbol='BTC', name_ko='비트코인', name_en='Bitcoin', 
                         logo_url='https://assets.coingecko.com/coins/images/1/standard/bitcoin.png', is_active=True),
            Cryptocurrency(crypto_id='ethereum', symbol='ETH', name_ko='이더리움', name_en='Ethereum',
                         logo_url='https://assets.coingecko.com/coins/images/279/standard/ethereum.png', is_active=True),
            Cryptocurrency(crypto_id='ripple', symbol='XRP', name_ko='리플', name_en='XRP',
                         logo_url='https://assets.coingecko.com/coins/images/44/standard/xrp-symbol-white-128.png', is_active=True),
            Cryptocurrency(crypto_id='solana', symbol='SOL', name_ko='솔라나', name_en='Solana',
                         logo_url='https://assets.coingecko.com/coins/images/4128/standard/solana.png', is_active=True),
            Cryptocurrency(crypto_id='dogecoin', symbol='DOGE', name_ko='도지코인', name_en='Dogecoin',
                         logo_url='https://assets.coingecko.com/coins/images/5/standard/dogecoin.png', is_active=True),
            Cryptocurrency(crypto_id='cardano', symbol='ADA', name_ko='에이다', name_en='Cardano',
                         logo_url='https://assets.coingecko.com/coins/images/975/standard/cardano.png', is_active=True),
            Cryptocurrency(crypto_id='polygon', symbol='MATIC', name_ko='폴리곤', name_en='Polygon',
                         logo_url='https://assets.coingecko.com/coins/images/4713/standard/polygon.png', is_active=True),
            Cryptocurrency(crypto_id='chainlink', symbol='LINK', name_ko='체인링크', name_en='Chainlink',
                         logo_url='https://assets.coingecko.com/coins/images/877/standard/chainlink-new-logo.png', is_active=True),
        ]
        
        for crypto in cryptocurrencies:
            existing = db.query(Cryptocurrency).filter(Cryptocurrency.symbol == crypto.symbol).first()
            if not existing:
                db.add(crypto)
        
        db.commit()
        print("✅ Initial data seeded successfully.")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_tables()
    seed_initial_data()
    print("🎉 Database setup completed!")

def add_crypto_metadata_columns():
    """
    암호화폐 테이블에 새로운 메타데이터 컬럼들을 추가합니다.
    이미 컬럼이 존재하는 경우 건너뛰고, 트랜잭션 내에서 실행하여 안전성을 보장합니다.
    """
    
    # 추가할 컬럼들과 타입 정의
    new_columns = [
        ("market_cap_rank", "INT"),
        ("circulating_supply", "DECIMAL(30, 8)"),
        ("max_supply", "DECIMAL(30, 8)"),
        ("category", "VARCHAR(100)"),
        ("website_url", "VARCHAR(255)"),
        ("whitepaper_url", "VARCHAR(255)")
    ]
    
    with engine.connect() as conn:
        # 트랜잭션 시작
        trans = conn.begin()
        
        try:
            print("🔄 암호화폐 테이블 구조 확장 시작...")
            
            # 각 컬럼을 하나씩 추가
            for column_name, column_type in new_columns:
                try:
                    # 컬럼이 이미 존재하는지 확인
                    check_query = text(f"""
                        SELECT COUNT(*) as count 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE table_schema = 'kimchiscan' 
                        AND table_name = 'cryptocurrencies' 
                        AND column_name = '{column_name}'
                    """)
                    
                    result = conn.execute(check_query)
                    row = result.fetchone()
                    exists = row is not None and row[0] > 0
                    
                    if not exists:
                        # 컬럼 추가
                        alter_query = text(f"ALTER TABLE cryptocurrencies ADD COLUMN {column_name} {column_type}")
                        conn.execute(alter_query)
                        print(f"✅ {column_name} 컬럼 추가 완료")
                    else:
                        print(f"ℹ️ {column_name} 컬럼이 이미 존재합니다")
                        
                except Exception as e:
                    print(f"❌ {column_name} 컬럼 추가 실패: {e}")
                    continue
            
            # 트랜잭션 커밋
            trans.commit()
            print("🎉 암호화폐 메타데이터 컬럼 추가 완료!")
            
        except Exception as e:
            # 트랜잭션 롤백
            trans.rollback()
            print(f"❌ 마이그레이션 실패: {e}")
            raise

def update_existing_crypto_data():
    """
    기존 데이터에 샘플 메타데이터를 업데이트합니다.
    주요 코인들에 대해 미리 정의된 메타데이터를 사용하여 데이터베이스를 채웁니다.
    """
    
    # 주요 코인들의 메타데이터
    sample_data = {
        'BTC': {
            'market_cap_rank': 1,
            'max_supply': 21000000,
            'category': 'Store of Value',
            'website_url': 'https://bitcoin.org',
            'whitepaper_url': 'https://bitcoin.org/bitcoin.pdf'
        },
        'ETH': {
            'market_cap_rank': 2,
            'category': 'Smart Contract Platform',
            'website_url': 'https://ethereum.org',
            'whitepaper_url': 'https://ethereum.org/en/whitepaper/'
        },
        'XRP': {
            'market_cap_rank': 3,
            'max_supply': 100000000000,
            'category': 'Payments',
            'website_url': 'https://ripple.com',
        },
        'SOL': {
            'market_cap_rank': 4,
            'category': 'Smart Contract Platform',
            'website_url': 'https://solana.com',
        }
    }
    
    with engine.connect() as conn:
        trans = conn.begin()
        
        try:
            print("🔄 기존 데이터 메타데이터 업데이트 시작...")
            
            for symbol, metadata in sample_data.items():
                # 동적으로 UPDATE 쿼리 구성
                set_clauses = []
                params = {'symbol': symbol}
                
                for key, value in metadata.items():
                    set_clauses.append(f"{key} = :{key}")
                    params[key] = value
                
                if set_clauses:
                    update_query = text(f"""
                        UPDATE cryptocurrencies 
                        SET {', '.join(set_clauses)}
                        WHERE symbol = :symbol
                    """)
                    
                    result = conn.execute(update_query, params)
                    if result.rowcount > 0:
                        print(f"✅ {symbol} 메타데이터 업데이트 완료")
                    else:
                        print(f"⚠️ {symbol} 코인을 찾을 수 없습니다")
            
            trans.commit()
            print("🎉 기존 데이터 메타데이터 업데이트 완료!")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ 데이터 업데이트 실패: {e}")
            raise

def full_setup():
    """전체 데이터베이스 설정 (테이블 생성 + 마이그레이션 + 시드 데이터)"""
    try:
        print("🚀 전체 데이터베이스 설정 시작...")
        create_tables()
        add_crypto_metadata_columns()
        update_existing_crypto_data()
        print("🎉 모든 데이터베이스 설정이 완료되었습니다!")
    except Exception as e:
        print(f"💥 데이터베이스 설정 실패: {e}")
        exit(1)
