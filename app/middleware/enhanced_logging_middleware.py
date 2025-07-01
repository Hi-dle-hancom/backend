"""
HAPA 실무 맞춤 강화된 로깅 미들웨어
- API별 우선순위 기반 상세 로깅
- 개인정보 자동 보호
- 비즈니스 메트릭 수집
- 스마트 샘플링
"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.logging_config import StructuredLogger

from ..core.production_logging_strategy import (
    LoggingLevel,
    PrivacyLevel,
    production_logger,
)

logger = StructuredLogger("security_middleware")


class SmartLoggingSampler:
    """스마트 샘플링 로직"""

    # API별 로깅 우선순위 설정
    API_PRIORITIES = {
        # Critical APIs (100% 로깅)
        "/api/v1/generate": {"level": LoggingLevel.DETAILED, "sample_rate": 1.0},
        "/api/v1/complete": {"level": LoggingLevel.DETAILED, "sample_rate": 1.0},
        "/api/v1/stream-generate": {"level": LoggingLevel.DETAILED, "sample_rate": 1.0},
        "/api/v1/auth": {"level": LoggingLevel.DETAILED, "sample_rate": 1.0},
        "/api/v1/users/login": {"level": LoggingLevel.DETAILED, "sample_rate": 1.0},
        # High Priority APIs (50% 샘플링)
        "/api/v1/settings": {"level": LoggingLevel.STANDARD, "sample_rate": 0.5},
        "/api/v1/history": {"level": LoggingLevel.STANDARD, "sample_rate": 0.5},
        "/api/v1/validation": {"level": LoggingLevel.STANDARD, "sample_rate": 0.5},
        "/api/v1/feedback": {"level": LoggingLevel.STANDARD, "sample_rate": 0.5},
        # Medium Priority APIs (10% 샘플링)
        "/api/v1/metrics": {"level": LoggingLevel.MINIMAL, "sample_rate": 0.1},
        "/api/v1/cache": {"level": LoggingLevel.MINIMAL, "sample_rate": 0.1},
        # Low Priority APIs (1% 샘플링)
        "/health": {"level": LoggingLevel.MINIMAL, "sample_rate": 0.01},
    }

    def should_log_detailed(
        self,
        endpoint: str,
        method: str,
        user_tier: str = "free",
        error_occurred: bool = False,
    ) -> tuple[bool, LoggingLevel]:
        """상세 로깅 여부 결정"""
        import random

        # 에러 발생시 무조건 상세 로깅
        if error_occurred:
            return True, LoggingLevel.DIAGNOSTIC

        # 유료 사용자는 더 상세히 로깅
        if user_tier in ["premium", "enterprise"]:
            return True, LoggingLevel.DETAILED

        # API별 우선순위 확인
        for api_pattern, config in self.API_PRIORITIES.items():
            if endpoint.startswith(api_pattern):
                should_log = random.random() < config["sample_rate"]
                return should_log, config["level"]

        # 기본값: 1% 샘플링
        return random.random() < 0.01, LoggingLevel.MINIMAL


class EnhancedLoggingMiddleware(BaseHTTPMiddleware):
    """강화된 로깅 미들웨어"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.sampler = SmartLoggingSampler()
        self.logger = logging.getLogger("enhanced_logging")

        # 민감한 헤더 목록
        self.sensitive_headers = {
            "authorization",
            "cookie",
            "x-api-key",
            "authentication",
            "x-forwarded-for",
            "x-real-ip",
        }

        # 성능 메트릭 추적
        self.performance_tracker = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청 처리 및 로깅"""

        # 고유 ID 생성
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))

        # 요청 시작 시간
        start_time = time.time()

        # 요청 정보 추출
        method = request.method
        endpoint = str(request.url.path)
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # 사용자 정보 추출 (API 키 또는 JWT에서)
        user_id, user_tier = await self._extract_user_info(request)

        # 로깅 여부 결정
        should_log, logging_level = self.sampler.should_log_detailed(
            endpoint, method, user_tier
        )

        if should_log:
            # 상세 요청 로깅
            await self._log_request_start(
                request_id,
                trace_id,
                request,
                method,
                endpoint,
                client_ip,
                user_agent,
                user_id,
                logging_level,
            )

        # 응답 처리
        error_occurred = False
        response = None

        try:
            response = await call_next(request)

        except Exception as e:
            error_occurred = True
            self.logger.error(f"Request processing error: {e}")
            # 에러 발생시 무조건 로깅
            should_log = True
            logging_level = LoggingLevel.DIAGNOSTIC

            # 에러 응답 생성
            if isinstance(e, HTTPException):
                response = JSONResponse(
                    status_code=e.status_code, content={"detail": e.detail}
                )
            else:
                response = JSONResponse(
                    status_code=500, content={
                        "detail": "Internal server error"})

        # 응답 시간 계산
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000

        if should_log or error_occurred:
            # 상세 응답 로깅
            await self._log_response_end(
                request_id,
                trace_id,
                request,
                response,
                method,
                endpoint,
                duration_ms,
                user_id,
                logging_level,
                error_occurred,
            )

        # 성능 메트릭 업데이트
        self._update_performance_metrics(
            endpoint, duration_ms, response.status_code)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        # 프록시 환경 고려
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"

    async def _extract_user_info(self, request: Request) -> tuple[Optional[str], str]:
        """사용자 정보 추출"""
        user_id = None
        user_tier = "free"

        # Authorization 헤더에서 추출
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # JWT 토큰에서 사용자 ID 추출 (간단 구현)
            try:
                # 실제로는 JWT 디코딩 필요
                user_id = "jwt_user"  # 임시값
                user_tier = "premium"  # JWT 사용자는 프리미엄으로 간주
            except BaseException:
                pass

        # API Key 헤더에서 추출
        api_key = request.headers.get("x-api-key", "")
        if api_key:
            # API 키에서 사용자 정보 추출
            user_id = f"api_user_{api_key[:8]}"
            user_tier = "standard"

        return user_id, user_tier

    async def _log_request_start(
        self,
        request_id: str,
        trace_id: str,
        request: Request,
        method: str,
        endpoint: str,
        client_ip: str,
        user_agent: str,
        user_id: Optional[str],
        logging_level: LoggingLevel,
    ):
        """상세 요청 시작 로깅"""

        # 요청 본문 크기 계산
        body_size = None
        if hasattr(request, "_body"):
            body_size = len(request._body) if request._body else 0

        # 안전한 헤더 필터링
        safe_headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in self.sensitive_headers
        }

        # 쿼리 파라미터
        query_params = dict(request.query_params)

        # 추가 컨텍스트 (비즈니스 로직)
        additional_context = {}

        # AI 관련 API인 경우 특별 처리
        if any(
            ai_endpoint in endpoint
            for ai_endpoint in ["/generate", "/complete", "/stream"]
        ):
            additional_context.update(
                {
                    "api_category": "ai_generation",
                    "business_critical": True,
                    "expected_high_latency": True,
                }
            )

        # 인증 관련 API인 경우
        elif any(
            auth_endpoint in endpoint
            for auth_endpoint in ["/auth", "/login", "/logout"]
        ):
            additional_context.update(
                {
                    "api_category": "authentication",
                    "security_sensitive": True,
                    "audit_required": True,
                }
            )

        await production_logger.log_api_request_detailed(
            request_id=request_id,
            trace_id=trace_id,
            method=method,
            endpoint=endpoint,
            user_id=user_id,
            session_id=request.headers.get("X-Session-ID"),
            ip_address=client_ip,
            user_agent=user_agent,
            headers=safe_headers,
            query_params=query_params,
            body_size=body_size,
            additional_context=additional_context,
        )

    async def _log_response_end(
        self,
        request_id: str,
        trace_id: str,
        request: Request,
        response: Response,
        method: str,
        endpoint: str,
        duration_ms: float,
        user_id: Optional[str],
        logging_level: LoggingLevel,
        error_occurred: bool,
    ):
        """상세 응답 종료 로깅"""

        status_code = response.status_code

        # 응답 크기 계산
        response_size = None
        if hasattr(response, "body"):
            response_size = len(response.body) if response.body else 0

        # 캐시 히트 여부 확인
        cache_hit = response.headers.get("X-Cache-Status") == "HIT"

        # 데이터베이스 쿼리 수 (헤더에서 추출)
        database_queries = None
        if "X-DB-Queries" in response.headers:
            try:
                database_queries = int(response.headers["X-DB-Queries"])
            except BaseException:
                pass

        # 외부 API 호출 수
        external_api_calls = None
        if "X-External-Calls" in response.headers:
            try:
                external_api_calls = int(response.headers["X-External-Calls"])
            except BaseException:
                pass

        # 에러 정보
        error_details = None
        if error_occurred and hasattr(response, "body"):
            try:
                error_details = {
                    "status_code": status_code,
                    "error_category": self._categorize_error(status_code),
                    "endpoint": endpoint,
                    "method": method,
                }
            except BaseException:
                pass

        # 비즈니스 메트릭 계산
        business_metrics = self._calculate_business_metrics(
            endpoint, method, duration_ms, status_code, user_id
        )

        await production_logger.log_api_response_detailed(
            request_id=request_id,
            trace_id=trace_id,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=duration_ms,
            response_size=response_size,
            cache_hit=cache_hit,
            database_queries=database_queries,
            external_api_calls=external_api_calls,
            error_details=error_details,
            business_metrics=business_metrics,
        )

    def _categorize_error(self, status_code: int) -> str:
        """에러 카테고리 분류"""
        if 400 <= status_code < 500:
            if status_code == 401:
                return "authentication_error"
            elif status_code == 403:
                return "authorization_error"
            elif status_code == 404:
                return "not_found_error"
            elif status_code == 429:
                return "rate_limit_error"
            else:
                return "client_error"
        elif 500 <= status_code < 600:
            if status_code == 503:
                return "service_unavailable"
            elif status_code == 504:
                return "timeout_error"
            else:
                return "server_error"
        else:
            return "unknown_error"

    def _calculate_business_metrics(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int,
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        """비즈니스 메트릭 계산"""

        metrics = {
            "success": status_code < 400,
            "performance_category": self._categorize_performance(duration_ms),
            "user_type": "authenticated" if user_id else "anonymous",
        }

        # AI 생성 API 특별 처리
        if any(
            ai_endpoint in endpoint for ai_endpoint in [
                "/generate",
                "/complete"]):
            metrics.update(
                {
                    "revenue_generating": True,
                    "ai_api_usage": True,
                    "performance_critical": True,
                }
            )

        # 인증 API 특별 처리
        elif any(auth_endpoint in endpoint for auth_endpoint in ["/auth", "/login"]):
            metrics.update(
                {
                    "security_event": True,
                    "user_acquisition": status_code == 201,  # 신규 가입
                    "user_retention": status_code == 200,  # 기존 로그인
                }
            )

        return metrics

    def _categorize_performance(self, duration_ms: float) -> str:
        """성능 카테고리 분류"""
        if duration_ms < 100:
            return "excellent"
        elif duration_ms < 500:
            return "good"
        elif duration_ms < 1000:
            return "acceptable"
        elif duration_ms < 3000:
            return "slow"
        else:
            return "very_slow"

    def _update_performance_metrics(
        self, endpoint: str, duration_ms: float, status_code: int
    ):
        """성능 메트릭 업데이트"""
        if endpoint not in self.performance_tracker:
            self.performance_tracker[endpoint] = {
                "total_requests": 0,
                "total_duration": 0,
                "error_count": 0,
                "last_updated": time.time(),
            }

        tracker = self.performance_tracker[endpoint]
        tracker["total_requests"] += 1
        tracker["total_duration"] += duration_ms
        tracker["last_updated"] = time.time()

        if status_code >= 400:
            tracker["error_count"] += 1

    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보 반환"""
        summary = {}

        for endpoint, tracker in self.performance_tracker.items():
            if tracker["total_requests"] > 0:
                summary[endpoint] = {
                    "avg_response_time_ms": tracker["total_duration"] /
                    tracker["total_requests"],
                    "total_requests": tracker["total_requests"],
                    "error_rate": tracker["error_count"] /
                    tracker["total_requests"],
                    "last_activity": tracker["last_updated"],
                }

        return summary
