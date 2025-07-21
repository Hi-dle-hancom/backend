"""
HAPA Backend 보안 강화 JWT 설정
DB Module과 동기화된 JWT 키 관리
"""

import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class BackendJWTConfig:
    """Backend용 JWT 설정 관리자"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.secrets_dir = self.project_root / "secrets"
        self.environment = os.getenv("ENVIRONMENT", "development")
        self._jwt_secret: Optional[str] = None
    
    def get_jwt_secret_key(self) -> str:
        """DB Module과 동일한 JWT 시크릿 키 로드"""
        if self._jwt_secret:
            return self._jwt_secret
        
        # 1. 환경변수에서 우선 로드
        env_key = os.getenv("JWT_SECRET_KEY")
        if env_key and len(env_key) >= 32:
            self._jwt_secret = env_key
            logger.info("🔐 Backend JWT 키를 환경변수에서 로드함")
            return self._jwt_secret
        
        # 2. 시크릿 파일에서 로드 (DB Module과 동일한 파일)
        secret_file = self.secrets_dir / f"jwt_secret_{self.environment}.key"
        if secret_file.exists():
            try:
                with open(secret_file, 'r') as f:
                    file_key = f.read().strip()
                
                if len(file_key) >= 32:
                    self._jwt_secret = file_key
                    logger.info(f"🔐 Backend JWT 키를 파일에서 로드함: {secret_file.name}")
                    return self._jwt_secret
            except Exception as e:
                logger.error(f"Backend JWT 시크릿 파일 로드 실패: {e}")
        
        # 3. 기본값 반환 (DB Module과 동기화)
        default_key = "HAPA_UNIFIED_SECRET_KEY_FOR_DEVELOPMENT_ONLY_CHANGE_IN_PRODUCTION_32CHARS"
        
        if self.environment == "production":
            raise ValueError(
                f"🚨 [PRODUCTION] Backend JWT_SECRET_KEY를 찾을 수 없습니다!\n"
                f"환경변수 또는 시크릿 파일을 설정해주세요: {secret_file}"
            )
        
        logger.warning("⚠️ Backend에서 기본 JWT 키 사용 중 (개발 환경)")
        self._jwt_secret = default_key
        return default_key
    
    def validate_sync_with_db_module(self) -> bool:
        """DB Module과 JWT 키 동기화 확인"""
        try:
            backend_key = self.get_jwt_secret_key()
            
            # DB Module 설정 파일 확인
            db_module_auth_file = self.project_root / "DB-Module" / "secure_jwt_manager.py"
            if not db_module_auth_file.exists():
                logger.warning("⚠️ DB Module JWT 관리자 파일을 찾을 수 없습니다")
                return False
            
            # 환경변수 동기화 확인
            db_env_key = os.getenv("JWT_SECRET_KEY")
            if backend_key == db_env_key:
                logger.info("✅ Backend-DB Module JWT 키 동기화 확인됨")
                return True
            else:
                logger.warning("⚠️ Backend-DB Module JWT 키가 동기화되지 않을 수 있습니다")
                return False
                
        except Exception as e:
            logger.error(f"Backend-DB Module JWT 동기화 확인 실패: {e}")
            return False

# 전역 인스턴스
backend_jwt_config = BackendJWTConfig()