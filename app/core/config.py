import os
from pydantic_settings import BaseSettings
from typing import List, Optional
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """애플리케이션 설정을 관리하는 클래스"""
    
    # 기본 API 설정
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AI Coding Assistant API"
    
    # CORS 설정
    CORS_ORIGINS: List[str] = ["*"]
    
    # 환경 설정
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # AI 모델 설정
    MODEL_NAME: str = "python_coding_assistant"
    MODEL_VERSION: str = "1.0.0"
    AI_MODEL_API_KEY: Optional[str] = None
    AI_MODEL_ENDPOINT: Optional[str] = None
    
    # 로깅 설정
    LOG_LEVEL: str = "INFO"
    
    # 보안 설정
    SECRET_KEY: str = "your-secret-key-here"
    
    # 성능 설정
    CACHE_TTL: int = 3600  # 캐시 TTL (초)
    MAX_CACHE_SIZE: int = 1000  # 최대 캐시 크기
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }

# 설정 인스턴스 생성
try:
    settings = Settings()
    logger.info(f"환경 설정 로드 완료: {settings.ENVIRONMENT} 모드")
except Exception as e:
    # .env 파일이 없어도 기본값으로 설정 인스턴스 생성
    logger.warning(f".env 파일을 찾을 수 없거나 로드하는 중 오류 발생: {e}")
    logger.info("기본 설정값을 사용합니다.")
    settings = Settings() 