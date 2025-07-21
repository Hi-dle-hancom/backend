"""
HAPA 중앙화된 설정 관리자
환경변수, 보안, 성능 설정을 통합 관리
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    url: str = Field(..., env="DATABASE_URL")
    pool_size: int = Field(10, env="DATABASE_POOL_SIZE")
    max_overflow: int = Field(20, env="DATABASE_MAX_OVERFLOW")


class RedisSettings(BaseSettings):
    """Redis 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    url: str = Field("redis://redis:6379", env="REDIS_URL")
    password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    db: int = Field(0, env="REDIS_DB")


class CacheSettings(BaseSettings):
    """캐시 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    ttl: int = Field(3600, env="CACHE_TTL")  # 캐시 TTL (초)
    max_cache_size: int = Field(1000, env="MAX_CACHE_SIZE")  # 최대 캐시 크기
    max_workers: int = Field(4, env="MAX_WORKERS")  # 최대 워커 수


class AISettings(BaseSettings):
    """AI 모델 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    model_name: str = Field("python_coding_assistant", env="MODEL_NAME")
    model_version: str = Field("1.0.0", env="MODEL_VERSION")
    api_key: Optional[str] = Field(None, env="AI_MODEL_API_KEY")
    endpoint: Optional[str] = Field(None, env="AI_MODEL_ENDPOINT")
    
    # 파일 처리 설정
    max_file_size: str = Field("10MB", env="MAX_FILE_SIZE")
    allowed_file_types: List[str] = Field(
        default=[".py", ".txt", ".md"], 
        env="ALLOWED_FILE_TYPES"
    )
    
    # 세션 설정
    max_concurrent_sessions: int = Field(100, env="MAX_CONCURRENT_SESSIONS")


class SecuritySettings(BaseSettings):
    """보안 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    secret_key: str = Field(default="hapa_dev_secret_key_not_for_production", env="SECRET_KEY")
    jwt_secret_key: str = Field(default="hapa_jwt_secret_key_dev_only", env="JWT_SECRET_KEY")
    api_key: str = Field(default="hapa_api_key_development_only", env="API_KEY")

    # CORS 설정
    allowed_origins: List[str] = Field(
        default=[
            "http://3.13.240.111:3000",
            "http://3.13.240.111:3001", 
            "http://localhost:3000",
            "vscode://",
            "vscode-webview://*"
        ],
        env="ALLOWED_ORIGINS"
    )
    allowed_hosts: List[str] = Field(
        default=["3.13.240.111", "localhost", "127.0.0.1"],
        env="ALLOWED_HOSTS"
    )
    
    # Rate Limiting 기본 설정
    rate_limit_requests: int = Field(100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(3600, env="RATE_LIMIT_WINDOW")
    
    # 고급 Rate Limiting 설정
    rate_limit_enabled: bool = Field(True, env="RATE_LIMIT_ENABLED")
    strict_rate_limiting: bool = Field(False, env="STRICT_RATE_LIMITING")
    rate_limit_by_ip: bool = Field(True, env="RATE_LIMIT_BY_IP")
    rate_limit_storage: str = Field("memory", env="RATE_LIMIT_STORAGE")
    
    # SSL 설정
    ssl_enabled: bool = Field(False, env="SSL_ENABLED")
    ssl_cert_path: Optional[str] = Field(None, env="SSL_CERT_PATH")
    ssl_key_path: Optional[str] = Field(None, env="SSL_KEY_PATH")
    
    # HSTS 보안 설정
    hsts_max_age: int = Field(31536000, env="HSTS_MAX_AGE")  # 1년
    security_headers_enabled: bool = Field(True, env="ENABLE_SECURITY_HEADERS")
    csrf_protection_enabled: bool = Field(True, env="ENABLE_CSRF_PROTECTION")
    
    @field_validator("allowed_origins", mode='before')
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            # JSON 배열 형식인지 확인
            if v.strip().startswith('[') and v.strip().endswith(']'):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # 쉼표로 구분된 문자열 처리
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("allowed_hosts", mode='before')
    @classmethod
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            # JSON 배열 형식인지 확인
            if v.strip().startswith('[') and v.strip().endswith(']'):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # 쉼표로 구분된 문자열 처리
            return [host.strip() for host in v.split(",") if host.strip()]
        return v
    
    @field_validator("secret_key", mode='after')
    @classmethod
    def validate_secret_key(cls, v):
        """SECRET_KEY 보안 강도 검증"""
        if len(v) < 32:
            raise ValueError("SECRET_KEY는 최소 32자 이상이어야 합니다.")
        
        # 약한 키워드 검사
        weak_patterns = ["dev", "test", "change_me", "default", "example", "demo"]
        if any(pattern in v.lower() for pattern in weak_patterns):
            logger.warning("보안이 약한 SECRET_KEY가 감지되었습니다. 운영환경에서는 강력한 키를 사용하세요.")
        
        return v
    
    @field_validator("hsts_max_age", mode='after')
    @classmethod
    def validate_hsts_max_age(cls, v):
        """HSTS max-age 값 검증"""
        if v < 300:  # 5분 미만
            raise ValueError("HSTS max-age는 최소 300초(5분) 이상이어야 합니다.")
        return v


class ServerSettings(BaseSettings):
    """서버 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    host: str = Field("0.0.0.0", env="BACKEND_HOST")
    port: int = Field(8000, env="BACKEND_PORT")


