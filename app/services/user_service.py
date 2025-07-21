import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class UserService:
    """DB Module과 통신하여 사용자 관리를 담당하는 서비스"""

    def __init__(self):
        self.db_module_url = settings.DB_MODULE_URL
        self.timeout = httpx.Timeout(10.0)

    async def login_or_register(
        self, email: str, username: str = None
    ) -> Optional[Dict[str, Any]]:
        """사용자 로그인 또는 자동 회원가입"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.db_module_url}/login",
                    json={"email": email, "username": username or email.split("@")[0]},
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"사용자 로그인 성공: {email}")
                    return data
                else:
                    logger.error(
                        f"사용자 로그인 실패: {response.status_code} - {response.text}"
                    )
                    return None

        except httpx.RequestError as e:
            logger.error(f"DB Module 연결 실패: {e}")
            return None

    async def get_user_settings(
        self, access_token: str
    ) -> Optional[List[Dict[str, Any]]]:
        """사용자 개인화 설정 조회"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.db_module_url}/settings/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info("사용자 설정 조회 성공")
                    return data
                else:
                    logger.error(f"사용자 설정 조회 실패: {response.status_code}")
                    return None

        except httpx.RequestError as e:
            logger.error(f"사용자 설정 조회 중 오류: {e}")
            return None

    async def update_user_settings(
        self, access_token: str, option_ids: List[int]
    ) -> bool:
        """사용자 설정 업데이트"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.db_module_url}/users/me/settings",
                    json={"option_ids": option_ids},
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code == 204:
                    logger.info("사용자 설정 업데이트 성공")
                    return True
                else:
                    logger.error(f"사용자 설정 업데이트 실패: {response.status_code}")
                    return False

        except httpx.RequestError as e:
            logger.error(f"사용자 설정 업데이트 중 오류: {e}")
            return False

    async def get_setting_options(
        self, access_token: str
    ) -> Optional[List[Dict[str, Any]]]:
        """전체 설정 옵션 조회"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.db_module_url}/settings/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info("설정 옵션 조회 성공")
                    return data
                else:
                    logger.error(f"설정 옵션 조회 실패: {response.status_code}")
                    return None

        except httpx.RequestError as e:
            logger.error(f"설정 옵션 조회 중 오류: {e}")
            return None

    async def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """현재 사용자 정보 조회"""
        try:
            logger.info(f"🔍 Backend → DB Module 사용자 정보 조회 시작")
            logger.info(f"🔍 DB_MODULE_URL: {self.db_module_url}")
            logger.info(f"🔍 Access Token 길이: {len(access_token)}")
            logger.info(f"🔍 Access Token prefix: {access_token[:50]}...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.db_module_url}/users/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                logger.info(f"🔍 DB Module 응답 상태코드: {response.status_code}")
                logger.info(f"🔍 DB Module 응답 헤더: {dict(response.headers)}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info("✅ 사용자 정보 조회 성공")
                    logger.info(f"🔍 응답 데이터: {data}")
                    return data
                else:
                    logger.error(f"❌ 사용자 정보 조회 실패: {response.status_code}")
                    logger.error(f"❌ 응답 본문: {response.text}")
                    logger.error(f"❌ 요청 URL: {self.db_module_url}/users/me")
                    logger.error(f"❌ Authorization 헤더: Bearer {access_token[:20]}...")
                    
                    # HTTP 상태코드별 상세 디버깅
                    if response.status_code == 401:
                        logger.error("❌ 401 Unauthorized - JWT 토큰 검증 실패")
                        logger.error("❌ 가능한 원인:")
                        logger.error("   - JWT 토큰이 만료됨")
                        logger.error("   - JWT SECRET_KEY 불일치")
                        logger.error("   - 토큰 형식 오류")
                        logger.error("   - 사용자가 데이터베이스에 존재하지 않음")
                    elif response.status_code == 422:
                        logger.error("❌ 422 Validation Error - 요청 형식 오류")
                    elif response.status_code == 500:
                        logger.error("❌ 500 Internal Server Error - DB Module 내부 오류")
                    
                    return None

        except httpx.RequestError as e:
            logger.error(f"❌ 사용자 정보 조회 중 네트워크 오류: {e}")
            logger.error(f"❌ 오류 타입: {type(e).__name__}")
            return None

    async def save_user_profile(
        self, access_token: str, profile_data: Dict[str, Any], option_ids: List[int]
    ) -> bool:
        """VSCode Extension 온보딩 데이터를 사용자 설정으로 저장"""
        try:
            # 1. 기존 설정 업데이트 (설정 옵션 ID 기반)
            settings_success = await self.update_user_settings(access_token, option_ids)

            if settings_success:
                logger.info(
                    f"사용자 프로필 저장 성공: {len(option_ids)}개 설정 저장",
                    extra={"profile_data": profile_data},
                )
                return True
            else:
                logger.error("사용자 설정 저장 실패")
                return False

        except Exception as e:
            logger.error(f"사용자 프로필 저장 중 오류: {e}")
            return False


# 싱글톤 인스턴스
user_service = UserService()
