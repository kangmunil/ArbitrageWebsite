# 프로젝트 코드베이스 이해

이 문서는 ArbitrageWebsite 프로젝트의 구조와 작동 방식에 대한 이해를 요약한 것입니다.

## 1. 프로젝트 개요
이 프로젝트는 한국 거래소(업비트, 빗썸)와 해외 거래소(바이낸스, 바이비트 등) 간의 암호화폐 가격 차이인 "김치 프리미엄"을 실시간으로 모니터링하고 시각화하는 웹사이트입니다. 또한, 여러 거래소의 청산 데이터를 집계하여 보여주는 기능도 제공합니다.

## 2. 아키텍처
애플리케이션은 FastAPI 백엔드와 React 프론트엔드로 구성되어 있으며, 실시간 데이터 통신을 위해 주로 WebSocket을 사용합니다. `docker-compose.yml`을 통해 백엔드, 프론트엔드, MySQL 데이터베이스 세 개의 컨테이너를 관리합니다.

## 3. 백엔드 구조 (`backend/`)
백엔드는 다양한 거래소에서 암호화폐 데이터를 가져오고, 김치 프리미엄을 계산하며, 청산 데이터를 수집하여 프론트엔드에 제공하는 FastAPI 애플리케이션입니다.

-   **`main.py`**:
    -   FastAPI 애플리케이션의 진입점입니다.
    -   `ConnectionManager` 클래스를 사용하여 가격 및 청산 데이터용 WebSocket 연결을 통합 관리합니다.
    -   애플리케이션 시작 시 백그라운드 태스크(`price_aggregator`, `start_liquidation_collection`)를 시작하여 데이터 수집을 자동화합니다.
    -   `/ws/prices` 및 `/ws/liquidations` 두 개의 WebSocket 엔드포인트를 제공합니다.
    -   과거 가격, 공포/탐욕 지수, 집계된 청산 데이터(`api/liquidations/aggregated`) 등을 위한 REST API 엔드포인트를 정의합니다.
    -   CORS 미들웨어가 설정되어 있습니다.
-   **`services.py`**:
    -   다양한 암호화폐 거래소 API(업비트, 바이낸스, 바이비트)와의 통합을 처리합니다.
    -   업비트, 바이낸스, 바이비트의 WebSocket 클라이언트를 통해 실시간 티커 정보를 수집하고 `shared_data`에 저장합니다.
    -   네이버 금융 웹 스크래핑을 통해 USD/KRW 환율을 가져옵니다.
    -   alternative.me API를 통해 암호화폐 공포/탐욕 지수를 조회합니다.
    -   `shared_data` 딕셔너리를 통해 실시간 데이터를 관리합니다.
-   **`liquidation_services.py`**:
    -   여러 거래소(바이낸스, 바이비트, OKX, BitMEX, Bitget, Hyperliquid)에서 실시간 청산 데이터를 수집하는 것을 관리합니다.
    -   바이낸스를 제외한 대부분의 거래소는 API 인증 문제 및 연결 불안정성으로 인해 시뮬레이션 데이터를 생성하여 사용합니다.
    -   수집된 청산 데이터를 1분 단위 버킷으로 집계하여 메모리에 저장합니다 (`liquidation_data`).
    -   `get_aggregated_liquidation_data` 함수를 통해 집계된 청산 데이터를 반환합니다.
    -   연결된 WebSocket 클라이언트에 실시간 청산 업데이트를 브로드캐스트합니다.
-   **`database.py`**: SQLAlchemy를 사용하여 데이터베이스 연결 및 세션을 관리합니다.
-   **`models.py`**: `Exchange`, `Cryptocurrency`, `CoinPrice`, `PremiumHistory` 등 데이터베이스 테이블에 매핑되는 SQLAlchemy ORM 모델을 정의합니다.
-   **`schemas.py`**: API 요청/응답의 유효성 검사 및 데이터 직렬화를 위한 Pydantic 스키마를 정의합니다.
-   **`create_db_tables.py`**: `models.py`에 정의된 모델을 기반으로 데이터베이스에 테이블을 생성하는 스크립트입니다.
-   **`seed.py`**: `exchanges.csv`와 `cryptocurrencies.csv` 파일의 데이터를 데이터베이스에 초기 데이터로 채우는 스크립트입니다 (현재 사용되지 않음).
-   **`backend/Dockerfile`**: 백엔드 서비스의 Docker 이미지를 빌드합니다.

## 4. 프론트엔드 구조 (`frontend/`)
프론트엔드는 백엔드로부터 데이터를 받아 사용자에게 시각적으로 보여주는 React 애플리케이션입니다.

