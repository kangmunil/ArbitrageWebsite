"""
외부 의존성 모니터링 및 알림 시스템

주요 기능:
1. 외부 API 상태 모니터링
2. 시스템 메트릭 수집
3. 알림 및 경고 시스템
4. 대시보드용 데이터 제공
5. 성능 추적 및 분석
"""

import asyncio
import time
import logging
import json
import smtplib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psutil
import aiohttp

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """알림 심각도"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertChannel(Enum):
    """알림 채널"""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"

@dataclass
class Alert:
    """알림 메시지"""
    title: str
    message: str
    severity: AlertSeverity
    category: str  # "exchange", "system", "data_quality" 등
    source: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

@dataclass
class SystemMetric:
    """시스템 메트릭"""
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)

class MetricsCollector:
    """시스템 메트릭 수집기"""
    
    def __init__(self):
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.collection_interval = 30  # 30초마다 수집
        
    async def start_collection(self):
        """메트릭 수집 시작"""
        logger.info("시스템 메트릭 수집 시작")
        
        while True:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"메트릭 수집 오류: {e}")
                await asyncio.sleep(10)
    
    async def _collect_system_metrics(self):
        """시스템 메트릭 수집"""
        timestamp = time.time()
        
        # CPU 사용률
        cpu_percent = psutil.cpu_percent(interval=1)
        self._record_metric("system.cpu.usage", cpu_percent, "percent", timestamp)
        
        # 메모리 사용률
        memory = psutil.virtual_memory()
        self._record_metric("system.memory.usage", memory.percent, "percent", timestamp)
        self._record_metric("system.memory.available", memory.available / (1024**3), "GB", timestamp)
        
        # 디스크 사용률
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        self._record_metric("system.disk.usage", disk_percent, "percent", timestamp)
        
        # 네트워크 I/O
        net_io = psutil.net_io_counters()
        self._record_metric("system.network.bytes_sent", net_io.bytes_sent, "bytes", timestamp)
        self._record_metric("system.network.bytes_recv", net_io.bytes_recv, "bytes", timestamp)
        
        # 프로세스 정보
        process = psutil.Process()
        self._record_metric("process.cpu.usage", process.cpu_percent(), "percent", timestamp)
        self._record_metric("process.memory.rss", process.memory_info().rss / (1024**2), "MB", timestamp)
        
        # 파일 디스크립터 사용량
        try:
            fd_count = process.num_fds() if hasattr(process, 'num_fds') else 0
            self._record_metric("process.file_descriptors", fd_count, "count", timestamp)
        except:
            pass
    
    def _record_metric(self, name: str, value: float, unit: str, timestamp: float):
        """메트릭 기록"""
        metric = SystemMetric(name=name, value=value, unit=unit, timestamp=timestamp)
        self.metrics_history[name].append(metric)
    
    def get_metric_history(self, metric_name: str, duration: int = 3600) -> List[SystemMetric]:
        """메트릭 이력 반환 (기본 1시간)"""
        cutoff_time = time.time() - duration
        history = self.metrics_history.get(metric_name, deque())
        
        return [
            metric for metric in history 
            if metric.timestamp >= cutoff_time
        ]
    
    def get_current_metrics(self) -> Dict[str, float]:
        """현재 메트릭 값들 반환"""
        current = {}
        for name, history in self.metrics_history.items():
            if history:
                current[name] = history[-1].value
        return current

class ExchangeMonitor:
    """거래소 모니터링"""
    
    def __init__(self):
        self.exchange_status: Dict[str, Dict[str, Any]] = {}
        self.response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.last_successful_request: Dict[str, float] = {}
        
        # 임계값 설정
        self.response_time_threshold = 5.0  # 5초
        self.error_rate_threshold = 0.1     # 10%
        self.connection_timeout_threshold = 300  # 5분
        
    async def monitor_exchange(self, exchange: str, endpoint: str):
        """거래소 모니터링"""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, timeout=10) as response:
                    response_time = time.time() - start_time
                    
                    # 응답 시간 기록
                    self.response_times[exchange].append(response_time)
                    
                    if response.status == 200:
                        self.last_successful_request[exchange] = time.time()
                        self._update_exchange_status(exchange, "healthy", response_time)
                    else:
                        self._record_error(exchange, f"HTTP {response.status}")
                        
        except asyncio.TimeoutError:
            self._record_error(exchange, "Timeout")
            self._update_exchange_status(exchange, "timeout", time.time() - start_time)
        except Exception as e:
            self._record_error(exchange, str(e))
            self._update_exchange_status(exchange, "error", time.time() - start_time)
    
    def _update_exchange_status(self, exchange: str, status: str, response_time: float):
        """거래소 상태 업데이트"""
        self.exchange_status[exchange] = {
            "status": status,
            "last_check": time.time(),
            "response_time": response_time,
            "error_count": self.error_counts[exchange],
            "avg_response_time": self._calculate_avg_response_time(exchange)
        }
    
    def _record_error(self, exchange: str):
        """오류 기록"""
        self.error_counts[exchange] += 1
    
    def _calculate_avg_response_time(self, exchange: str) -> float:
        """평균 응답 시간 계산"""
        times = list(self.response_times[exchange])
        return sum(times) / len(times) if times else 0.0
    
    def get_exchange_health(self) -> Dict[str, Any]:
        """거래소 건강 상태 반환"""
        health_data = {}
        
        for exchange, status in self.exchange_status.items():
            # 상태 분석
            is_healthy = (
                status["status"] == "healthy" and
                status["response_time"] < self.response_time_threshold and
                (time.time() - status["last_check"]) < self.connection_timeout_threshold
            )
            
            health_data[exchange] = {
                **status,
                "is_healthy": is_healthy,
                "last_successful": self.last_successful_request.get(exchange, 0)
            }
        
        return health_data

class AlertManager:
    """알림 관리자"""
    
    def __init__(self):
        self.alert_rules: List[Dict[str, Any]] = []
        self.alert_history: deque = deque(maxlen=1000)
        self.notification_channels: Dict[AlertChannel, Callable] = {}
        self.alert_cooldown: Dict[str, float] = {}  # 중복 알림 방지
        self.cooldown_period = 300  # 5분
        
        # 기본 알림 채널 설정
        self._setup_default_channels()
        
        # 기본 알림 규칙 설정
        self._setup_default_rules()
    
    def _setup_default_channels(self):
        """기본 알림 채널 설정"""
        self.notification_channels[AlertChannel.LOG] = self._send_log_alert
        self.notification_channels[AlertChannel.CONSOLE] = self._send_console_alert
    
    def _setup_default_rules(self):
        """기본 알림 규칙 설정"""
        self.alert_rules = [
            {
                "name": "high_cpu_usage",
                "condition": lambda metrics: metrics.get("system.cpu.usage", 0) > 80,
                "severity": AlertSeverity.WARNING,
                "category": "system",
                "message": "CPU 사용률이 높습니다: {cpu_usage:.1f}%"
            },
            {
                "name": "high_memory_usage", 
                "condition": lambda metrics: metrics.get("system.memory.usage", 0) > 85,
                "severity": AlertSeverity.WARNING,
                "category": "system",
                "message": "메모리 사용률이 높습니다: {memory_usage:.1f}%"
            },
            {
                "name": "exchange_connection_lost",
                "condition": lambda health: any(
                    not exchange_data["is_healthy"] 
                    for exchange_data in health.values()
                ),
                "severity": AlertSeverity.ERROR,
                "category": "exchange",
                "message": "거래소 연결 문제 감지"
            }
        ]
    
    async def check_alert_conditions(self, metrics: Dict[str, float], exchange_health: Dict[str, Any]):
        """알림 조건 확인"""
        for rule in self.alert_rules:
            try:
                rule_name = rule["name"]
                
                # 쿨다운 확인
                if self._is_in_cooldown(rule_name):
                    continue
                
                # 조건 확인
                if rule["category"] == "system":
                    triggered = rule["condition"](metrics)
                    context = metrics
                elif rule["category"] == "exchange":
                    triggered = rule["condition"](exchange_health)
                    context = exchange_health
                else:
                    continue
                
                if triggered:
                    await self._send_alert(rule, context)
                    self._set_cooldown(rule_name)
                    
            except Exception as e:
                logger.error(f"알림 규칙 확인 오류 ({rule.get('name', 'unknown')}): {e}")
    
    async def _send_alert(self, rule: Dict[str, Any], context: Dict[str, Any]):
        """알림 전송"""
        message = rule["message"].format(**context)
        
        alert = Alert(
            title=rule["name"].replace("_", " ").title(),
            message=message,
            severity=rule["severity"],
            category=rule["category"],
            source="monitoring_system",
            metadata={"rule": rule["name"], "context": context}
        )
        
        self.alert_history.append(alert)
        
        # 모든 활성화된 채널로 알림 전송
        for channel, sender in self.notification_channels.items():
            try:
                await sender(alert)
            except Exception as e:
                logger.error(f"알림 전송 실패 ({channel.value}): {e}")
    
    async def _send_log_alert(self, alert: Alert):
        """로그 알림 전송"""
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.INFO)
        
        logger.log(log_level, f"[ALERT] {alert.title}: {alert.message}")
    
    async def _send_console_alert(self, alert: Alert):
        """콘솔 알림 전송"""
        severity_icons = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨"
        }
        
        icon = severity_icons.get(alert.severity, "📢")
        print(f"{icon} [{alert.severity.value.upper()}] {alert.title}: {alert.message}")
    
    def _is_in_cooldown(self, rule_name: str) -> bool:
        """쿨다운 중인지 확인"""
        last_alert = self.alert_cooldown.get(rule_name, 0)
        return (time.time() - last_alert) < self.cooldown_period
    
    def _set_cooldown(self, rule_name: str):
        """쿨다운 설정"""
        self.alert_cooldown[rule_name] = time.time()
    
    def add_notification_channel(self, channel: AlertChannel, sender: Callable):
        """알림 채널 추가"""
        self.notification_channels[channel] = sender
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 알림 반환"""
        recent = list(self.alert_history)[-limit:]
        return [alert.to_dict() for alert in recent]

