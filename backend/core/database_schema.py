#!/usr/bin/env python3
"""
새로운 다중거래소 실시간 데이터 시스템 테이블 스키마
want.txt 요구사항 기반 설계
"""

import os
from sqlalchemy import create_engine, text
from datetime import datetime

# 데이터베이스 연결
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@db:3306/kimchiscan")

def create_new_schema():
    """새로운 테이블 스키마 생성"""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("🗄️ 새로운 테이블 스키마 생성 시작...")
        
        # 기존 테이블들 백업 후 삭제 (안전한 마이그레이션)
        backup_existing_tables(conn)
        
        # 1. 글로벌 코인 마스터 (CoinGecko 기준)
        create_coin_master_table(conn)
        
        # 2. 분리된 한국 거래소 테이블들
        create_korean_exchange_tables(conn)
        
        # 3. 해외 거래소 가격 테이블
        create_global_price_table(conn)
        
        # 4. 김치프리미엄 계산 결과 테이블
        create_kimchi_premium_table(conn)
        
        # 5. 시스템 설정 테이블
        create_system_tables(conn)
        
        conn.commit()
        print("✅ 새로운 스키마 생성 완료!")

def backup_existing_tables(conn):
    """기존 테이블 백업"""
    print("📦 기존 테이블 백업...")
    
    try:
        # 중요 데이터만 백업
        backup_tables = [
            "cryptocurrencies", "exchanges", "coin_metadata", 
            "exchange_listings", "kimchi_pairs"
        ]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for table in backup_tables:
            try:
                # 테이블 존재 확인
                result = conn.execute(text(f"SHOW TABLES LIKE '{table}'"))
                if result.fetchone():
                    # 백업 테이블 생성
                    conn.execute(text(f"""
                        CREATE TABLE {table}_backup_{timestamp} 
                        AS SELECT * FROM {table}
                    """))
                    print(f"   ✅ {table} → {table}_backup_{timestamp}")
            except Exception as e:
                print(f"   ⚠️ {table} 백업 스킵: {e}")
        
        print("📦 백업 완료")
        
    except Exception as e:
        print(f"⚠️ 백업 중 오류: {e}")

def create_coin_master_table(conn):
    """글로벌 코인 마스터 테이블"""
    print("🌍 coin_master 테이블 생성...")
    
    conn.execute(text("DROP TABLE IF EXISTS coin_master"))
    
    conn.execute(text("""
        CREATE TABLE coin_master (
            coingecko_id VARCHAR(50) PRIMARY KEY COMMENT 'CoinGecko 고유 ID (bitcoin, ethereum)',
            symbol VARCHAR(20) NOT NULL COMMENT '대표 심볼 (BTC, ETH)',
            name_en VARCHAR(100) COMMENT '영문명',
            image_url VARCHAR(255) COMMENT '아이콘 URL (CoinGecko)',
            market_cap_rank INT COMMENT '시가총액 순위',
            description TEXT COMMENT '코인 설명',
            homepage_url VARCHAR(255) COMMENT '공식 홈페이지',
            is_active BOOLEAN DEFAULT TRUE COMMENT '활성 상태',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_symbol (symbol),
            INDEX idx_rank (market_cap_rank),
            INDEX idx_active (is_active),
            INDEX idx_updated (updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='CoinGecko 기반 글로벌 코인 마스터'
    """))
    
    print("   ✅ coin_master 테이블 생성 완료")

