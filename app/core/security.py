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
from app.services.user_service import UserService

# 보안 설정
security_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

logger = StructuredLogger("security")

# 🔐 JWT 보안 설정 초기화 및 검증
def validate_jwt_configuration():
    """Backend의 JWT 설정을 검증하고 로그에 출력"""
    jwt_key = settings.JWT_SECRET_KEY
    environment = settings.ENVIRONMENT
    
    logger.info(f"🔐 Backend JWT 설정 초기화")
    logger.info(f"🔍 환경: {environment}")
    logger.info(f"🔍 JWT_SECRET_KEY 길이: {len(jwt_key)}")
    try:
        safe_key_prefix = jwt_key[:20].encode('ascii', 'replace').decode('ascii')
        logger.info(f"🔍 JWT_SECRET_KEY prefix: {safe_key_prefix}...")
    except Exception:
        logger.info("🔍 JWT_SECRET_KEY prefix: [인코딩 문제로 생략]")
            
    if environment == "production" and len(jwt_key) < 32:
        logger.error(f"🚨 [PRODUCTION] JWT_SECRET_KEY가 너무 짧습니다! 현재: {len(jwt_key)}자, 최소: 32자")
        raise ValueError(f"Production 환경에서 JWT_SECRET_KEY는 최소 32자 이상이어야 합니다.")
    
    if jwt_key == "HAPA_UNIFIED_SECRET_KEY_FOR_DEVELOPMENT_ONLY_CHANGE_IN_PRODUCTION_32CHARS":
        if environment == "production":
            logger.error("🚨 [PRODUCTION] 기본 개발용 JWT_SECRET_KEY를 사용 중입니다!")
            raise ValueError("Production 환경에서는 고유한 JWT_SECRET_KEY를 사용해야 합니다.")
        else:
            logger.warning("⚠️ [DEVELOPMENT] 기본 개발용 JWT_SECRET_KEY 사용 중")
    
    logger.info("✅ Backend JWT 설정 검증 완료")

# JWT 설정 검증 실행
try:
    validate_jwt_configuration()
except Exception as e:
    logger.error(f"❌ Backend JWT 설정 검증 실패: {e}")
    if settings.ENVIRONMENT == "production":
        raise

# 토큰 블랙리스트 서비스 통합
try:
    from app.services.token_blacklist_service import token_blacklist_service

    BLACKLIST_ENABLED = True
except ImportError:
    import logging
    logging.getLogger(__name__).warning("토큰 블랙리스트 서비스를 찾을 수 없습니다. 기본 보안 기능으로 작동합니다.")
    BLACKLIST_ENABLED = False


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
        # 통일된 데이터 경로 사용 (프로젝트 루트 기준)
        self.data_dir = Path(settings.get_absolute_data_dir)
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
        """✅ 완전 개선: 하드코딩 없는 동적 사용자 인증 시스템"""
        # 모든 하드코딩 제거 - API 키는 실제 사용자 요청 시에만 동적 생성
        if settings.DYNAMIC_USER_AUTH_ENABLED:
            logger.info("🔒 동적 DB 기반 사용자 인증 시스템 활성화")
            logger.info("📝 API 키는 실제 사용자 로그인/등록 시 동적으로 생성됩니다")
        else:
            logger.warning("⚠️ 동적 사용자 인증이 비활성화되어 있습니다")

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

    async def generate_api_key_for_db_user(self, email: str, username: str = None) -> Optional[str]:
        """✅ 신규: 실제 DB 사용자를 위한 API 키 생성"""
        try:
            user_service = UserService()
            
            # DB에서 사용자 확인 또는 생성
            user_data = await user_service.login_or_register(email, username)
            
            if user_data:
                logger.info(f"DB 사용자 확인 완료: {email}")
                
                # 새로운 API 키 생성
                api_key = self.generate_api_key(
                    user_id=email,
                    permissions=[
                        "code_generation",
                        "code_completion", 
                        "feedback",
                        "history"
                    ]
                )
                
                logger.info(f"실제 DB 사용자용 API 키 생성 완료: {email}")
                return api_key
            else:
                logger.error(f"DB 사용자 생성/확인 실패: {email}")
                return None
                
        except Exception as e:
            logger.error(f"DB 사용자용 API 키 생성 오류: {e}")
            return None

    async def get_user_api_key_by_email(self, email: str, username: str = None) -> Optional[str]:
        """✅ 완전 개선: 이메일 기반 동적 API 키 조회/생성 (하드코딩 없음)"""
        if not settings.DYNAMIC_USER_AUTH_ENABLED:
            logger.warning("동적 사용자 인증이 비활성화되어 있습니다")
            return None
            
        try:
            # 기존 API 키 검색
            for api_key, api_key_model in self._api_keys.items():
                if api_key_model.user_id == email:
                    if api_key_model.is_active and (
                        not api_key_model.expires_at or 
                        api_key_model.expires_at > datetime.now()
                    ):
                        try:
                            safe_api_key_prefix = api_key[:20].encode('ascii', 'replace').decode('ascii')
                            logger.info(f"기존 사용자 API 키 사용: {email} - {safe_api_key_prefix}...")
                        except Exception:
                            logger.info(f"기존 사용자 API 키 사용: {email} - [인코딩 문제로 생략]...")
                        return api_key
            
            # 새로운 API 키 생성 (실제 DB 사용자 확인 후)
            logger.info(f"새 사용자 API 키 생성 시작: {email}")
            return await self.generate_api_key_for_db_user(email, username)
            
        except Exception as e:
            logger.error(f"사용자 API 키 조회/생성 오류: {e}")
            return None

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
def get_api_key_manager():
    """API Key Manager 인스턴스 반환 (lazy loading)"""
    if not hasattr(get_api_key_manager, '_instance'):
        get_api_key_manager._instance = APIKeyManager()
    return get_api_key_manager._instance

