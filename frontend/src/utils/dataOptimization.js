/**
 * 데이터 필터링 및 정렬 최적화 유틸리티
 * 
 * 주요 최적화 기능:
 * 1. 메모이제이션된 필터링
 * 2. 최적화된 정렬 알고리즘
 * 3. 검색 인덱싱
 * 4. 가상화 지원
 */

// LRU 캐시 구현
class LRUCache {
  /**
   * LRU (Least Recently Used) 캐시를 구현합니다.
   * 지정된 최대 크기를 초과하면 가장 오랫동안 사용되지 않은 항목을 제거합니다.
   *
   * @param {number} [maxSize=50] - 캐시의 최대 크기. 기본값은 50입니다.
   */
  constructor(maxSize = 50) {
    this.maxSize = maxSize;
    this.cache = new Map();
  }
  
  /**
   * 캐시에서 지정된 키에 해당하는 값을 가져옵니다.
   * 항목이 존재하면 가장 최근에 사용된 것으로 표시하고 맨 뒤로 이동시킵니다.
   *
   * @param {*} key - 가져올 항목의 키.
   * @returns {*} 키에 해당하는 값 또는 null (항목이 없는 경우).
   */
  get(key) {
    if (this.cache.has(key)) {
      // 최근 사용된 항목을 맨 뒤로 이동
      const value = this.cache.get(key);
      this.cache.delete(key);
      this.cache.set(key, value);
      return value;
    }
    return null;
  }
  