def create_korean_exchange_tables(conn):
    """분리된 한국 거래소 테이블들"""
    print("🇰🇷 한국 거래소 테이블들 생성...")
    
    # 1. 업비트 상장 코인 (API 한글명 포함)
    conn.execute(text("DROP TABLE IF EXISTS upbit_listings"))
    conn.execute(text("""
        CREATE TABLE upbit_listings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            market VARCHAR(20) NOT NULL UNIQUE COMMENT '마켓 코드 (KRW-BTC)',
            symbol VARCHAR(20) NOT NULL COMMENT '심볼 (BTC)',
            korean_name VARCHAR(100) NOT NULL COMMENT '한글명 (API 제공)',
            english_name VARCHAR(100) COMMENT '영문명 (API 제공)',
            coingecko_id VARCHAR(50) COMMENT 'CoinGecko ID 매핑',
            market_warning VARCHAR(20) COMMENT '유의종목 여부',
            is_active BOOLEAN DEFAULT TRUE COMMENT '거래 활성 상태',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            FOREIGN KEY (coingecko_id) REFERENCES coin_master(coingecko_id) ON DELETE SET NULL,
            INDEX idx_symbol (symbol),
            INDEX idx_korean_name (korean_name),
            INDEX idx_active (is_active),
            INDEX idx_coingecko (coingecko_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='업비트 상장 코인 (API 한글명)'
    """))
    
    # 2. 빗썸 상장 코인 (CoinGecko 한글명 매핑)
    conn.execute(text("DROP TABLE IF EXISTS bithumb_listings"))
    conn.execute(text("""
        CREATE TABLE bithumb_listings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL UNIQUE COMMENT '심볼 (BTC)',
            korean_name VARCHAR(100) COMMENT '한글명 (CoinGecko/수동 매핑)',
            coingecko_id VARCHAR(50) COMMENT 'CoinGecko ID 매핑',
            trading_pair VARCHAR(20) GENERATED ALWAYS AS (CONCAT('KRW-', symbol)) STORED COMMENT '거래쌍',
            is_active BOOLEAN DEFAULT TRUE COMMENT '거래 활성 상태',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            FOREIGN KEY (coingecko_id) REFERENCES coin_master(coingecko_id) ON DELETE SET NULL,
            INDEX idx_symbol (symbol),
            INDEX idx_korean_name (korean_name),
            INDEX idx_active (is_active),
            INDEX idx_coingecko (coingecko_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='빗썸 상장 코인 (CoinGecko 한글명)'
    """))
    
    print("   ✅ upbit_listings, bithumb_listings 테이블 생성 완료")

def create_global_price_table(conn):
    """해외 거래소 가격 데이터 테이블"""
    print("🌏 해외 거래소 가격 테이블 생성...")
    
    # 1. 거래소 등록 테이블
    conn.execute(text("DROP TABLE IF EXISTS exchange_registry"))
    conn.execute(text("""
        CREATE TABLE exchange_registry (
            exchange_id VARCHAR(20) PRIMARY KEY COMMENT '거래소 ID (binance, bybit)',
            exchange_name VARCHAR(50) NOT NULL COMMENT '거래소 명 (바이낸스, 바이빗)',
            region VARCHAR(10) NOT NULL COMMENT '지역 (KR, GLOBAL)',
            base_currency VARCHAR(10) COMMENT '기본 통화 (KRW, USDT)',
            api_enabled BOOLEAN DEFAULT TRUE COMMENT 'API 활성화',
            rate_limit_per_minute INT DEFAULT 1200 COMMENT '분당 요청 제한',
            priority_order INT DEFAULT 999 COMMENT '우선순위 (낮을수록 높음)',
            ccxt_id VARCHAR(20) COMMENT 'CCXT 라이브러리 ID',
            is_active BOOLEAN DEFAULT TRUE COMMENT '활성 상태',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_health_check TIMESTAMP,
            
            INDEX idx_region (region),
            INDEX idx_active (is_active),
            INDEX idx_priority (priority_order)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='거래소 등록 정보'
    """))
    
    # 2. 실시간 가격 스냅샷 테이블 (파티셔닝 고려)
    conn.execute(text("DROP TABLE IF EXISTS price_snapshots"))
    conn.execute(text("""
        CREATE TABLE price_snapshots (
            id BIGINT AUTO_INCREMENT,
            coingecko_id VARCHAR(50) NOT NULL COMMENT 'CoinGecko ID',
            exchange_id VARCHAR(20) NOT NULL COMMENT '거래소 ID',
            symbol VARCHAR(20) NOT NULL COMMENT '심볼',
            trading_pair VARCHAR(20) NOT NULL COMMENT '거래쌍 (BTCUSDT, BTC-KRW)',
            price DECIMAL(20,8) NOT NULL COMMENT '현재가',
            volume_24h DECIMAL(20,8) COMMENT '24시간 거래량',
            price_change_24h DECIMAL(10,4) COMMENT '24시간 가격 변화율',
            bid_price DECIMAL(20,8) COMMENT '최고 매수가',
            ask_price DECIMAL(20,8) COMMENT '최저 매도가',
            last_trade_time TIMESTAMP COMMENT '마지막 거래 시간',
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '수집 시간',
            
            PRIMARY KEY (id, collected_at),
            FOREIGN KEY (coingecko_id) REFERENCES coin_master(coingecko_id) ON DELETE CASCADE,
            FOREIGN KEY (exchange_id) REFERENCES exchange_registry(exchange_id) ON DELETE CASCADE,
            
            INDEX idx_coin_exchange (coingecko_id, exchange_id),
            INDEX idx_symbol_time (symbol, collected_at),
            INDEX idx_exchange_time (exchange_id, collected_at),
            INDEX idx_collected_at (collected_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='실시간 가격 데이터'
        PARTITION BY RANGE (TO_DAYS(collected_at)) (
            PARTITION p_old VALUES LESS THAN (TO_DAYS('2024-01-01')),
            PARTITION p_current VALUES LESS THAN MAXVALUE
        )
    """))
    
    print("   ✅ exchange_registry, price_snapshots 테이블 생성 완료")

