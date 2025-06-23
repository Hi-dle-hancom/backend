from fastapi import APIRouter, HTTPException, status, Header
from typing import List, Dict, Any, Optional
from app.services.user_service import user_service
from app.schemas.users import (
    UserLoginRequest, 
    UserTokenResponse, 
    UserSettingsRequest,
    UserProfileRequest,
    UserProfileResponse
)
from app.core.logging_config import api_monitor

router = APIRouter()

@router.post("/login", response_model=UserTokenResponse)
async def user_login(user_data: UserLoginRequest):
    """
    사용자 로그인 또는 자동 회원가입
    DB Module에 요청을 전달하여 JWT 토큰을 발급받습니다.
    """
    try:
        result = await user_service.login_or_register(
            email=user_data.email,
            username=user_data.username
        )
        
        if result:
            api_monitor.logger.info(f"사용자 로그인 성공: {user_data.email}")
            return UserTokenResponse(**result)
        else:
            api_monitor.logger.error(f"사용자 로그인 실패: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="로그인에 실패했습니다. DB Module 서버 상태를 확인해주세요."
            )
            
    except Exception as e:
        api_monitor.log_error(e, {"email": user_data.email})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 내부 오류가 발생했습니다."
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
async def get_my_info(authorization: str = Header(...)):
    """
    현재 사용자 정보 조회
    """
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="잘못된 인증 헤더 형식입니다."
            )
        
        access_token = authorization.split(" ")[1]
        
        user_info = await user_service.get_user_info(access_token)
        
        if user_info:
            api_monitor.logger.info("사용자 정보 조회 성공")
            return user_info
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자 정보를 찾을 수 없습니다."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(e, {"operation": "get_user_info"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보 조회 중 오류가 발생했습니다."
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

@router.post("/profile", response_model=UserProfileResponse)
async def save_user_profile(
    profile_request: UserProfileRequest,
    authorization: str = Header(...)
):
    """
    VSCode Extension 온보딩 완료 시 사용자 프로필 저장
    온보딩에서 수집한 사용자 특징을 DB의 설정 옵션으로 저장합니다.
    """
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="잘못된 인증 헤더 형식입니다."
            )
        
        access_token = authorization.split(" ")[1]
        
        # 사용자 프로필 데이터를 DB에 저장
        success = await user_service.save_user_profile(
            access_token=access_token,
            profile_data=profile_request.profile_data,
            option_ids=profile_request.settings_mapping
        )
        
        if success:
            api_monitor.logger.info(
                "사용자 프로필 저장 성공",
                extra={
                    "profile_data": profile_request.profile_data,
                    "settings_count": len(profile_request.settings_mapping)
                }
            )
            return UserProfileResponse(
                success=True,
                message="사용자 프로필이 성공적으로 저장되었습니다.",
                saved_settings_count=len(profile_request.settings_mapping)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="프로필 저장에 실패했습니다."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(
            e, 
            {
                "operation": "save_user_profile",
                "profile_data": profile_request.profile_data
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프로필 저장 중 오류가 발생했습니다."
        )