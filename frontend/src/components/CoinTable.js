import React, { useState, useEffect } from 'react';
import './CoinTable.css';
import PriceCell from './PriceCell';
import PremiumCell from './PremiumCell';

// 개별 코인 행 컴포넌트 (React.memo로 메모이제이션 적용)
const CoinRow = React.memo(({ coin, index, getCoinName, formatPrice, formatVolume, exchangeDisplayNames, selectedDomesticExchange, selectedGlobalExchange, isWatched, onToggleWatch, coinImages }) => {
  /**
   * 코인 아이콘 URL을 반환합니다.
   * @param {string} symbol - 코인 심볼
   * @returns {string | null} 코인 아이콘 URL 또는 null
   */
  const getCoinIcon = (symbol) => {
    // 1순위: DB에서 가져온 이미지 URL
    if (coinImages[symbol]) {
      return coinImages[symbol];
    }
    
    // 2순위: 하드코딩된 백업 URL (DB에 없는 경우)
    const fallbackUrls = {
      'BTC': 'https://assets.coingecko.com/coins/images/1/standard/bitcoin.png',
      'ETH': 'https://assets.coingecko.com/coins/images/279/standard/ethereum.png',
      'XRP': 'https://assets.coingecko.com/coins/images/44/standard/xrp-symbol-white-128.png',
      'SOL': 'https://assets.coingecko.com/coins/images/4128/standard/solana.png'
    };
    return fallbackUrls[symbol] || null;
  };

  return (
    <div
      className={`!grid !grid-cols-12 cursor-pointer gap-x-2 border-t border-gray-700/40 px-3 py-2 transition-colors hover:bg-gray-700/20 ${
        isWatched 
          ? 'bg-yellow-500/10 hover:bg-yellow-500/20 border-l-4 border-yellow-500' 
          : index === 0 
            ? 'bg-blue-500/10 hover:bg-blue-500/20' 
            : ''
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
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-white">{getCoinName(coin.symbol)}</p>
          <p className="truncate text-[11px] text-gray-400">{coin.symbol}</p>
        </div>
        {/* 관심 코인 별 모양 버튼 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleWatch(coin.symbol);
          }}
          className="flex-shrink-0 text-lg hover:scale-110 transition-transform"
          title={isWatched ? "관심 코인에서 제거" : "관심 코인으로 추가"}
        >
          {isWatched ? '⭐' : '☆'}
        </button>
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
});

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
  
  // 운영 모드: 데이터 수신 확인 비활성화

  /**
   * 가격을 포맷팅합니다.
   * @param {number} price - 포맷할 가격
   * @param {string} currency - 통화 (기본값: '₩')
   * @returns {string} 포맷된 가격 문자열
   */
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
  const [coinImages, setCoinImages] = useState({}); // API에서 가져온 코인 이미지 URL
  const [isLoadingNames, setIsLoadingNames] = useState(true); // 한글명 로딩 상태
  const [watchedCoins, setWatchedCoins] = useState(new Set()); // 관심 코인 목록
  
  // 로그 관련 유틸리티 제거 (더 이상 사용하지 않음)

  /**
   * 거래량을 포맷팅합니다.
   * @param {number} volume - 포맷할 거래량
   * @param {string} currency - 통화
   * @returns {string} 포맷된 거래량 문자열
   */
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

  // 컴포넌트 마운트 시 관심 코인을 localStorage에서 로드
  useEffect(() => {
    try {
      const savedWatchedCoins = localStorage.getItem('watchedCoins');
      if (savedWatchedCoins) {
        setWatchedCoins(new Set(JSON.parse(savedWatchedCoins)));
      }
    } catch (error) {
      console.error('Failed to load watched coins from localStorage:', error);
    }
  }, []);

  // 컴포넌트 마운트 시 한글 코인명과 이미지 URL 데이터 로드
  useEffect(() => {
    const fetchCoinData = async () => {
      try {
        // 한글 코인명과 이미지 URL 병렬로 가져오기
        const [namesResponse, imagesResponse] = await Promise.all([
          fetch('http://localhost:8000/api/coin-names'),
          fetch('http://localhost:8000/api/coin-images')
        ]);
        
        const namesData = await namesResponse.json();
        const imagesData = await imagesResponse.json();
        
        setCoinNames(namesData);
        setCoinImages(imagesData);
        setIsLoadingNames(false);
        console.log('Coin names and images loaded:', Object.keys(namesData).length, 'names,', Object.keys(imagesData).length, 'images');
      } catch (error) {
        console.error('Failed to load coin data:', error);
        setIsLoadingNames(false);
      }
    };

    fetchCoinData();
  }, []);

  /**
   * 코인 심볼에 해당하는 한글명을 반환합니다.
   * @param {string} symbol - 코인 심볼
   * @returns {string} 한글 코인명 또는 심볼
   */
  const getCoinName = (symbol) => {
    return coinNames[symbol] || symbol;
  };

  /**
   * 관심 코인을 토글합니다.
   * @param {string} symbol - 토글할 코인 심볼
   */
  const handleToggleWatch = async (symbol) => {
    try {
      const newWatchedCoins = new Set(watchedCoins);
      
      if (watchedCoins.has(symbol)) {
        // 관심 코인에서 제거
        newWatchedCoins.delete(symbol);
        console.log(`❌ ${symbol} 관심 코인에서 제거`);
      } else {
        // 관심 코인으로 추가 & 백엔드 API 호출
        newWatchedCoins.add(symbol);
        console.log(`⭐ ${symbol} 관심 코인으로 추가`);
        
        // 백엔드에 우선순위 업데이트 요청
        try {
          const response = await fetch(`http://localhost:8000/api/watch-coin/${symbol}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
          });
          
          if (response.ok) {
            const result = await response.json();
            console.log(`🚀 ${symbol} 서버에서 우선순위 업데이트 완료:`, result.message);
          } else {
            console.warn(`⚠️ ${symbol} 서버 우선순위 업데이트 실패`);
          }
        } catch (apiError) {
          console.error('API 호출 오류:', apiError);
          // API 실패해도 로컬 상태는 유지
        }
      }
      
      // 상태 업데이트
      setWatchedCoins(newWatchedCoins);
      
      // localStorage에 저장
      localStorage.setItem('watchedCoins', JSON.stringify([...newWatchedCoins]));
      
    } catch (error) {
      console.error('관심 코인 토글 오류:', error);
    }
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

      // 운영 모드: 상세 로그 비활성화

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

    // 관심 코인을 최상단으로 정렬
    data = data.sort((a, b) => {
      const aIsWatched = watchedCoins.has(a.symbol);
      const bIsWatched = watchedCoins.has(b.symbol);
      
      // 관심 코인이 우선
      if (aIsWatched && !bIsWatched) return -1;
      if (!aIsWatched && bIsWatched) return 1;
      
      // 둘 다 관심 코인이거나 둘 다 일반 코인인 경우 기본 정렬 적용
      if (sortColumn) {
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
      }
      
      return 0;
    });

    return data;
  })(); // 즉시 실행 함수로 변경

  // 실시간 업데이트를 위해 useMemo 제거
  const displayData = showAll ? processedData : processedData.slice(0, 20);
  
  // 디버깅: 데이터 구조 분석
  if (displayData.length === 0) {
    console.log('No coin data available for display');
    console.log('allCoinsData length:', allCoinsData?.length);
    console.log('processedData length:', processedData?.length);
    if (allCoinsData && allCoinsData.length > 0) {
      console.log('Sample coin data:', allCoinsData[0]);
      console.log('Selected exchanges:', selectedDomesticExchange, selectedGlobalExchange);
    }
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

  /**
   * 테이블 정렬을 처리합니다.
   * @param {string} column - 정렬할 컬럼
   */
  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  /**
   * 정렬 표시기를 렌더링합니다.
   * @param {string} column - 정렬 표시기를 렌더링할 컬럼
   * @returns {string} 정렬 표시기 문자열
   */
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
              key={coin.symbol}
              coin={coin}
              index={index}
              getCoinName={getCoinName}
              formatPrice={formatPrice}
              formatVolume={formatVolume}
              exchangeDisplayNames={exchangeDisplayNames}
              selectedDomesticExchange={selectedDomesticExchange}
              selectedGlobalExchange={selectedGlobalExchange}
              isWatched={watchedCoins.has(coin.symbol)}
              onToggleWatch={handleToggleWatch}
              coinImages={coinImages}
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
