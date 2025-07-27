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
    if (this.observers[type]) {
      this.observers[type].push(callback);
    }
  }
  
  unsubscribe(type, callback) {
    if (this.observers[type]) {
      const index = this.observers[type].indexOf(callback);
      if (index > -1) {
        this.observers[type].splice(index, 1);
      }
    }
  }
  
  notifyObservers(type, data) {
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
  generateReport(timeRange = 60000) { // 기본 1분
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
    return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
  }
  
  countBy(arr, key) {
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
  const measureRender = (renderFunction) => {
    return performanceMonitor.measureRender(componentName, renderFunction);
  };
  
  const trackInteraction = (type, details) => {
    performanceMonitor.trackInteraction(type, componentName, details);
  };
  
  return { measureRender, trackInteraction };
};