def create_kimchi_premium_table(conn):
    """김치프리미엄 계산 결과 테이블"""
    print("🌶️ 김치프리미엄 테이블 생성...")
    
    conn.execute(text("DROP TABLE IF EXISTS kimchi_premium"))
    conn.execute(text("""
        CREATE TABLE kimchi_premium (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            coingecko_id VARCHAR(50) NOT NULL COMMENT 'CoinGecko ID',
            symbol VARCHAR(20) NOT NULL COMMENT '심볼',
            
            -- 국내 가격 정보
            upbit_price DECIMAL(20,8) COMMENT '업비트 가격',
            bithumb_price DECIMAL(20,8) COMMENT '빗썸 가격',
            korean_avg_price DECIMAL(20,8) COMMENT '국내 평균가',
            korean_volume_24h DECIMAL(20,8) COMMENT '국내 24h 거래량',
            
            -- 해외 가격 정보
            global_avg_price DECIMAL(20,8) COMMENT '해외 평균가 (USD)',
            global_avg_price_krw DECIMAL(20,8) COMMENT '해외 평균가 (KRW 환산)',
            global_volume_24h DECIMAL(20,8) COMMENT '해외 24h 거래량',
            participating_exchanges JSON COMMENT '참여 거래소 목록',
            
            -- 김치프리미엄 계산
            usd_krw_rate DECIMAL(10,4) NOT NULL COMMENT '달러-원 환율',
            kimchi_premium DECIMAL(10,4) COMMENT '김치 프리미엄 (%)',
            premium_abs DECIMAL(20,8) COMMENT '절대 프리미엄 (KRW)',
            
            -- 메타데이터
            calculation_confidence DECIMAL(5,2) DEFAULT 100.00 COMMENT '계산 신뢰도 (%)',
            data_quality_score DECIMAL(5,2) COMMENT '데이터 품질 점수',
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '계산 시간',
            
            FOREIGN KEY (coingecko_id) REFERENCES coin_master(coingecko_id) ON DELETE CASCADE,
            
            INDEX idx_symbol_calc (symbol, calculated_at),
            INDEX idx_premium (kimchi_premium),
            INDEX idx_calc_time (calculated_at),
            INDEX idx_confidence (calculation_confidence)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='김치프리미엄 계산 결과'
    """))
    
    print("   ✅ kimchi_premium 테이블 생성 완료")

def create_system_tables(conn):
    """시스템 관리 테이블들"""
    print("⚙️ 시스템 관리 테이블들 생성...")
    
    # 1. 수집 작업 로그
    conn.execute(text("DROP TABLE IF EXISTS collection_logs"))
    conn.execute(text("""
        CREATE TABLE collection_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_type VARCHAR(50) NOT NULL COMMENT '작업 유형 (price_collection, metadata_update)',
            exchange_id VARCHAR(20) COMMENT '거래소 ID',
            status VARCHAR(20) NOT NULL COMMENT '상태 (SUCCESS, FAILED, RUNNING)',
            records_processed INT DEFAULT 0 COMMENT '처리된 레코드 수',
            error_message TEXT COMMENT '오류 메시지',
            execution_time_ms INT COMMENT '실행 시간 (밀리초)',
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            
            INDEX idx_job_type (job_type),
            INDEX idx_status (status),
            INDEX idx_started_at (started_at),
            INDEX idx_exchange (exchange_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='데이터 수집 작업 로그'
    """))
    
    # 2. 환율 정보
    conn.execute(text("DROP TABLE IF EXISTS exchange_rates"))
    conn.execute(text("""
        CREATE TABLE exchange_rates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            currency_pair VARCHAR(10) NOT NULL COMMENT '통화쌍 (USDKRW)',
            rate DECIMAL(10,4) NOT NULL COMMENT '환율',
            source VARCHAR(50) NOT NULL COMMENT '환율 소스 (api, manual)',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY unique_pair (currency_pair),
            INDEX idx_updated (updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='환율 정보'
    """))
    
    # 초기 환율 데이터 삽입
    conn.execute(text("""
        INSERT INTO exchange_rates (currency_pair, rate, source) 
        VALUES ('USDKRW', 1350.00, 'manual')
        ON DUPLICATE KEY UPDATE rate=VALUES(rate), updated_at=NOW()
    """))
    
    print("   ✅ collection_logs, exchange_rates 테이블 생성 완료")