-   **`App.js`**:
    -   메인 애플리케이션 컴포넌트입니다.
    -   `/ws/prices` WebSocket 엔드포인트에 연결하여 실시간 가격 데이터를 수신하고 상태를 관리합니다.
    -   `Header`, `FearGreedIndex`, `SidebarLiquidations`, `CoinTable` 컴포넌트를 렌더링합니다.
-   **`components/CoinTable.js`**:
    -   선택된 국내 및 해외 거래소 간의 암호화폐 가격을 테이블 형태로 비교하여 보여줍니다.
    -   실시간으로 김치 프리미엄을 계산하고 표시합니다.
    -   사용자가 국내/해외 거래소를 직접 선택할 수 있는 드롭다운 메뉴를 제공합니다.
-   **`components/LiquidationChart.js`**:
    -   `/ws/liquidations` WebSocket 엔드포인트에 연결하여 실시간 청산 데이터를 시각화합니다.
    -   실시간 청산 스트림과 5분 단위 누적 차트 두 부분을 제공합니다.
    -   사용자가 차트에 표시할 거래소를 선택할 수 있는 체크박스 기능을 제공합니다.
    -   WebSocket 연결 실패 시, REST API를 통해 데이터를 가져오거나 데모 데이터를 생성하여 차트를 표시하는 Fallback 기능이 구현되어 있습니다.
-   **`components/SidebarLiquidations.js`**:
    -   사이드바에 표시되는 청산 데이터 위젯입니다.
    -   `useLiquidations` 커스텀 훅을 사용하여 데이터를 관리합니다.
    -   `Recharts`를 사용하여 5분 및 1시간 단위의 거래소별 누적 청산 데이터를 수평 막대그래프로 시각화합니다.
-   **`hooks/useLiquidations.js`**:
    -   실시간 청산 데이터 수신 및 상태 관리를 위한 커스텀 훅입니다.
    -   WebSocket 연결, 데이터 집계 로직을 캡슐화하여 코드의 재사용성과 유지보수성을 높입니다.
    -   `/api/liquidations/aggregated` REST API를 통해 초기 데이터를 가져오고, WebSocket을 통해 실시간 업데이트를 받습니다.
-   **`components/FearGreedIndex.js`**: 게이지 차트(react-gauge-chart)를 사용하여 암호화폐 공포/탐욕 지수를 시각적으로 표시합니다.
-   **`frontend/Dockerfile`**: 프론트엔드 서비스의 Docker 이미지를 빌드합니다.

## 5. 데이터 흐름
1.  백엔드의 `services.py` 모듈은 WebSocket을 통해 업비트, 바이낸스, 바이비트에서 실시간 가격 데이터를 수집하고, 웹 스크래핑을 통해 USD/KRW 환율을 가져와 `shared_data`에 저장합니다.
2.  `main.py`의 `price_aggregator` 태스크는 `shared_data`를 주기적으로 읽어 김치 프리미엄을 계산하고, `/ws/prices` WebSocket을 통해 프론트엔드에 브로드캐스트합니다.
3.  `liquidation_services.py` 모듈은 별도의 태스크에서 실시간(바이낸스) 및 시뮬레이션(기타 거래소) 청산 데이터를 수집하고 1분 단위로 집계하여 `liquidation_data`에 저장합니다.
4.  집계된 청산 데이터는 `/ws/liquidations` WebSocket을 통해 프론트엔드에 브로드캐스트되며, `/api/liquidations/aggregated` REST API를 통해서도 조회 가능합니다.
5.  프론트엔드의 `App.js`는 `/ws/prices`를 구독하여 `CoinTable.js`에 데이터를 전달합니다.
6.  `CoinTable.js`는 전달받은 데이터와 사용자가 선택한 거래소에 맞춰 실시간 가격 및 프리미엄을 업데이트합니다.
7.  `SidebarLiquidations.js`와 `LiquidationChart.js`는 `useLiquidations` 훅을 통해 `/ws/liquidations`를 구독하여 청산 데이터를 시각화합니다.

## 6. 개발 노트
-   프론트엔드는 `ws://localhost:8000` 또는 `ws://127.0.0.1:8000`에서 백엔드 WebSocket에 연결합니다.
-   백엔드는 웹 스크래핑을 통해 네이버 금융에서 USD/KRW 환율을 가져오므로, 네이버 금융의 HTML 구조 변경 시 기능에 영향을 받을 수 있습니다.
-   가격 추적 대상 암호화폐는 `main.py`에서 업비트의 모든 KRW 마켓을 동적으로 가져오도록 변경되었습니다.
-   데이터베이스 자격 증명은 `docker-compose.yml`에 하드코딩되어 있습니다.
-   초기 데이터베이스 테이블 생성은 `docker exec -it <backend_container_name> python -m app.create_db_tables` 명령어를 통해 수동으로 실행해야 합니다.
