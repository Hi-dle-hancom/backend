import httpx
import logging
from typing import Optional, List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class UserService:
    """DB Module과 통신하여 사용자 관리를 담당하는 서비스"""
    
    def __init__(self):
        self.db_module_url = settings.DB_MODULE_URL
        self.timeout = httpx.Timeout(10.0)
        
    async def login_or_register(self, email: str, username: str = None) -> Optional[Dict[str, Any]]:
        """사용자 로그인 또는 자동 회원가입"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.db_module_url}/login",
                    json={
                        "email": email,
                        "username": username or email.split("@")[0]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"사용자 로그인 성공: {email}")
                    return data
                else:
                    logger.error(f"사용자 로그인 실패: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.RequestError as e:
            logger.error(f"DB Module 연결 실패: {e}")
            return None
    
    async def get_user_settings(self, access_token: str) -> Optional[List[Dict[str, Any]]]:
        """사용자 개인화 설정 조회"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.db_module_url}/users/me/settings",
                    headers={"Authorization": f"Bearer {access_token}"}
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
    
    async def update_user_settings(self, access_token: str, option_ids: List[int]) -> bool:
        """사용자 설정 업데이트"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.db_module_url}/users/me/settings",
                    json={"option_ids": option_ids},
                    headers={"Authorization": f"Bearer {access_token}"}
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
    
    async def get_setting_options(self, access_token: str) -> Optional[List[Dict[str, Any]]]:
        """전체 설정 옵션 조회"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.db_module_url}/settings/options",
                    headers={"Authorization": f"Bearer {access_token}"}
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.db_module_url}/users/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info("사용자 정보 조회 성공")
                    return data
                else:
                    logger.error(f"사용자 정보 조회 실패: {response.status_code}")
                    return None
                    
        except httpx.RequestError as e:
            logger.error(f"사용자 정보 조회 중 오류: {e}")
            return None

# 싱글톤 인스턴스
user_service = UserService() 