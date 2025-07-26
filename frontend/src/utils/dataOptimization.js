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
  constructor(maxSize = 50) {
    this.maxSize = maxSize;
    this.cache = new Map();
  }
  
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
  
  clear() {
    this.cache.clear();
  }
}

// 전역 캐시 인스턴스
const filterCache = new LRUCache(100);
const sortCache = new LRUCache(50);
const searchIndexCache = new LRUCache(10);

/**
 * 검색 인덱스 생성 (한글명과 심볼명 모두 포함)
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
 * 최적화된 검색 필터링
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
 * 최적화된 정렬 (Quick Sort 변형)
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
 * 가상화를 위한 데이터 청크 분할
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
 * 디바운스된 검색 핸들러
 */
export const createDebouncedSearch = (callback, delay = 300) => {
  let timeoutId;
  
  return function debouncedSearch(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => callback.apply(this, args), delay);
  };
};

/**
 * 메모리 사용량 모니터링
 */
export const getMemoryUsage = () => {
  if (performance && performance.memory) {
    return {
      used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
      total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024),
      limit: Math.round(performance.memory.jsHeapSizeLimit / 1024 / 1024)
    };
  }
  return null;
};

/**
 * 캐시 정리
 */
export const clearAllCaches = () => {
  filterCache.clear();
  sortCache.clear();
  searchIndexCache.clear();
  console.log('All data optimization caches cleared');
};

/**
 * 캐시 통계
 */
export const getCacheStats = () => {
  return {
    filterCache: {
      size: filterCache.cache.size,
      maxSize: filterCache.maxSize
    },
    sortCache: {
      size: sortCache.cache.size,
      maxSize: sortCache.maxSize
    },
    searchIndexCache: {
      size: searchIndexCache.cache.size,
      maxSize: searchIndexCache.maxSize
    }
  };
};