import React, { useState, useMemo, useEffect, useCallback, memo } from 'react';
import './CoinTable.css';
import { optimizedFilter, optimizedSort, createDebouncedSearch } from '../utils/dataOptimization';
import cacheManager, { cachedFetch } from '../utils/cacheManager';

// 개별 코인 행 컴포넌트 메모이제이션
const CoinRow = memo(({ coin, index, getCoinName, formatPrice, exchangeDisplayNames, selectedDomesticExchange, selectedGlobalExchange }) => {
  const getCoinIcon = useCallback((symbol) => {
    const iconUrls = {
      'BTC': 'https://assets.coingecko.com/coins/images/1/standard/bitcoin.png',
      'ETH': 'https://assets.coingecko.com/coins/images/279/standard/ethereum.png',
      'XRP': 'https://assets.coingecko.com/coins/images/44/standard/xrp-symbol-white-128.png',
      'SOL': 'https://assets.coingecko.com/coins/images/4128/standard/solana.png'
    };
    return iconUrls[symbol] || null;
  }, []);

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
          {coin.domestic_price ? formatPrice(coin.domestic_price, '₩') : 'N/A'}
        </span>
        <span className="text-gray-400">
          {coin.global_price ? formatPrice(coin.global_price, '$') : 'N/A'}
        </span>
      </div>

      {/* 김프 */}
      <div className="col-span-2 flex flex-col items-end">
        <span className={`${
          coin.premium > 0 ? 'text-emerald-400' : 
          coin.premium < 0 ? 'text-red-400' : 'text-gray-400'
        }`}>
          {coin.premium !== null ? `${coin.premium > 0 ? '+' : ''}${coin.premium.toFixed(2)}%` : 'N/A'}
        </span>
      </div>

      {/* 전일대비 */}
      <div className="col-span-2 flex flex-col items-end">
        <span className={`${
          coin.domestic_change_percent > 0 ? 'text-emerald-400' : 
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
            `${(coin.domestic_volume / 100_000_000).toFixed(0)}억 원` : 'N/A'}
        </span>
        <span className="text-gray-400 text-xs">
          {coin.global_volume && coin.global_volume > 0 ? 
            `$${(coin.global_volume / 1_000_000).toFixed(1)}M` : 'N/A'}
        </span>
      </div>
    </div>
  );
});

CoinRow.displayName = 'CoinRow';

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
const CoinTable = memo(({ allCoinsData, selectedDomesticExchange, setSelectedDomesticExchange, selectedGlobalExchange, setSelectedGlobalExchange, connectionStatus, lastUpdate, getConnectionStatusColor, reconnect }) => {
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

  // 컴포넌트 마운트 시 한글 코인명 데이터 로드 (캐시 적용)
  useEffect(() => {
    const fetchCoinNames = async () => {
      try {
        // 먼저 캐시에서 확인
        const cachedNames = cacheManager.getLocalStorage('coin_names');
        if (cachedNames) {
          setCoinNames(cachedNames);
          setIsLoadingNames(false);
          console.log('한글 코인명 캐시 로드');
          return;
        }
        
        // 캐시된 데이터가 없으면 API 호출
        const response = await cachedFetch(
          'http://localhost:8000/api/coin-names', 
          {}, 
          24 * 60 * 60 * 1000 // 24시간 캐시
        );
        
        setCoinNames(response);
        cacheManager.setLocalStorage('coin_names', response, 24 * 60 * 60 * 1000);
        setIsLoadingNames(false);
      } catch (error) {
        console.error('한글 코인명 로드 실패:', error);
        setIsLoadingNames(false);
        // 오류 시 빈 객체 유지 (심볼이 그대로 표시됨)
      }
    };

    fetchCoinNames();
  }, []);

  // 한글 코인명 반환 함수 (useCallback으로 최적화)
  const getCoinName = useCallback((symbol) => {
    // API에서 가져온 한글명 사용, 없으면 심볼 그대로 반환
    return coinNames[symbol] || symbol;
  }, [coinNames]);
  
  // 디바운스된 검색 핸들러
  const debouncedSearchHandler = useMemo(
    () => createDebouncedSearch((term) => {
      setDebouncedSearchTerm(term);
    }, 300),
    []
  );
  
  // 검색어 변경 시 디바운스 실행
  useEffect(() => {
    debouncedSearchHandler(searchTerm);
  }, [searchTerm, debouncedSearchHandler]);

  const processedData = useMemo(() => {
    
    if (!allCoinsData || allCoinsData.length === 0) {
      console.log('❌ CoinTable: No data to process');
      return [];
    }

    let data = allCoinsData.map(coin => {
      
      // 선택된 국내 거래소 가격, 거래량, 변동률
      const domesticPriceKey = `${selectedDomesticExchange}_price`;
      const domesticVolumeKey = `${selectedDomesticExchange}_volume`;
      const domesticChangePercentKey = `${selectedDomesticExchange}_change_percent`;
      const domesticPrice = coin[domesticPriceKey];
      const domesticVolume = coin[domesticVolumeKey];
      const domesticChangePercent = coin[domesticChangePercentKey];

      // 선택된 해외 거래소 가격, 거래량, 변동률
      const globalPriceKey = `${selectedGlobalExchange}_price`;
      const globalVolumeKey = `${selectedGlobalExchange}_volume`;
      const globalChangePercentKey = `${selectedGlobalExchange}_change_percent`;
      const globalPrice = coin[globalPriceKey];
      const globalVolume = coin[globalVolumeKey];
      const globalChangePercent = coin[globalChangePercentKey];
      


      let premium = null;
      if (domesticPrice !== null && globalPrice !== null && coin.exchange_rate !== null) {
        const globalPriceInKRW = globalPrice * coin.exchange_rate;
        if (globalPriceInKRW !== 0) {
          premium = ((domesticPrice - globalPriceInKRW) / globalPriceInKRW) * 100;
          premium = parseFloat(premium.toFixed(2));
        }
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
    }); // 임시로 필터 비활성화
    
    // 원래 필터 (임시 비활성화)
    // .filter(coin => coin.domestic_price !== null && coin.global_price !== null);
    

    // 최적화된 검색어 필터링
    if (debouncedSearchTerm) {
      data = optimizedFilter(data, debouncedSearchTerm, getCoinName);
    }

    // 최적화된 정렬
    if (sortColumn) {
      data = optimizedSort(data, sortColumn, sortDirection);
    }

    return data;
  }, [allCoinsData, debouncedSearchTerm, sortColumn, sortDirection, selectedDomesticExchange, selectedGlobalExchange, getCoinName]);
  
  // 디버깅: processedData 변경 추적
  

  const displayData = useMemo(() => {
    return showAll ? processedData : processedData.slice(0, 20);
  }, [processedData, showAll]);

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
          <span className="text-green-400">
            마지막 업데이트: {lastUpdate ? lastUpdate.toLocaleTimeString('ko-KR') : '대기 중'} | 코인 수: {displayData.length}개
          </span>
          {connectionStatus === 'failed' && reconnect && (
            <button 
              onClick={reconnect}
              className="text-xs bg-blue-600 px-2 py-1 rounded hover:bg-blue-700"
            >
              재연결
            </button>
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
              key={coin.symbol}
              coin={coin}
              index={index}
              getCoinName={getCoinName}
              formatPrice={formatPrice}
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
});

CoinTable.displayName = 'CoinTable';

export default CoinTable;