import React, { useState, useEffect } from 'react';
import './CoinTable.css';
import PriceCell from './PriceCell';
import PremiumCell from './PremiumCell';

// 개별 코인 행 컴포넌트 (메모이제이션 완전 제거 - 강제 리렌더링)
const CoinRow = ({ coin, index, getCoinName, formatPrice, formatVolume, exchangeDisplayNames, selectedDomesticExchange, selectedGlobalExchange }) => {
  // CoinRow 디버그 로그 (XRP만)
  if (coin.symbol === 'XRP') {
    console.log(`🎯 [CoinRow] XRP 받은 props: domestic_price=${coin.domestic_price}, global_price=${coin.global_price}`);
  }
  const getCoinIcon = (symbol) => {
    const iconUrls = {
      'BTC': 'https://assets.coingecko.com/coins/images/1/standard/bitcoin.png',
      'ETH': 'https://assets.coingecko.com/coins/images/279/standard/ethereum.png',
      'XRP': 'https://assets.coingecko.com/coins/images/44/standard/xrp-symbol-white-128.png',
      'SOL': 'https://assets.coingecko.com/coins/images/4128/standard/solana.png'
    };
    return iconUrls[symbol] || null;
  };

  return (
    <div
      className={`!grid !grid-cols-12 cursor-pointer gap-x-2 border-t border-gray-700/40 px-3 py-2 transition-colors hover:bg-gray-700/20 ${
        index === 0 ? 'bg-blue-500/10 hover:bg-blue-500/20' : ''
      }`}
    >
      {/* 이름 */}
      <div className="col-span-3 flex min-w-0 items-center space-x-2">
        {getCoinIcon(coin.symbol) ? (
          <img 
            className="size-4 flex-shrink-0 rounded-full" 
            src={getCoinIcon(coin.symbol)} 
            alt={coin.symbol}
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.nextSibling.style.display = 'flex';
            }}
          />
        ) : null}
        <div 
          className={`size-4 flex-shrink-0 rounded-full bg-gray-600 items-center justify-center text-[10px] text-white font-bold ${
            getCoinIcon(coin.symbol) ? 'hidden' : 'flex'
          }`}
        >
          {coin.symbol.charAt(0)}
        </div>
        <div className="min-w-0">
          <p className="truncate font-medium text-white">{getCoinName(coin.symbol)}</p>
          <p className="truncate text-[11px] text-gray-400">{coin.symbol}</p>
        </div>
      </div>

      {/* 현재가 */}
      <div className="col-span-3 flex flex-col items-end">
        <span className="font-medium text-white">
          <PriceCell 
            price={coin.domestic_price}
            currency="₩" 
          />
        </span>
        <span className="text-gray-400">
          <PriceCell 
            price={coin.global_price}
            currency="$" 
          />
        </span>
      </div>

      {/* 김프 */}
      <div className="col-span-2 flex flex-col items-end">
        <PremiumCell 
          premium={coin.premium}
        />
      </div>

      {/* 전일대비 */}
      <div className="col-span-2 flex flex-col items-end">
        <span className={`${
          coin.domestic_change_percent > 0 ? 'text-green-400' : 
          coin.domestic_change_percent < 0 ? 'text-red-400' : 'text-gray-400'
        }`}>
          {coin.domestic_change_percent ? 
            `${coin.domestic_change_percent > 0 ? '+' : ''}${coin.domestic_change_percent.toFixed(2)}%` : 'N/A'}
        </span>
      </div>

      {/* 거래량 */}
      <div className="col-span-2 flex flex-col items-end">
        <span className="text-white text-xs">
          {coin.domestic_volume && coin.domestic_volume > 0 ? 
            formatVolume(coin.domestic_volume, 'KRW') : 'N/A'}
        </span>
        <span className="text-gray-400 text-xs">
          {coin.global_volume && coin.global_volume > 0 ? 
            formatVolume(coin.global_volume, 'USD') : 'N/A'}
        </span>
      </div>
    </div>
  );
};

/**
 * 코인 가격 비교 테이블 컴포넌트.
 * 
 * 국내외 거래소 가격을 비교하여 김치 프리미엄을 계산하고 표시합니다.
 * 거래소 선택, 검색, 정렬 기능을 제공합니다.
 * 
 * @param {Object} props - 컴포넌트 props
 * @param {Array} props.allCoinsData - 모든 코인의 가격 데이터 배열
 * @param {string} props.selectedDomesticExchange - 선택된 국내 거래소
 * @param {Function} props.setSelectedDomesticExchange - 국내 거래소 선택 변경 함수
 * @param {string} props.selectedGlobalExchange - 선택된 해외 거래소
 * @param {Function} props.setSelectedGlobalExchange - 해외 거래소 선택 변경 함수
 * @returns {JSX.Element} 코인 테이블 UI
 */
