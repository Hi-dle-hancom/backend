import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Header, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.users import UserLoginRequest, UserInfo, UserProfileRequest
from app.core.security import get_api_key, get_current_user_from_jwt, get_current_user_with_token, JWTUserInfo

router = APIRouter(prefix="/users", tags=["Users"])
security = HTTPBearer()
logger = logging.getLogger("users_api")


def log_user_action(action: str, user_id: str, details: Optional[Dict[str, Any]] = None):
    """사용자 액션 로깅"""
    logger.info(
        f"사용자 액션: {action}",
        extra={
            "user_id": user_id,
            "action": action,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
    )


# =============================================================================
# 누락된 스키마 정의들
# =============================================================================

class AuthResponse(BaseModel):
    """인증 응답 모델"""
    access_token: str
    token_type: str = "bearer"
    
class UserSettingsRequest(BaseModel):
    """사용자 설정 요청 모델"""
    option_ids: List[int]


# =============================================================================
# API 엔드포인트들
# =============================================================================

@router.post("/login", response_model=AuthResponse)
async def login_user(user_data: UserLoginRequest):
    """
    온보딩 사용자 로그인/등록
    이메일과 사용자명을 받아 DB Module에 전달하고 JWT 토큰을 반환합니다.
    """
    try:
        log_user_action(
            "로그인 요청", user_data.email, details={"username": user_data.username}
        )

        # DB Module에 로그인/등록 요청
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.DB_MODULE_URL}/login",
                json={"email": user_data.email, "username": user_data.username},
                timeout=settings.DB_MODULE_TIMEOUT,
            )

        if response.status_code == 200:
            auth_data = response.json()
            log_user_action(
                "로그인 성공",
                user_data.email,
                details={"token_type": auth_data.get("token_type")},
            )
            return AuthResponse(
                access_token=auth_data["access_token"],
                token_type=auth_data["token_type"],
            )
        else:
            log_user_action(
                "로그인 실패",
                user_data.email,
                details={"status_code": response.status_code},
            )
            raise HTTPException(
                status_code=response.status_code,
                detail="사용자 인증에 실패했습니다."
            )

    except httpx.TimeoutException:
        logger.error(f"DB Module 연결 타임아웃 - URL: {settings.DB_MODULE_URL}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="사용자 인증 서비스가 일시적으로 이용불가입니다.",
        )
    except Exception as e:
        logger.error(f"사용자 로그인 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다.",
        )


@router.post("/generate-api-key")
async def generate_api_key(
    user_data: UserLoginRequest,
):
    """
    사용자용 API 키 발급
    이메일 기반으로 새로운 API 키를 생성하고 반환합니다.
    """
    try:
        from app.core.security import api_key_manager
        
        # 사용자 검증을 위해 로그인 시도
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.DB_MODULE_URL}/login",
                json={"email": user_data.email, "username": user_data.username},
                timeout=settings.DB_MODULE_TIMEOUT,
            )

        if response.status_code == 200:
            # 새로운 API 키 생성
            api_key = api_key_manager.generate_api_key(
                user_id=user_data.email,
                permissions=[
                    "code_generation", 
                    "code_completion", 
                    "feedback", 
                    "history"
                ]
            )
            
            try:
                safe_api_key_prefix = api_key[:10].encode('ascii', 'replace').decode('ascii')
                api_key_prefix = safe_api_key_prefix
            except Exception:
                api_key_prefix = "[encoding_error]"

            log_user_action(
                "API 키 발급 성공",
                user_data.email,
                details={"api_key_prefix": api_key_prefix}  # ✅ 안전한 변수 사용
            )
            
            return {
                "api_key": api_key,
                "user_id": user_data.email,
                "permissions": ["code_generation", "code_completion", "feedback", "history"],
                "expires_in_days": settings.API_KEY_EXPIRY_DAYS,
                "message": "API 키가 성공적으로 발급되었습니다."
            }
        else:
            raise HTTPException(
                status_code=401, 
                detail="사용자 인증에 실패했습니다. 올바른 이메일을 입력해주세요."
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="사용자 인증 서비스가 일시적으로 이용불가입니다.",
        )
    except Exception as e:
        logger.error(f"API 키 발급 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API 키 발급 중 오류가 발생했습니다.",
        )


@router.get("/me")
async def get_my_profile(user_info: Dict[str, Any] = Depends(get_current_user_from_jwt)):
    """
    현재 사용자의 프로필 정보 조회 (JWT 토큰 기반)
    """
    try:
        log_user_action(
            "프로필 조회 성공", user_info.get("email", "unknown"), details={}
        )
        return user_info
    except Exception as e:
        logger.error(f"프로필 조회 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보 조회 중 오류가 발생했습니다.",
        )


@router.get("/settings")
async def get_user_settings(jwt_user: JWTUserInfo = Depends(get_current_user_with_token)):
    """
    현재 사용자의 설정 조회 (JWT 토큰 기반)
    """
    try:
        logger.info(f"사용자 설정 조회 시작: {jwt_user.email}")
        
        # UserService를 통해 DB 모듈에서 설정 조회
        from app.services.user_service import user_service
        
        settings_data = await user_service.get_user_settings(jwt_user.jwt_token)
        
        if settings_data is None:
            logger.warning(f"사용자 설정 조회 실패: {jwt_user.email}")
            # 빈 배열 반환 (새 사용자의 경우)
            settings_data = []
        
        log_user_action(
            "설정 조회 성공",
            jwt_user.email,
            details={"settings_count": len(settings_data)},
        )
        
        logger.info(f"사용자 설정 조회 완료: {jwt_user.email}, {len(settings_data)}개 설정")
        return settings_data

    except Exception as e:
        logger.error(f"설정 조회 중 예외 발생: {jwt_user.email} - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 조회 중 오류가 발생했습니다.",
        )


@router.post("/settings")
async def update_user_settings(
    settings_data: UserSettingsRequest,
    jwt_user: JWTUserInfo = Depends(get_current_user_with_token)
):
    """
    사용자 설정 업데이트 (JWT 토큰 기반)
    """
    try:
        logger.info(f"사용자 설정 업데이트 시작: {jwt_user.email}")
        
        # UserService를 통해 DB 모듈에 설정 업데이트
        from app.services.user_service import user_service
        
        success = await user_service.update_user_settings(
            jwt_user.jwt_token, 
            settings_data.option_ids
        )
        
        if not success:
            logger.error(f"설정 업데이트 실패: {jwt_user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="설정 업데이트에 실패했습니다."
            )
        
        log_user_action(
            "설정 업데이트 성공", 
            jwt_user.email, 
            details={"settings_count": len(settings_data.option_ids)}
        )
        
        logger.info(f"사용자 설정 업데이트 완료: {jwt_user.email}")
        return {"message": "설정이 성공적으로 업데이트되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"설정 업데이트 중 예외 발생: {jwt_user.email} - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 업데이트 중 오류가 발생했습니다.",
        )


# ✅ 완전 개선: 하드코딩된 온보딩 엔드포인트 제거
# 모든 사용자는 동적 로그인/등록을 통해 API 키 발급 받음
