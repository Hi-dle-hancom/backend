"""
HAPA 중앙화된 설정 관리자
환경변수, 보안, 성능 설정을 통합 관리
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from pydantic import BaseSettings, Field, validator
from functools import lru_cache


class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""
    url: str = Field(..., env="DATABASE_URL")
    pool_size: int = Field(10, env="DB_POOL_SIZE")
    max_overflow: int = Field(20, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(30, env="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(3600, env="DB_POOL_RECYCLE")
    
    class Config:
        env_prefix = "DB_"


class RedisSettings(BaseSettings):
    """Redis 설정"""
    host: str = Field("localhost", env="REDIS_HOST")
    port: int = Field(6379, env="REDIS_PORT")
    password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    db: int = Field(0, env="REDIS_DB")
    max_connections: int = Field(20, env="REDIS_MAX_CONNECTIONS")
    
    class Config:
        env_prefix = "REDIS_"


class SecuritySettings(BaseSettings):
    """보안 설정"""
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    api_key: str = Field(..., env="API_KEY")
    
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
    
    # Rate Limiting
    rate_limit_requests: int = Field(100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(3600, env="RATE_LIMIT_WINDOW")
    
    # SSL 설정
    ssl_enabled: bool = Field(False, env="SSL_ENABLED")
    ssl_cert_path: Optional[str] = Field(None, env="SSL_CERT_PATH")
    ssl_key_path: Optional[str] = Field(None, env="SSL_KEY_PATH")
    
    @validator("allowed_origins", pre=True)
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("allowed_hosts", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    class Config:
        env_prefix = "SECURITY_"


class ServerSettings(BaseSettings):
    """서버 설정"""
    host: str = Field("0.0.0.0", env="BACKEND_HOST")
    port: int = Field(8000, env="BACKEND_PORT")
    workers: int = Field(1, env="WORKERS")
    reload: bool = Field(False, env="RELOAD")
    
    class Config:
        env_prefix = "SERVER_"


class LoggingSettings(BaseSettings):
    """로깅 설정"""
    level: str = Field("INFO", env="LOG_LEVEL")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    file_enabled: bool = Field(True, env="LOG_FILE_ENABLED")
    file_path: str = Field("logs/app.log", env="LOG_FILE_PATH")
    max_size: int = Field(10 * 1024 * 1024, env="LOG_MAX_SIZE")  # 10MB
    backup_count: int = Field(5, env="LOG_BACKUP_COUNT")
    
    class Config:
        env_prefix = "LOG_"


class VLLMSettings(BaseSettings):
    """VLLM 서버 설정"""
    host: str = Field("3.13.240.111", env="VLLM_HOST")
    port: int = Field(8002, env="VLLM_PORT")
    timeout: int = Field(300, env="VLLM_TIMEOUT")
    max_retries: int = Field(3, env="VLLM_MAX_RETRIES")
    
    class Config:
        env_prefix = "VLLM_"


class MonitoringSettings(BaseSettings):
    """모니터링 설정"""
    prometheus_enabled: bool = Field(True, env="PROMETHEUS_ENABLED")
    prometheus_port: int = Field(9090, env="PROMETHEUS_PORT")
    grafana_enabled: bool = Field(True, env="GRAFANA_ENABLED")
    grafana_port: int = Field(3001, env="GRAFANA_PORT")
    
    class Config:
        env_prefix = "MONITORING_"


class HAPASettings(BaseSettings):
    """HAPA 통합 설정 클래스"""
    
    # 환경 설정
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # 서브 설정들
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    security: SecuritySettings = SecuritySettings()
    server: ServerSettings = ServerSettings()
    logging: LoggingSettings = LoggingSettings()
    vllm: VLLMSettings = VLLMSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_logging()
        self._validate_settings()
    
    def _setup_logging(self):
        """로깅 설정"""
        log_level = getattr(logging, self.logging.level.upper(), logging.INFO)
        
        # 로그 디렉토리 생성
        log_path = Path(self.logging.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 로깅 설정
        logging.basicConfig(
            level=log_level,
            format=self.logging.format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(
                    self.logging.file_path,
                    encoding='utf-8'
                ) if self.logging.file_enabled else logging.NullHandler()
            ]
        )
    
    def _validate_settings(self):
        """설정 유효성 검증"""
        logger = logging.getLogger(__name__)
        
        # 프로덕션 환경 보안 검증
        if self.environment == "production":
            if self.debug:
                logger.warning("프로덕션 환경에서 DEBUG 모드가 활성화되어 있습니다!")
            
            if not self.security.ssl_enabled:
                logger.warning("프로덕션 환경에서 SSL이 비활성화되어 있습니다!")
            
            # 기본 시크릿 키 검증
            weak_keys = ["dev_secret", "change_me", "default", "test"]
            if any(weak in self.security.secret_key.lower() for weak in weak_keys):
                raise ValueError("프로덕션 환경에서 약한 시크릿 키를 사용할 수 없습니다!")
        
        logger.info(f"HAPA 설정 로드 완료 - 환경: {self.environment}")
    
    def get_database_url(self) -> str:
        """데이터베이스 URL 반환"""
        return self.database.url
    
    def get_redis_url(self) -> str:
        """Redis URL 반환"""
        auth = f":{self.redis.password}@" if self.redis.password else ""
        return f"redis://{auth}{self.redis.host}:{self.redis.port}/{self.redis.db}"
    
    def get_cors_config(self) -> Dict[str, Any]:
        """CORS 설정 반환"""
        return {
            "allow_origins": self.security.allowed_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
        }
    
    def get_rate_limit_config(self) -> Dict[str, int]:
        """Rate Limit 설정 반환"""
        return {
            "requests": self.security.rate_limit_requests,
            "window": self.security.rate_limit_window,
        }
    
    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.environment == "development"
    
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.environment == "production"
    
    def export_config(self, safe_only: bool = True) -> Dict[str, Any]:
        """설정을 딕셔너리로 내보내기"""
        config = self.dict()
        
        if safe_only:
            # 민감한 정보 제거
            sensitive_keys = [
                "secret_key", "jwt_secret_key", "api_key", 
                "password", "DATABASE_URL"
            ]
            
            def remove_sensitive(obj, path=""):
                if isinstance(obj, dict):
                    return {
                        k: "***REDACTED***" if any(sens in k.lower() for sens in sensitive_keys)
                        else remove_sensitive(v, f"{path}.{k}")
                        for k, v in obj.items()
                    }
                return obj
            
            config = remove_sensitive(config)
        
        return config


@lru_cache()
def get_settings() -> HAPASettings:
    """설정 인스턴스 가져오기 (캐시됨)"""
    return HAPASettings()


# 전역 설정 인스턴스
settings = get_settings()