const CoinTable = ({ allCoinsData, selectedDomesticExchange, setSelectedDomesticExchange, selectedGlobalExchange, setSelectedGlobalExchange, connectionStatus, lastUpdate, getConnectionStatusColor, reconnect, refresh, error }) => {
  
  // 3번: CoinTable이 새로운 데이터를 받는지 확인
  const xrpInData = allCoinsData?.find(coin => coin.symbol === 'XRP');
  if (xrpInData) {
    console.log(`🔍 [CoinTable 받은 데이터] XRP allCoinsData: upbit_price=${xrpInData.upbit_price}, 배열길이=${allCoinsData.length}`);
  }

  // formatPrice 함수 (최적화 제거)
  const formatPrice = (price, currency = '₩') => {
    if (!price || price === 0) return 'N/A';
    
    if (price < 0.01) {
      // 0.01 미만의 작은 가격: 최대 6자리 소수점
      return `${currency}${price.toFixed(6)}`;
    } else if (price < 1) {
      // 1 미만: 최대 4자리 소수점
      return `${currency}${price.toFixed(4)}`;
    } else if (price < 100) {
      // 100 미만: 최대 2자리 소수점
      return `${currency}${price.toFixed(2)}`;
    } else {
      // 100 이상: 정수로 표시
      return `${currency}${Math.round(price).toLocaleString()}`;
    }
  };

  // 거래소 코드에서 표시명으로의 매핑
  const exchangeDisplayNames = {
    upbit: 'Upbit',
    bithumb: 'Bithumb',
    binance: 'Binance',
    bybit: 'Bybit',
    okx: 'OKX',
    gateio: 'Gate.io',
    mexc: 'MEXC',
  };
  
  const [searchTerm, setSearchTerm] = useState(''); // 검색어 상태
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState(''); // 디바운스된 검색어
  const [sortColumn, setSortColumn] = useState('domestic_volume'); // 기본 정렬 대상 열: 한국 거래소 거래량
  const [sortDirection, setSortDirection] = useState('desc'); // 기본 정렬 방향: 내림차순
  const [showAll, setShowAll] = useState(false); // 더보기 상태
  const [coinNames, setCoinNames] = useState({}); // API에서 가져온 한글 코인명
  const [isLoadingNames, setIsLoadingNames] = useState(true); // 한글명 로딩 상태
  
  // 로그 관련 유틸리티 제거 (더 이상 사용하지 않음)

  // 거래량 포맷팅 함수 (최적화 제거)
  const formatVolume = (volume, currency) => {
    if (!volume || volume <= 0) return 'N/A';
    
    if (currency === 'KRW') {
      // KRW: 억원 단위로 표시
      if (volume >= 100_000_000) {
        return `${(volume / 100_000_000).toFixed(0)}억`;
      } else if (volume >= 10_000_000) {
        return `${(volume / 10_000_000).toFixed(1)}천만`;
      } else if (volume >= 1_000_000) {
        return `${(volume / 1_000_000).toFixed(1)}백만`;
      } else {
        return `${(volume / 10_000).toFixed(0)}만`;
      }
    } else {
      // USD: 백만달러 단위로 표시
      if (volume >= 1_000_000) {
        return `$${(volume / 1_000_000).toFixed(1)}M`;
      } else if (volume >= 1_000) {
        return `$${(volume / 1_000).toFixed(1)}K`;
      } else {
        return `$${volume.toFixed(0)}`;
      }
    }
  };

  // 컴포넌트 마운트 시 한글 코인명 데이터 로드 (캐시 적용)
  useEffect(() => {
    const fetchCoinNames = async () => {
      try {
        // 직접 API 호출 (캐시 제거)
        const response = await fetch('http://localhost:8000/api/coin-names');
        const data = await response.json();
        
        setCoinNames(data);
        setIsLoadingNames(false);
        console.log('한글 코인명 로드');
      } catch (error) {
        console.error('한글 코인명 로드 실패:', error);
        setIsLoadingNames(false);
      }
    };

    fetchCoinNames();
  }, []);

  // 한글 코인명 반환 함수 (최적화 제거)
  const getCoinName = (symbol) => {
    return coinNames[symbol] || symbol;
  };
  
  // 디바운스 제거 - 즉시 검색어 업데이트
  useEffect(() => {
    setDebouncedSearchTerm(searchTerm);
  }, [searchTerm]);

  // 실시간 업데이트를 위해 useMemo 제거 - 매번 재계산
  const processedData = (() => {
    if (!allCoinsData || allCoinsData.length === 0) {
      return [];
    }

    let data = allCoinsData.map((coin) => {
      const domesticPriceKey = `${selectedDomesticExchange}_price`;
      const domesticVolumeKey = `${selectedDomesticExchange}_volume`;
      const domesticChangePercentKey = `${selectedDomesticExchange}_change_percent`;
      const domesticPrice = coin[domesticPriceKey];
      const domesticVolume = coin[domesticVolumeKey];
      const domesticChangePercent = coin[domesticChangePercentKey];

      const globalPriceKey = `${selectedGlobalExchange}_price`;
      const globalVolumeKey = `${selectedGlobalExchange}_volume_usd`;
      const globalChangePercentKey = `${selectedGlobalExchange}_change_percent`;
      const globalPrice = coin[globalPriceKey];
      const globalVolume = coin[globalVolumeKey];
      const globalChangePercent = coin[globalChangePercentKey];
      
      let premium = null;
      if (domesticPrice !== null && globalPrice !== null && coin.usdt_krw_rate !== null) {
        const globalPriceInKRW = globalPrice * coin.usdt_krw_rate;
        if (globalPriceInKRW !== 0) {
          premium = ((domesticPrice - globalPriceInKRW) / globalPriceInKRW) * 100;
          premium = parseFloat(premium.toFixed(2));
        }
      }

      // XRP 디버그 로그 활성화 (실시간 애니메이션 테스트용)
      if (coin.symbol === 'XRP') {
        console.log(`🔍 [CoinTable processedData] XRP 원본: upbit_price=${coin.upbit_price} → domestic_price=${domesticPrice}`);
      }

      return {
        ...coin,
        domestic_price: domesticPrice,
        domestic_volume: domesticVolume,
        domestic_change_percent: domesticChangePercent,
        global_price: globalPrice,
        global_volume: globalVolume,
        global_change_percent: globalChangePercent,
        premium: premium,
      };
    }).filter(coin => coin.domestic_price !== null && coin.global_price !== null);

    // 최적화 제거 - 기본 배열 메서드 사용
    if (debouncedSearchTerm) {
      data = data.filter(coin => {
        const coinName = getCoinName(coin.symbol).toLowerCase();
        const symbol = coin.symbol.toLowerCase();
        const searchLower = debouncedSearchTerm.toLowerCase();
        return coinName.includes(searchLower) || symbol.includes(searchLower);
      });
    }

    if (sortColumn) {
      data = data.sort((a, b) => {
        let aValue = a[sortColumn];
        let bValue = b[sortColumn];
        
        // null/undefined 값 처리
        if (aValue === null || aValue === undefined) aValue = 0;
        if (bValue === null || bValue === undefined) bValue = 0;
        
        // 문자열 처리
        if (typeof aValue === 'string') {
          return sortDirection === 'asc' 
            ? aValue.localeCompare(bValue)
            : bValue.localeCompare(aValue);
        }
        
        // 숫자 처리
        return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
      });
    }

    return data;
  })(); // 즉시 실행 함수로 변경

  // 실시간 업데이트를 위해 useMemo 제거
  const displayData = showAll ? processedData : processedData.slice(0, 20);
  
  // GAS 코인이 표시되는지 확인 (디버그용)
  const gasInDisplay = displayData.find(coin => coin.symbol === 'GAS');
  if (gasInDisplay) {
    console.log(`🔍 [CoinTable displayData] GAS 코인 포함됨: domestic_price=${gasInDisplay.domestic_price}`);
  } else {
    console.log(`❌ [CoinTable displayData] GAS 코인이 상위 20개에 없음 (전체: ${processedData.length}개)`);
  }

  if (!allCoinsData || allCoinsData.length === 0 || isLoadingNames) {
    return (
      <div className="w-full max-w-[960px] rounded-md bg-gray-900 text-[14px] text-gray-200 p-8">
        <div className="text-center">
          <p className="text-lg">
            {isLoadingNames ? '코인 정보를 불러오는 중...' : '코인 데이터를 불러오는 중...'}
          </p>
          <p className="text-sm text-gray-400 mt-2">
            {isLoadingNames ? '한글 코인명을 로드하고 있습니다.' : 'WebSocket 연결을 확인하고 있습니다.'}
          </p>
        </div>
      </div>
    );
  }

  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const renderSortIndicator = (column) => {
    if (sortColumn === column) {
      return sortDirection === 'asc' ? '🔼' : '🔽';
    }
    return '';
  };

  return (
    <div>
      <div className="coin-table-controls mb-4 flex items-center space-x-4 text-[12px]">
        <div className="exchange-selection flex items-center space-x-2">
          <label htmlFor="domestic-exchange-select" className="flex items-center h-8 leading-[32px]">국내 거래소:</label>
          <select
            id="domestic-exchange-select"
            value={selectedDomesticExchange}
            onChange={(e) => setSelectedDomesticExchange(e.target.value)}
            className="h-8 leading-[32px] flex items-center"
          >
            <option value="upbit">Upbit</option>
            <option value="bithumb">Bithumb</option>
          </select>

          <label htmlFor="global-exchange-select" className="flex items-center h-8 leading-[32px]">해외 거래소:</label>
          <select
            id="global-exchange-select"
            value={selectedGlobalExchange}
            onChange={(e) => setSelectedGlobalExchange(e.target.value)}
            className="h-8 leading-[32px] flex items-center"
          >
            <option value="binance">Binance</option>
            <option value="bybit">Bybit</option>
          </select>
        </div>
        <input
          type="text"
          placeholder="심볼 또는 한글명으로 검색..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input h-8 leading-[32px] flex items-center"
        />
      </div>

      {/* 호가판형 테이블 */}
      <div className="w-full max-w-[960px] mx-auto rounded-md coin-table text-[14px] leading-tight text-gray-200 shadow">
        {/* 실시간 업데이트 확인 */}
        <div className="px-3 py-1 text-xs border-b border-gray-700 flex justify-between items-center">
          <span style={{ color: getConnectionStatusColor && getConnectionStatusColor(connectionStatus) }}>
            ● {connectionStatus ? connectionStatus.toUpperCase() : 'UNKNOWN'}
          </span>
          <span className="text-green-400 flex items-center space-x-2">
            <span>마지막 업데이트: {lastUpdate ? lastUpdate.toLocaleTimeString('ko-KR') : '대기 중'}</span>
            <span>|</span>
            <span>코인 수: {displayData.length}개</span>
            {connectionStatus === 'connected' && (
              <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
            )}
          </span>
          {(connectionStatus === 'failed' || connectionStatus === 'error') && (
            <div className="flex space-x-2">
              {reconnect && (
                <button 
                  onClick={reconnect}
                  className="text-xs bg-blue-600 px-2 py-1 rounded hover:bg-blue-700"
                >
                  재연결
                </button>
              )}
              {refresh && (
                <button 
                  onClick={refresh}
                  className="text-xs bg-green-600 px-2 py-1 rounded hover:bg-green-700"
                >
                  새로고침
                </button>
              )}
            </div>
          )}
          {error && (
            <span className="text-xs text-red-400">
              오류: {error}
            </span>
          )}
        </div>
        
        {/* 헤더 */}
        <div className="hidden md:!grid !grid-cols-12 px-3 py-2 text-xs font-semibold text-gray-400 border-b border-gray-600">
          <div className="col-span-3 cursor-pointer" onClick={() => handleSort('symbol')}>
            이름{renderSortIndicator('symbol')}
          </div>
          <div className="col-span-3 text-right cursor-pointer" onClick={() => handleSort('domestic_price')}>
            {exchangeDisplayNames[selectedDomesticExchange]}/{exchangeDisplayNames[selectedGlobalExchange]}{renderSortIndicator('domestic_price')}
          </div>
          <div className="col-span-2 text-right cursor-pointer" onClick={() => handleSort('premium')}>
            김프{renderSortIndicator('premium')}
          </div>
          <div className="col-span-2 text-right cursor-pointer" onClick={() => handleSort('domestic_change_percent')}>
            전일대비{renderSortIndicator('domestic_change_percent')}
          </div>
          <div className="col-span-2 text-right cursor-pointer" onClick={() => handleSort('domestic_volume')}>
            거래량{renderSortIndicator('domestic_volume')}
          </div>
        </div>

        {/* 데이터 행들 */}
        <div>
          {displayData.map((coin, index) => (
            <CoinRow
              key={`${coin.symbol}-${coin.domestic_price || 0}-${coin.global_price || 0}`}
              coin={coin}
              index={index}
              getCoinName={getCoinName}
              formatPrice={formatPrice}
              formatVolume={formatVolume}
              exchangeDisplayNames={exchangeDisplayNames}
              selectedDomesticExchange={selectedDomesticExchange}
              selectedGlobalExchange={selectedGlobalExchange}
            />
          ))}
        </div>
      </div>
      
      {!showAll && processedData.length > 20 && (
        <button 
          onClick={() => setShowAll(true)} 
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
        >
          더보기 ({processedData.length - 20}개)
        </button>
      )}
    </div>
  );
};

CoinTable.displayName = 'CoinTable';

export default CoinTable;