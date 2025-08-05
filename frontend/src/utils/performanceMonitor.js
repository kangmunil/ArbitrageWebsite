/**
 * React 애플리케이션 성능 모니터링 도구
 * 
 * 주요 기능:
 * - 컴포넌트 렌더링 성능 측정
 * - API 호출 시간 추적
 * - 사용자 상호작용 기록
 * - 메모리 사용량 모니터링
 * - Core Web Vitals 측정
 * - 성능 리포트 생성 및 내보내기
 */

class PerformanceMonitor {
  /**
   * PerformanceMonitor 클래스의 생성자입니다.
   * 개발 환경에서만 모니터링을 활성화하고, 메트릭 저장소 및 옵저버 콜백을 초기화합니다.
   * 또한, 자동 메모리 모니터링을 시작합니다.
   */
  constructor() {
    this.isEnabled = process.env.NODE_ENV === 'development';
    this.maxMetrics = 1000; // 메트릭 최대 개수
    
    // 메트릭 저장소
    this.metrics = {
      renders: [],
      apiCalls: [],
      interactions: [],
      memory: [],
      errors: []
    };
    
    // 옵저버 패턴용 콜백들
    this.observers = {
      render: [],
      apiCall: [],
      interaction: [],
      memory: [],
      error: []
    };
    
    // 자동 메모리 모니터링 시작
    this.startMemoryMonitoring();
  }
  
  /**
   * 컴포넌트 렌더링 성능 측정
   */
  measureRender(componentName, renderFunction) {
    /**
     * 컴포넌트의 렌더링 성능을 측정합니다.
     * 개발 모드에서만 작동하며, 렌더링 시간, 컴포넌트 이름 등을 기록합니다.
     * 렌더링 시간이 50ms를 초과하면 경고를 출력합니다.
     *
     * @param {string} componentName - 렌더링되는 컴포넌트의 이름.
     * @param {Function} renderFunction - 실제 컴포넌트 렌더링 로직을 포함하는 함수.
     * @returns {*} `renderFunction`의 반환 값.
     * @throws {Error} `renderFunction` 실행 중 발생한 모든 에러.
     */
    if (!this.isEnabled) return renderFunction();
    
    const startTime = performance.now();
    
    try {
      const result = renderFunction();
      const endTime = performance.now();
      const duration = endTime - startTime;
      
      const metric = {
        type: 'render',
        component: componentName,
        duration: duration,
        timestamp: Date.now(),
        isSlowRender: duration > 16 // 60fps 기준
      };
      
      this.addMetric('renders', metric);
      this.notifyObservers('render', metric);
      
      if (duration > 50) { // 50ms 이상이면 경고
        console.warn(`🐌 Slow render detected: ${componentName} (${duration.toFixed(2)}ms)`);
      }
      
      return result;
    } catch (error) {
      const endTime = performance.now();
      this.trackError('render', componentName, error);
      throw error;
    }
  }
  
  /**
   * API 호출 성능 추적
   */
  async measureApiCall(url, apiFunction) {
    /**
     * API 호출의 성능을 추적합니다.
     * 개발 모드에서만 작동하며, API 호출 시간, 성공 여부 등을 기록합니다.
     * 호출 시간이 3초를 초과하면 경고를 출력합니다.
     *
     * @param {string} url - 호출되는 API의 URL.
     * @param {Function} apiFunction - 실제 API 호출 로직을 포함하는 비동기 함수.
     * @returns {Promise<*>} `apiFunction`의 비동기 반환 값.
     * @throws {Error} `apiFunction` 실행 중 발생한 모든 에러.
     */
    if (!this.isEnabled) return apiFunction();
    
    const startTime = performance.now();
    
    try {
      const result = await apiFunction();
      const endTime = performance.now();
      const duration = endTime - startTime;
      
      const metric = {
        type: 'apiCall',
        url: url,
        duration: duration,
        success: true,
        timestamp: Date.now(),
        isSlow: duration > 1000 // 1초 이상이면 느린 호출
      };
      
      this.addMetric('apiCalls', metric);
      this.notifyObservers('apiCall', metric);
      
      if (duration > 3000) { // 3초 이상이면 경고
        console.warn(`🐌 Slow API call: ${url} (${duration.toFixed(2)}ms)`);
      }
      
      return result;
    } catch (error) {
      const endTime = performance.now();
      const duration = endTime - startTime;
      
      const metric = {
        type: 'apiCall',
        url: url,
        duration: duration,
        success: false,
        error: error.message,
        timestamp: Date.now()
      };
      
      this.addMetric('apiCalls', metric);
      this.trackError('api', url, error);
      
      throw error;
    }
  }
  
