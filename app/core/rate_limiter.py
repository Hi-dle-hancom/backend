"""
API Rate Limiting 모듈
FastAPI와 함께 사용할 수 있는 속도 제한 데코레이터
"""

import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.structured_logger import StructuredLogger

logger = StructuredLogger("rate_limiter")


class RateLimiter:
    """
    메모리 기반 Rate Limiter
    API 엔드포인트별로 요청 수를 제한
    """

    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.enabled = getattr(settings, "RATE_LIMIT_ENABLED", True)
        self.default_limit = getattr(settings, "DEFAULT_RATE_LIMIT", 100)
        self.window_minutes = getattr(
            settings, "RATE_LIMIT_WINDOW_MINUTES", 60)

    def _get_client_id(self, request: Optional[Request] = None) -> str:
        """클라이언트 식별자 생성"""
        if request:
            # IP 주소 기반 식별
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()
            return request.client.host if request.client else "unknown"
        return "global"

    def _cleanup_old_requests(self, client_id: str, window_seconds: int):
        """윈도우 밖의 오래된 요청 제거"""
        now = time.time()
        cutoff = now - window_seconds

        while self.requests[client_id] and self.requests[client_id][0] < cutoff:
            self.requests[client_id].popleft()

    def is_allowed(
        self,
        rate_limit: str,
        client_id: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> bool:
        """
        요청이 허용되는지 확인

        Args:
            rate_limit: "10/minute", "100/hour" 형식의 제한
            client_id: 클라이언트 식별자 (없으면 자동 생성)
            request: FastAPI Request 객체
        """
        if not self.enabled:
            return True

        # rate_limit 파싱 (예: "10/minute")
        try:
            limit_str, period_str = rate_limit.split("/")
            limit = int(limit_str)

            # 시간 단위 변환
            if period_str == "minute":
                window_seconds = 60
            elif period_str == "hour":
                window_seconds = 3600
            elif period_str == "day":
                window_seconds = 86400
            else:
                window_seconds = 60  # 기본값

        except (ValueError, AttributeError):
            logger.warning(f"잘못된 rate_limit 형식: {rate_limit}")
            return True

        # 클라이언트 ID 결정
        if not client_id:
            client_id = self._get_client_id(request)

        # 오래된 요청 정리
        self._cleanup_old_requests(client_id, window_seconds)

        # 현재 요청 수 확인
        current_requests = len(self.requests[client_id])

        if current_requests >= limit:
            logger.warning(
                f"Rate limit 초과",
                extra={
                    "client_id": client_id,
                    "limit": limit,
                    "current_requests": current_requests,
                    "period": period_str,
                },
            )
            return False

        # 새 요청 기록
        self.requests[client_id].append(time.time())

        return True

    def limit(self, rate_limit: str):
        """
        Rate limiting 데코레이터

        사용 예:
        @limiter.limit("10/minute")
        async def my_endpoint():
            pass
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> Any:
                # FastAPI Request 객체 찾기
                request = None
                for arg in args:
                    if hasattr(arg, "client") and hasattr(arg, "headers"):
                        request = arg
                        break

                if not request:
                    # kwargs에서 request 찾기
                    request = kwargs.get("request")

                client_id = self._get_client_id(request)

                if not self.is_allowed(rate_limit, client_id, request):
                    # Rate limit 정보 파싱하여 에러 메시지 생성
                    try:
                        limit_str, period_str = rate_limit.split("/")
                        raise HTTPException(status_code=429, detail=f"Rate limit 초과: {
                            period_str}당 {limit_str}회까지 요청 가능합니다.", )
                    except ValueError:
                        raise HTTPException(
                            status_code=429, detail="Rate limit 초과")

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def get_stats(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """Rate limiting 통계 조회"""
        if client_id:
            return {
                "client_id": client_id,
                "current_requests": len(self.requests.get(client_id, [])),
                "enabled": self.enabled,
            }
        else:
            return {
                "total_clients": len(
                    self.requests),
                "total_requests": sum(
                    len(reqs) for reqs in self.requests.values()),
                "enabled": self.enabled,
                "default_limit": self.default_limit,
                "window_minutes": self.window_minutes,
            }

    def reset(self, client_id: Optional[str] = None):
        """Rate limit 리셋"""
        if client_id:
            if client_id in self.requests:
                del self.requests[client_id]
                logger.info(f"Rate limit 리셋: {client_id}")
        else:
            self.requests.clear()
            logger.info("모든 Rate limit 리셋")


# 전역 rate limiter 인스턴스
limiter = RateLimiter()