class LoggingSettings(BaseSettings):
    """로깅 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    level: str = Field("INFO", env="LOG_LEVEL")
    file_rotation: bool = Field(True, env="LOG_FILE_ROTATION")
    max_size: str = Field("10MB", env="LOG_MAX_SIZE")
    backup_count: int = Field(5, env="LOG_BACKUP_COUNT")


class VLLMSettings(BaseSettings):
    """vLLM 서버 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    server_url: str = Field("http://localhost:8002", env="VLLM_SERVER_URL")
    timeout: int = Field(300, env="VLLM_TIMEOUT_SECONDS")
    max_retries: int = Field(3, env="VLLM_MAX_RETRIES")
    health_check_interval: int = Field(60, env="VLLM_HEALTH_CHECK_INTERVAL")
    
    # vLLM 모델 기본 설정
    default_temperature: float = Field(0.3, env="VLLM_DEFAULT_TEMPERATURE")
    default_top_p: float = Field(0.95, env="VLLM_DEFAULT_TOP_P")
    default_max_tokens: int = Field(1024, env="VLLM_DEFAULT_MAX_TOKENS")


class MonitoringSettings(BaseSettings):
    """모니터링 설정"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    enabled: bool = Field(True, env="ENABLE_METRICS")
    port: int = Field(9090, env="METRICS_PORT")
    health_check_interval: int = Field(30, env="HEALTH_CHECK_INTERVAL")


class HAPASettings(BaseSettings):
    """HAPA 전체 설정 관리자"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )
    
    # 기본 환경 설정
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings()
    
    @property
    def redis(self) -> RedisSettings:
        return RedisSettings()
    
    @property
    def cache(self) -> CacheSettings:
        return CacheSettings()
    
    @property
    def ai(self) -> AISettings:
        return AISettings()
    
    @property
    def security(self) -> SecuritySettings:
        return SecuritySettings()
    
    @property
    def server(self) -> ServerSettings:
        return ServerSettings()
    
    @property
    def logging(self) -> LoggingSettings:
        return LoggingSettings()
    
    @property
    def vllm(self) -> VLLMSettings:
        return VLLMSettings()
    
    @property
    def monitoring(self) -> MonitoringSettings:
        return MonitoringSettings()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_startup_info()

    def _log_startup_info(self):
        """시작 정보 로깅"""
        logger.info(f"HAPA 설정 로드 완료 - 환경: {self.environment}")

    def get_data_dir(self) -> Path:
        """통일된 데이터 디렉토리 경로 반환"""
        base_dir = os.getenv("DATA_DIR")
        if base_dir:
            return Path(base_dir)
        
        # 환경별 기본 경로
        if self.environment == "production":
            return Path("/app/data")
        else:
            # 개발 환경: 프로젝트 루트의 data 디렉토리
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            return project_root / "data"

    @property
    def get_absolute_data_dir(self) -> str:
        """절대 경로 문자열로 데이터 디렉토리 반환"""
        return str(self.get_data_dir().resolve())

    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """서비스별 설정 반환"""
        config_map = {
            "database": self.database,
            "redis": self.redis,
            "cache": self.cache,
            "ai": self.ai,
            "security": self.security,
            "server": self.server,
            "logging": self.logging,
            "vllm": self.vllm,
            "monitoring": self.monitoring
        }
        
        service_config = config_map.get(service_name)
        if not service_config:
            raise ValueError(f"Unknown service: {service_name}")
        
        return service_config.model_dump()

    def get_environment_info(self) -> Dict[str, Any]:
        """환경 정보 반환"""
        return {
            "environment": self.environment,
            "debug": self.debug,
            "data_dir": self.get_absolute_data_dir,
            "timestamp": datetime.now(datetime.UTC).isoformat()
        }

    def validate_critical_settings(self) -> List[str]:
        """중요 설정 유효성 검사"""
        errors = []
        
        # 보안 설정 검증
        security = self.security
        if self.environment == "production":
            if "dev" in security.secret_key.lower() or "test" in security.secret_key.lower():
                errors.append("프로덕션 환경에서 개발용 SECRET_KEY 사용 중")
            
            if not security.ssl_enabled:
                errors.append("프로덕션 환경에서 SSL이 비활성화됨")
                
            if not security.security_headers_enabled:
                errors.append("프로덕션 환경에서 보안 헤더가 비활성화됨")
        
        # 데이터베이스 설정 검증
        try:
            db = self.database
            if not db.url:
                errors.append("DATABASE_URL이 설정되지 않음")
        except Exception as e:
            errors.append(f"데이터베이스 설정 오류: {e}")
        
        # AI 설정 검증
        try:
            ai = self.ai
            if self.environment == "production" and not ai.api_key:
                errors.append("프로덕션 환경에서 AI_MODEL_API_KEY가 설정되지 않음")
        except Exception as e:
            errors.append(f"AI 설정 오류: {e}")
        
        return errors

    def get_cors_config(self) -> Dict[str, Any]:
        """CORS 설정 반환"""
        security = self.security
        return {
            "allow_origins": security.allowed_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
        }

    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Rate Limit 설정 반환"""
        security = self.security
        return {
            "enabled": security.rate_limit_enabled,
            "requests": security.rate_limit_requests,
            "window": security.rate_limit_window,
            "strict": security.strict_rate_limiting,
            "by_ip": security.rate_limit_by_ip,
            "storage": security.rate_limit_storage,
        }


# 전역 설정 인스턴스
def get_settings() -> HAPASettings:
    """설정 인스턴스 반환 (싱글톤 패턴)"""
    if not hasattr(get_settings, "_instance"):
        get_settings._instance = HAPASettings()
    return get_settings._instance

  
# 호환성을 위한 별칭
hapa_settings = get_settings()