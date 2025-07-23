from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class ErrorCategory(str, Enum):
    """오류 카테고리"""

    CLIENT_ERROR = "client_error"  # 클라이언트 측 오류 (4xx)
    SERVER_ERROR = "server_error"  # 서버 측 오류 (5xx)
    VALIDATION_ERROR = "validation_error"  # 유효성 검사 오류
    BUSINESS_ERROR = "business_error"  # 비즈니스 로직 오류
    EXTERNAL_ERROR = "external_error"  # 외부 서비스 오류


class ErrorSeverity(str, Enum):
    """오류 심각도"""

    LOW = "low"  # 경고 수준 (서비스 정상 동작)
    MEDIUM = "medium"  # 일부 기능 제한
    HIGH = "high"  # 중요 기능 영향
    CRITICAL = "critical"  # 서비스 중단 위험


class RecoveryAction(str, Enum):
    """복구 액션"""

    RETRY = "retry"  # 재시도
    CONTACT_SUPPORT = "contact_support"  # 지원팀 문의
    CHECK_SETTINGS = "check_settings"  # 설정 확인
    UPDATE_INPUT = "update_input"  # 입력 수정
    RESTART_SERVICE = "restart_service"  # 서비스 재시작
    WAIT_AND_RETRY = "wait_and_retry"  # 대기 후 재시도


class StandardErrorCode(str, Enum):
    """표준 오류 코드"""

    # Client Errors (4xx)
    INVALID_REQUEST = "E4001"  # 잘못된 요청
    INVALID_PARAMETERS = "E4002"  # 잘못된 파라미터
    MISSING_REQUIRED_FIELD = "E4003"  # 필수 필드 누락
    INVALID_FORMAT = "E4004"  # 잘못된 형식
    UNAUTHORIZED = "E4011"  # 인증 실패
    FORBIDDEN = "E4031"  # 권한 부족
    RESOURCE_NOT_FOUND = "E4041"  # 리소스 없음
    CONFLICT = "E4091"  # 리소스 충돌
    RATE_LIMIT_EXCEEDED = "E4291"  # 요청 한도 초과

    # Server Errors (5xx)
    INTERNAL_SERVER_ERROR = "E5001"  # 내부 서버 오류
    DATABASE_ERROR = "E5002"  # 데이터베이스 오류
    EXTERNAL_API_ERROR = "E5003"  # 외부 API 오류
    SERVICE_UNAVAILABLE = "E5031"  # 서비스 불가
    TIMEOUT_ERROR = "E5041"  # 시간 초과

    # Validation Errors (V)
    VALIDATION_FAILED = "V1001"  # 유효성 검사 실패
    SCHEMA_VALIDATION_ERROR = "V1002"  # 스키마 검증 오류
    TYPE_MISMATCH = "V1003"  # 타입 불일치
    RANGE_VIOLATION = "V1004"  # 범위 위반

    # Business Logic Errors (B)
    BUSINESS_RULE_VIOLATION = "B2001"  # 비즈니스 규칙 위반
    INSUFFICIENT_RESOURCES = "B2002"  # 리소스 부족
    OPERATION_NOT_ALLOWED = "B2003"  # 허용되지 않는 작업


class ErrorContext(BaseModel):
    """오류 컨텍스트 정보"""

    user_id: Optional[str] = Field(None, description="사용자 ID")
    session_id: Optional[str] = Field(None, description="세션 ID")
    request_id: Optional[str] = Field(None, description="요청 ID")
    endpoint: Optional[str] = Field(None, description="API 엔드포인트")
    method: Optional[str] = Field(None, description="HTTP 메서드")
    user_agent: Optional[str] = Field(None, description="사용자 에이전트")
    ip_address: Optional[str] = Field(None, description="IP 주소")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="발생 시간")
    trace_id: Optional[str] = Field(None, description="분산 추적 ID")


class RecoveryGuide(BaseModel):
    """오류 복구 가이드"""

    actions: List[RecoveryAction] = Field(..., description="권장 복구 액션")
    user_message: str = Field(..., description="사용자 친화적 메시지")
    developer_message: Optional[str] = Field(None, description="개발자용 메시지")
    documentation_url: Optional[str] = Field(None, description="문서 링크")
    retry_after: Optional[int] = Field(None, description="재시도 권장 시간(초)")
    max_retries: Optional[int] = Field(None, description="최대 재시도 횟수")