  /**
   * 캐시에 키-값 쌍을 설정합니다.
   * 이미 존재하는 키인 경우 업데이트하고, 캐시가 최대 크기에 도달하면
   * 가장 오랫동안 사용되지 않은 항목을 제거합니다.
   *
   * @param {*} key - 설정할 항목의 키.
   * @param {*} value - 설정할 항목의 값.
   */
  set(key, value) {
    if (this.cache.has(key)) {
      this.cache.delete(key);
    } else if (this.cache.size >= this.maxSize) {
      // 가장 오래된 항목 제거
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    this.cache.set(key, value);
  }
  
  /**
   * 캐시의 모든 항목을 지웁니다.
   */
  clear() {
    this.cache.clear();
  }
}

// 전역 캐시 인스턴스
const filterCache = new LRUCache(100);
const sortCache = new LRUCache(50);
const searchIndexCache = new LRUCache(10);

/**
 * 주어진 코인 데이터에 대한 검색 인덱스를 생성합니다.
 * 심볼, 한글명, 그리고 부분 문자열을 포함하여 효율적인 검색을 가능하게 합니다.
 * 캐싱을 통해 반복적인 인덱스 생성을 최적화합니다.
 *
 * @param {Array<Object>} data - 검색 인덱스를 생성할 코인 데이터 배열.
 * @param {Function} getCoinName - 코인 심볼에 해당하는 한글명을 반환하는 함수.
 * @returns {Map<string, number[]>} 검색어(키)와 해당 코인 데이터의 인덱스 배열(값)을 매핑하는 Map 객체.
 */
export const createSearchIndex = (data, getCoinName) => {
  const cacheKey = `search_${data.length}_${Date.now()}`;
  
  // 캐시에서 확인
  const cached = searchIndexCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  
  const index = new Map();
  
  data.forEach((coin, idx) => {
    const symbol = coin.symbol.toLowerCase();
    const koreanName = getCoinName(coin.symbol).toLowerCase();
    
    // 심볼로 인덱싱
    if (!index.has(symbol)) {
      index.set(symbol, []);
    }
    index.get(symbol).push(idx);
    
    // 한글명으로 인덱싱
    if (koreanName !== symbol) {
      if (!index.has(koreanName)) {
        index.set(koreanName, []);
      }
      index.get(koreanName).push(idx);
    }
    
    // 부분 문자열로도 인덱싱 (3글자 이상)
    for (let i = 0; i <= symbol.length - 3; i++) {
      const substring = symbol.substr(i, 3);
      if (!index.has(substring)) {
        index.set(substring, []);
      }
      index.get(substring).push(idx);
    }
    
    for (let i = 0; i <= koreanName.length - 2; i++) {
      const substring = koreanName.substr(i, 2);
      if (!index.has(substring)) {
        index.set(substring, []);
      }
      index.get(substring).push(idx);
    }
  });
  
  searchIndexCache.set(cacheKey, index);
  return index;
};

/**
 * 검색어에 따라 코인 데이터를 최적화하여 필터링합니다.
 * 짧은 검색어는 간단한 필터링을, 긴 검색어는 `createSearchIndex`를 활용한 인덱스 기반 검색을 수행합니다.
 * 캐싱을 통해 필터링 성능을 향상시킵니다.
 *
 * @param {Array<Object>} data - 필터링할 코인 데이터 배열.
 * @param {string} searchTerm - 사용자가 입력한 검색어.
 * @param {Function} getCoinName - 코인 심볼에 해당하는 한글명을 반환하는 함수.
 * @returns {Array<Object>} 필터링된 코인 데이터 배열.
 */
export const optimizedFilter = (data, searchTerm, getCoinName) => {
  if (!searchTerm || searchTerm.length === 0) {
    return data;
  }
  
  const cacheKey = `filter_${searchTerm}_${data.length}`;
  const cached = filterCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  
  const searchLower = searchTerm.toLowerCase();
  
  // 짧은 검색어는 간단한 필터링
  if (searchTerm.length < 3) {
    const filtered = data.filter(coin => {
      const symbol = coin.symbol.toLowerCase();
      const koreanName = getCoinName(coin.symbol).toLowerCase();
      return symbol.includes(searchLower) || koreanName.includes(searchLower);
    });
    
    filterCache.set(cacheKey, filtered);
    return filtered;
  }
  
  // 긴 검색어는 인덱스 활용
  const searchIndex = createSearchIndex(data, getCoinName);
  const matchedIndices = new Set();
  
  // 정확한 매치 우선
  if (searchIndex.has(searchLower)) {
    searchIndex.get(searchLower).forEach(idx => matchedIndices.add(idx));
  }
  
  // 부분 매치
  for (const [key, indices] of searchIndex.entries()) {
    if (key.includes(searchLower) || searchLower.includes(key)) {
      indices.forEach(idx => matchedIndices.add(idx));
    }
  }
  
  const filtered = Array.from(matchedIndices)
    .sort((a, b) => a - b)
    .map(idx => data[idx]);
  
  filterCache.set(cacheKey, filtered);
  return filtered;
};

/**
 * 코인 데이터를 지정된 열과 방향에 따라 최적화하여 정렬합니다.
 * 작은 배열에는 기본 정렬을 사용하고, 큰 배열에는 Quick Sort 변형을 사용합니다.
 * 캐싱을 통해 정렬 성능을 향상시킵니다.
 *
 * @param {Array<Object>} data - 정렬할 코인 데이터 배열.
 * @param {string} sortColumn - 정렬 기준으로 사용할 열의 이름.
 * @param {'asc' | 'desc'} sortDirection - 정렬 방향 ('asc' 또는 'desc').
 * @returns {Array<Object>} 정렬된 코인 데이터 배열.
 */
export const optimizedSort = (data, sortColumn, sortDirection) => {
  if (!sortColumn || data.length <= 1) {
    return data;
  }
  
  const cacheKey = `sort_${sortColumn}_${sortDirection}_${data.length}`;
  const cached = sortCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  
  // 작은 배열은 기본 정렬 사용
  if (data.length < 50) {
    const sorted = [...data].sort((a, b) => {
      const aValue = a[sortColumn];
      const bValue = b[sortColumn];
      
      if (aValue === null || aValue === undefined) return sortDirection === 'asc' ? 1 : -1;
      if (bValue === null || bValue === undefined) return sortDirection === 'asc' ? -1 : 1;
      
      if (typeof aValue === 'string') {
        return sortDirection === 'asc' ? 
          aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
      } else {
        return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
      }
    });
    
    sortCache.set(cacheKey, sorted);
    return sorted;
  }
  
  // 큰 배열은 Quick Sort 사용
  const quickSort = (arr, low = 0, high = arr.length - 1) => {
    if (low < high) {
      const pi = partition(arr, low, high);
      quickSort(arr, low, pi - 1);
      quickSort(arr, pi + 1, high);
    }
    return arr;
  };
  
  const partition = (arr, low, high) => {
    const pivot = arr[high][sortColumn];
    let i = low - 1;
    
    for (let j = low; j < high; j++) {
      const currentValue = arr[j][sortColumn];
      let shouldSwap = false;
      
      if (currentValue === null || currentValue === undefined) {
        shouldSwap = sortDirection === 'desc';
      } else if (pivot === null || pivot === undefined) {
        shouldSwap = sortDirection === 'asc';
      } else if (typeof currentValue === 'string') {
        const comparison = currentValue.localeCompare(pivot);
        shouldSwap = sortDirection === 'asc' ? comparison <= 0 : comparison >= 0;
      } else {
        shouldSwap = sortDirection === 'asc' ? currentValue <= pivot : currentValue >= pivot;
      }
      
      if (shouldSwap) {
        i++;
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
    }
    
    [arr[i + 1], arr[high]] = [arr[high], arr[i + 1]];
    return i + 1;
  };
  
  const sorted = quickSort([...data]);
  sortCache.set(cacheKey, sorted);
  return sorted;
};

/**
 * 가상 스크롤링을 위해 데이터를 청크(덩어리)로 분할합니다.
 * 큰 데이터 세트를 작은 부분으로 나누어 성능을 최적화합니다.
 *
 * @param {Array<Object>} data - 청크로 분할할 데이터 배열.
 * @param {number} [chunkSize=20] - 각 청크의 최대 크기. 기본값은 20입니다.
 * @returns {Array<Object>} 각 청크의 시작/끝 인덱스와 데이터를 포함하는 배열.
 */
export const createVirtualizedChunks = (data, chunkSize = 20) => {
  const chunks = [];
  for (let i = 0; i < data.length; i += chunkSize) {
    chunks.push({
      startIndex: i,
      endIndex: Math.min(i + chunkSize, data.length),
      data: data.slice(i, i + chunkSize)
    });
  }
  return chunks;
};

/**
 * 디바운스된 함수를 생성하여, 특정 시간(delay) 내에 여러 번 호출되어도
 * 마지막 호출만 실행되도록 합니다.
 *
 * @param {Function} callback - 디바운스할 함수.
 * @param {number} [delay=300] - 디바운스 지연 시간(ms). 기본값은 300ms입니다.
 * @returns {Function} 디바운스된 함수.
 */
export const createDebouncedSearch = (callback, delay = 300) => {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      callback(...args);
    }, delay);
  };
};
