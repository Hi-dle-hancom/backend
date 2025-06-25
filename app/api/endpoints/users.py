from fastapi import APIRouter, HTTPException, status, Header, Depends
from fastapi.security import HTTPBearer
import httpx
import json
from typing import List, Dict, Any, Optional
from app.services.user_service import user_service
from app.schemas.users import (
    UserLoginRequest, 
    UserTokenResponse, 
    UserSettingsRequest,
    UserProfileRequest,
    UserProfileResponse,
    AuthResponse
)
from app.core.logging_config import api_monitor
from app.core.config import settings
from app.core.structured_logger import log_api_request, log_api_response, log_user_action, log_system_event

router = APIRouter()
security = HTTPBearer()

@router.post("/login", response_model=AuthResponse)
async def login_user(user_data: UserLoginRequest):
    """
    온보딩 사용자 로그인/등록
    이메일과 사용자명을 받아 DB Module에 전달하고 JWT 토큰을 반환합니다.
    """
    try:
        log_user_action("로그인 요청", user_data.email, details={"username": user_data.username})
        
        # DB Module에 로그인/등록 요청
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.DB_MODULE_URL}/login",
                json={
                    "email": user_data.email,
                    "username": user_data.username
                },
                timeout=settings.DB_MODULE_TIMEOUT
            )
            
        if response.status_code == 200:
            auth_data = response.json()
            log_user_action("로그인 성공", user_data.email, details={"token_type": auth_data.get("token_type")})
            return AuthResponse(
                access_token=auth_data["access_token"],
                token_type=auth_data["token_type"]
            )
        else:
            log_user_action("로그인 실패", user_data.email, details={"status_code": response.status_code})
            raise HTTPException(
                status_code=response.status_code,
                detail="사용자 인증에 실패했습니다."
            )
            
    except httpx.TimeoutException:
        log_system_event("DB Module 연결 타임아웃", "failed", details={"url": settings.DB_MODULE_URL})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="사용자 인증 서비스가 일시적으로 이용불가합니다."
        )
    except Exception as e:
        log_system_event("사용자 로그인 오류", "error", details={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다."
        )

@router.get("/me/settings")
async def get_my_settings(authorization: str = Header(...)):
    """
    현재 사용자의 개인화 설정 조회
    Authorization 헤더에서 Bearer 토큰을 추출하여 DB Module에 전달합니다.
    """
    try:
        # Bearer 토큰에서 실제 토큰 추출
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="잘못된 인증 헤더 형식입니다."
            )
        
        access_token = authorization.split(" ")[1]
        
        settings = await user_service.get_user_settings(access_token)
        
        if settings is not None:
            api_monitor.logger.info("사용자 설정 조회 성공")
            return {"settings": settings}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자 설정을 찾을 수 없습니다."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(e, {"operation": "get_user_settings"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 조회 중 오류가 발생했습니다."
        )

