import json
import logging
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LogLevel(Enum):
    """로그 레벨 열거형"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """로그 카테고리 열거형"""

    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    AI_GENERATION = "ai_generation"
    CACHE_OPERATION = "cache_operation"
    DATABASE_OPERATION = "database_operation"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    ERROR_EVENT = "error_event"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class LogEntry:
    """구조화된 로그 엔트리"""

    timestamp: str
    level: str
    category: str
    message: str
    service: str
    version: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None


class StructuredLogger:
    """구조화된 로깅 시스템"""

    def __init__(self, name: str = "HAPA", version: str = "0.4.0"):
        self.logger = logging.getLogger(name)
        self.service_name = name
        self.version = version
        self.start_time = time.time()

    def _create_base_entry(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> LogEntry:
        """기본 로그 엔트리 생성"""
        return LogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level.value,
            category=category.value,
            message=message,
            service=self.service_name,
            version=self.version,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
        )

    def _log_structured(self, entry: LogEntry):
        """구조화된 로그 출력"""
        log_data = asdict(entry)
        # None 값 제거
        log_data = {k: v for k, v in log_data.items() if v is not None}

        # 로그 레벨에 따른 출력
        level_map = {
            "DEBUG": self.logger.debug,
            "INFO": self.logger.info,
            "WARNING": self.logger.warning,
            "ERROR": self.logger.error,
            "CRITICAL": self.logger.critical,
        }

        log_func = level_map.get(entry.level, self.logger.info)
        log_func(json.dumps(log_data, ensure_ascii=False))

    def log_api_request(
        self,
        method: str,
        endpoint: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        body_size: Optional[int] = None,
    ):
        """API 요청 로그"""
        entry = self._create_base_entry(
            LogLevel.INFO,
            LogCategory.API_REQUEST,
            f"API 요청: {method} {endpoint}",
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
        )

        entry.metadata = {
            "method": method,
            "endpoint": endpoint,
            "headers": headers or {},
            "query_params": query_params or {},
            "body_size": body_size,
        }

        self._log_structured(entry)

    def log_api_response(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        response_size: Optional[int] = None,
        cache_hit: Optional[bool] = None,
    ):
        """API 응답 로그"""
        level = LogLevel.INFO if 200 <= status_code < 400 else LogLevel.WARNING

        entry = self._create_base_entry(
            level,
            LogCategory.API_RESPONSE,
            f"API 응답: {method} {endpoint} - {status_code}",
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
        )

        entry.duration_ms = response_time_ms
        entry.metadata = {
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_size": response_size,
            "cache_hit": cache_hit,
        }

        self._log_structured(entry)

    def log_ai_generation(
        self,
        model_name: str,
        prompt_length: int,
        response_length: int,
        generation_time_ms: float,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
        cache_hit: Optional[bool] = None,
    ):
        """AI 코드 생성 로그"""
        entry = self._create_base_entry(
            LogLevel.INFO,
            LogCategory.AI_GENERATION,
            f"AI 코드 생성 완료: {model_name}",
            user_id=user_id,
            request_id=request_id,
        )

        entry.duration_ms = generation_time_ms
        entry.metadata = {
            "model_name": model_name,
            "prompt_length": prompt_length,
            "response_length": response_length,
            "tokens_used": tokens_used,
            "cost": cost,
            "cache_hit": cache_hit,
            "efficiency_ratio": (
                response_length / prompt_length if prompt_length > 0 else 0
            ),
        }

        self._log_structured(entry)

    def log_cache_operation(
        self,
        operation: str,  # get, set, delete, clear
        cache_type: str,  # redis, file, hybrid
        key: str,
        hit: Optional[bool] = None,
        duration_ms: Optional[float] = None,
        size_bytes: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
    ):
        """캐시 작업 로그"""
        entry = self._create_base_entry(
            LogLevel.DEBUG,
            LogCategory.CACHE_OPERATION,
            f"캐시 작업: {operation} ({cache_type})",
        )

        entry.duration_ms = duration_ms
        entry.metadata = {
            "operation": operation,
            "cache_type": cache_type,
            "key_hash": key[:16] + "..." if len(key) > 16 else key,
            "hit": hit,
            "size_bytes": size_bytes,
            "ttl_seconds": ttl_seconds,
        }

        self._log_structured(entry)

    def log_database_operation(
        self,
        operation: str,  # select, insert, update, delete
        table: str,
        duration_ms: float,
        rows_affected: Optional[int] = None,
        user_id: Optional[str] = None,
        error: Optional[Exception] = None,
    ):
        """데이터베이스 작업 로그"""
        level = LogLevel.ERROR if error else LogLevel.DEBUG

        entry = self._create_base_entry(
            level,
            LogCategory.DATABASE_OPERATION,
            f"DB 작업: {operation} on {table}",
            user_id=user_id,
        )

        entry.duration_ms = duration_ms
        entry.metadata = {
            "operation": operation,
            "table": table,
            "rows_affected": rows_affected,
        }

        if error:
            entry.error_details = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
            }

        self._log_structured(entry)

    def log_user_action(
        self,
        action: str,
        user_id: str,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """사용자 행동 로그"""
        entry = self._create_base_entry(
            LogLevel.INFO,
            LogCategory.USER_ACTION,
            f"사용자 행동: {action}",
            user_id=user_id,
            session_id=session_id,
        )

        entry.metadata = {
            "action": action,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "details": details or {},
        }

        self._log_structured(entry)

    def log_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        tags: Optional[Dict[str, str]] = None,
        threshold_exceeded: Optional[bool] = None,
    ):
        """성능 메트릭 로그"""
        level = LogLevel.WARNING if threshold_exceeded else LogLevel.DEBUG

        entry = self._create_base_entry(
            level,
            LogCategory.PERFORMANCE,
            f"성능 메트릭: {metric_name} = {value} {unit}",
        )

        entry.metadata = {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "tags": tags or {},
            "threshold_exceeded": threshold_exceeded,
        }

        self._log_structured(entry)

    def log_security_event(
        self,
        event_type: str,
        severity: str,  # low, medium, high, critical
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        """보안 이벤트 로그"""
        level_map = {
            "low": LogLevel.INFO,
            "medium": LogLevel.WARNING,
            "high": LogLevel.ERROR,
            "critical": LogLevel.CRITICAL,
        }
        level = level_map.get(severity, LogLevel.WARNING)

        entry = self._create_base_entry(
            level,
            LogCategory.SECURITY,
            f"보안 이벤트: {event_type} - {description}",
            user_id=user_id,
        )

        entry.metadata = {
            "event_type": event_type,
            "severity": severity,
            "ip_address": ip_address,
            "additional_data": additional_data or {},
        }

        self._log_structured(entry)

    def log_error(
        self,
        error: Exception,
        context: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        """에러 로그"""
        entry = self._create_base_entry(
            LogLevel.ERROR,
            LogCategory.ERROR_EVENT,
            f"에러 발생: {context}",
            user_id=user_id,
            request_id=request_id,
        )

        entry.error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "traceback": traceback.format_exc(),
            "additional_data": additional_data or {},
        }

        self._log_structured(entry)

    def log_system_event(
        self,
        event: str,
        status: str,  # started, stopped, failed, success
        details: Optional[Dict[str, Any]] = None,
    ):
        """시스템 이벤트 로그"""
        level = LogLevel.ERROR if status in [
            "failed", "error"] else LogLevel.INFO

        entry = self._create_base_entry(
            level, LogCategory.SYSTEM_EVENT, f"시스템 이벤트: {event} - {status}"
        )

        entry.metadata = {
            "event": event,
            "status": status,
            "uptime_seconds": time.time() - self.start_time,
            "details": details or {},
        }

        self._log_structured(entry)

    def get_log_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """로그 통계 조회 (실제 구현시 별도 저장소 필요)"""
        return {
            "time_window_minutes": minutes,
            "total_logs": 0,
            "by_level": {level.value: 0 for level in LogLevel},
            "by_category": {cat.value: 0 for cat in LogCategory},
            "avg_response_time_ms": 0.0,
            "error_rate_percent": 0.0,
        }


# 글로벌 구조화 로거 인스턴스
structured_logger = StructuredLogger()


# 편의 함수들
def log_api_request(method: str, endpoint: str, **kwargs):
    """API 요청 로그 편의 함수"""
    structured_logger.log_api_request(method, endpoint, **kwargs)


def log_api_response(
        method: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        **kwargs):
    """API 응답 로그 편의 함수"""
    structured_logger.log_api_response(
        method, endpoint, status_code, response_time_ms, **kwargs
    )


def log_ai_generation(
    model_name: str,
    prompt_length: int,
    response_length: int,
    generation_time_ms: float,
    **kwargs,
):
    """AI 생성 로그 편의 함수"""
    structured_logger.log_ai_generation(
        model_name,
        prompt_length,
        response_length,
        generation_time_ms,
        **kwargs)


def log_error(error: Exception, context: str, **kwargs):
    """에러 로그 편의 함수"""
    structured_logger.log_error(error, context, **kwargs)


def log_user_action(action: str, user_id: str, **kwargs):
    """사용자 행동 로그 편의 함수"""
    structured_logger.log_user_action(action, user_id, **kwargs)


def log_system_event(event: str, status: str, **kwargs):
    """시스템 이벤트 로그 편의 함수"""
    structured_logger.log_system_event(event, status, **kwargs)