class MonitoringDashboard:
    """모니터링 대시보드 데이터 제공"""
    
    def __init__(self, metrics_collector: MetricsCollector, exchange_monitor: ExchangeMonitor, alert_manager: AlertManager):
        self.metrics_collector = metrics_collector
        self.exchange_monitor = exchange_monitor
        self.alert_manager = alert_manager
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """대시보드용 종합 데이터"""
        current_metrics = self.metrics_collector.get_current_metrics()
        exchange_health = self.exchange_monitor.get_exchange_health()
        recent_alerts = self.alert_manager.get_recent_alerts(20)
        
        # 시스템 상태 요약
        system_status = "healthy"
        if current_metrics.get("system.cpu.usage", 0) > 80 or current_metrics.get("system.memory.usage", 0) > 85:
            system_status = "warning"
        
        # 거래소 상태 요약
        healthy_exchanges = sum(1 for data in exchange_health.values() if data["is_healthy"])
        total_exchanges = len(exchange_health)
        
        return {
            "timestamp": time.time(),
            "system": {
                "status": system_status,
                "cpu_usage": current_metrics.get("system.cpu.usage", 0),
                "memory_usage": current_metrics.get("system.memory.usage", 0),
                "disk_usage": current_metrics.get("system.disk.usage", 0),
                "uptime": time.time()  # 시작 시간부터 계산 필요
            },
            "exchanges": {
                "healthy_count": healthy_exchanges,
                "total_count": total_exchanges,
                "health_percentage": (healthy_exchanges / total_exchanges * 100) if total_exchanges > 0 else 0,
                "details": exchange_health
            },
            "alerts": {
                "recent_count": len(recent_alerts),
                "recent_alerts": recent_alerts,
                "severity_distribution": self._get_alert_severity_distribution(recent_alerts)
            },
            "performance": {
                "avg_response_times": self._get_avg_response_times(exchange_health),
                "error_rates": self._get_error_rates(exchange_health)
            }
        }
    
    def _get_alert_severity_distribution(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """알림 심각도 분포"""
        distribution = defaultdict(int)
        for alert in alerts:
            distribution[alert["severity"]] += 1
        return dict(distribution)
    
    def _get_avg_response_times(self, exchange_health: Dict[str, Any]) -> Dict[str, float]:
        """평균 응답 시간"""
        return {
            exchange: data.get("avg_response_time", 0)
            for exchange, data in exchange_health.items()
        }
    
    def _get_error_rates(self, exchange_health: Dict[str, Any]) -> Dict[str, float]:
        """오류율"""
        return {
            exchange: data.get("error_count", 0)
            for exchange, data in exchange_health.items()
        }

class ComprehensiveMonitoringSystem:
    """종합 모니터링 시스템"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.exchange_monitor = ExchangeMonitor()
        self.alert_manager = AlertManager()
        self.dashboard = MonitoringDashboard(
            self.metrics_collector, 
            self.exchange_monitor, 
            self.alert_manager
        )
        
        self.is_running = False
        
        # 거래소 엔드포인트 설정
        self.exchange_endpoints = {
            "upbit": "https://api.upbit.com/v1/market/all",
            "binance": "https://api.binance.com/api/v3/ping",
            "bybit": "https://api.bybit.com/v5/market/time"
        }
    
    async def start(self):
        """모니터링 시스템 시작"""
        logger.info("종합 모니터링 시스템 시작")
        self.is_running = True
        
        # 백그라운드 태스크 시작
        tasks = [
            asyncio.create_task(self.metrics_collector.start_collection()),
            asyncio.create_task(self._monitor_exchanges()),
            asyncio.create_task(self._check_alerts_periodically())
        ]
        
        logger.info("모든 모니터링 서비스 시작 완료")
        
        # 태스크들이 완료될 때까지 대기
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """모니터링 시스템 종료"""
        logger.info("모니터링 시스템 종료")
        self.is_running = False
    
    async def _monitor_exchanges(self):
        """거래소 모니터링 루프"""
        while self.is_running:
            try:
                tasks = [
                    self.exchange_monitor.monitor_exchange(exchange, endpoint)
                    for exchange, endpoint in self.exchange_endpoints.items()
                ]
                
                await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                logger.error(f"거래소 모니터링 오류: {e}")
                await asyncio.sleep(10)
    
    async def _check_alerts_periodically(self):
        """주기적 알림 확인"""
        while self.is_running:
            try:
                current_metrics = self.metrics_collector.get_current_metrics()
                exchange_health = self.exchange_monitor.get_exchange_health()
                
                await self.alert_manager.check_alert_conditions(current_metrics, exchange_health)
                
                await asyncio.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                logger.error(f"알림 확인 오류: {e}")
                await asyncio.sleep(10)
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 반환"""
        return self.dashboard.get_dashboard_data()
    
    async def send_manual_alert(self, title: str, message: str, severity: AlertSeverity = AlertSeverity.INFO):
        """수동 알림 전송"""
        alert = Alert(
            title=title,
            message=message,
            severity=severity,
            category="manual",
            source="user"
        )
        
        self.alert_manager.alert_history.append(alert)
        
        for channel, sender in self.alert_manager.notification_channels.items():
            try:
                await sender(alert)
            except Exception as e:
                logger.error(f"수동 알림 전송 실패 ({channel.value}): {e}")

# 전역 모니터링 시스템 인스턴스
monitoring_system = ComprehensiveMonitoringSystem()