@router.post("/me/settings")
async def update_my_settings(
    settings_data: UserSettingsRequest,
    authorization: str = Header(...)
):
    """
    사용자 개인화 설정 업데이트
    """
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="잘못된 인증 헤더 형식입니다."
            )
        
        access_token = authorization.split(" ")[1]
        
        success = await user_service.update_user_settings(
            access_token=access_token,
            option_ids=settings_data.option_ids
        )
        
        if success:
            api_monitor.logger.info("사용자 설정 업데이트 성공")
            return {"message": "설정이 성공적으로 업데이트되었습니다."}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="설정 업데이트에 실패했습니다."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(e, {"operation": "update_user_settings"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 업데이트 중 오류가 발생했습니다."
        )

@router.get("/me")
async def get_my_profile(authorization: str = Depends(security)):
    """
    현재 사용자의 프로필 정보 조회
    """
    try:
        token = authorization.credentials
        
        # DB Module에서 사용자 정보 조회
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.DB_MODULE_URL}/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=settings.DB_MODULE_TIMEOUT
            )
            
        if response.status_code == 200:
            user_data = response.json()
            log_user_action("프로필 조회 성공", user_data.get("email", "unknown"), details={})
            return user_data
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail="사용자 정보를 가져올 수 없습니다."
            )
            
    except httpx.TimeoutException:
        log_system_event("DB Module 연결 타임아웃", "failed", details={"url": settings.DB_MODULE_URL})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="사용자 정보 서비스가 일시적으로 이용불가합니다."
        )
    except Exception as e:
        log_system_event("프로필 조회 오류", "error", details={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보 조회 중 오류가 발생했습니다."
        )

@router.get("/settings")
async def get_user_settings(authorization: str = Depends(security)):
    """
    현재 사용자의 설정 조회
    """
    try:
        token = authorization.credentials
        
        # DB Module에서 사용자 설정 조회
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.DB_MODULE_URL}/users/me/settings",
                headers={"Authorization": f"Bearer {token}"},
                timeout=settings.DB_MODULE_TIMEOUT
            )
            
        if response.status_code == 200:
            settings_data = response.json()
            log_user_action("설정 조회 성공", "unknown", details={"settings_count": len(settings_data)})
            return settings_data
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail="사용자 설정을 가져올 수 없습니다."
            )
            
    except httpx.TimeoutException:
        log_system_event("DB Module 연결 타임아웃", "failed", details={"url": settings.DB_MODULE_URL})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="설정 조회 서비스가 일시적으로 이용불가합니다."
        )
    except Exception as e:
        log_system_event("설정 조회 오류", "error", details={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 조회 중 오류가 발생했습니다."
        )

@router.get("/settings/options")
async def get_setting_options(authorization: str = Header(...)):
    """
    전체 설정 옵션 조회
    """
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="잘못된 인증 헤더 형식입니다."
            )
        
        access_token = authorization.split(" ")[1]
        
        options = await user_service.get_setting_options(access_token)
        
        if options is not None:
            api_monitor.logger.info("설정 옵션 조회 성공")
            return {"options": options}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="설정 옵션을 찾을 수 없습니다."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(e, {"operation": "get_setting_options"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="설정 옵션 조회 중 오류가 발생했습니다."
        )

@router.post("/profile")
async def save_user_profile(
    profile_request: UserProfileRequest,
    authorization: str = Depends(security)
):
    """
    온보딩 사용자 프로필 저장
    JWT 토큰을 검증하고 프로필 데이터와 설정 매핑을 DB에 저장합니다.
    """
    try:
        # JWT 토큰 추출
        token = authorization.credentials
        
        log_user_action("프로필 저장 요청", "unknown", details={
            "profile_data_keys": list(profile_request.profile_data.keys()) if profile_request.profile_data else [],
            "settings_count": len(profile_request.settings_mapping)
        })
        
        # DB Module에 설정 저장 요청
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.DB_MODULE_URL}/users/me/settings",
                json={
                    "option_ids": profile_request.settings_mapping
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                timeout=settings.DB_MODULE_TIMEOUT
            )
            
        if response.status_code == 204:
            log_user_action("프로필 저장 성공", "unknown", details={"settings_count": len(profile_request.settings_mapping)})
            return {"message": "프로필이 성공적으로 저장되었습니다."}
        else:
            log_user_action("프로필 저장 실패", "unknown", details={"status_code": response.status_code})
            raise HTTPException(
                status_code=response.status_code,
                detail="프로필 저장에 실패했습니다."
            )
            
    except httpx.TimeoutException:
        log_system_event("DB Module 연결 타임아웃", "failed", details={"url": settings.DB_MODULE_URL})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="프로필 저장 서비스가 일시적으로 이용불가합니다."
        )
    except Exception as e:
        log_system_event("프로필 저장 오류", "error", details={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프로필 저장 중 오류가 발생했습니다."
        )