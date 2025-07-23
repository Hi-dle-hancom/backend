import json
import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.core.config import settings

# Prometheus 메트릭 정의
REQUEST_COUNT = Counter(
    "api_requests_total", "Total API requests", [
        "method", "endpoint", "status"])
REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "API request duration")
AI_INFERENCE_DURATION = Histogram(
    "ai_inference_duration_seconds", "AI model inference duration"
)
ACTIVE_CONNECTIONS = Gauge(
    "active_connections",
    "Number of active connections")
ERROR_COUNT = Counter("api_errors_total", "Total API errors", ["error_type"])
CACHE_HIT_RATE = Gauge("cache_hit_rate", "Cache hit rate percentage")


class StructuredLogger:
    """구조화된 로깅을 위한 클래스"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.setup_logger()

    def setup_logger(self):
        """로거 설정"""
        # 로그 레벨 설정
        log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(log_level)

        # 기존 핸들러 제거
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # 콘솔 핸들러 추가
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # 파일 핸들러 추가 (프로덕션 환경)
        if not settings.DEBUG:
            if os.path.exists('/.dockerenv'):
                log_dir = Path("/app/logs")
            else:
                log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            file_handler = logging.FileHandler(
                log_dir / f"hapa_{datetime.now().strftime('%Y%m%d')}.log"
            )
            file_handler.setLevel(log_level)
            self.logger.addHandler(file_handler)

        # 포맷터 설정
        formatter = StructuredFormatter()
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.propagate = False

    def info(self, message: str, **kwargs):
        """INFO 레벨 로그"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """WARNING 레벨 로그"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """ERROR 레벨 로그"""
        self._log(logging.ERROR, message, **kwargs)
        ERROR_COUNT.labels(
            error_type=kwargs.get(
                "error_type",
                "unknown")).inc()

    def debug(self, message: str, **kwargs):
        """DEBUG 레벨 로그"""
        self._log(logging.DEBUG, message, **kwargs)

    def _log(self, level: int, message: str, **kwargs):
        """내부 로깅 메서드"""
        extra = {
            "timestamp": datetime.now().isoformat(),
            "service": "hapa-backend",
            "environment": "development" if settings.DEBUG else "production",
            **kwargs,
        }
        self.logger.log(level, message, extra=extra)


class StructuredFormatter(logging.Formatter):
    """JSON 구조화된 로그 포맷터"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # extra 필드 추가
        if hasattr(record, "timestamp"):
            log_entry.update(
                {
                    k: v
                    for k, v in record.__dict__.items()
                    if k
                    not in (
                        "name",
                        "msg",
                        "args",
                        "levelname",
                        "levelno",
                        "pathname",
                        "filename",
                        "module",
                        "lineno",
                        "funcName",
                        "created",
                        "msecs",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "processName",
                        "process",
                        "getMessage",
                    )
                }
            )

        return json.dumps(log_entry, ensure_ascii=False)


class APIMonitor:
    """API 모니터링 클래스"""

    def __init__(self):
        self.logger = StructuredLogger("api_monitor")

    def log_request_start(
            self,
            method: str,
            endpoint: str,
            client_ip: str = None):
        """API 요청 시작 로그"""
        self.logger.info(
            f"API 요청 시작: {method} {endpoint}",
            method=method,
            endpoint=endpoint,
            client_ip=client_ip,
            event_type="request_start",
        )
        ACTIVE_CONNECTIONS.inc()

    def log_request_end(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        client_ip: str = None,
    ):
        """API 요청 종료 로그"""
        self.logger.info(
            f"API 요청 완료: {method} {endpoint} - {status_code} ({duration:.4f}s)",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration,
            client_ip=client_ip,
            event_type="request_end",
        )

        # Prometheus 메트릭 업데이트
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=status_code).inc()
        REQUEST_DURATION.observe(duration)
        ACTIVE_CONNECTIONS.dec()

    def log_ai_inference(
        self,
        duration: float,
        prompt_length: int,
        response_length: int,
        cached: bool = False,
    ):
        """AI 추론 로그"""
        self.logger.info(
            f"AI 추론 완료: {duration:.4f}s (입력: {prompt_length}자, 출력: {response_length}자, 캐시: {cached})",
            duration=duration,
            prompt_length=prompt_length,
            response_length=response_length,
            cached=cached,
            event_type="ai_inference",
        )

        if not cached:
            AI_INFERENCE_DURATION.observe(duration)

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """에러 로그"""
        self.logger.error(
            f"오류 발생: {type(error).__name__}: {str(error)}",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context or {},
            event_type="error",
        )

    def log_cache_metrics(self, hit_rate: float, cache_size: int):
        """캐시 메트릭 로그"""
        self.logger.info(
            f"캐시 상태: 적중률 {hit_rate:.2%}, 크기 {cache_size}",
            hit_rate=hit_rate,
            cache_size=cache_size,
            event_type="cache_metrics",
        )
        CACHE_HIT_RATE.set(hit_rate * 100)


class PerformanceMonitor:
    """성능 모니터링 클래스"""

    def __init__(self):
        self.logger = StructuredLogger("performance_monitor")
        self.metrics = {
            "requests_per_minute": 0,
            "average_response_time": 0.0,
            "error_rate": 0.0,
            "cache_hit_rate": 0.0,
        }

    def update_metrics(self, **kwargs):
        """메트릭 업데이트"""
        self.metrics.update(kwargs)

        self.logger.info(
            "성능 메트릭 업데이트",
            metrics=self.metrics,
            event_type="performance_update",
        )

    def get_health_status(self) -> Dict[str, Any]:
        """시스템 헬스 상태 반환"""
        import psutil

        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
            },
            "application": self.metrics,
            "checks": {
                "high_cpu": psutil.cpu_percent() > 80,
                "high_memory": psutil.virtual_memory().percent > 80,
                "high_error_rate": self.metrics["error_rate"] > 0.05,
            },
        }

        # 전체 상태 결정
        if any(health_data["checks"].values()):
            health_data["status"] = "unhealthy"

        return health_data


# 로깅 설정 함수
def setup_logging():
    """애플리케이션 로깅 설정"""

    # 기본 로깅 설정
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": StructuredFormatter,
            },
            "simple": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL.upper(),
                "formatter": "structured" if not settings.DEBUG else "simple",
                "stream": sys.stdout,
            }},
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": settings.LOG_LEVEL.upper(),
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False},
            "fastapi": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False},
        },
    }

    logging.config.dictConfig(logging_config)

    # 로깅 설정 완료 로그
    logger = StructuredLogger("startup")
    logger.info(
        "로깅 시스템 초기화 완료",
        log_level=settings.LOG_LEVEL,
        debug_mode=settings.DEBUG,
    )


# 전역 모니터 인스턴스
api_monitor = APIMonitor()
performance_monitor = PerformanceMonitor()


# Prometheus 메트릭 엔드포인트를 위한 함수
def get_prometheus_metrics():
    """Prometheus 메트릭 반환"""
    return generate_latest()
