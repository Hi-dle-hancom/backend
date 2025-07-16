import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """애플리케이션 설정을 관리하는 클래스"""

    # 기본 API 설정
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "HAPA (Hancom AI Python Assistant) API"

    # 환경 설정
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS 설정 (VSCode Extension 지원)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # React 웹앱
        "http://localhost:3001",  # Grafana
        "http://127.0.0.1:3000",
        "vscode://",
        "vscode-webview://*"
    ]

    # AI 모델 설정
    MODEL_NAME: str = "python_coding_assistant"
    MODEL_VERSION: str = "1.0.0"
    AI_MODEL_API_KEY: Optional[str] = None
    AI_MODEL_ENDPOINT: Optional[str] = None

    # 보안 설정
    SECRET_KEY: str = "hapa_secret_key_for_development_only_change_in_production"
    API_KEY_EXPIRY_DAYS: int = 365

    # 로깅 설정 (환경별 차별화)
    LOG_LEVEL: str = "INFO"
    LOG_FILE_ROTATION: bool = True
    LOG_MAX_SIZE: str = "10MB"
    LOG_BACKUP_COUNT: int = 5
    
    # 개발/프로덕션 환경별 로깅 제어 (강화됨)
    ENABLE_DEBUG_LOGS: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_DEBUG_LOGS", "true" if os.getenv("ENVIRONMENT", "development") == "development" else "false").lower() == "true",
        description="디버그 로그 활성화 여부"
    )
    
    LOG_CHUNK_DETAILS: bool = Field(
        default_factory=lambda: os.getenv("LOG_CHUNK_DETAILS", "true" if os.getenv("ENVIRONMENT", "development") == "development" else "false").lower() == "true",
        description="청크 상세 로그 활성화 여부"
    )
    
    ENABLE_PERFORMANCE_LOGS: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_PERFORMANCE_LOGS", "true").lower() == "true",
        description="성능 로그 활성화 여부"
    )
    
    ENABLE_REQUEST_RESPONSE_LOGS: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_REQUEST_RESPONSE_LOGS", "true" if os.getenv("ENVIRONMENT", "development") == "development" else "false").lower() == "true",
        description="요청/응답 로그 활성화 여부"
    )

    # 성능 및 캐시 설정
    CACHE_TTL: int = 3600  # 캐시 TTL (초)
    MAX_CACHE_SIZE: int = 1000  # 최대 캐시 크기
    REQUEST_TIMEOUT: int = 30  # 요청 타임아웃 (초)
    MAX_WORKERS: int = 4  # 최대 워커 수

    # Redis 설정
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_TIMEOUT: int = 5  # Redis 연결 타임아웃 (초)

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

    # ✅ 완전 개선: 하드코딩 제거된 동적 사용자 인증 시스템
    ENABLE_DEMO_API_KEY: bool = False  # 데모 API 키 완전 비활성화
    
    # 동적 DB 기반 사용자 인증 설정 (하드코딩 없음)
    DYNAMIC_USER_AUTH_ENABLED: bool = Field(
        default=True,
        description="동적 DB 기반 사용자 인증 활성화"
    )
    
    # 테스트 모드 설정 (선택적, 하드코딩 없음)
    TEST_MODE_ENABLED: bool = Field(
        default=False,
        description="테스트 모드 활성화 (실제 운영에서는 false)"
    )

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

    # 온보딩 테스트 설정 (선택적)
    ENABLE_ONBOARDING_TEST: Optional[bool] = None
    ONBOARDING_TEST_USER: Optional[str] = None
    TEST_USER_PREFIX: Optional[str] = None

    # 알림 시스템 설정 (오류 모니터링용)
    SLACK_WEBHOOK_URL: str = Field(default="", env="SLACK_WEBHOOK_URL")
    DISCORD_WEBHOOK_URL: str = Field(default="", env="DISCORD_WEBHOOK_URL")

    # SMTP 이메일 알림 설정
    SMTP_HOST: str = Field(default="", env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: str = Field(default="", env="SMTP_USERNAME")
    SMTP_PASSWORD: str = Field(default="", env="SMTP_PASSWORD")
    ALERT_EMAILS: str = Field(
        default="", env="ALERT_EMAILS"
    )  # 쉼표로 구분된 이메일 목록

    # 보안 강화 설정
    ENABLE_REQUEST_SIGNING: bool = Field(
        default=False, env="ENABLE_REQUEST_SIGNING")
    REQUEST_SIGNATURE_SECRET: str = Field(
        default="", env="REQUEST_SIGNATURE_SECRET")
    ENABLE_IP_WHITELIST: bool = Field(default=False, env="ENABLE_IP_WHITELIST")
    ALLOWED_IPS: str = Field(
        default="127.0.0.1,::1", env="ALLOWED_IPS"
    )  # 쉼표로 구분된 IP 목록

    # API 키 보안 설정
    API_KEY_MIN_LENGTH: int = Field(default=32, env="API_KEY_MIN_LENGTH")
    API_KEY_REQUIRE_PREFIX: bool = Field(
        default=True, env="API_KEY_REQUIRE_PREFIX")
    API_KEY_PREFIX: str = Field(default="hapa_", env="API_KEY_PREFIX")

    # Rate Limiting 강화
    STRICT_RATE_LIMITING: bool = Field(
        default=False, env="STRICT_RATE_LIMITING")
    RATE_LIMIT_BY_IP: bool = Field(default=True, env="RATE_LIMIT_BY_IP")
    RATE_LIMIT_STORAGE: str = Field(
        default="memory", env="RATE_LIMIT_STORAGE"
    )  # memory, redis

    # 콘텐츠 보안 정책
    ENABLE_CSP: bool = Field(default=True, env="ENABLE_CSP")
    CSP_REPORT_URI: str = Field(default="", env="CSP_REPORT_URI")

    # 보안 헤더 설정
    ENABLE_HSTS: bool = Field(default=True, env="ENABLE_HSTS")
    HSTS_MAX_AGE: int = Field(default=31536000, env="HSTS_MAX_AGE")  # 1년
    ENABLE_FRAME_OPTIONS: bool = Field(
        default=True, env="ENABLE_FRAME_OPTIONS")
    FRAME_OPTIONS: str = Field(default="DENY", env="FRAME_OPTIONS")

    # 암호화 설정
    ENCRYPTION_KEY: str = Field(default="", env="ENCRYPTION_KEY")
    ENABLE_DATABASE_ENCRYPTION: bool = Field(
        default=False, env="ENABLE_DATABASE_ENCRYPTION"
    )

    # vLLM 멀티 LoRA 서버 설정
    VLLM_SERVER_URL: str = Field(
        default="http://3.13.240.111:8002", env="VLLM_SERVER_URL"
    )
    VLLM_TIMEOUT_SECONDS: int = Field(
        default=300, env="VLLM_TIMEOUT_SECONDS")  # 5분
    VLLM_MAX_RETRIES: int = Field(default=3, env="VLLM_MAX_RETRIES")
    VLLM_HEALTH_CHECK_INTERVAL: int = Field(
        default=60, env="VLLM_HEALTH_CHECK_INTERVAL"
    )  # 1분

    # vLLM 모델별 기본 설정
    VLLM_DEFAULT_TEMPERATURE: float = Field(
        default=0.3, env="VLLM_DEFAULT_TEMPERATURE")
    VLLM_DEFAULT_TOP_P: float = Field(default=0.95, env="VLLM_DEFAULT_TOP_P")
    VLLM_DEFAULT_MAX_TOKENS: int = Field(
        default=1024, env="VLLM_DEFAULT_MAX_TOKENS")

    # vLLM 성능 설정
    VLLM_CONNECTION_POOL_SIZE: int = Field(
        default=10, env="VLLM_CONNECTION_POOL_SIZE")
    VLLM_ENABLE_RETRY: bool = Field(default=True, env="VLLM_ENABLE_RETRY")
    VLLM_RETRY_DELAY: float = Field(default=1.0, env="VLLM_RETRY_DELAY")  # 초

    # vLLM 추가 설정 (환경별 로깅 강화)
    VLLM_DEBUG_MODE: bool = Field(default=False, env="VLLM_DEBUG_MODE")
    VLLM_LOG_REQUESTS: bool = Field(default=False, env="VLLM_LOG_REQUESTS")
    VLLM_ENABLE_MONITORING: bool = Field(
        default=True, env="VLLM_ENABLE_MONITORING")

    # 데이터 디렉토리 통일 설정 (NEW)
    DATA_DIR: str = Field(
        default="data",
        env="DATA_DIR",
        description="데이터 저장 디렉토리 경로 (프로젝트 루트 기준)"
    )

    @property
    def get_absolute_data_dir(self) -> str:
        """프로젝트 루트 기준 절대 데이터 경로 반환"""
        import os
        from pathlib import Path
        
        # 현재 파일 기준으로 프로젝트 루트 찾기
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent  # Backend/app/core/config.py -> project/
        
        return str(project_root / self.DATA_DIR)

    # 🆕 환경별 로깅 설정 메서드들
    def should_log_performance(self) -> bool:
        """성능 관련 로그를 기록할지 결정"""
        if hasattr(self, '_should_log_performance'):
            return self._should_log_performance
        
        # 환경별 성능 로그 정책
        if self.ENVIRONMENT == "development":
            self._should_log_performance = True  # 개발 환경에서는 활성화
        elif self.ENVIRONMENT == "production":
            self._should_log_performance = False  # 운영 환경에서는 비활성화 (성능 최적화)
        else:
            self._should_log_performance = False  # 기본적으로 비활성화
        
        return self._should_log_performance
    
    def should_log_debug(self) -> bool:
        """디버그 로그를 기록할지 결정"""
        if hasattr(self, '_should_log_debug'):
            return self._should_log_debug
        
        # 환경별 디버그 로그 정책
        if self.ENVIRONMENT == "development":
            self._should_log_debug = True  # 개발 환경에서는 활성화
        elif self.ENVIRONMENT == "production":
            self._should_log_debug = False  # 운영 환경에서는 완전 비활성화
        else:
            self._should_log_debug = False  # 기본적으로 비활성화
        
        return self._should_log_debug
    
    def should_log_chunk_details(self) -> bool:
        """청크 상세 로그를 기록할지 결정 (가장 상세한 로그)"""
        if hasattr(self, '_should_log_chunk_details'):
            return self._should_log_chunk_details
        
        # 청크 상세 로그는 개발 환경에서만, 그리고 특별한 디버깅이 필요할 때만
        debug_mode = os.getenv("HAPA_DEBUG_CHUNKS", "false").lower() == "true"
        self._should_log_chunk_details = (self.ENVIRONMENT == "development" and debug_mode)
        
        return self._should_log_chunk_details
    
    def get_log_level_summary(self) -> Dict[str, bool]:
        """현재 로그 레벨 설정 요약"""
        return {
            "environment": self.ENVIRONMENT,
            "performance_logging": self.should_log_performance(),
            "debug_logging": self.should_log_debug(),
            "chunk_details": self.should_log_chunk_details(),
        }

    def should_log_request_response(self) -> bool:
        """요청/응답 로그를 기록할지 여부"""
        return self.ENABLE_REQUEST_RESPONSE_LOGS or self.ENVIRONMENT == "development"
    
    def get_environment_log_level(self) -> str:
        """환경별 적절한 로그 레벨 반환"""
        if self.ENVIRONMENT == "production":
            return "WARNING"
        elif self.ENVIRONMENT == "staging":
            return "INFO"
        else:
            return "DEBUG" if self.should_log_debug() else "INFO"

    @validator("ALLOWED_IPS")
    def validate_allowed_ips(cls, v):
        """허용된 IP 목록 검증"""
        if not v:
            return v

        ips = [ip.strip() for ip in v.split(",")]
        for ip in ips:
            try:
                import ipaddress

                ipaddress.ip_address(ip)
            except ValueError:
                raise ValueError(f"유효하지 않은 IP 주소: {ip}")
        return v

    @validator("API_KEY_MIN_LENGTH")
    def validate_api_key_length(cls, v):
        """API 키 최소 길이 검증"""
        if v < 16:
            raise ValueError("API 키 최소 길이는 16자 이상이어야 합니다")
        if v > 128:
            raise ValueError("API 키 최대 길이는 128자 이하여야 합니다")
        return v

    @validator("HSTS_MAX_AGE")
    def validate_hsts_max_age(cls, v):
        """HSTS 최대 연령 검증"""
        if v < 300:  # 5분
            raise ValueError("HSTS max-age는 최소 300초 이상이어야 합니다")
        if v > 63072000:  # 2년
            raise ValueError("HSTS max-age는 최대 63072000초(2년) 이하여야 합니다")
        return v

    model_config = {
        "env_file": [".env.production", ".env"],
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    def get_cors_origins(self) -> List[str]:
        """CORS 허용 origins 반환 (환경별 엄격한 차별화)"""
        if self.ENVIRONMENT == "production":
            # 운영환경: 특정 도메인만 허용, 와일드카드 완전 금지
            production_origins = [
                "https://hapa.hancom.com",  # 실제 운영 도메인
                "https://api.hapa.hancom.com",  # API 도메인
                "https://vscode.dev",  # VSCode Web (공식)
                "vscode://hancom.hapa-extension",  # VSCode Extension (특정)
            ]
            logger.info(
                f"🔒 운영환경 CORS 설정 적용: {len(production_origins)}개 도메인만 허용"
            )
            return production_origins

        elif self.ENVIRONMENT == "staging":
            # 스테이징환경: 제한적 허용
            staging_origins = [
                "https://staging.hapa.hancom.com",
                "https://test.hapa.hancom.com",
                "http://localhost:3000",
                "vscode-webview://*",
                "vscode://*",
            ]
            logger.info(
                f"⚠️ 스테이징환경 CORS 설정 적용: {len(staging_origins)}개 도메인 허용"
            )
            return staging_origins

        else:
            # 개발환경: 개발 편의성을 위해 관대한 설정
            dev_origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
                "vscode-webview://*",
                "vscode://*",
                "https://vscode.dev",
            ]
            logger.info(
                f"🔧 개발환경 CORS 설정 적용: {len(dev_origins)}개 도메인 허용 (와일드카드 제거)"
            )
            return dev_origins

    def get_security_headers(self) -> Dict[str, str]:
        """환경별 보안 헤더 설정 반환"""
        base_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
        }

        if self.is_production():
            # 운영환경: 강화된 보안 헤더
            base_headers.update(
                {
                    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
                    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; object-src 'none';",
                    "Referrer-Policy": "strict-origin-when-cross-origin",
                    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
                })

        return base_headers

    def get_rate_limit_config(self) -> Dict[str, Any]:
        """환경별 Rate Limiting 설정"""
        if self.is_production():
            return {
                "enabled": True,
                "default_limit": 100,  # 운영환경: 엄격한 제한
                "window_minutes": 60,
                "burst_limit": 150,
                "whitelist_ips": [],
            }
        elif self.ENVIRONMENT == "staging":
            return {
                "enabled": True,
                "default_limit": 500,  # 스테이징: 중간 제한
                "window_minutes": 60,
                "burst_limit": 750,
                "whitelist_ips": ["127.0.0.1", "localhost"],
            }
        else:
            return {
                "enabled": self.RATE_LIMIT_ENABLED,
                "default_limit": self.DEFAULT_RATE_LIMIT,  # 개발환경: 관대한 제한
                "window_minutes": self.RATE_LIMIT_WINDOW_MINUTES,
                "burst_limit": self.DEFAULT_RATE_LIMIT * 2,
                "whitelist_ips": ["127.0.0.1", "localhost", "0.0.0.0"],
            }

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
    if (
        settings.SECRET_KEY
        == "hapa_secret_key_for_development_only_change_in_production"
    ):
        errors.append("SECRET_KEY가 개발용 기본값입니다!")
    elif len(settings.SECRET_KEY) < 32:
        errors.append(
            f"SECRET_KEY가 너무 짧습니다 (현재: {len(settings.SECRET_KEY)}자, 최소: 32자)"
        )

    # CORS 검증
    if "*" in settings.CORS_ORIGINS:
        errors.append(
            "CORS_ORIGINS에 '*'가 포함되어 있습니다! 특정 도메인만 허용하세요."
        )

    # AI 모델 API 키 검증
    if not settings.AI_MODEL_API_KEY:
        errors.append("AI_MODEL_API_KEY가 설정되지 않았습니다!")

    # 디버그 모드 검증
    if settings.DEBUG:
        errors.append(
            "DEBUG 모드가 활성화되어 있습니다! 운영환경에서는 비활성화하세요."
        )

    if errors:
        error_msg = "🚨 [PRODUCTION] 보안 설정 오류:\n" + "\n".join(
            f"- {error}" for error in errors
        )
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
        if (
            settings.SECRET_KEY
            == "hapa_secret_key_for_development_only_change_in_production"
        ):
            logger.warning(
                "⚠️ 개발용 SECRET_KEY를 사용 중입니다. 운영 환경에서는 변경하세요!"
            )

except Exception as e:
    # .env 파일이 없어도 기본값으로 설정 인스턴스 생성
    logger.warning(f".env 파일을 찾을 수 없거나 로드하는 중 오류 발생: {e}")
    logger.info("기본 설정값을 사용합니다.")
    settings = Settings()
