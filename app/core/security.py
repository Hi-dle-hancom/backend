import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import StructuredLogger

import logging
from app.services.token_blacklist_service import token_blacklist_service

# 토큰 블랙리스트 서비스 통합
try:
    from app.services.token_blacklist_service import token_blacklist_service

    BLACKLIST_ENABLED = True
except ImportError:
    import logging
    logging.getLogger(__name__).warning("토큰 블랙리스트 서비스를 찾을 수 없습니다. 기본 보안 기능으로 작동합니다.")
    BLACKLIST_ENABLED = False

# 보안 설정
security_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

logger = StructuredLogger("security")


class APIKeyModel(BaseModel):
    """API Key 모델"""

    api_key: str
    user_id: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True
    usage_count: int = 0
    last_used: Optional[datetime] = None


class APIKeyManager:
    """API Key 관리 클래스"""

    def __init__(self):
        # 환경변수에서 데이터 경로 읽기
        self.data_dir = Path("data")
        self.api_keys_file = self.data_dir / "api_keys.json"
        self.rate_limits_file = self.data_dir / "rate_limits.json"

        # 데이터 디렉토리 생성
        self.data_dir.mkdir(exist_ok=True)

        self._api_keys = {}
        self._rate_limits = {}
        self._load_api_keys()
        self._load_rate_limits()

    def _load_api_keys(self):
        """API Key 데이터 로드"""
        try:
            if self.api_keys_file.exists():
                with open(self.api_keys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        value["created_at"] = datetime.fromisoformat(
                            value["created_at"]
                        )
                        if value.get("expires_at"):
                            value["expires_at"] = datetime.fromisoformat(
                                value["expires_at"]
                            )
                        if value.get("last_used"):
                            value["last_used"] = datetime.fromisoformat(
                                value["last_used"]
                            )
                        self._api_keys[key] = APIKeyModel(**value)
            else:
                # 초기 데이터 생성
                self._create_initial_data()
        except Exception as e:
            logger.error(f"API Key 데이터 로드 실패: {e}")
            self._create_initial_data()

    def _create_initial_data(self):
        """초기 데이터 생성"""
        if settings.ENABLE_DEMO_API_KEY:
            # 환경변수에서 데모 키 읽기
            demo_key = getattr(
                settings,
                "DEMO_API_KEY",
                "hapa_demo_20241228_secure_key_for_testing")

            demo_api_key = APIKeyModel(
                api_key=demo_key,
                user_id=settings.DEMO_USER_ID,
                permissions=[
                    "code_generation",
                    "code_completion",
                    "feedback",
                    "history",
                    "admin",
                ],
                created_at=datetime.now(),
                expires_at=datetime.now()
                + timedelta(days=settings.API_KEY_EXPIRY_DAYS),
                is_active=True,
            )
            self._api_keys[demo_key] = demo_api_key
            self._save_api_keys()

    def _save_api_keys(self):
        """API Key 데이터 저장"""
        try:
            data = {}
            for key, api_key_model in self._api_keys.items():
                data[key] = {
                    "api_key": api_key_model.api_key,
                    "user_id": api_key_model.user_id,
                    "permissions": api_key_model.permissions,
                    "created_at": api_key_model.created_at.isoformat(),
                    "expires_at": (
                        api_key_model.expires_at.isoformat()
                        if api_key_model.expires_at
                        else None
                    ),
                    "is_active": api_key_model.is_active,
                    "usage_count": api_key_model.usage_count,
                    "last_used": (
                        api_key_model.last_used.isoformat()
                        if api_key_model.last_used
                        else None
                    ),
                }

            with open(self.api_keys_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"API Key 데이터 저장 실패: {e}")

    def _load_rate_limits(self):
        """Rate Limit 데이터 로드"""
        try:
            if self.rate_limits_file.exists():
                with open(self.rate_limits_file, "r", encoding="utf-8") as f:
                    self._rate_limits = json.load(f)
        except Exception as e:
            logger.error(f"Rate Limit 데이터 로드 실패: {e}")
            self._rate_limits = {}

    def _save_rate_limits(self):
        """Rate Limit 데이터 저장"""
        try:
            with open(self.rate_limits_file, "w", encoding="utf-8") as f:
                json.dump(self._rate_limits, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Rate Limit 데이터 저장 실패: {e}")

    def validate_api_key(self, api_key: str) -> Optional[APIKeyModel]:
        """API Key 유효성 검사"""
        if not api_key:
            return None

        api_key_model = self._api_keys.get(api_key)
        if not api_key_model:
            return None

        # 활성 상태 확인
        if not api_key_model.is_active:
            return None

        # 만료일 확인
        if api_key_model.expires_at and api_key_model.expires_at < datetime.now():
            return None

        # 사용 기록 업데이트
        api_key_model.usage_count += 1
        api_key_model.last_used = datetime.now()
        self._save_api_keys()

        return api_key_model

    def generate_api_key(self, user_id: str, permissions: List[str]) -> str:
        """새로운 API Key 생성"""
        # 보안성 강화된 키 생성
        random_part = secrets.token_hex(16)
        api_key = f"hapa_{random_part}"

        api_key_model = APIKeyModel(
            api_key=api_key,
            user_id=user_id,
            permissions=permissions,
            created_at=datetime.now(),
            expires_at=datetime.now() +
            timedelta(
                days=settings.API_KEY_EXPIRY_DAYS),
            is_active=True,
        )

        self._api_keys[api_key] = api_key_model
        self._save_api_keys()

        logger.info(f"새로운 API Key 생성 완료", user_id=user_id)
        return api_key

    def check_rate_limit(
            self,
            api_key: str,
            endpoint: str,
            limit: int) -> bool:
        """Rate Limit 확인"""
        if not settings.RATE_LIMIT_ENABLED:
            return True

        now = time.time()
        window_start = now - (settings.RATE_LIMIT_WINDOW_MINUTES * 60)

        # 키 생성
        rate_key = f"{api_key}:{endpoint}"

        # 기존 요청 기록 확인
        if rate_key not in self._rate_limits:
            self._rate_limits[rate_key] = []

        # 윈도우 밖의 요청 제거
        self._rate_limits[rate_key] = [
            req_time
            for req_time in self._rate_limits[rate_key]
            if req_time > window_start
        ]

        # 현재 요청 수 확인
        current_requests = len(self._rate_limits[rate_key])

        if current_requests >= limit:
            return False

        # 새 요청 기록
        self._rate_limits[rate_key].append(now)
        self._save_rate_limits()

        return True


# 전역 인스턴스
api_key_manager = APIKeyManager()


async def get_current_api_key(
    api_key_header: Optional[str] = Depends(api_key_header),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> APIKeyModel:
    """
    보안 강화된 API Key 또는 Bearer Token 인증 처리
    JWT 토큰 블랙리스트 확인 추가
    """

    # Header에서 API Key 추출
    api_key = None
    is_jwt_token = False

    if api_key_header:
        api_key = api_key_header
    elif bearer_token and bearer_token.scheme.lower() == "bearer":
        api_key = bearer_token.credentials
        is_jwt_token = True

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key가 필요합니다. X-API-Key 헤더 또는 Authorization Bearer 토큰을 제공해주세요.",
        )

    # JWT 토큰인 경우 블랙리스트 확인
    if is_jwt_token and BLACKLIST_ENABLED:
        try:
            is_blacklisted = await token_blacklist_service.is_blacklisted(api_key)
            if is_blacklisted:
                logger.warning(f"블랙리스트된 토큰 접근 시도: {api_key[:20]}...")
                raise HTTPException(
                    status_code=401,
                    detail="토큰이 무효화되었습니다 (로그아웃됨)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception as e:
            logger.error(f"토큰 블랙리스트 확인 실패: {e}")

    # API Key 유효성 검사
    api_key_model = api_key_manager.validate_api_key(api_key)
    if not api_key_model:
        raise HTTPException(
            status_code=401, detail="유효하지 않거나 만료된 API Key입니다."
        )

    return api_key_model


def check_permission(required_permission: str):
    """권한 확인 의존성"""

    async def permission_checker(
        api_key: APIKeyModel = Depends(get_current_api_key),
    ) -> APIKeyModel:
        if required_permission not in api_key.permissions:
            raise HTTPException(
                status_code=403, detail=f"'{required_permission}' 권한이 필요합니다."
            )
        return api_key

    return permission_checker


def check_rate_limit_dependency(endpoint: str, limit: int):
    """Rate Limit 확인 의존성"""

    async def rate_limit_checker(
        api_key: APIKeyModel = Depends(get_current_api_key),
    ) -> APIKeyModel:
        if not api_key_manager.check_rate_limit(
                api_key.api_key, endpoint, limit):
            raise HTTPException(status_code=429, detail=f"Rate limit 초과: {endpoint} 엔드포인트는 {
                settings.RATE_LIMIT_WINDOW_MINUTES}분당 {limit}회까지 요청 가능합니다.", )
        return api_key

    return rate_limit_checker


def create_demo_api_key() -> Optional[Dict[str, Any]]:
    """데모 API Key 생성 (개발 환경용)"""
    if not settings.ENABLE_DEMO_API_KEY:
        return None

    # 환경변수에서 데모 키 읽기
    demo_key = getattr(settings, "DEMO_API_KEY", None)
    if not demo_key:
        return None

    return {
        "api_key": demo_key,
        "user_id": settings.DEMO_USER_ID,
        "permissions": [
            "code_generation",
            "code_completion",
            "feedback",
            "history"],
        "message": "개발 환경용 데모 API Key입니다.",
    }


# 보안 유틸리티 함수들
def hash_password(password: str) -> str:
    """비밀번호 해시화"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        100000)
    return f"{salt}:{hash_obj.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """비밀번호 검증"""
    try:
        salt, hash_hex = hashed.split(":")
        hash_obj = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100000
        )
        return hash_obj.hex() == hash_hex
    except ValueError:
        return False


def generate_csrf_token() -> str:
    """CSRF 토큰 생성"""
    return secrets.token_hex(32)


# code_generation.py에서 사용하는 함수들 추가
async def get_api_key(
    api_key_header: Optional[str] = Depends(api_key_header),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> str:
    """
    API Key 문자열만 반환하는 간단한 버전
    code_generation.py에서 호환성을 위해 추가
    """
    api_key_model = await get_current_api_key(api_key_header, bearer_token)
    return api_key_model.api_key


async def get_current_user(
    api_key_model: APIKeyModel = Depends(get_current_api_key),
) -> Dict[str, Any]:
    """
    현재 사용자 정보를 반환
    code_generation.py에서 호환성을 위해 추가
    """
    return {
        "user_id": api_key_model.user_id,
        "api_key": api_key_model.api_key,
        "permissions": api_key_model.permissions,
        "is_active": api_key_model.is_active,
        "usage_count": api_key_model.usage_count,
        "last_used": api_key_model.last_used,
    }


def verify_token(token: str) -> bool:
    """
    JWT 토큰 검증
    """
    try:
        if token_blacklist_service.is_blacklisted(token):
            logger.warning("블랙리스트에 등록된 토큰 접근 시도")
            return False
        
        # 토큰 검증 로직 (실제 구현 필요)
        return True
    except Exception as e:
        logger.warning("토큰 블랙리스트 서비스를 찾을 수 없습니다. 기본 보안 기능으로 작동합니다.")
        return True
