#!/usr/bin/env python3
"""
최소한의 의존성으로 새로운 스키마 생성
"""

import os
import sys
import pymysql
from datetime import datetime

# 환경변수에서 DB 연결 정보 가져오기
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'user'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'kimchiscan'),
    'charset': 'utf8mb4'
}

def get_connection():
    """데이터베이스 연결"""
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        sys.exit(1)

def execute_sql(cursor, sql, description):
    """SQL 실행 및 로깅"""
    try:
        cursor.execute(sql)
        print(f"   ✅ {description}")
        return True
    except Exception as e:
        print(f"   ❌ {description} 실패: {e}")
        return False

def backup_existing_data(cursor):
    """기존 데이터 백업"""
    print("📦 기존 데이터 백업...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_tables = ["cryptocurrencies", "exchanges", "coin_metadata"]
    
    for table in backup_tables:
        try:
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if cursor.fetchone():
                cursor.execute(f"""
                    CREATE TABLE {table}_backup_{timestamp} 
                    AS SELECT * FROM {table}
                """)
                print(f"   ✅ {table} → {table}_backup_{timestamp}")
        except:
            pass

def create_new_schema(cursor):
    """새로운 스키마 생성"""
    print("🗄️ 새로운 테이블 스키마 생성...")
    
    # 1. coin_master 테이블
    sql_coin_master = """
    CREATE TABLE coin_master (
        coingecko_id VARCHAR(50) PRIMARY KEY COMMENT 'CoinGecko 고유 ID',
        symbol VARCHAR(20) NOT NULL COMMENT '대표 심볼',
        name_en VARCHAR(100) COMMENT '영문명',
        image_url VARCHAR(255) COMMENT '아이콘 URL',
        market_cap_rank INT COMMENT '시가총액 순위',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        INDEX idx_symbol (symbol),
        INDEX idx_rank (market_cap_rank),
        INDEX idx_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='CoinGecko 기반 글로벌 코인 마스터'
    """
    
    cursor.execute("DROP TABLE IF EXISTS coin_master")
    execute_sql(cursor, sql_coin_master, "coin_master 테이블 생성")
    
    # 2. upbit_listings 테이블
    sql_upbit = """
    CREATE TABLE upbit_listings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        market VARCHAR(20) NOT NULL UNIQUE COMMENT '마켓 코드',
        symbol VARCHAR(20) NOT NULL COMMENT '심볼',
        korean_name VARCHAR(100) NOT NULL COMMENT '한글명',
        english_name VARCHAR(100) COMMENT '영문명',
        coingecko_id VARCHAR(50) COMMENT 'CoinGecko ID',
        is_active BOOLEAN DEFAULT TRUE,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        INDEX idx_symbol (symbol),
        INDEX idx_korean_name (korean_name),
        INDEX idx_coingecko (coingecko_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='업비트 상장 코인'
    """
    
    cursor.execute("DROP TABLE IF EXISTS upbit_listings")
    execute_sql(cursor, sql_upbit, "upbit_listings 테이블 생성")
    
    # 3. bithumb_listings 테이블
    sql_bithumb = """
    CREATE TABLE bithumb_listings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL UNIQUE COMMENT '심볼',
        korean_name VARCHAR(100) COMMENT '한글명',
        coingecko_id VARCHAR(50) COMMENT 'CoinGecko ID',
        trading_pair VARCHAR(20) GENERATED ALWAYS AS (CONCAT('KRW-', symbol)) STORED,
        is_active BOOLEAN DEFAULT TRUE,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        INDEX idx_symbol (symbol),
        INDEX idx_korean_name (korean_name),
        INDEX idx_coingecko (coingecko_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='빗썸 상장 코인'
    """
    
    cursor.execute("DROP TABLE IF EXISTS bithumb_listings")
    execute_sql(cursor, sql_bithumb, "bithumb_listings 테이블 생성")
    
    # 4. exchange_registry 테이블
    sql_exchange_registry = """
    CREATE TABLE exchange_registry (
        exchange_id VARCHAR(20) PRIMARY KEY COMMENT '거래소 ID',
        exchange_name VARCHAR(50) NOT NULL COMMENT '거래소 명',
        region VARCHAR(10) NOT NULL COMMENT '지역',
        base_currency VARCHAR(10) COMMENT '기본 통화',
        api_enabled BOOLEAN DEFAULT TRUE,
        rate_limit_per_minute INT DEFAULT 1200,
        priority_order INT DEFAULT 999,
        ccxt_id VARCHAR(20) COMMENT 'CCXT ID',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        INDEX idx_region (region),
        INDEX idx_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='거래소 등록'
    """
    
    cursor.execute("DROP TABLE IF EXISTS exchange_registry")
    execute_sql(cursor, sql_exchange_registry, "exchange_registry 테이블 생성")
    
    # 5. price_snapshots 테이블
    sql_price_snapshots = """
    CREATE TABLE price_snapshots (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        coingecko_id VARCHAR(50) NOT NULL,
        exchange_id VARCHAR(20) NOT NULL,
        symbol VARCHAR(20) NOT NULL,
        trading_pair VARCHAR(20) NOT NULL,
        price DECIMAL(20,8) NOT NULL,
        volume_24h DECIMAL(20,8),
        price_change_24h DECIMAL(10,4),
        collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        INDEX idx_coin_exchange (coingecko_id, exchange_id),
        INDEX idx_symbol_time (symbol, collected_at),
        INDEX idx_collected_at (collected_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='실시간 가격 데이터'
    """
    
    cursor.execute("DROP TABLE IF EXISTS price_snapshots")
    execute_sql(cursor, sql_price_snapshots, "price_snapshots 테이블 생성")
    
    # 6. kimchi_premium 테이블
    sql_kimchi_premium = """
    CREATE TABLE kimchi_premium (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        coingecko_id VARCHAR(50) NOT NULL,
        symbol VARCHAR(20) NOT NULL,
        upbit_price DECIMAL(20,8),
        bithumb_price DECIMAL(20,8),
        korean_avg_price DECIMAL(20,8),
        global_avg_price DECIMAL(20,8),
        global_avg_price_krw DECIMAL(20,8),
        usd_krw_rate DECIMAL(10,4) NOT NULL,
        kimchi_premium DECIMAL(10,4),
        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        INDEX idx_symbol_calc (symbol, calculated_at),
        INDEX idx_premium (kimchi_premium),
        INDEX idx_calc_time (calculated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='김치프리미엄 계산 결과'
    """
    
    cursor.execute("DROP TABLE IF EXISTS kimchi_premium")
    execute_sql(cursor, sql_kimchi_premium, "kimchi_premium 테이블 생성")
    
    # 7. 환율 테이블
    sql_exchange_rates = """
    CREATE TABLE exchange_rates (
        id INT AUTO_INCREMENT PRIMARY KEY,
        currency_pair VARCHAR(10) NOT NULL UNIQUE,
        rate DECIMAL(10,4) NOT NULL,
        source VARCHAR(50) NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        INDEX idx_updated (updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='환율 정보'
    """
    
    cursor.execute("DROP TABLE IF EXISTS exchange_rates")
    execute_sql(cursor, sql_exchange_rates, "exchange_rates 테이블 생성")
    
    print("✅ 새로운 테이블 스키마 생성 완료")

def initialize_data(cursor):
    """초기 데이터 삽입"""
    print("📊 초기 데이터 삽입...")
    
    # 거래소 등록
    exchanges = [
        ('upbit', '업비트', 'KR', 'KRW', 1, 600, 1, 'upbit'),
        ('bithumb', '빗썸', 'KR', 'KRW', 1, 300, 2, 'bithumb'),
        ('binance', '바이낸스', 'GLOBAL', 'USDT', 1, 1200, 3, 'binance'),
        ('bybit', '바이빗', 'GLOBAL', 'USDT', 1, 600, 4, 'bybit'),
        ('okx', 'OKX', 'GLOBAL', 'USDT', 1, 300, 5, 'okx'),
        ('gateio', 'Gate.io', 'GLOBAL', 'USDT', 1, 300, 6, 'gateio'),
        ('bitget', 'Bitget', 'GLOBAL', 'USDT', 1, 300, 7, 'bitget'),
        ('mexc', 'MEXC', 'GLOBAL', 'USDT', 1, 300, 8, 'mexc'),
        ('coinbasepro', 'Coinbase Pro', 'GLOBAL', 'USD', 1, 300, 9, 'coinbasepro')
    ]
    
    for ex in exchanges:
        cursor.execute("""
            INSERT INTO exchange_registry 
            (exchange_id, exchange_name, region, base_currency, api_enabled, 
             rate_limit_per_minute, priority_order, ccxt_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (ex[0], ex[1], ex[2], ex[3], ex[4], ex[5], ex[6], ex[7], True))
    
    # 초기 환율
    cursor.execute("""
        INSERT INTO exchange_rates (currency_pair, rate, source) 
        VALUES ('USDKRW', 1350.00, 'manual')
    """)
    
    print(f"   ✅ {len(exchanges)}개 거래소 등록")
    print("   ✅ 초기 환율 설정 (1USD = 1350KRW)")

def create_views(cursor):
    """유용한 뷰 생성"""
    print("👁️ 뷰 생성...")
    
    # 한국 거래소 통합 뷰
    cursor.execute("DROP VIEW IF EXISTS v_korean_coins")
    sql_korean_view = """
    CREATE VIEW v_korean_coins AS
    SELECT 
        'upbit' as exchange,
        symbol,
        korean_name,
        coingecko_id,
        market as trading_pair,
        is_active
    FROM upbit_listings
    WHERE is_active = 1
    
    UNION ALL
    
    SELECT 
        'bithumb' as exchange,
        symbol,
        korean_name,
        coingecko_id,
        trading_pair,
        is_active
    FROM bithumb_listings
    WHERE is_active = 1
    """
    
    execute_sql(cursor, sql_korean_view, "v_korean_coins 뷰 생성")
    
    print("✅ 뷰 생성 완료")

def main():
    print("🚀 새로운 데이터베이스 스키마 생성 시작\n")
    
    connection = get_connection()
    cursor = connection.cursor()
    
    try:
        # 1. 기존 데이터 백업
        backup_existing_data(cursor)
        
        # 2. 새로운 스키마 생성
        create_new_schema(cursor)
        
        # 3. 초기 데이터 삽입
        initialize_data(cursor)
        
        # 4. 뷰 생성
        create_views(cursor)
        
        # 커밋
        connection.commit()
        
        print("\n🎉 새로운 데이터베이스 스키마 생성 완료!")
        print("💡 다음 단계: 데이터 수집 시스템 구축")
        
    except Exception as e:
        print(f"❌ 스키마 생성 실패: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    main()