/**
 * 프론트엔드 캐싱 전략 관리자
 * 
 * 주요 기능:
 * 1. 브라우저 캐시 (localStorage, sessionStorage)
 * 2. 메모리 캐시 (런타임 캐시)
 * 3. API 응답 캐시
 * 4. 이미지 캐시
 * 5. 자동 만료 및 정리
 */

class CacheManager {
  /**
   * CacheManager 인스턴스를 생성합니다.
   */
  constructor() {
    this.memoryCache = new Map();
    this.defaultTTL = 5 * 60 * 1000; // 5분
    this.maxMemoryCacheSize = 100;
    
    // 주기적으로 만료된 항목 정리
    this.startCleanupInterval();
  }
  
  /**
   * 메모리 캐시에 데이터를 저장합니다.
   * @param {string} key - 캐시 키
   * @param {any} data - 저장할 데이터
   * @param {number} ttl - 캐시 유효 기간 (ms)
   */
  setMemoryCache(key, data, ttl = this.defaultTTL) {
    // 캐시 크기 제한
    if (this.memoryCache.size >= this.maxMemoryCacheSize) {
      const firstKey = this.memoryCache.keys().next().value;
      this.memoryCache.delete(firstKey);
    }
    
    const expiryTime = Date.now() + ttl;
    this.memoryCache.set(key, {
      data,
      expiryTime,
      accessCount: 0,
      lastAccess: Date.now()
    });
    
    // Memory cache updated
  }
  
  /**
   * 메모리 캐시에서 데이터를 조회합니다.
   * @param {string} key - 조회할 캐시 키
   * @returns {any | null} 캐시된 데이터 또는 null
   */
  getMemoryCache(key) {
    const cached = this.memoryCache.get(key);
    
    if (!cached) {
      return null;
    }
    
    if (Date.now() > cached.expiryTime) {
      this.memoryCache.delete(key);
      // Cache item expired
      return null;
    }
    
    // 접근 통계 업데이트
    cached.accessCount += 1;
    cached.lastAccess = Date.now();
    
    return cached.data;
  }
  
  /**
   * localStorage에 데이터를 저장합니다. (영구 저장)
   * @param {string} key - 캐시 키
   * @param {any} data - 저장할 데이터
   * @param {number | null} ttl - 캐시 유효 기간 (ms)
   */
  setLocalStorage(key, data, ttl = null) {
    try {
      const cacheData = {
        data,
        timestamp: Date.now(),
        expiryTime: ttl ? Date.now() + ttl : null
      };
      
      localStorage.setItem(`cache_${key}`, JSON.stringify(cacheData));
      // LocalStorage updated
    } catch (error) {
      console.error(`LocalStorage cache failed: ${key}`, error);
      // 저장 공간 부족 시 오래된 항목 정리
      this.cleanupLocalStorage();
    }
  }
  
  /**
   * localStorage에서 데이터를 조회합니다.
   * @param {string} key - 조회할 캐시 키
   * @returns {any | null} 캐시된 데이터 또는 null
   */
  getLocalStorage(key) {
    try {
      const cached = localStorage.getItem(`cache_${key}`);
      if (!cached) {
        return null;
      }
      
      const cacheData = JSON.parse(cached);
      
      // 만료 확인
      if (cacheData.expiryTime && Date.now() > cacheData.expiryTime) {
        localStorage.removeItem(`cache_${key}`);
        // LocalStorage item expired
        return null;
      }
      
      return cacheData.data;
    } catch (error) {
      console.error(`LocalStorage cache read failed: ${key}`, error);
      return null;
    }
  }
  
  /**
   * sessionStorage에 데이터를 저장합니다. (세션 종료 시 삭제)
   * @param {string} key - 캐시 키
   * @param {any} data - 저장할 데이터
   */
  setSessionStorage(key, data) {
    try {
      const cacheData = {
        data,
        timestamp: Date.now()
      };
      
      sessionStorage.setItem(`cache_${key}`, JSON.stringify(cacheData));
      // SessionStorage updated
    } catch (error) {
      console.error(`SessionStorage cache failed: ${key}`, error);
    }
  }
  