  /**
   * 사용자 상호작용 추적
   */
  trackInteraction(type, component, details = {}) {
    /**
     * 사용자 상호작용을 추적합니다.
     * 개발 모드에서만 작동하며, 상호작용 유형, 관련 컴포넌트, 추가 세부 정보를 기록합니다.
     *
     * @param {string} type - 상호작용의 유형 (예: 'click', 'submit', 'input').
     * @param {string} component - 상호작용이 발생한 컴포넌트의 이름.
     * @param {Object} [details={}] - 상호작용에 대한 추가 세부 정보.
     */
    if (!this.isEnabled) return;
    
    const metric = {
      type: type,
      component: component,
      details: details,
      timestamp: Date.now()
    };
    
    this.addMetric('interactions', metric);
    this.notifyObservers('interaction', metric);
  }
  
  /**
   * 메모리 사용량 모니터링
   */
  startMemoryMonitoring() {
    /**
     * 주기적으로 메모리 사용량을 모니터링하고 기록합니다.
     * 개발 모드에서만 작동하며, 5초마다 메모리 정보를 수집합니다.
     * 메모리 사용량이 100MB를 초과하면 경고를 출력합니다.
     */
    if (!this.isEnabled) return;
    
    setInterval(() => {
      const memoryInfo = this.getMemoryUsage();
      if (memoryInfo) {
        this.addMetric('memory', {
          ...memoryInfo,
          timestamp: Date.now()
        });
        
        // 메모리 사용량이 높으면 경고
        if (memoryInfo.used > 100) { // 100MB 이상
          console.warn(`🔥 High memory usage: ${memoryInfo.used}MB`);
        }
      }
    }, 5000); // 5초마다 체크
  }
  
  /**
   * 에러 추적
   */
  trackError(category, context, error) {
    /**
     * 애플리케이션에서 발생한 에러를 추적하고 기록합니다.
     * 개발 모드에서만 작동하며, 에러의 카테고리, 컨텍스트, 메시지, 스택 트레이스 등을 기록합니다.
     *
     * @param {string} category - 에러의 분류 (예: 'render', 'api', 'general').
     * @param {string} context - 에러가 발생한 컨텍스트 (예: 컴포넌트 이름, URL).
     * @param {Error} error - 발생한 Error 객체.
     */
    if (!this.isEnabled) return;
    
    const metric = {
      category: category,
      context: context,
      message: error.message,
      stack: error.stack,
      timestamp: Date.now()
    };
    
    this.addMetric('errors', metric);
    this.notifyObservers('error', metric);
  }
  
  /**
   * 메트릭 추가
   */
  addMetric(type, metric) {
    /**
     * 지정된 유형의 메트릭을 저장소에 추가합니다.
     * 메트릭의 최대 개수를 초과하면 가장 오래된 메트릭부터 제거합니다.
     *
     * @param {string} type - 추가할 메트릭의 유형 (예: 'renders', 'apiCalls', 'interactions', 'memory', 'errors').
     * @param {Object} metric - 추가할 메트릭 데이터 객체.
     */
    this.metrics[type].push(metric);
    
    // 메트릭 수 제한
    if (this.metrics[type].length > this.maxMetrics) {
      this.metrics[type] = this.metrics[type].slice(-this.maxMetrics);
    }
  }
  
