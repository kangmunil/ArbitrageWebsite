import React, { useState, useMemo } from 'react';
import './CoinTable.css';

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
function CoinTable({ allCoinsData, selectedDomesticExchange, setSelectedDomesticExchange, selectedGlobalExchange, setSelectedGlobalExchange }) {
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
  const [sortColumn, setSortColumn] = useState('domestic_volume'); // 기본 정렬 대상 열: 한국 거래소 거래량
  const [sortDirection, setSortDirection] = useState('desc'); // 기본 정렬 방향: 내림차순
  const [showAll, setShowAll] = useState(false); // 더보기 상태

  const processedData = useMemo(() => {
    if (!allCoinsData || allCoinsData.length === 0) {
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
    }).filter(coin => coin.domestic_price !== null && coin.global_price !== null); // 국내/해외 가격이 있는 코인만 표시

    // 검색어 필터링
    if (searchTerm) {
      data = data.filter(coin =>
        coin.symbol.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // 정렬
    if (sortColumn) {
      data.sort((a, b) => {
        const aValue = a[sortColumn];
        const bValue = b[sortColumn];

        if (aValue === null || aValue === undefined) return sortDirection === 'asc' ? 1 : -1;
        if (bValue === null || bValue === undefined) return sortDirection === 'asc' ? -1 : 1;

        if (typeof aValue === 'string') {
          return sortDirection === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
        } else {
          return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
        }
      });
    }

    return data;
  }, [allCoinsData, searchTerm, sortColumn, sortDirection, selectedDomesticExchange, selectedGlobalExchange]);

  const displayData = useMemo(() => {
    return showAll ? processedData : processedData.slice(0, 20);
  }, [processedData, showAll]);

  if (!allCoinsData || allCoinsData.length === 0) {
    return (
      <div className="w-full max-w-[960px] rounded-md bg-gray-900 text-[14px] text-gray-200 p-8">
        <div className="text-center">
          <p className="text-lg">코인 데이터를 불러오는 중...</p>
          <p className="text-sm text-gray-400 mt-2">WebSocket 연결을 확인하고 있습니다.</p>
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

  const getCoinName = (symbol) => {
    const coinNames = {
      'BTC': '비트코인',
      'ETH': '이더리움', 
      'XRP': '엑스알피(리플)',
      'SOL': '솔라나',
      'ADA': '에이다',
      'DOT': '폴카닷',
      'LINK': '체인링크',
      'UNI': '유니스왑',
      'AVAX': '아발란체'
    };
    return coinNames[symbol] || symbol;
  };

  const getCoinIcon = (symbol) => {
    const iconUrls = {
      'BTC': 'https://assets.coingecko.com/coins/images/1/standard/bitcoin.png',
      'ETH': 'https://assets.coingecko.com/coins/images/279/standard/ethereum.png',
      'XRP': 'https://assets.coingecko.com/coins/images/44/standard/xrp-symbol-white-128.png',
      'SOL': 'https://assets.coingecko.com/coins/images/4128/standard/solana.png'
    };
    return iconUrls[symbol] || null;
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
          placeholder="Search by symbol..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input h-8 leading-[32px] flex items-center"
        />
      </div>

      {/* 호가판형 테이블 */}
      <div className="w-full max-w-[960px] rounded-md coin-table text-[14px] leading-tight text-gray-200 shadow">
        {/* 실시간 업데이트 확인 */}
        <div className="px-3 py-1 text-xs text-green-400 border-b border-gray-700">
          마지막 업데이트: {new Date().toLocaleTimeString('ko-KR')} | 코인 수: {displayData.length}개
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
            <div
              key={coin.symbol}
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
}

export default CoinTable;