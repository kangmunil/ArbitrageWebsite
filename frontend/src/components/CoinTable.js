import React, { useState, useMemo } from 'react';

function CoinTable({ allCoinsData, selectedDomesticExchange, setSelectedDomesticExchange, selectedGlobalExchange, setSelectedGlobalExchange }) {
  const exchangeDisplayNames = {
    upbit: 'Upbit',
    bithumb: 'Bithumb',
    binance: 'Binance',
    bybit: 'Bybit',
    okx: 'OKX',
    gateio: 'Gate.io',
    mexc: 'MEXC',
  };
  const [searchTerm, setSearchTerm] = useState('');
  const [sortColumn, setSortColumn] = useState(null);
  const [sortDirection, setSortDirection] = useState('asc');

  const filteredAndSortedData = useMemo(() => {
    if (!allCoinsData || allCoinsData.length === 0) {
      return []; // Return empty array if data is not available yet
    }

    let filteredData = allCoinsData.filter(coin =>
      coin.symbol.toLowerCase().includes(searchTerm.toLowerCase())
    ).map(coin => {
      // 선택된 국내 거래소 가격
      const domesticPriceKey = `${selectedDomesticExchange}_price`;
      const domesticPrice = coin[domesticPriceKey];

      // 선택된 해외 거래소 가격
      const globalPriceKey = `${selectedGlobalExchange}_price`;
      const globalPrice = coin[globalPriceKey];

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
        global_price: globalPrice,
        domestic_volume: coin[`${selectedDomesticExchange}_volume`],
        global_volume: coin[`${selectedGlobalExchange}_volume`],
        domestic_change_percent: coin[`${selectedDomesticExchange}_change_percent`],
        global_change_percent: coin[`${selectedGlobalExchange}_change_percent`],
        premium: premium,
      };
    }).filter(coin => coin.domestic_price !== null && coin.global_price !== null); // 가격이 없는 코인 필터링

    if (sortColumn) {
      filteredData.sort((a, b) => {
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
    return filteredData;
  }, [allCoinsData, searchTerm, sortColumn, sortDirection, selectedDomesticExchange, selectedGlobalExchange]);

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
            <th onClick={() => handleSort('domestic_price')}>{exchangeDisplayNames[selectedDomesticExchange]} Price{renderSortIndicator('domestic_price')}</th>
            <th onClick={() => handleSort('global_price')}>{exchangeDisplayNames[selectedGlobalExchange]} Price{renderSortIndicator('global_price')}</th>
            <th onClick={() => handleSort('global_volume')}>{exchangeDisplayNames[selectedGlobalExchange]} Volume (24h){renderSortIndicator('global_volume')}</th>
            <th onClick={() => handleSort('global_change_percent')}>{exchangeDisplayNames[selectedGlobalExchange]} Change (%){renderSortIndicator('global_change_percent')}</th>
            <th onClick={() => handleSort('premium')}>Kimchi Premium (%){renderSortIndicator('premium')}</th>
          </tr>
        </thead>
        <tbody>
          {filteredAndSortedData.map((coin) => (
            <tr key={coin.symbol}>
              <td>{coin.symbol}</td>
              <td>{coin.domestic_price ? coin.domestic_price.toLocaleString() : 'N/A'} KRW</td>
              <td>{coin.global_price ? `${coin.global_price.toLocaleString()}` : 'N/A'}</td>
              <td>{coin.global_volume ? coin.global_volume.toLocaleString() : 'N/A'}</td>
              <td>{coin.global_change_percent ? `${coin.global_change_percent.toFixed(2)}%` : 'N/A'}</td>
              <td className={coin.premium > 0 ? 'premium-plus' : 'premium-minus'}>
                {coin.premium !== null ? `${coin.premium}%` : 'N/A'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default CoinTable;
