import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from pydantic import BaseModel
import json
from pathlib import Path

from app.core.config import settings
from app.core.logging_config import StructuredLogger

logger = StructuredLogger("security")

# API Key 보안 스키마 정의
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

class APIKeyModel(BaseModel):
    """API Key 데이터 모델"""
    key_id: str
    key_hash: str
    user_id: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True
    usage_count: int = 0
    rate_limit: int = 1000  # 일일 요청 제한
    last_used_at: Optional[datetime] = None
    permissions: List[str] = ["code_generation", "code_completion"]

class RateLimitModel(BaseModel):
    """Rate Limiting 데이터 모델"""
    user_id: str
    endpoint: str
    requests: List[datetime]
    limit: int
    window_minutes: int = 60

class APIKeyManager:
    """API Key 관리 클래스"""
    
    def __init__(self):
        self.api_keys_file = Path("data/api_keys.json")
        self.rate_limits_file = Path("data/rate_limits.json")
        self.api_keys_file.parent.mkdir(exist_ok=True)
        self.rate_limits_file.parent.mkdir(exist_ok=True)
        
        # 기본 데이터 구조 초기화
        self._init_storage()
    
    def _init_storage(self):
        """저장소 초기화"""
        if not self.api_keys_file.exists():
            self._save_api_keys({})
        if not self.rate_limits_file.exists():
            self._save_rate_limits({})
    
    def _load_api_keys(self) -> Dict[str, Dict]:
        """API Keys 로드"""
        try:
            with open(self.api_keys_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_api_keys(self, api_keys: Dict[str, Dict]):
        """API Keys 저장"""
        with open(self.api_keys_file, 'w', encoding='utf-8') as f:
            json.dump(api_keys, f, ensure_ascii=False, indent=2, default=str)
    
    def _load_rate_limits(self) -> Dict[str, Dict]:
        """Rate Limits 로드"""
        try:
            with open(self.rate_limits_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # datetime 객체로 변환
                for user_id, limits in data.items():
                    for endpoint, limit_data in limits.items():
                        limit_data['requests'] = [
                            datetime.fromisoformat(req) for req in limit_data['requests']
                        ]
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_rate_limits(self, rate_limits: Dict[str, Dict]):
        """Rate Limits 저장"""
        # datetime 객체를 문자열로 변환
        serializable_data = {}
        for user_id, limits in rate_limits.items():
            serializable_data[user_id] = {}
            for endpoint, limit_data in limits.items():
                serializable_data[user_id][endpoint] = {
                    **limit_data,
                    'requests': [req.isoformat() for req in limit_data['requests']]
                }
        
        with open(self.rate_limits_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, ensure_ascii=False, indent=2, default=str)
    
    def generate_api_key(self, user_id: str, name: str = "Default Key", 
                        rate_limit: int = 1000, 
                        permissions: List[str] = None) -> Dict[str, str]:
        """새 API Key 생성"""
        if permissions is None:
            permissions = ["code_generation", "code_completion"]
        
        # 고유 키 생성
        key_id = f"hapa_{secrets.token_hex(8)}"
        raw_key = f"{key_id}_{secrets.token_hex(16)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # API Key 모델 생성
        api_key_data = APIKeyModel(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            name=name,
            created_at=datetime.now(),
            rate_limit=rate_limit,
            permissions=permissions
        )
        
        # 저장
        api_keys = self._load_api_keys()
        api_keys[key_hash] = api_key_data.dict()
        self._save_api_keys(api_keys)
        
        logger.info(
            f"새 API Key 생성: {key_id}",
            user_id=user_id,
            key_id=key_id,
            permissions=permissions
        )
        
        return {
            "api_key": raw_key,
            "key_id": key_id,
            "user_id": user_id,
            "rate_limit": rate_limit,
            "permissions": permissions
        }
    
    def verify_api_key(self, api_key: str) -> Optional[APIKeyModel]:
        """API Key 검증"""
        if not api_key:
            return None
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        api_keys = self._load_api_keys()
        
        if key_hash not in api_keys:
            logger.warning(f"유효하지 않은 API Key 시도", key_hash=key_hash[:10])
            return None
        
        key_data = api_keys[key_hash]
        api_key_model = APIKeyModel(**key_data)
        
        # 활성 상태 확인
        if not api_key_model.is_active:
            logger.warning(f"비활성화된 API Key 사용 시도", key_id=api_key_model.key_id)
            return None
        
        # 만료일 확인
        if api_key_model.expires_at and datetime.now() > api_key_model.expires_at:
            logger.warning(f"만료된 API Key 사용 시도", key_id=api_key_model.key_id)
            return None
        
        # 사용 횟수 업데이트
        api_key_model.usage_count += 1
        api_key_model.last_used_at = datetime.now()
        
        # 저장
        api_keys[key_hash] = api_key_model.dict()
        self._save_api_keys(api_keys)
        
        logger.info(
            f"API Key 검증 성공",
            key_id=api_key_model.key_id,
            user_id=api_key_model.user_id,
            usage_count=api_key_model.usage_count
        )
        
        return api_key_model
    
    def check_rate_limit(self, user_id: str, endpoint: str, limit: int = 100, 
                        window_minutes: int = 60) -> bool:
        """Rate Limiting 확인"""
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        rate_limits = self._load_rate_limits()
        
        if user_id not in rate_limits:
            rate_limits[user_id] = {}
        
        if endpoint not in rate_limits[user_id]:
            rate_limits[user_id][endpoint] = {
                'requests': [],
                'limit': limit,
                'window_minutes': window_minutes
            }
        
        user_limits = rate_limits[user_id][endpoint]
        
        # 윈도우 밖의 요청 제거
        user_limits['requests'] = [
            req for req in user_limits['requests'] if req > window_start
        ]
        
        # 제한 확인
        if len(user_limits['requests']) >= limit:
            logger.warning(
                f"Rate limit 초과",
                user_id=user_id,
                endpoint=endpoint,
                requests_count=len(user_limits['requests']),
                limit=limit
            )
            return False
        
        # 현재 요청 추가
        user_limits['requests'].append(now)
        self._save_rate_limits(rate_limits)
        
        return True
    
    def revoke_api_key(self, key_id: str) -> bool:
        """API Key 폐기"""
        api_keys = self._load_api_keys()
        
        for key_hash, key_data in api_keys.items():
            if key_data.get('key_id') == key_id:
                key_data['is_active'] = False
                api_keys[key_hash] = key_data
                self._save_api_keys(api_keys)
                
                logger.info(f"API Key 폐기", key_id=key_id)
                return True
        
        return False
    
    def get_api_key_stats(self, user_id: str) -> Dict[str, Any]:
        """사용자 API Key 통계"""
        api_keys = self._load_api_keys()
        user_keys = [
            APIKeyModel(**key_data) for key_data in api_keys.values()
            if key_data.get('user_id') == user_id
        ]
        
        total_usage = sum(key.usage_count for key in user_keys)
        active_keys = len([key for key in user_keys if key.is_active])
        
        return {
            'user_id': user_id,
            'total_keys': len(user_keys),
            'active_keys': active_keys,
            'total_usage': total_usage,
            'keys': [
                {
                    'key_id': key.key_id,
                    'name': key.name,
                    'created_at': key.created_at,
                    'usage_count': key.usage_count,
                    'is_active': key.is_active,
                    'last_used_at': key.last_used_at
                }
                for key in user_keys
            ]
        }

# 전역 API Key 매니저 인스턴스
api_key_manager = APIKeyManager()

# FastAPI 의존성 함수들
async def get_api_key_from_header(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """헤더에서 API Key 추출"""
    return api_key

async def get_api_key_from_bearer(credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)) -> Optional[str]:
    """Bearer 토큰에서 API Key 추출"""
    if credentials and credentials.scheme.lower() == "apikey":
        return credentials.credentials
    return None

async def get_current_api_key(
    header_key: Optional[str] = Depends(get_api_key_from_header),
    bearer_key: Optional[str] = Depends(get_api_key_from_bearer)
) -> APIKeyModel:
    """현재 요청의 유효한 API Key 반환"""
    
    # API Key 추출 (헤더 우선, 없으면 Bearer)
    api_key = header_key or bearer_key
    
    if not api_key:
        logger.warning("API Key가 제공되지 않음")
        raise HTTPException(
            status_code=401,
            detail="API Key가 필요합니다. X-API-Key 헤더 또는 Authorization: ApiKey 형식으로 제공해주세요."
        )
    
    # API Key 검증
    verified_key = api_key_manager.verify_api_key(api_key)
    
    if not verified_key:
        logger.warning("유효하지 않은 API Key", api_key_prefix=api_key[:10])
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 API Key입니다."
        )
    
    return verified_key

async def check_permission(permission: str):
    """권한 확인 의존성"""
    def permission_checker(api_key: APIKeyModel = Depends(get_current_api_key)):
        if permission not in api_key.permissions:
            logger.warning(
                f"권한 부족",
                user_id=api_key.user_id,
                required_permission=permission,
                user_permissions=api_key.permissions
            )
            raise HTTPException(
                status_code=403,
                detail=f"'{permission}' 권한이 필요합니다."
            )
        return api_key
    
    return permission_checker

async def check_rate_limit_dependency(endpoint: str, limit: int = 100):
    """Rate Limiting 확인 의존성"""
    def rate_limit_checker(api_key: APIKeyModel = Depends(get_current_api_key)):
        if not api_key_manager.check_rate_limit(api_key.user_id, endpoint, limit):
            logger.warning(
                f"Rate limit 초과",
                user_id=api_key.user_id,
                endpoint=endpoint,
                limit=limit
            )
            raise HTTPException(
                status_code=429,
                detail=f"요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요. (제한: {limit}회/시간)"
            )
        return api_key
    
    return rate_limit_checker

# 보안 유틸리티 함수들
def hash_password(password: str) -> str:
    """비밀번호 해시화"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{hash_obj.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """비밀번호 검증"""
    try:
        salt, hash_hex = hashed.split(':')
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hash_obj.hex() == hash_hex
    except ValueError:
        return False

def generate_csrf_token() -> str:
    """CSRF 토큰 생성"""
    return secrets.token_hex(32)

# 데모용 API Key 생성 (개발 환경에서만)
def create_demo_api_key():
    """데모용 API Key 생성"""
    if settings.DEBUG:
        demo_key = api_key_manager.generate_api_key(
            user_id="demo_user",
            name="Demo API Key",
            rate_limit=10000,
            permissions=["code_generation", "code_completion", "feedback", "history"]
        )
        
        logger.info(
            "데모 API Key 생성됨",
            api_key=demo_key["api_key"],
            key_id=demo_key["key_id"]
        )
        
        return demo_key
    
    return None 