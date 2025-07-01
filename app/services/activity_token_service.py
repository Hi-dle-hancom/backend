"""
활동기반 토큰 관리 서비스
Backend에서 DB Module의 활동기반 인증과 연동하는 서비스입니다.
"""

import asyncio
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.structured_logger import log_system_event


class ActivityTokenService:
    """활동기반 토큰 관리 서비스"""

    def __init__(self):
        self.db_module_url = settings.DB_MODULE_URL
        self.timeout = settings.DB_MODULE_TIMEOUT

    async def verify_activity_token(self, token: str) -> Optional[Dict[str, Any]]:
        """활동기반 토큰 검증"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.db_module_url}/api/v1/activity-auth/verify",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                log_system_event(
                    "활동기반 토큰 검증 실패",
                    "warning",
                    details={
                        "status_code": response.status_code,
                        "token": token[:20] + "...",
                    },
                )
                return None

        except Exception as e:
            log_system_event(
                "활동기반 토큰 검증 오류", "error", details={"error": str(e)}
            )
            return None

    async def refresh_activity_token(self, token: str) -> Optional[Dict[str, Any]]:
        """활동기반 토큰 갱신"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.db_module_url}/api/v1/activity-auth/refresh",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                log_system_event(
                    "활동기반 토큰 갱신 실패",
                    "warning",
                    details={
                        "status_code": response.status_code,
                        "token": token[:20] + "...",
                    },
                )
                return None

        except Exception as e:
            log_system_event(
                "활동기반 토큰 갱신 오류", "error", details={"error": str(e)}
            )
            return None

    async def logout_activity_session(self, token: str) -> bool:
        """활동기반 세션 로그아웃"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.db_module_url}/api/v1/activity-auth/logout",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.timeout,
                )

            return response.status_code == 200

        except Exception as e:
            log_system_event(
                "활동기반 로그아웃 오류", "error", details={"error": str(e)}
            )
            return False

    async def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 통계 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.db_module_url}/api/v1/activity-auth/session-stats/{session_id}",
                    timeout=self.timeout,
                )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            log_system_event("세션 통계 조회 오류", "error", details={"error": str(e)})
            return None

    async def auto_refresh_if_needed(self, token: str) -> Optional[str]:
        """필요한 경우 자동으로 토큰 갱신"""
        verification = await self.verify_activity_token(token)

        if not verification:
            return None

        if verification.get("needs_refresh", False):
            log_system_event(
                "토큰 자동 갱신 시작", "info", details={
                    "time_remaining": verification.get(
                        "time_remaining", 0)}, )

            refresh_result = await self.refresh_activity_token(token)
            if refresh_result:
                new_token = refresh_result.get(
                    "token_info", {}).get("access_token")
                log_system_event(
                    "토큰 자동 갱신 성공",
                    "info",
                    details={
                        "new_token": new_token[:20] + "..." if new_token else "None"
                    },
                )
                return new_token

        return token  # 갱신이 필요하지 않거나 실패한 경우 기존 토큰 반환

    async def refresh_token_background(self, token: str):
        """백그라운드에서 토큰 갱신 (비동기 처리)"""
        try:
            await asyncio.sleep(1)  # 1초 후 갱신 시도
            await self.refresh_activity_token(token)
        except Exception as e:
            log_system_event(
                "백그라운드 토큰 갱신 실패", "error", details={"error": str(e)}
            )


# 전역 인스턴스
activity_token_service = ActivityTokenService()