  /**
   * sessionStorage에서 데이터를 조회합니다.
   * @param {string} key - 조회할 캐시 키
   * @returns {any | null} 캐시된 데이터 또는 null
   */
  getSessionStorage(key) {
    try {
      const cached = sessionStorage.getItem(`cache_${key}`);
      if (!cached) {
        return null;
      }
      
      const cacheData = JSON.parse(cached);
      return cacheData.data;
    } catch (error) {
      console.error(`SessionStorage cache read failed: ${key}`, error);
      return null;
    }
  }
  
  /**
   * API 응답을 캐시합니다. (메모리 + localStorage 조합)
   * @param {string} url - API URL
   * @param {any} response - 캐시할 응답 데이터
   * @param {number} ttl - 캐시 유효 기간 (ms)
   */
  async cacheApiResponse(url, response, ttl = this.defaultTTL) {
    const key = `api_${this.hashString(url)}`;
    
    // 메모리 캐시에 저장 (빠른 접근)
    this.setMemoryCache(key, response, ttl);
    
    // 중요한 데이터는 localStorage에도 저장
    if (ttl > 30000) { // 30초 이상 TTL인 경우
      this.setLocalStorage(key, response, ttl);
    }
  }
  
  /**
   * 캐시된 API 응답을 조회합니다.
   * @param {string} url - 조회할 API URL
   * @returns {any | null} 캐시된 응답 데이터 또는 null
   */
  getCachedApiResponse(url) {
    const key = `api_${this.hashString(url)}`;
    
    // 메모리 캐시 우선 확인
    let cached = this.getMemoryCache(key);
    if (cached) {
      return cached;
    }
    
    // localStorage에서 확인
    cached = this.getLocalStorage(key);
    if (cached) {
      // 메모리 캐시에도 복원 (다음 접근 최적화)
      this.setMemoryCache(key, cached, this.defaultTTL);
      return cached;
    }
    
    return null;
  }
  
