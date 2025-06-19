from pydantic import BaseModel, EmailStr
from typing import List, Optional

class UserLoginRequest(BaseModel):
    """사용자 로그인 요청 모델"""
    email: EmailStr
    username: Optional[str] = None

class UserTokenResponse(BaseModel):
    """JWT 토큰 응답 모델"""
    access_token: str
    token_type: str = "bearer"

class UserSettingsRequest(BaseModel):
    """사용자 설정 업데이트 요청 모델"""
    option_ids: List[int]

class SettingOption(BaseModel):
    """설정 옵션 모델"""
    id: int
    setting_type: str
    option_value: str

class UserInfo(BaseModel):
    """사용자 정보 모델"""
    id: int
    email: str
    username: Optional[str] = None 