# 전역 API Key Manager 인스턴스
api_key_manager = get_api_key_manager()


async def verify_jwt_token_with_db(jwt_token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 토큰을 DB 모듈에 전달하여 검증
    🔐 디버깅: Backend와 DB Module의 JWT 키 동기화 확인
    """
    try:
        # 🔍 디버깅: Backend JWT 설정 로그
        logger.info(f"🔍 Backend JWT 검증 시작")
        logger.info(f"🔍 Backend JWT_SECRET_KEY 길이: {len(settings.JWT_SECRET_KEY)}")
        try:
            safe_secret_prefix = settings.JWT_SECRET_KEY[:20].encode('ascii', 'replace').decode('ascii')
            logger.info(f"🔍 Backend JWT_SECRET_KEY prefix: {safe_secret_prefix}...")
        except Exception:
            logger.info("🔍 Backend JWT_SECRET_KEY prefix: [인코딩 문제로 생략]")

        logger.info(f"🔍 검증할 토큰 길이: {len(jwt_token)}")
        try:
            safe_token_prefix = jwt_token[:50].encode('ascii', 'replace').decode('ascii')
            logger.info(f"🔍 검증할 토큰 prefix: {safe_token_prefix}...")
        except Exception:
            logger.info("🔍 검증할 토큰 prefix: [인코딩 문제로 생략]")
        
        user_service = UserService()
        user_info = await user_service.get_user_info(jwt_token)
        
        if user_info:
            logger.info(f"✅ Backend JWT 토큰 검증 성공: {user_info.get('email', 'unknown')}")
            return user_info
        else:
            logger.error("❌ Backend JWT 토큰 검증 실패: DB Module에서 거부")
            logger.error("❌ 가능한 원인:")
            logger.error("   - Backend와 DB Module의 JWT_SECRET_KEY 불일치")
            logger.error("   - 토큰 만료")
            logger.error("   - 사용자가 DB에 존재하지 않음")
            logger.error("   - DB Module 서비스 오류")
            return None
            
    except Exception as e:
        try:
            safe_error_message = str(e).encode('ascii', 'replace').decode('ascii')
            logger.error(f"❌ Backend JWT 토큰 검증 중 예외 발생: {safe_error_message}")
        except Exception:
            logger.error("❌ Backend JWT 토큰 검증 중 예외 발생: [인코딩 문제로 메시지 생략]")
        
        try:
            safe_exception_type = type(e).__name__.encode('ascii', 'replace').decode('ascii')
            logger.error(f"❌ 예외 타입: {safe_exception_type}")
        except Exception:
            logger.error("❌ 예외 타입: [인코딩 문제로 생략]")
            
        return None


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

    # JWT 토큰인 경우 DB 모듈에서 검증
    if is_jwt_token:
        # JWT 토큰 블랙리스트 확인
        if BLACKLIST_ENABLED:
            try:
                is_blacklisted = await token_blacklist_service.is_blacklisted(api_key)
                if is_blacklisted:
                    try:
                        safe_api_key_prefix = api_key[:20].encode('ascii', 'replace').decode('ascii')
                        logger.warning(f"블랙리스트된 토큰 접근 시도: {safe_api_key_prefix}...")
                    except Exception:
                        logger.warning("블랙리스트된 토큰 접근 시도: [인코딩 문제로 토큰 생략]...")
                    raise HTTPException(
                        status_code=401,
                        detail="토큰이 무효화되었습니다 (로그아웃됨)",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"토큰 블랙리스트 확인 실패: {e}")

        # DB 모듈에서 JWT 토큰 검증
        user_info = await verify_jwt_token_with_db(api_key)
        
        # JWT 토큰용 가상 APIKeyModel 생성
        return APIKeyModel(
            api_key=api_key,
            user_id=user_info.get('email', 'unknown'),
            permissions=['code_generation', 'feedback', 'history'],
            created_at=datetime.now(),
            is_active=True,
            usage_count=0
        )
    else:
        # 기존 API Key 검증 로직
        api_key_model = api_key_manager.validate_api_key(api_key)
        if not api_key_model:
            raise HTTPException(
                status_code=401, detail="유효하지 않거나 만료된 API Key입니다."
            )
        return api_key_model


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


async def get_current_user_from_jwt(
    bearer_token: HTTPAuthorizationCredentials = Depends(security_bearer),
) -> Dict[str, Any]:
    """
    JWT 토큰에서 사용자 정보 조회 (개인화 설정용)
    """
    if not bearer_token or bearer_token.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="JWT Bearer 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        safe_token_info = f"Bearer token scheme: {bearer_token.scheme}, length: {len(bearer_token.credentials)}"
        print("bearer_token", safe_token_info)
    except Exception:
        print("bearer_token", "[인코딩 문제로 토큰 정보 생략]")

    jwt_token = bearer_token.credentials
    
    # 블랙리스트 확인
    if BLACKLIST_ENABLED:
        try:
            is_blacklisted = await token_blacklist_service.is_blacklisted(jwt_token)
            if is_blacklisted:
                raise HTTPException(
                    status_code=401,
                    detail="토큰이 무효화되었습니다 (로그아웃됨)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception as e:
            logger.error(f"토큰 블랙리스트 확인 실패: {e}")
    
    # DB 모듈에서 사용자 정보 조회
    user_info = await verify_jwt_token_with_db(jwt_token)
    if not user_info:
        raise HTTPException(
            status_code=401, 
            detail="유효하지 않거나 만료된 JWT 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user_info


class JWTUserInfo(BaseModel):
    """JWT 토큰 기반 사용자 정보"""
    user_info: Dict[str, Any]
    jwt_token: str
    email: str
    user_id: int


async def get_current_user_with_token(
    bearer_token: HTTPAuthorizationCredentials = Depends(security_bearer),
) -> JWTUserInfo:
    """
    JWT 토큰과 사용자 정보를 함께 반환 (DB 호출용)
    """
    if not bearer_token or bearer_token.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="JWT Bearer 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    jwt_token = bearer_token.credentials
    
    # 블랙리스트 확인
    if BLACKLIST_ENABLED:
        try:
            is_blacklisted = await token_blacklist_service.is_blacklisted(jwt_token)
            if is_blacklisted:
                raise HTTPException(
                    status_code=401,
                    detail="토큰이 무효화되었습니다 (로그아웃됨)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception as e:
            logger.error(f"토큰 블랙리스트 확인 실패: {e}")
    
    # DB 모듈에서 사용자 정보 조회
    user_info = await verify_jwt_token_with_db(jwt_token)
    if not user_info:
        raise HTTPException(
            status_code=401, 
            detail="유효하지 않거나 만료된 JWT 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return JWTUserInfo(
        user_info=user_info,
        jwt_token=jwt_token,
        email=user_info.get('email', ''),
        user_id=user_info.get('id', 0)
    )


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
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit 초과: {endpoint} 엔드포인트는 {settings.RATE_LIMIT_WINDOW_MINUTES}분당 {limit}회까지 요청 가능합니다.",
            )
        return api_key

    return rate_limit_checker


# ✅ 완전 제거: create_demo_api_key 함수 삭제됨 (하드코딩 제거)


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