  /**
   * 옵저버 패턴으로 실시간 알림
   */
  subscribe(type, callback) {
    /**
     * 특정 유형의 메트릭 업데이트를 구독합니다.
     * 해당 유형의 메트릭이 추가될 때마다 콜백 함수가 호출됩니다.
     *
     * @param {string} type - 구독할 메트릭의 유형.
     * @param {Function} callback - 메트릭 업데이트 시 호출될 콜백 함수.
     */
    if (this.observers[type]) {
      this.observers[type].push(callback);
    }
  }
  
  unsubscribe(type, callback) {
    /**
     * 특정 유형의 메트릭 업데이트 구독을 해지합니다.
     *
     * @param {string} type - 구독 해지할 메트릭의 유형.
     * @param {Function} callback - 구독 해지할 콜백 함수.
     */
    if (this.observers[type]) {
      const index = this.observers[type].indexOf(callback);
      if (index > -1) {
        this.observers[type].splice(index, 1);
      }
    }
  }
  
  notifyObservers(type, data) {
    /**
     * 특정 유형의 메트릭을 구독하는 모든 옵저버에게 알림을 보냅니다.
     *
     * @param {string} type - 알림을 보낼 메트릭의 유형.
     * @param {Object} data - 옵저버에게 전달할 메트릭 데이터.
     */
    if (this.observers[type]) {
      this.observers[type].forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Observer callback error:', error);
        }
      });
    }
  }
  
  /**
   * 현재 메모리 사용량 조회
   */
  getMemoryUsage() {
    /**
     * 현재 JavaScript 힙 메모리 사용량을 조회합니다.
     * `performance.memory` API를 사용하여 사용된, 총, 제한된 힙 크기를 MB 단위로 반환합니다.
     *
     * @returns {Object | null} 메모리 사용량 정보를 담은 객체 (used, total, limit) 또는 API를 사용할 수 없는 경우 null.
     */
    if (performance && performance.memory) {
      return {
        used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
        total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024),
        limit: Math.round(performance.memory.jsHeapSizeLimit / 1024 / 1024)
      };
    }
    return null;
  }
  
  /**
   * 성능 리포트 생성
   */
  generateReport(timeRange = 60000) {
    /**
     * 지정된 시간 범위 내의 성능 메트릭을 기반으로 보고서를 생성합니다.
     * 렌더링, API 호출, 상호작용, 메모리, 에러에 대한 요약 통계를 제공합니다.
     *
     * @param {number} [timeRange=60000] - 보고서를 생성할 시간 범위(밀리초). 기본값은 60초(60000ms)입니다.
     * @returns {Object} 생성된 성능 보고서 객체.
     */
    const now = Date.now();
    const cutoff = now - timeRange;
    
    const filterByTime = (metrics) => 
      metrics.filter(m => m.timestamp >= cutoff);
    
    const recentRenders = filterByTime(this.metrics.renders);
    const recentApiCalls = filterByTime(this.metrics.apiCalls);
    const recentInteractions = filterByTime(this.metrics.interactions);
    const recentMemory = filterByTime(this.metrics.memory);
    const recentErrors = filterByTime(this.metrics.errors);
    
    const report = {
      timeRange: `${timeRange / 1000}s`,
      timestamp: new Date().toISOString(),
      
      renders: {
        count: recentRenders.length,
        avgDuration: this.average(recentRenders.map(r => r.duration)),
        slowRenders: recentRenders.filter(r => r.duration > 16).length,
        components: [...new Set(recentRenders.map(r => r.component))]
      },
      
      apiCalls: {
        count: recentApiCalls.length,
        avgDuration: this.average(recentApiCalls.map(a => a.duration)),
        successRate: (recentApiCalls.filter(a => a.success).length / recentApiCalls.length * 100) || 0,
        slowCalls: recentApiCalls.filter(a => a.duration > 1000).length
      },
      
      interactions: {
        count: recentInteractions.length,
        types: this.countBy(recentInteractions, 'type')
      },
      
      memory: {
        current: this.getMemoryUsage(),
        peak: recentMemory.length > 0 ? Math.max(...recentMemory.map(m => m.used)) : 0,
        average: this.average(recentMemory.map(m => m.used))
      },
      
      errors: {
        count: recentErrors.length,
        categories: this.countBy(recentErrors, 'category')
      }
    };
    
    return report;
  }
  
  /**
   * 콘솔 대시보드 출력
   */
  showDashboard() {
    /**
     * 현재 성능 메트릭을 콘솔에 대시보드 형태로 출력합니다.
     * 개발 모드에서만 작동하며, 렌더링, API 호출, 상호작용, 메모리, 에러에 대한 요약 정보를 보여줍니다.
     *
     * @returns {Object} 생성된 성능 보고서 객체.
     */
    if (!this.isEnabled) {
      console.log('Performance monitoring is disabled in production');
      return;
    }
    
    const report = this.generateReport();
    
    console.group('🚀 Performance Dashboard');
    console.log('📊 Renders:', report.renders);
    console.log('🌐 API Calls:', report.apiCalls);
    console.log('👆 Interactions:', report.interactions);
    console.log('💾 Memory:', report.memory);
    console.log('❌ Errors:', report.errors);
    console.groupEnd();
    
    return report;
  }
  
  /**
   * 유틸리티 함수들
   */
  average(arr) {
    /**
     * 숫자 배열의 평균을 계산합니다.
     * 배열이 비어 있으면 0을 반환합니다.
     *
     * @param {number[]} arr - 평균을 계산할 숫자 배열.
     * @returns {number} 배열의 평균.
     */
    return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
  }
  
  countBy(arr, key) {
    /**
     * 배열 내 객체들의 특정 키 값에 따라 항목 수를 계산합니다.
     *
     * @param {Array<Object>} arr - 처리할 객체 배열.
     * @param {string} key - 항목 수를 계산할 객체의 키.
     * @returns {Object} 각 키 값과 해당 항목 수를 매핑하는 객체.
     */
    return arr.reduce((acc, item) => {
      const value = item[key];
      acc[value] = (acc[value] || 0) + 1;
      return acc;
    }, {});
  }
  
  /**
   * 모니터링 초기화
   */
  reset() {
    /**
     * 모든 성능 메트릭 데이터를 초기화합니다.
     *
     * @returns {void}
     */
    this.metrics = {
      renders: [],
      apiCalls: [],
      interactions: [],
      memory: [],
      errors: []
    };
    
    console.log('Performance metrics reset');
  }
}

// 전역 성능 모니터 인스턴스
const performanceMonitor = new PerformanceMonitor();

// 개발자 도구에서 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  window.performanceMonitor = performanceMonitor;
  
  console.log('🚀 Performance Monitor initialized. Use window.performanceMonitor to access.');
  console.log('Available methods: showDashboard(), reset()');
}

export default performanceMonitor;

/**
 * React Hook for performance monitoring
 */
export const usePerformanceMonitor = (componentName) => {
  /**
   * React 컴포넌트의 성능 모니터링을 위한 커스텀 훅입니다.
   * 렌더링 시간 측정 및 사용자 상호작용 추적 기능을 제공합니다.
   *
   * @param {string} componentName - 이 훅을 사용하는 컴포넌트의 이름.
   * @returns {{measureRender: Function, trackInteraction: Function}}
   *          - `measureRender`: 컴포넌트 렌더링을 측정하는 함수.
   *          - `trackInteraction`: 사용자 상호작용을 추적하는 함수.
   */
  const measureRender = (renderFunction) => {
    return performanceMonitor.measureRender(componentName, renderFunction);
  };
  
  const trackInteraction = (type, details) => {
    performanceMonitor.trackInteraction(type, componentName, details);
  };
  
  return { measureRender, trackInteraction };
};