  /**
   * 이미지를 미리 로드합니다. (브라우저 캐시 활용)
   * @param {Array<string>} imageUrls - 미리 로드할 이미지 URL 목록
   * @returns {Promise<Array>} 각 이미지의 로드 결과
   */
  preloadImages(imageUrls) {
    const promises = imageUrls.map(url => {
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(url);
        img.onerror = () => reject(url);
        img.src = url;
      });
    });
    
    return Promise.allSettled(promises);
  }
  
  /**
   * 코인 아이콘을 캐시합니다.
   * @param {string} url - 캐시할 이미지 URL
   * @returns {Promise<string>} 캐시된 이미지의 Object URL 또는 원본 URL
   */
  async cacheImage(url) {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      
      const key = `image_${this.hashString(url)}`;
      this.setMemoryCache(key, objectUrl, 60 * 60 * 1000); // 1시간 캐시
      
      return objectUrl;
    } catch (error) {
      console.error(`Image cache failed: ${url}`, error);
      return url; // 원본 URL 반환
    }
  }
  
  /**
   * 주기적인 정리 작업을 시작합니다.
   */
  startCleanupInterval() {
    setInterval(() => {
      this.cleanupMemoryCache();
      this.cleanupLocalStorage();
    }, 5 * 60 * 1000); // 5분마다 실행
  }
  
  /**
   * 메모리 캐시를 정리합니다.
   */
  cleanupMemoryCache() {
    const now = Date.now();
    const toDelete = [];
    
    this.memoryCache.forEach((value, key) => {
      if (now > value.expiryTime) {
        toDelete.push(key);
      }
    });
    
    toDelete.forEach(key => {
      this.memoryCache.delete(key);
    });
    
    if (toDelete.length > 0) {
      // Memory cache cleaned
    }
  }
  
  /**
   * localStorage를 정리합니다.
   */
  cleanupLocalStorage() {
    try {
      const keys = Object.keys(localStorage);
      const cacheKeys = keys.filter(key => key.startsWith('cache_'));
      const now = Date.now();
      let cleanedCount = 0;
      
      cacheKeys.forEach(key => {
        try {
          const cached = JSON.parse(localStorage.getItem(key));
          if (cached.expiryTime && now > cached.expiryTime) {
            localStorage.removeItem(key);
            cleanedCount++;
          }
        } catch (error) {
          // 손상된 캐시 데이터 제거
          localStorage.removeItem(key);
          cleanedCount++;
        }
      });
      
      if (cleanedCount > 0) {
        // LocalStorage cleaned
      }
    } catch (error) {
      console.error('LocalStorage cleanup failed:', error);
    }
  }
  
  /**
   * 문자열을 해시하여 캐시 키로 사용합니다.
   * @param {string} str - 해시할 문자열
   * @returns {string} 해시된 문자열
   */
  hashString(str) {
    let hash = 0;
    if (str.length === 0) return hash;
    
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 32비트 정수 변환
    }
    
    return Math.abs(hash).toString(36);
  }
  
  /**
   * 캐시 통계를 조회합니다.
   * @returns {Object} 캐시 통계 정보
   */
  getStats() {
    const memoryStats = {
      size: this.memoryCache.size,
      items: Array.from(this.memoryCache.entries()).map(([key, value]) => ({
        key,
        size: JSON.stringify(value.data).length,
        expiryTime: value.expiryTime,
        accessCount: value.accessCount,
        lastAccess: value.lastAccess
      }))
    };
    
    const localStorageStats = {
      size: Object.keys(localStorage).filter(key => key.startsWith('cache_')).length,
      totalSize: this.getLocalStorageSize()
    };
    
    return {
      memory: memoryStats,
      localStorage: localStorageStats,
      sessionStorage: {
        size: Object.keys(sessionStorage).filter(key => key.startsWith('cache_')).length
      }
    };
  }
  
  /**
   * localStorage의 사용량을 계산합니다.
   * @returns {number} localStorage 사용량 (bytes)
   */
  getLocalStorageSize() {
    let total = 0;
    try {
      for (let key in localStorage) {
        if (localStorage.hasOwnProperty(key) && key.startsWith('cache_')) {
          total += localStorage[key].length;
        }
      }
    } catch (error) {
      console.error('LocalStorage size calculation failed:', error);
    }
    return total;
  }
  
  /**
   * 모든 캐시를 초기화합니다.
   */
  clearAll() {
    // 메모리 캐시 초기화
    this.memoryCache.clear();
    
    // localStorage 캐시 초기화
    try {
      const keys = Object.keys(localStorage);
      const cacheKeys = keys.filter(key => key.startsWith('cache_'));
      cacheKeys.forEach(key => localStorage.removeItem(key));
    } catch (error) {
      console.error('LocalStorage clear failed:', error);
    }
    
    // sessionStorage 캐시 초기화
    try {
      const keys = Object.keys(sessionStorage);
      const cacheKeys = keys.filter(key => key.startsWith('cache_'));
      cacheKeys.forEach(key => sessionStorage.removeItem(key));
    } catch (error) {
      console.error('SessionStorage clear failed:', error);
    }
    
    // All caches cleared
  }
}

// 전역 캐시 매니저 인스턴스
const cacheManager = new CacheManager();

export default cacheManager;

/**
 * 캐시된 fetch 함수입니다.
 * @param {string} url - 요청 URL
 * @param {Object} options - fetch 옵션
 * @param {number} ttl - 캐시 유효 기간 (ms)
 * @returns {Promise<Object>} API 응답 데이터
 */
export const cachedFetch = async (url, options = {}, ttl = 5 * 60 * 1000) => {
  // 캐시에서 확인
  const cached = cacheManager.getCachedApiResponse(url);
  if (cached) {
    // Cache hit
    return Promise.resolve({ ...cached, fromCache: true });
  }
  
  // 실제 API 호출
  try {
    const response = await fetch(url, options);
    const data = await response.json();
    
    // 성공한 응답만 캐시
    if (response.ok) {
      await cacheManager.cacheApiResponse(url, data, ttl);
      // API response cached
    }
    
    return { ...data, fromCache: false };
  } catch (error) {
    console.error(`API call failed: ${url}`, error);
    throw error;
  }
};