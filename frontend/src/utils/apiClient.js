/**
 * 공통 API 클라이언트 유틸리티
 * 
 * 표준화된 API 호출, 오류 처리, 재시도 로직을 제공합니다.
 */

import { cachedFetch } from './cacheManager';

// 기본 설정
const DEFAULT_TIMEOUT = 20000; // 20초로 증가
const DEFAULT_RETRY_COUNT = 2; // 재시도 횟수 감소
const RETRY_DELAY = 2000; // 2초로 증가

// API 기본 URL
export const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

/**
 * 커스텀 오류 클래스
 */
export class ApiError extends Error {
  /**
   * ApiError 인스턴스를 생성합니다.
   * @param {string} message - 오류 메시지
   * @param {number} status - HTTP 상태 코드
   * @param {string} endpoint - 오류가 발생한 엔드포인트
   * @param {any} data - 응답 데이터
   */
  constructor(message, status, endpoint, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.endpoint = endpoint;
    this.data = data;
  }
}

/**
 * 네트워크 연결 상태를 확인합니다.
 * @returns {boolean} 온라인 상태이면 true, 그렇지 않으면 false
 */
export const isOnline = () => {
  return navigator.onLine;
};

/**
 * 지정된 시간(ms)만큼 지연합니다.
 * @param {number} ms - 지연할 시간(ms)
 * @returns {Promise<void>}
 */
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * 타임아웃 및 재시도 로직을 포함한 기본 fetch 래퍼입니다.
 * @param {string} url - 요청 URL
 * @param {Object} options - fetch 옵션
 * @param {number} retryCount - 남은 재시도 횟수
 * @returns {Promise<Response>} fetch 응답
 */
