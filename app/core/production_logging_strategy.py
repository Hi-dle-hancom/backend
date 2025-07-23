"""
HAPA 프로젝트 실무 맞춤 로깅 전략
: 실제 운영환경에서 필요한 로깅 수준과 개인정보 보호를 고려한 구현
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import user_agents


class LoggingLevel(Enum):
    """실무 로깅 수준 정의"""

    MINIMAL = "minimal"  # 기본 API 성공/실패만
    STANDARD = "standard"  # 표준 비즈니스 로직
    DETAILED = "detailed"  # 상세 디버깅 정보
    DIAGNOSTIC = "diagnostic"  # 문제 진단용 상세 정보


class PrivacyLevel(Enum):
    """개인정보 보호 수준"""

    PUBLIC = "public"  # 공개 가능
    INTERNAL = "internal"  # 내부용 (해시화)
    RESTRICTED = "restricted"  # 제한적 (일부만)
    SENSITIVE = "sensitive"  # 민감정보 (로깅 금지)


@dataclass
class ProductionLogEntry:
    """실무용 로그 엔트리"""

    # 필수 메타데이터
    timestamp: str
    request_id: str
    trace_id: str
    service: str
    version: str
    environment: str

    # 요청 정보
    method: str
    endpoint: str
    status_code: int
    duration_ms: float

    # 사용자 정보 (개인정보 보호)
    user_id_hash: Optional[str] = None
    session_id_hash: Optional[str] = None
    ip_hash: Optional[str] = None

    # 기술적 정보
    user_agent_parsed: Optional[Dict[str, str]] = None
    request_size_bytes: Optional[int] = None
    response_size_bytes: Optional[int] = None

    # 비즈니스 메트릭
    business_metrics: Optional[Dict[str, Any]] = None

    # AI 관련 메트릭 (HAPA 특화)
    ai_metrics: Optional[Dict[str, Any]] = None

    # 에러 정보
    error_info: Optional[Dict[str, Any]] = None

    # 성능 정보
    performance_metrics: Optional[Dict[str, Any]] = None


class ProductionLogger:
    """실무 맞춤 프로덕션 로거"""

    def __init__(self, service_name: str = "HAPA", version: str = "1.0.0"):
        self.service_name = service_name
        self.version = version
        self.environment = self._detect_environment()
        self.logger = logging.getLogger(f"{service_name}.production")

        # 개인정보 보호를 위한 솔트
        self._privacy_salt = "HAPA_PRIVACY_SALT_2024"

    def _detect_environment(self) -> str:
        """환경 감지"""
        import os

        return os.getenv("ENVIRONMENT", "development")

    def _hash_sensitive_data(self, data: str) -> str:
        """민감 데이터 해시화"""
        if not data:
            return None
        return hashlib.sha256(
            f"{data}{self._privacy_salt}".encode()).hexdigest()[:16]

    def _parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        """User-Agent 파싱"""
        if not user_agent:
            return {"browser": "unknown", "os": "unknown", "device": "unknown"}

        try:
            ua = user_agents.parse(user_agent)
            return {
                "browser": f"{ua.browser.family} {ua.browser.version_string}",
                "os": f"{ua.os.family} {ua.os.version_string}",
                "device": ua.device.family,
                "is_mobile": ua.is_mobile,
                "is_bot": ua.is_bot,
            }
        except BaseException:
            return {"browser": "unknown", "os": "unknown", "device": "unknown"}

    def _sanitize_for_privacy(
            self,
            data: Any,
            privacy_level: PrivacyLevel) -> Any:
        """개인정보 보호를 위한 데이터 정제"""
        if privacy_level == PrivacyLevel.SENSITIVE:
            return "[REDACTED]"
        elif privacy_level == PrivacyLevel.RESTRICTED:
            if isinstance(data, str) and len(data) > 10:
                return f"{data[:3]}***{data[-3:]}"
            return "[RESTRICTED]"
        elif privacy_level == PrivacyLevel.INTERNAL:
            if isinstance(data, str):
                return self._hash_sensitive_data(data)
        return data

    async def log_api_request_detailed(
        self,
        request_id: str,
        trace_id: str,
        method: str,
        endpoint: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        body_size: Optional[int] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ):
        """상세 API 요청 로깅"""

        # 개인정보 보호 처리
        user_id_hash = self._hash_sensitive_data(user_id) if user_id else None
        session_id_hash = self._hash_sensitive_data(
            session_id) if session_id else None
        ip_hash = self._hash_sensitive_data(ip_address) if ip_address else None

        # User-Agent 파싱
        user_agent_parsed = self._parse_user_agent(user_agent)

        # 민감한 헤더 필터링
        safe_headers = {}
        if headers:
            dangerous_headers = {
                "authorization",
                "cookie",
                "x-api-key",
                "authentication",
            }
            safe_headers = {
                k: v for k,
                v in headers.items() if k.lower() not in dangerous_headers}

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "api_request_start",
            "request_id": request_id,
            "trace_id": trace_id,
            "service": self.service_name,
            "version": self.version,
            "environment": self.environment,
            # 요청 정보
            "method": method,
            "endpoint": endpoint,
            "request_size_bytes": body_size,
            # 사용자 정보 (해시화)
            "user_id_hash": user_id_hash,
            "session_id_hash": session_id_hash,
            "ip_hash": ip_hash,
            # 기술적 정보
            "user_agent_parsed": user_agent_parsed,
            "safe_headers": safe_headers,
            "query_params": query_params,
            # 추가 컨텍스트
            "additional_context": additional_context or {},
        }

        self.logger.info(json.dumps(log_data, ensure_ascii=False))

    async def log_api_response_detailed(
        self,
        request_id: str,
        trace_id: str,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        response_size: Optional[int] = None,
        cache_hit: Optional[bool] = None,
        database_queries: Optional[int] = None,
        external_api_calls: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None,
        business_metrics: Optional[Dict[str, Any]] = None,
    ):
        """상세 API 응답 로깅"""

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "api_response_end",
            "request_id": request_id,
            "trace_id": trace_id,
            "service": self.service_name,
            "version": self.version,
            "environment": self.environment,
            # 응답 정보
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "response_size_bytes": response_size,
            # 성능 메트릭
            "performance_metrics": {
                "cache_hit": cache_hit,
                "database_queries": database_queries,
                "external_api_calls": external_api_calls,
                "requests_per_second": 1000 / duration_ms if duration_ms > 0 else 0,
            },
            # 비즈니스 메트릭
            "business_metrics": business_metrics or {},
            # 에러 정보 (개인정보 제거)
            "error_info": (
                self._sanitize_error_details(
                    error_details) if error_details else None
            ),
        }

        self.logger.info(json.dumps(log_data, ensure_ascii=False))

    async def log_ai_operation_detailed(
        self,
        request_id: str,
        operation_type: str,  # generate, complete, stream
        model_name: str,
        prompt_length: int,
        response_length: int,
        generation_time_ms: float,
        tokens_used: Optional[int] = None,
        cost_estimate: Optional[float] = None,
        quality_score: Optional[float] = None,
        user_satisfaction: Optional[int] = None,
        personalization_used: Optional[bool] = None,
        cache_hit: Optional[bool] = None,
        error_occurred: Optional[bool] = None,
    ):
        """AI 작업 상세 로깅"""

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "ai_operation",
            "request_id": request_id,
            "service": self.service_name,
            "version": self.version,
            # AI 작업 정보
            "ai_metrics": {
                "operation_type": operation_type,
                "model_name": model_name,
                "prompt_length": prompt_length,
                "response_length": response_length,
                "generation_time_ms": generation_time_ms,
                "tokens_used": tokens_used,
                "cost_estimate": cost_estimate,
                "quality_score": quality_score,
                "user_satisfaction": user_satisfaction,
                "personalization_used": personalization_used,
                "cache_hit": cache_hit,
                "error_occurred": error_occurred,
                # 효율성 메트릭
                "tokens_per_second": (
                    tokens_used / (generation_time_ms / 1000)
                    if tokens_used and generation_time_ms > 0
                    else None
                ),
                "characters_per_token": (
                    response_length / tokens_used
                    if tokens_used and tokens_used > 0
                    else None
                ),
                "cost_per_token": (
                    cost_estimate / tokens_used
                    if cost_estimate and tokens_used and tokens_used > 0
                    else None
                ),
            },
        }

        self.logger.info(json.dumps(log_data, ensure_ascii=False))

    async def log_user_behavior_detailed(
        self,
        user_id: str,
        action: str,
        session_id: Optional[str] = None,
        page_url: Optional[str] = None,
        previous_page: Optional[str] = None,
        time_spent_seconds: Optional[float] = None,
        interaction_data: Optional[Dict[str, Any]] = None,
        feature_flags: Optional[List[str]] = None,
        ab_test_groups: Optional[Dict[str, str]] = None,
    ):
        """사용자 행동 상세 로깅"""

        user_id_hash = self._hash_sensitive_data(user_id)
        session_id_hash = self._hash_sensitive_data(
            session_id) if session_id else None

        # URL에서 개인정보 제거
        safe_url = self._sanitize_url(page_url) if page_url else None
        safe_previous_url = self._sanitize_url(
            previous_page) if previous_page else None

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "user_behavior",
            "service": self.service_name,
            "version": self.version,
            # 사용자 정보 (해시화)
            "user_id_hash": user_id_hash,
            "session_id_hash": session_id_hash,
            # 행동 정보
            "user_behavior": {
                "action": action,
                "page_url": safe_url,
                "previous_page": safe_previous_url,
                "time_spent_seconds": time_spent_seconds,
                "interaction_data": interaction_data or {},
                "feature_flags": feature_flags or [],
                "ab_test_groups": ab_test_groups or {},
            },
        }

        self.logger.info(json.dumps(log_data, ensure_ascii=False))

    def _sanitize_error_details(
            self, error_details: Dict[str, Any]) -> Dict[str, Any]:
        """에러 정보에서 개인정보 제거"""
        sanitized = {}

        # 안전한 필드만 포함
        safe_fields = [
            "error_type",
            "error_code",
            "status_code",
            "retry_count",
            "timeout",
            "rate_limit",
            "validation_errors",
        ]

        for field in safe_fields:
            if field in error_details:
                sanitized[field] = error_details[field]

        # 에러 메시지에서 개인정보 패턴 제거
        if "error_message" in error_details:
            sanitized["error_message"] = self._sanitize_error_message(
                error_details["error_message"]
            )

        return sanitized

    def _sanitize_error_message(self, message: str) -> str:
        """에러 메시지에서 개인정보 패턴 제거"""
        if not message:
            return message

        # 이메일 패턴 제거
        message = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "[EMAIL]",
            message)

        # 전화번호 패턴 제거
        message = re.sub(r"\b\d{3}-\d{3,4}-\d{4}\b", "[PHONE]", message)

        # API 키 패턴 제거
        message = re.sub(r"\b[A-Za-z0-9]{32,}\b", "[API_KEY]", message)

        # 파일 경로에서 사용자명 제거
        message = re.sub(r"/Users/[^/]+/", "/Users/[USER]/", message)
        message = re.sub(
            r"C:\\Users\\[^\\]+\\",
            "C:\\Users\\[USER]\\",
            message)

        return message

    def _sanitize_url(self, url: str) -> str:
        """URL에서 개인정보 제거"""
        if not url:
            return url

        try:
            parsed = urlparse(url)

            # 쿼리 파라미터에서 민감한 정보 제거
            safe_query = re.sub(
                r"(token|key|password|secret)=[^&]*",
                r"\1=[REDACTED]",
                parsed.query)

            # 경로에서 ID 패턴 제거
            safe_path = re.sub(r"/users/\d+", "/users/[USER_ID]", parsed.path)
            safe_path = re.sub(
                r"/sessions/[a-f0-9-]+", "/sessions/[SESSION_ID]", safe_path
            )

            return f"{parsed.scheme}://{parsed.netloc}{safe_path}?{safe_query}"
        except BaseException:
            return "[INVALID_URL]"

    async def log_security_event_detailed(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_path: Optional[str] = None,
        attack_vector: Optional[str] = None,
        blocked: Optional[bool] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        """보안 이벤트 상세 로깅"""

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "security_event",
            "service": self.service_name,
            "version": self.version,
            # 보안 이벤트 정보
            "security_event": {
                "event_type": event_type,
                "severity": severity,
                "description": description,
                "attack_vector": attack_vector,
                "blocked": blocked,
                "request_path": request_path,
                # 해시화된 식별자
                "user_id_hash": self._hash_sensitive_data(user_id) if user_id else None,
                "ip_hash": (
                    self._hash_sensitive_data(
                        ip_address) if ip_address else None
                ),
                # 파싱된 User-Agent
                "user_agent_parsed": self._parse_user_agent(user_agent),
                # 추가 데이터 (민감정보 제거)
                "additional_data": (
                    self._sanitize_for_privacy(
                        additional_data, PrivacyLevel.INTERNAL)
                    if additional_data
                    else {}
                ),
            },
        }

        self.logger.warning(json.dumps(log_data, ensure_ascii=False))


# 싱글톤 인스턴스
production_logger = ProductionLogger()


# 편의 함수들
async def log_api_request_detailed(**kwargs):
    """API 요청 상세 로깅 편의 함수"""
    await production_logger.log_api_request_detailed(**kwargs)


async def log_api_response_detailed(**kwargs):
    """API 응답 상세 로깅 편의 함수"""
    await production_logger.log_api_response_detailed(**kwargs)


async def log_ai_operation_detailed(**kwargs):
    """AI 작업 상세 로깅 편의 함수"""
    await production_logger.log_ai_operation_detailed(**kwargs)


async def log_user_behavior_detailed(**kwargs):
    """사용자 행동 상세 로깅 편의 함수"""
    await production_logger.log_user_behavior_detailed(**kwargs)


async def log_security_event_detailed(**kwargs):
    """보안 이벤트 상세 로깅 편의 함수"""
    await production_logger.log_security_event_detailed(**kwargs)
