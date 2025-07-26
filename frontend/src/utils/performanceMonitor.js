/**
 * 프론트엔드 성능 모니터링 유틸리티
 * 
 * 주요 기능:
 * 1. 렌더링 성능 측정
 * 2. API 호출 성능 추적
 * 3. 메모리 사용량 모니터링
 * 4. 사용자 상호작용 추적
 * 5. 성능 지표 대시보드
 */

class PerformanceMonitor {
  constructor() {
    this.metrics = {
      renders: [],
      apiCalls: [],
      interactions: [],
      memory: [],
      errors: []
    };
    
    this.observers = {
      render: [],
      api: [],
      memory: [],
      error: []
    };
    
    this.isEnabled = process.env.NODE_ENV === 'development';
    this.maxMetrics = 1000; // 최대 메트릭 수
    
    if (this.isEnabled) {
      this.startMonitoring();
      this.setupGlobalErrorHandling();
    }
  }
  
  /**
   * 렌더링 성능 측정
   */
  measureRender(componentName, renderFunction) {
    if (!this.isEnabled) {
      return renderFunction();
    }
    
    const startTime = performance.now();
    const startMemory = this.getMemoryUsage();
    
    try {
      const result = renderFunction();
      
      const endTime = performance.now();
      const endMemory = this.getMemoryUsage();
      const duration = endTime - startTime;
      
      const metric = {
        timestamp: Date.now(),
        component: componentName,
        duration,
        memoryDelta: endMemory ? endMemory.used - startMemory.used : 0,
        type: 'render'
      };
      
      this.addMetric('renders', metric);
      this.notifyObservers('render', metric);
      
      // 느린 렌더링 경고
      if (duration > 16) { // 60fps 기준
        console.warn(`Slow render detected: ${componentName} took ${duration.toFixed(2)}ms`);
      }
      
      return result;
    } catch (error) {
      this.recordError('render', componentName, error);
      throw error;
    }
  }
  
  /**
   * API 호출 성능 추적
   */
  async measureApiCall(url, apiFunction) {
    if (!this.isEnabled) {
      return apiFunction();
    }
    
    const startTime = performance.now();
    const startMemory = this.getMemoryUsage();
    
    try {
      const result = await apiFunction();
      
      const endTime = performance.now();
      const endMemory = this.getMemoryUsage();
      const duration = endTime - startTime;
      
      const metric = {
        timestamp: Date.now(),
        url,
        duration,
        memoryDelta: endMemory ? endMemory.used - startMemory.used : 0,
        success: true,
        type: 'api'
      };
      
      this.addMetric('apiCalls', metric);
      this.notifyObservers('api', metric);
      
      // 느린 API 호출 경고
      if (duration > 1000) {
        console.warn(`Slow API call: ${url} took ${duration.toFixed(2)}ms`);
      }
      
      return result;
    } catch (error) {
      const endTime = performance.now();
      const duration = endTime - startTime;
      
      const metric = {
        timestamp: Date.now(),
        url,
        duration,
        success: false,
        error: error.message,
        type: 'api'
      };
      
      this.addMetric('apiCalls', metric);
      this.recordError('api', url, error);
      throw error;
    }
  }
  
  /**
   * 사용자 상호작용 추적
   */
  trackInteraction(type, target, details = {}) {
    if (!this.isEnabled) return;
    
    const metric = {
      timestamp: Date.now(),
      type,
      target,
      details,
      userAgent: navigator.userAgent,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight
      }
    };
    