export const fetchWithRetry = async (url, options = {}, retryCount = DEFAULT_RETRY_COUNT) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || DEFAULT_TIMEOUT);
  
  const fetchOptions = {
    ...options,
    signal: controller.signal,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };
  
  try {
    const response = await fetch(url, fetchOptions);
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      throw new ApiError(
        `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        url
      );
    }
    
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    
    // 재시도 로직
    if (retryCount > 0 && shouldRetry(error)) {
      console.warn(`API 호출 실패, 재시도 중... (${DEFAULT_RETRY_COUNT - retryCount + 1}/${DEFAULT_RETRY_COUNT})`, error.message);
      await delay(RETRY_DELAY * (DEFAULT_RETRY_COUNT - retryCount + 1)); // 지수적 백오프
      return fetchWithRetry(url, options, retryCount - 1);
    }
    
    throw error;
  }
};

/**
 * 재시도 여부를 판단합니다.
 * @param {Error} error - 발생한 오류
 * @returns {boolean} 재시도해야 하면 true, 그렇지 않으면 false
 */
const shouldRetry = (error) => {
  // 네트워크 오류나 서버 오류 시 재시도
  if (error.name === 'AbortError') return false; // 타임아웃은 재시도하지 않음
  if (error.status >= 400 && error.status < 500) return false; // 클라이언트 오류는 재시도하지 않음
  return true;
};

/**
 * GET 요청을 보냅니다.
 * @param {string} endpoint - API 엔드포인트
 * @param {Object} options - fetch 옵션
 * @returns {Promise<{success: boolean, data: any, status: number}>}
 */
export const apiGet = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const response = await fetchWithRetry(url, {
      method: 'GET',
      ...options,
    });
    
    const data = await response.json();
    return { success: true, data, status: response.status };
  } catch (error) {
    console.error(`GET ${endpoint} 실패:`, error);
    return handleApiError(error, endpoint);
  }
};

/**
 * POST 요청을 보냅니다.
 * @param {string} endpoint - API 엔드포인트
 * @param {Object} body - 요청 본문
 * @param {Object} options - fetch 옵션
 * @returns {Promise<{success: boolean, data: any, status: number}>}
 */
export const apiPost = async (endpoint, body = null, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const response = await fetchWithRetry(url, {
      method: 'POST',
      body: body ? JSON.stringify(body) : null,
      ...options,
    });
    
    const data = await response.json();
    return { success: true, data, status: response.status };
  } catch (error) {
    console.error(`POST ${endpoint} 실패:`, error);
    return handleApiError(error, endpoint);
  }
};

/**
 * PUT 요청을 보냅니다.
 * @param {string} endpoint - API 엔드포인트
 * @param {Object} body - 요청 본문
 * @param {Object} options - fetch 옵션
 * @returns {Promise<{success: boolean, data: any, status: number}>}
 */
export const apiPut = async (endpoint, body = null, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const response = await fetchWithRetry(url, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : null,
      ...options,
    });
    
    const data = await response.json();
    return { success: true, data, status: response.status };
  } catch (error) {
    console.error(`PUT ${endpoint} 실패:`, error);
    return handleApiError(error, endpoint);
  }
};

/**
 * DELETE 요청을 보냅니다.
 * @param {string} endpoint - API 엔드포인트
 * @param {Object} options - fetch 옵션
 * @returns {Promise<{success: boolean, data: any, status: number}>}
 */
export const apiDelete = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const response = await fetchWithRetry(url, {
      method: 'DELETE',
      ...options,
    });
    
    const data = await response.json();
    return { success: true, data, status: response.status };
  } catch (error) {
    console.error(`DELETE ${endpoint} 실패:`, error);
    return handleApiError(error, endpoint);
  }
};

/**
 * 캐시된 GET 요청을 보냅니다.
 * @param {string} endpoint - API 엔드포인트
 * @param {Object} options - fetch 옵션
 * @returns {Promise<{success: boolean, data: any, fromCache: boolean, status: number}>}
 */
export const apiGetCached = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const ttl = options.ttl || 5 * 60 * 1000; // 기본 5분 캐시
  
  try {
    const data = await cachedFetch(url, {
      method: 'GET',
      ...options,
    }, ttl);
    
    return { 
      success: true, 
      data: data.fromCache ? data : data,
      fromCache: data.fromCache || false,
      status: 200 
    };
  } catch (error) {
    console.error(`Cached GET ${endpoint} 실패:`, error);
    return handleApiError(error, endpoint);
  }
};

/**
 * API 오류를 처리합니다.
 * @param {Error} error - 발생한 오류
 * @param {string} endpoint - 오류가 발생한 엔드포인트
 * @returns {{success: boolean, error: string, status: number, endpoint: string, timestamp: string}}
 */
const handleApiError = (error, endpoint) => {
  let message = '알 수 없는 오류가 발생했습니다.';
  let status = 0;
  
  if (error instanceof ApiError) {
    message = error.message;
    status = error.status;
  } else if (error.name === 'AbortError') {
    message = '요청 시간이 초과되었습니다.';
    status = 408;
  } else if (!isOnline()) {
    message = '네트워크 연결을 확인해주세요.';
    status = 0;
  } else {
    message = error.message || '서버 연결에 실패했습니다.';
  }
  
  return {
    success: false,
    error: message,
    status,
    endpoint,
    timestamp: new Date().toISOString()
  };
};

/**
 * 일반적인 API 엔드포인트 목록
 */
export const apiEndpoints = {
  // 코인 데이터
  coins: {
    latest: '/api/coins/latest',
    names: '/api/coin-names',
    historical: (symbol) => `/api/historical_prices/${symbol}`,
  },
  
  // 청산 데이터
  liquidations: {
    aggregated: '/api/liquidations/aggregated',
    debug: '/api/liquidations/debug',
    raw: '/api/liquidations/raw',
  },
  
  // 기타
  fearGreed: '/api/fear_greed_index',
  health: '/health',
  
  // 서비스별 직접 접근 (디버깅용)
  services: {
    market: {
      base: 'http://localhost:8001',
      health: 'http://localhost:8001/health',
      combined: 'http://localhost:8001/api/market/combined',
    },
    liquidation: {
      base: 'http://localhost:8002',
      health: 'http://localhost:8002/health',
      aggregated: 'http://localhost:8002/api/liquidations/aggregated',
    }
  }
};

/**
 * 특정 API 함수 모음
 */
export const coinApi = {
  getLatest: (useCache = true) => {
    return useCache 
      ? apiGetCached(apiEndpoints.coins.latest, { ttl: 1000 }) // 1초 캐시
      : apiGet(apiEndpoints.coins.latest);
  },
  
  getNames: (useCache = true) => {
    return useCache
      ? apiGetCached(apiEndpoints.coins.names, { ttl: 10 * 60 * 1000 }) // 10분 캐시
      : apiGet(apiEndpoints.coins.names);
  },
  
  getHistorical: (symbol, useCache = true) => {
    const endpoint = apiEndpoints.coins.historical(symbol);
    return useCache
      ? apiGetCached(endpoint, { ttl: 5 * 60 * 1000 }) // 5분 캐시
      : apiGet(endpoint);
  }
};

export const liquidationApi = {
  getAggregated: (limit = 60, useCache = false) => {
    const endpoint = `${apiEndpoints.liquidations.aggregated}?limit=${limit}`;
    return useCache
      ? apiGetCached(endpoint, { ttl: 30 * 1000 }) // 30초 캐시
      : apiGet(endpoint);
  },
  
  getDebug: () => apiGet(apiEndpoints.liquidations.debug),
  getRaw: (exchange = null, limit = 60) => {
    let endpoint = `${apiEndpoints.liquidations.raw}?limit=${limit}`;
    if (exchange) endpoint += `&exchange=${exchange}`;
    return apiGet(endpoint);
  }
};

export const healthApi = {
  getApiGateway: () => apiGet(apiEndpoints.health),
  getMarketService: () => apiGet(apiEndpoints.services.market.health),
  getLiquidationService: () => apiGet(apiEndpoints.services.liquidation.health),
  
  getAll: async () => {
    const [gateway, market, liquidation] = await Promise.allSettled([
      healthApi.getApiGateway(),
      healthApi.getMarketService(),
      healthApi.getLiquidationService()
    ]);
    
    return {
      gateway: gateway.status === 'fulfilled' ? gateway.value : { success: false, error: gateway.reason },
      market: market.status === 'fulfilled' ? market.value : { success: false, error: market.reason },
      liquidation: liquidation.status === 'fulfilled' ? liquidation.value : { success: false, error: liquidation.reason }
    };
  }
};

/**
 * WebSocket URL을 생성합니다.
 * @param {string} endpoint - WebSocket 엔드포인트
 * @returns {string} WebSocket URL
 */
export const getWebSocketUrl = (endpoint) => {
  const wsBase = API_BASE_URL.replace('http', 'ws');
  return `${wsBase}${endpoint}`;
};

/**
 * API 클라이언트 상태 모니터를 생성합니다.
 * @returns {{addRequest: Function, getStats: Function, reset: Function}}
 */
export const createApiMonitor = () => {
  const stats = {
    totalRequests: 0,
    successfulRequests: 0,
    failedRequests: 0,
    averageResponseTime: 0,
    lastRequestTime: null,
    errors: []
  };
  
  const addRequest = (success, responseTime, error = null) => {
    stats.totalRequests++;
    stats.lastRequestTime = new Date();
    
    if (success) {
      stats.successfulRequests++;
    } else {
      stats.failedRequests++;
      if (error) {
        stats.errors.push({
          error: error.message,
          timestamp: new Date(),
          endpoint: error.endpoint
        });
        
        // 최근 10개 오류만 보관
        if (stats.errors.length > 10) {
          stats.errors = stats.errors.slice(-10);
        }
      }
    }
    
    // 평균 응답 시간 계산
    stats.averageResponseTime = 
      (stats.averageResponseTime * (stats.totalRequests - 1) + responseTime) / stats.totalRequests;
  };
  
  const getStats = () => ({ ...stats });
  const reset = () => {
    Object.keys(stats).forEach(key => {
      if (typeof stats[key] === 'number') stats[key] = 0;
      else if (Array.isArray(stats[key])) stats[key] = [];
      else stats[key] = null;
    });
  };
  
  return { addRequest, getStats, reset };
};

// 전역 API 모니터
export const apiMonitor = createApiMonitor();

const apiClient = {
  get: apiGet,
  post: apiPost,
  put: apiPut,
  delete: apiDelete,
  getCached: apiGetCached,
  endpoints: apiEndpoints,
  coin: coinApi,
  liquidation: liquidationApi,
  health: healthApi,
  getWebSocketUrl,
  monitor: apiMonitor
};

export default apiClient;
