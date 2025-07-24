import React, { useState, useMemo } from 'react';

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
    }).filter(coin => coin.domestic_price !== null && coin.global_price !== null && coin.domestic_volume !== null); // 국내/해외 가격 및 국내 거래량 없는 코인 필터링

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
    return <p>Loading coin data...</p>;
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
      return sortDirection === 'asc' ? ' 🔼' : ' 🔽';
    }
    return '';
  };

  return (
    <div>
      <div className="coin-table-controls">
        <div className="exchange-selection">
          <label htmlFor="domestic-exchange-select">국내 거래소:</label>
          <select
            id="domestic-exchange-select"
            value={selectedDomesticExchange}
            onChange={(e) => setSelectedDomesticExchange(e.target.value)}
          >
            <option value="upbit">Upbit</option>
            <option value="bithumb">Bithumb</option>
          </select>

          <label htmlFor="global-exchange-select">해외 거래소:</label>
          <select
            id="global-exchange-select"
            value={selectedGlobalExchange}
            onChange={(e) => setSelectedGlobalExchange(e.target.value)}
          >
            <option value="binance">Binance</option>
            <option value="bybit">Bybit</option>
            {/* <option value="okx">OKX</option>
            <option value="gateio">Gate.io</option>
            <option value="mexc">MEXC</option> */}
          </select>
        </div>
        <input
          type="text"
          placeholder="Search by symbol..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>
      <table>
        <thead>
          <tr>
            <th onClick={() => handleSort('symbol')}>Symbol{renderSortIndicator('symbol')}</th>
            <th onClick={() => handleSort('domestic_price')}>
              한국거래소 가격<br/>
              <small>({exchangeDisplayNames[selectedDomesticExchange]})</small>
              {renderSortIndicator('domestic_price')}
            </th>
            <th onClick={() => handleSort('global_price')}>
              해외거래소 가격<br/>
              <small>({exchangeDisplayNames[selectedGlobalExchange]})</small>
              {renderSortIndicator('global_price')}
            </th>
            <th onClick={() => handleSort('premium')}>김프(%){renderSortIndicator('premium')}</th>
            <th onClick={() => handleSort('domestic_volume')}>거래량 (24h){renderSortIndicator('domestic_volume')}</th>
            <th onClick={() => handleSort('domestic_change_percent')}>24h 변동률{renderSortIndicator('domestic_change_percent')}</th>
          </tr>
        </thead>
        <tbody>
          {displayData.map((coin) => (
            <tr key={coin.symbol}>
              <td>{coin.symbol}</td>
              <td>{coin.domestic_price ? `₩${coin.domestic_price.toLocaleString()}` : 'N/A'}</td>
              <td>{coin.global_price ? `$${coin.global_price.toLocaleString()}` : 'N/A'}</td>
              <td className={coin.premium > 0 ? 'premium-plus' : 'premium-minus'}>
                {coin.premium !== null ? `${coin.premium}%` : 'N/A'}
              </td>
              <td>{coin.domestic_volume ? `₩${(coin.domestic_volume / 100_000_000).toFixed(2)}억` : 'N/A'}</td>
              <td>{coin.domestic_change_percent ? `${coin.domestic_change_percent.toFixed(2)}%` : 'N/A'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!showAll && processedData.length > 20 && (
        <button onClick={() => setShowAll(true)} className="show-more-button">
          더보기 ({processedData.length - 20}개)
        </button>
      )}
    </div>
  );
}

export default CoinTable;
