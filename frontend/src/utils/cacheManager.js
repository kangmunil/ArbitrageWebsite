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
  constructor() {
    this.memoryCache = new Map();
    this.defaultTTL = 5 * 60 * 1000; // 5분
    this.maxMemoryCacheSize = 100;
    
    // 주기적으로 만료된 항목 정리
    this.startCleanupInterval();
  }
  
  /**
   * 메모리 캐시에 데이터 저장
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
    
    console.log(`Memory cache set: ${key} (TTL: ${ttl}ms)`);
  }
  
  /**
   * 메모리 캐시에서 데이터 조회
   */
  getMemoryCache(key) {
    const cached = this.memoryCache.get(key);
    
    if (!cached) {
      return null;
    }
    
    if (Date.now() > cached.expiryTime) {
      this.memoryCache.delete(key);
      console.log(`Memory cache expired: ${key}`);
      return null;
    }
    
    // 접근 통계 업데이트
    cached.accessCount += 1;
    cached.lastAccess = Date.now();
    
    return cached.data;
  }
  
  /**
   * localStorage에 데이터 저장 (영구 저장)
   */
  setLocalStorage(key, data, ttl = null) {
    try {
      const cacheData = {
        data,
        timestamp: Date.now(),
        expiryTime: ttl ? Date.now() + ttl : null
      };
      
      localStorage.setItem(`cache_${key}`, JSON.stringify(cacheData));
      console.log(`LocalStorage cache set: ${key}`);
    } catch (error) {
      console.error(`LocalStorage cache failed: ${key}`, error);
      // 저장 공간 부족 시 오래된 항목 정리
      this.cleanupLocalStorage();
    }
  }
  
  /**
   * localStorage에서 데이터 조회
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
        console.log(`LocalStorage cache expired: ${key}`);
        return null;
      }
      
      return cacheData.data;
    } catch (error) {
      console.error(`LocalStorage cache read failed: ${key}`, error);
      return null;
    }
  }
  
  /**
   * sessionStorage에 데이터 저장 (세션 종료 시 삭제)
   */
  setSessionStorage(key, data) {
    try {
      const cacheData = {
        data,
        timestamp: Date.now()
      };
      
      sessionStorage.setItem(`cache_${key}`, JSON.stringify(cacheData));
      console.log(`SessionStorage cache set: ${key}`);
    } catch (error) {
      console.error(`SessionStorage cache failed: ${key}`, error);
    }
  }
  
  /**
   * sessionStorage에서 데이터 조회
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
   * API 응답 캐시 (메모리 + localStorage 조합)
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
   * API 응답 캐시 조회
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
   * 이미지 캐시 (브라우저 캐시 활용)
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
   * 코인 아이콘 캐시
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
   * 주기적 정리 작업
   */
  startCleanupInterval() {
    setInterval(() => {
      this.cleanupMemoryCache();
      this.cleanupLocalStorage();
    }, 5 * 60 * 1000); // 5분마다 실행
  }
  
  /**
   * 메모리 캐시 정리
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
      console.log(`Memory cache cleanup: ${toDelete.length} items removed`);
    }
  }
  
  /**
   * localStorage 정리
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
        console.log(`LocalStorage cleanup: ${cleanedCount} items removed`);
      }
    } catch (error) {
      console.error('LocalStorage cleanup failed:', error);
    }
  }
  
  /**
   * 문자열 해시 생성 (캐시 키용)
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
   * 캐시 통계 조회
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
   * localStorage 사용량 계산
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
   * 전체 캐시 초기화
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
    
    console.log('All caches cleared');
  }
}

// 전역 캐시 매니저 인스턴스
const cacheManager = new CacheManager();

export default cacheManager;

/**
 * 캐시된 fetch 함수
 */
export const cachedFetch = async (url, options = {}, ttl = 5 * 60 * 1000) => {
  // 캐시에서 확인
  const cached = cacheManager.getCachedApiResponse(url);
  if (cached) {
    console.log(`Cache hit: ${url}`);
    return Promise.resolve({ ...cached, fromCache: true });
  }
  
  // 실제 API 호출
  try {
    const response = await fetch(url, options);
    const data = await response.json();
    
    // 성공한 응답만 캐시
    if (response.ok) {
      await cacheManager.cacheApiResponse(url, data, ttl);
      console.log(`API call cached: ${url}`);
    }
    
    return { ...data, fromCache: false };
  } catch (error) {
    console.error(`API call failed: ${url}`, error);
    throw error;
  }
};