class EnhancedErrorResponse(BaseModel):
    """강화된 오류 응답 모델"""

    # 기본 오류 정보
    status: Literal["error"] = Field("error", description="응답 상태")
    error_code: StandardErrorCode = Field(..., description="표준 오류 코드")
    error_message: str = Field(..., description="오류 메시지")

    # 오류 분류 정보
    category: ErrorCategory = Field(..., description="오류 카테고리")
    severity: ErrorSeverity = Field(..., description="오류 심각도")

    # 상세 정보
    details: Optional[Dict[str, Any]] = Field(None, description="상세 오류 정보")
    field_errors: Optional[Dict[str, List[str]]] = Field(
        None, description="필드별 오류"
    )

    # 컨텍스트 정보
    context: Optional[ErrorContext] = Field(None, description="오류 발생 컨텍스트")

    # 복구 가이드
    recovery_guide: Optional[RecoveryGuide] = Field(None, description="복구 가이드")

    # 메타데이터
    timestamp: datetime = Field(
        default_factory=datetime.now, description="응답 생성 시간"
    )
    correlation_id: Optional[str] = Field(None, description="상관관계 ID")

    @field_validator("error_message")
    @classmethod
    def validate_error_message(cls, v):
        """오류 메시지 검증"""
        if not v or len(v.strip()) < 5:
            raise ValueError("오류 메시지는 최소 5자 이상이어야 합니다.")
        return v.strip()


class ValidationErrorDetail(BaseModel):
    """유효성 검사 오류 상세 정보"""

    field: str = Field(..., description="오류 발생 필드")
    value: Any = Field(..., description="입력된 값")
    constraint: str = Field(..., description="위반된 제약 조건")
    message: str = Field(..., description="오류 메시지")
    suggestion: Optional[str] = Field(None, description="수정 제안")


class ClientErrorResponse(EnhancedErrorResponse):
    """클라이언트 오류 응답 (4xx)"""

    category: Literal[ErrorCategory.CLIENT_ERROR] = ErrorCategory.CLIENT_ERROR
    validation_errors: Optional[List[ValidationErrorDetail]] = Field(
        None, description="유효성 검사 오류 목록"
    )

    @field_validator("error_code")
    @classmethod
    def validate_client_error_code(cls, v):
        """클라이언트 오류 코드 검증"""
        if not v.value.startswith("E4") and not v.value.startswith("V"):
            raise ValueError(
                "클라이언트 오류는 E4xxx 또는 Vxxx 코드를 사용해야 합니다."
            )
        return v


class ServerErrorResponse(EnhancedErrorResponse):
    """서버 오류 응답 (5xx)"""

    category: Literal[ErrorCategory.SERVER_ERROR] = ErrorCategory.SERVER_ERROR
    debug_info: Optional[Dict[str, Any]] = Field(
        None, description="디버그 정보 (개발 환경만)"
    )
    incident_id: Optional[str] = Field(None, description="인시던트 ID")

    @field_validator("error_code")
    @classmethod
    def validate_server_error_code(cls, v):
        """서버 오류 코드 검증"""
        if not v.value.startswith("E5") and not v.value.startswith("B"):
            raise ValueError("서버 오류는 E5xxx 또는 Bxxx 코드를 사용해야 합니다.")
        return v


class ErrorPattern(BaseModel):
    """오류 패턴 분석"""

    error_code: StandardErrorCode = Field(..., description="오류 코드")
    count: int = Field(..., description="발생 횟수")
    first_seen: datetime = Field(..., description="최초 발생 시간")
    last_seen: datetime = Field(..., description="최근 발생 시간")
    affected_users: int = Field(..., description="영향받은 사용자 수")
    avg_resolution_time: Optional[float] = Field(
        None, description="평균 해결 시간(초)")


class ErrorSummary(BaseModel):
    """오류 요약 통계"""

    total_errors: int = Field(..., description="총 오류 수")
    client_errors: int = Field(..., description="클라이언트 오류 수")
    server_errors: int = Field(..., description="서버 오류 수")
    validation_errors: int = Field(..., description="유효성 검사 오류 수")
    critical_errors: int = Field(..., description="심각한 오류 수")
    patterns: List[ErrorPattern] = Field(..., description="오류 패턴 목록")
    time_range: str = Field(..., description="분석 시간 범위")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="생성 시간"
    )