    this.addMetric('interactions', metric);
  }
  
  /**
   * 메모리 사용량 모니터링 시작
   */
  startMonitoring() {
    // 5초마다 메모리 사용량 기록
    setInterval(() => {
      const memoryUsage = this.getMemoryUsage();
      if (memoryUsage) {
        const metric = {
          timestamp: Date.now(),
          ...memoryUsage,
          type: 'memory'
        };
        
        this.addMetric('memory', metric);
        this.notifyObservers('memory', metric);
        
        // 메모리 사용량 경고
        if (memoryUsage.used > memoryUsage.limit * 0.8) {
          console.warn(`High memory usage: ${memoryUsage.used}MB / ${memoryUsage.limit}MB`);
        }
      }
    }, 5000);
  }
  
  /**
   * 전역 에러 핸들링 설정
   */
  setupGlobalErrorHandling() {
    window.addEventListener('error', (event) => {
      this.recordError('javascript', event.filename, {
        message: event.message,
        lineno: event.lineno,
        colno: event.colno,
        stack: event.error?.stack
      });
    });
    
    window.addEventListener('unhandledrejection', (event) => {
      this.recordError('promise', 'unhandled', {
        reason: event.reason
      });
    });
  }
  
  /**
   * 에러 기록
   */
  recordError(category, source, error) {
    const metric = {
      timestamp: Date.now(),
      category,
      source,
      message: error.message || String(error),
      stack: error.stack,
      userAgent: navigator.userAgent,
      url: window.location.href
    };
    
    this.addMetric('errors', metric);
    this.notifyObservers('error', metric);
  }
  
  /**
   * 메트릭 추가
   */
  addMetric(type, metric) {\n    this.metrics[type].push(metric);\n    \n    // 메트릭 수 제한\n    if (this.metrics[type].length > this.maxMetrics) {\n      this.metrics[type] = this.metrics[type].slice(-this.maxMetrics);\n    }\n  }\n  \n  /**\n   * 옵저버 패턴으로 실시간 알림\n   */\n  subscribe(type, callback) {\n    if (this.observers[type]) {\n      this.observers[type].push(callback);\n    }\n  }\n  \n  unsubscribe(type, callback) {\n    if (this.observers[type]) {\n      const index = this.observers[type].indexOf(callback);\n      if (index > -1) {\n        this.observers[type].splice(index, 1);\n      }\n    }\n  }\n  \n  notifyObservers(type, data) {\n    if (this.observers[type]) {\n      this.observers[type].forEach(callback => {\n        try {\n          callback(data);\n        } catch (error) {\n          console.error('Observer callback error:', error);\n        }\n      });\n    }\n  }\n  \n  /**\n   * 현재 메모리 사용량 조회\n   */\n  getMemoryUsage() {\n    if (performance && performance.memory) {\n      return {\n        used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),\n        total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024),\n        limit: Math.round(performance.memory.jsHeapSizeLimit / 1024 / 1024)\n      };\n    }\n    return null;\n  }\n  \n  /**\n   * Core Web Vitals 측정\n   */\n  measureWebVitals() {\n    if (!this.isEnabled) return;\n    \n    // Largest Contentful Paint\n    new PerformanceObserver((list) => {\n      const entries = list.getEntries();\n      const lastEntry = entries[entries.length - 1];\n      \n      console.log('LCP:', lastEntry.startTime);\n      this.trackInteraction('web_vital', 'lcp', {\n        value: lastEntry.startTime,\n        element: lastEntry.element?.tagName\n      });\n    }).observe({ entryTypes: ['largest-contentful-paint'] });\n    \n    // First Input Delay\n    new PerformanceObserver((list) => {\n      const entries = list.getEntries();\n      entries.forEach((entry) => {\n        console.log('FID:', entry.processingStart - entry.startTime);\n        this.trackInteraction('web_vital', 'fid', {\n          value: entry.processingStart - entry.startTime,\n          name: entry.name\n        });\n      });\n    }).observe({ entryTypes: ['first-input'] });\n    \n    // Cumulative Layout Shift\n    let clsValue = 0;\n    new PerformanceObserver((list) => {\n      const entries = list.getEntries();\n      entries.forEach((entry) => {\n        if (!entry.hadRecentInput) {\n          clsValue += entry.value;\n        }\n      });\n      \n      console.log('CLS:', clsValue);\n      this.trackInteraction('web_vital', 'cls', {\n        value: clsValue\n      });\n    }).observe({ entryTypes: ['layout-shift'] });\n  }\n  \n  /**\n   * 성능 리포트 생성\n   */\n  generateReport(timeRange = 60000) { // 기본 1분\n    const now = Date.now();\n    const cutoff = now - timeRange;\n    \n    const filterByTime = (metrics) => \n      metrics.filter(m => m.timestamp >= cutoff);\n    \n    const recentRenders = filterByTime(this.metrics.renders);\n    const recentApiCalls = filterByTime(this.metrics.apiCalls);\n    const recentInteractions = filterByTime(this.metrics.interactions);\n    const recentMemory = filterByTime(this.metrics.memory);\n    const recentErrors = filterByTime(this.metrics.errors);\n    \n    const report = {\n      timeRange: `${timeRange / 1000}s`,\n      timestamp: new Date().toISOString(),\n      \n      renders: {\n        count: recentRenders.length,\n        avgDuration: this.average(recentRenders.map(r => r.duration)),\n        slowRenders: recentRenders.filter(r => r.duration > 16).length,\n        components: [...new Set(recentRenders.map(r => r.component))]\n      },\n      \n      apiCalls: {\n        count: recentApiCalls.length,\n        avgDuration: this.average(recentApiCalls.map(a => a.duration)),\n        successRate: (recentApiCalls.filter(a => a.success).length / recentApiCalls.length * 100) || 0,\n        slowCalls: recentApiCalls.filter(a => a.duration > 1000).length\n      },\n      \n      interactions: {\n        count: recentInteractions.length,\n        types: this.countBy(recentInteractions, 'type')\n      },\n      \n      memory: {\n        current: this.getMemoryUsage(),\n        peak: recentMemory.length > 0 ? Math.max(...recentMemory.map(m => m.used)) : 0,\n        average: this.average(recentMemory.map(m => m.used))\n      },\n      \n      errors: {\n        count: recentErrors.length,\n        categories: this.countBy(recentErrors, 'category')\n      }\n    };\n    \n    return report;\n  }\n  \n  /**\n   * 콘솔 대시보드 출력\n   */\n  showDashboard() {\n    if (!this.isEnabled) {\n      console.log('Performance monitoring is disabled in production');\n      return;\n    }\n    \n    const report = this.generateReport();\n    \n    console.group('🚀 Performance Dashboard');\n    console.log('📊 Renders:', report.renders);\n    console.log('🌐 API Calls:', report.apiCalls);\n    console.log('👆 Interactions:', report.interactions);\n    console.log('💾 Memory:', report.memory);\n    console.log('❌ Errors:', report.errors);\n    console.groupEnd();\n    \n    return report;\n  }\n  \n  /**\n   * 유틸리티 함수들\n   */\n  average(arr) {\n    return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;\n  }\n  \n  countBy(arr, key) {\n    return arr.reduce((acc, item) => {\n      const value = item[key];\n      acc[value] = (acc[value] || 0) + 1;\n      return acc;\n    }, {});\n  }\n  \n  /**\n   * 성능 데이터 내보내기\n   */\n  exportData() {\n    const data = {\n      timestamp: Date.now(),\n      metrics: this.metrics,\n      report: this.generateReport(300000), // 5분 리포트\n      browser: {\n        userAgent: navigator.userAgent,\n        language: navigator.language,\n        platform: navigator.platform,\n        cookieEnabled: navigator.cookieEnabled,\n        onLine: navigator.onLine\n      },\n      page: {\n        url: window.location.href,\n        title: document.title,\n        referrer: document.referrer\n      }\n    };\n    \n    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });\n    const url = URL.createObjectURL(blob);\n    \n    const a = document.createElement('a');\n    a.href = url;\n    a.download = `performance_data_${new Date().toISOString().slice(0, 19)}.json`;\n    a.click();\n    \n    URL.revokeObjectURL(url);\n  }\n  \n  /**\n   * 모니터링 초기화\n   */\n  reset() {\n    this.metrics = {\n      renders: [],\n      apiCalls: [],\n      interactions: [],\n      memory: [],\n      errors: []\n    };\n    \n    console.log('Performance metrics reset');\n  }\n}\n\n// 전역 성능 모니터 인스턴스\nconst performanceMonitor = new PerformanceMonitor();\n\n// 개발자 도구에서 접근 가능하게 설정\nif (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {\n  window.performanceMonitor = performanceMonitor;\n  \n  // Web Vitals 측정 시작\n  performanceMonitor.measureWebVitals();\n  \n  console.log('🚀 Performance Monitor initialized. Use window.performanceMonitor to access.');\n  console.log('Available methods: showDashboard(), exportData(), reset()');\n}\n\nexport default performanceMonitor;\n\n/**\n * React Hook for performance monitoring\n */\nexport const usePerformanceMonitor = (componentName) => {\n  const measureRender = (renderFunction) => {\n    return performanceMonitor.measureRender(componentName, renderFunction);\n  };\n  \n  const trackInteraction = (type, details) => {\n    performanceMonitor.trackInteraction(type, componentName, details);\n  };\n  \n  return { measureRender, trackInteraction };\n};