def initialize_exchange_registry(conn):
    """거래소 등록 정보 초기화"""
    print("🏢 거래소 등록 정보 초기화...")
    
    exchanges = [
        # 한국 거래소
        ('upbit', '업비트', 'KR', 'KRW', True, 600, 1, 'upbit'),
        ('bithumb', '빗썸', 'KR', 'KRW', True, 300, 2, 'bithumb'),
        
        # 해외 거래소
        ('binance', '바이낸스', 'GLOBAL', 'USDT', True, 1200, 3, 'binance'),
        ('bybit', '바이빗', 'GLOBAL', 'USDT', True, 600, 4, 'bybit'),
        ('okx', 'OKX', 'GLOBAL', 'USDT', True, 300, 5, 'okx'),
        ('gateio', 'Gate.io', 'GLOBAL', 'USDT', True, 300, 6, 'gateio'),
        ('bitget', 'Bitget', 'GLOBAL', 'USDT', True, 300, 7, 'bitget'),
        ('mexc', 'MEXC', 'GLOBAL', 'USDT', True, 300, 8, 'mexc'),
        ('coinbasepro', 'Coinbase Pro', 'GLOBAL', 'USD', True, 300, 9, 'coinbasepro')
    ]
    
    for exchange in exchanges:
        conn.execute(text("""
            INSERT INTO exchange_registry 
            (exchange_id, exchange_name, region, base_currency, api_enabled, 
             rate_limit_per_minute, priority_order, ccxt_id, is_active)
            VALUES (:id, :name, :region, :currency, :enabled, :rate_limit, :priority, :ccxt_id, :active)
            ON DUPLICATE KEY UPDATE 
                exchange_name=VALUES(exchange_name),
                region=VALUES(region),
                rate_limit_per_minute=VALUES(rate_limit_per_minute)
        """), {
            'id': exchange[0], 'name': exchange[1], 'region': exchange[2],
            'currency': exchange[3], 'enabled': exchange[4], 'rate_limit': exchange[5],
            'priority': exchange[6], 'ccxt_id': exchange[7], 'active': True
        })
    
    print(f"   ✅ {len(exchanges)}개 거래소 등록 완료")

def create_useful_views(conn):
    """유용한 뷰들 생성"""
    print("👁️ 유용한 뷰들 생성...")
    
    # 1. 한국 거래소 통합 뷰
    conn.execute(text("DROP VIEW IF EXISTS v_korean_coins"))
    conn.execute(text("""
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
    """))
    
    # 2. 김치프리미엄 계산 가능 코인 뷰
    conn.execute(text("DROP VIEW IF EXISTS v_kimchi_ready_coins"))
    conn.execute(text("""
        CREATE VIEW v_kimchi_ready_coins AS
        SELECT 
            cm.coingecko_id,
            cm.symbol,
            cm.name_en,
            cm.image_url,
            cm.market_cap_rank,
            kc.korean_name,
            kc.exchange as korean_exchange,
            COUNT(DISTINCT ps.exchange_id) as global_exchange_count,
            MAX(ps.collected_at) as last_price_update
        FROM coin_master cm
        JOIN v_korean_coins kc ON cm.coingecko_id = kc.coingecko_id
        JOIN price_snapshots ps ON cm.coingecko_id = ps.coingecko_id
        JOIN exchange_registry er ON ps.exchange_id = er.exchange_id AND er.region = 'GLOBAL'
        WHERE cm.is_active = 1 
          AND kc.is_active = 1
          AND ps.collected_at > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
        GROUP BY cm.coingecko_id, cm.symbol, cm.name_en, cm.image_url, 
                 cm.market_cap_rank, kc.korean_name, kc.exchange
        HAVING global_exchange_count >= 2
        ORDER BY cm.market_cap_rank ASC
    """))
    
    print("   ✅ v_korean_coins, v_kimchi_ready_coins 뷰 생성 완료")

if __name__ == "__main__":
    try:
        print("🚀 새로운 데이터베이스 스키마 생성 시작\n")
        
        # 1. 새 스키마 생성
        create_new_schema()
        
        # 2. 거래소 등록 정보 초기화
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            initialize_exchange_registry(conn)
            create_useful_views(conn)
            conn.commit()
        
        print("\n🎉 새로운 데이터베이스 스키마 생성 완료!")
        print("💡 다음 단계: Core 모듈 구현 및 데이터 수집 시스템 구축")
        
    except Exception as e:
        print(f"❌ 스키마 생성 실패: {e}")
        raise