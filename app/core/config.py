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
    PROJECT_NAME: str = "HAPA (Hancom AI Python Assistant) API"
    
    # 환경 설정
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS 설정
    CORS_ORIGINS: List[str] = ["*"]
    
    # AI 모델 설정
    MODEL_NAME: str = "python_coding_assistant"
    MODEL_VERSION: str = "1.0.0"
    AI_MODEL_API_KEY: Optional[str] = None
    AI_MODEL_ENDPOINT: Optional[str] = None
    
    # 보안 설정
    SECRET_KEY: str = "hapa_secret_key_for_development_only_change_in_production"
    API_KEY_EXPIRY_DAYS: int = 365
    
    # 로깅 설정
    LOG_LEVEL: str = "INFO"
    LOG_FILE_ROTATION: bool = True
    LOG_MAX_SIZE: str = "10MB"
    LOG_BACKUP_COUNT: int = 5
    
    # 성능 및 캐시 설정
    CACHE_TTL: int = 3600  # 캐시 TTL (초)
    MAX_CACHE_SIZE: int = 1000  # 최대 캐시 크기
    REQUEST_TIMEOUT: int = 30  # 요청 타임아웃 (초)
    MAX_WORKERS: int = 4  # 최대 워커 수
    
    # Rate Limiting 설정
    RATE_LIMIT_ENABLED: bool = True
    DEFAULT_RATE_LIMIT: int = 100
    RATE_LIMIT_WINDOW_MINUTES: int = 60
    
    # 데이터베이스 설정 (향후 확장용)
    DATABASE_URL: str = "sqlite:///./hapa.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # 외부 서비스 설정
    EXTERNAL_API_TIMEOUT: int = 10
    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: int = 1
    
    # 모니터링 설정
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    HEALTH_CHECK_INTERVAL: int = 30
    
    # 개발 전용 설정
    ENABLE_DEMO_API_KEY: bool = True
    DEMO_USER_ID: str = "demo_user"
    DEMO_API_KEY: str = "hapa_demo_20241228_secure_key_for_testing"
    DEMO_API_KEY_PERMISSIONS: List[str] = ["code_generation", "code_completion", "feedback", "history"]
    
    # 보안 헤더 설정
    ENABLE_SECURITY_HEADERS: bool = True
    ENABLE_CSRF_PROTECTION: bool = False
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "0.0.0.0"]
    
    # 파일 업로드 설정
    MAX_FILE_SIZE: str = "10MB"
    ALLOWED_FILE_TYPES: List[str] = [".py", ".txt", ".md"]
    
    # 세션 설정
    SESSION_TIMEOUT: int = 1800  # 30분
    MAX_CONCURRENT_SESSIONS: int = 100
    
    # SSL/TLS 설정 (운영환경용)
    SSL_ENABLED: bool = False
    SSL_CERT_PATH: Optional[str] = None
    SSL_KEY_PATH: Optional[str] = None
    
    # 백업 설정 (운영환경용)
    BACKUP_ENABLED: bool = False
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 30
    
    # DB Module 마이크로서비스 설정
    DB_MODULE_URL: str = "http://localhost:8001"
    DB_MODULE_TIMEOUT: int = 10
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }
    
    def get_cors_origins(self) -> List[str]:
        """CORS 허용 origins 반환"""
        if self.ENVIRONMENT == "production":
            return [origin for origin in self.CORS_ORIGINS if origin != "*"]
        return self.CORS_ORIGINS
    
    def is_production(self) -> bool:
        """운영 환경인지 확인"""
        return self.ENVIRONMENT == "production"
    
    def get_log_level(self) -> int:
        """로그 레벨 정수값 반환"""
        return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)

# 설정 검증 함수
def validate_production_settings(settings: Settings) -> None:
    """운영 환경에서 필수 보안 설정을 검증합니다."""
    if not settings.is_production():
        return
    
    errors = []
    
    # SECRET_KEY 검증
    if settings.SECRET_KEY == "hapa_secret_key_for_development_only_change_in_production":
        errors.append("SECRET_KEY가 개발용 기본값입니다!")
    elif len(settings.SECRET_KEY) < 32:
        errors.append(f"SECRET_KEY가 너무 짧습니다 (현재: {len(settings.SECRET_KEY)}자, 최소: 32자)")
    
    # CORS 검증
    if "*" in settings.CORS_ORIGINS:
        errors.append("CORS_ORIGINS에 '*'가 포함되어 있습니다! 특정 도메인만 허용하세요.")
    
    # AI 모델 API 키 검증
    if not settings.AI_MODEL_API_KEY:
        errors.append("AI_MODEL_API_KEY가 설정되지 않았습니다!")
    
    # 디버그 모드 검증
    if settings.DEBUG:
        errors.append("DEBUG 모드가 활성화되어 있습니다! 운영환경에서는 비활성화하세요.")
    
    if errors:
        error_msg = "🚨 [PRODUCTION] 보안 설정 오류:\n" + "\n".join(f"- {error}" for error in errors)
        raise ValueError(error_msg)

# 설정 인스턴스 생성 및 검증
try:
    settings = Settings()
    logger.info(f"환경 설정 로드 완료: {settings.ENVIRONMENT} 모드")
    
    # 운영 환경 보안 검증
    validate_production_settings(settings)
    
    if settings.is_production():
        logger.warning("⚠️  운영 환경 모드로 실행 중입니다.")
        logger.info("✅ 운영 환경 보안 설정 검증 완료")
    else:
        logger.info("🔧 개발 환경 모드로 실행 중입니다.")
        if settings.SECRET_KEY == "hapa_secret_key_for_development_only_change_in_production":
            logger.warning("⚠️ 개발용 SECRET_KEY를 사용 중입니다. 운영 환경에서는 변경하세요!")
        
except Exception as e:
    # .env 파일이 없어도 기본값으로 설정 인스턴스 생성
    logger.warning(f".env 파일을 찾을 수 없거나 로드하는 중 오류 발생: {e}")
    logger.info("기본 설정값을 사용합니다.")
    settings = Settings() 