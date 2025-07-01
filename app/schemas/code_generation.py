from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, root_validator, validator


class PythonSkillLevel(str, Enum):
    """Python 스킬 수준"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CodeOutputStructure(str, Enum):
    """코드 출력 구조"""

    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class ExplanationStyle(str, Enum):
    """설명 스타일"""

    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"
    EDUCATIONAL = "educational"


class ProjectContext(str, Enum):
    """프로젝트 컨텍스트"""

    WEB_DEVELOPMENT = "web_development"
    DATA_SCIENCE = "data_science"
    AUTOMATION = "automation"
    GENERAL_PURPOSE = "general_purpose"
    ACADEMIC = "academic"
    ENTERPRISE = "enterprise"


class ErrorHandlingPreference(str, Enum):
    """오류 처리 선호도"""

    MINIMAL = "minimal"
    BASIC = "basic"
    COMPREHENSIVE = "comprehensive"
    PRODUCTION_READY = "production_ready"


class PythonLanguageFeature(str, Enum):
    """Python 언어 기능"""

    TYPE_HINTS = "type_hints"
    DATACLASSES = "dataclasses"
    ASYNC_AWAIT = "async_await"
    COMPREHENSIONS = "comprehensions"
    GENERATORS = "generators"
    DECORATORS = "decorators"
    CONTEXT_MANAGERS = "context_managers"
    F_STRINGS = "f_strings"


class UserProfile(BaseModel):
    """사용자 프로필"""

    pythonSkillLevel: PythonSkillLevel = Field(
        default=PythonSkillLevel.INTERMEDIATE, description="Python 스킬 수준"
    )
    codeOutputStructure: CodeOutputStructure = Field(
        default=CodeOutputStructure.STANDARD, description="코드 출력 구조"
    )
    explanationStyle: ExplanationStyle = Field(
        default=ExplanationStyle.STANDARD, description="설명 스타일"
    )
    projectContext: ProjectContext = Field(
        default=ProjectContext.GENERAL_PURPOSE, description="프로젝트 컨텍스트"
    )
    errorHandlingPreference: ErrorHandlingPreference = Field(
        default=ErrorHandlingPreference.BASIC, description="오류 처리 선호도"
    )
    preferredLanguageFeatures: List[PythonLanguageFeature] = Field(
        default=[
            PythonLanguageFeature.TYPE_HINTS,
            PythonLanguageFeature.F_STRINGS],
        description="선호하는 Python 언어 기능",
    )


class ErrorResponse(BaseModel):
    """표준 오류 응답 모델"""

    status: str = Field("error", description="응답 상태 (항상 error)")
    error_message: str = Field(..., description="오류 메시지")
    error_code: Optional[str] = Field(None, description="오류 코드 (선택사항)")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="상세 오류 정보 (선택사항)"
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """상태 값은 항상 error여야 합니다."""
        return "error"


class ValidationErrorResponse(ErrorResponse):
    """유효성 검사 오류 응답 모델"""

    error_code: str = Field("VALIDATION_ERROR", description="유효성 검사 오류 코드")
    error_details: Dict[str, List[str]] = Field(
        ..., description="필드별 유효성 검사 오류 목록"
    )


class CodeComplexity(str, Enum):
    """코드 복잡도 레벨"""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    ADVANCED = "advanced"


class CodeLanguage(str, Enum):
    """지원되는 프로그래밍 언어"""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"


class StreamingChunkType(str, Enum):
    """스트리밍 청크 타입"""

    START = "start"
    TOKEN = "token"
    CODE = "code"
    EXPLANATION = "explanation"
    DONE = "done"
    ERROR = "error"


class ModelType(str, Enum):
    """HAPA에서 지원하는 코드 생성 모델 타입"""

    CODE_COMPLETION = "code_completion"  # 자동완성 → vLLM autocomplete
    CODE_GENERATION = "code_generation"  # 일반 생성 → vLLM prompt
    CODE_EXPLANATION = "code_explanation"  # 설명/주석 → vLLM comment
    CODE_REVIEW = "code_review"  # 리뷰 → vLLM comment
    BUG_FIX = "bug_fix"  # 버그 수정 → vLLM error_fix
    CODE_OPTIMIZATION = "code_optimization"  # 최적화 → vLLM prompt
    UNIT_TEST_GENERATION = "unit_test_generation"  # 테스트 → vLLM prompt
    DOCUMENTATION = "documentation"  # 문서화 → vLLM comment


class ProgrammingLevel(str, Enum):
    """프로그래밍 기술 수준"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ExplanationDetail(str, Enum):
    """설명 상세도"""

    MINIMAL = "minimal"  # 간단한 설명
    STANDARD = "standard"  # 표준 설명
    DETAILED = "detailed"  # 상세 설명
    COMPREHENSIVE = "comprehensive"  # 포괄적 설명


class CodeStyle(str, Enum):
    """코드 스타일"""

    CLEAN = "clean"  # 깔끔한 스타일
    PERFORMANCE = "performance"  # 성능 중심
    READABLE = "readable"  # 가독성 중심
    PYTHONIC = "pythonic"  # 파이썬 스타일


class CodeGenerationRequest(BaseModel):
    """vLLM 서버를 통한 코드 생성 요청"""

    # 핵심 요청 정보
    prompt: str = Field(
        ...,
        description="코드 생성 요청 내용 (한국어 또는 영어)",
        min_length=1,
        max_length=4000,
    )

    model_type: ModelType = Field(
        default=ModelType.CODE_GENERATION, description="사용할 모델 타입"
    )

    context: Optional[str] = Field(
        default="", description="추가 컨텍스트 또는 기존 코드", max_length=8000
    )

    # vLLM 서버 전용 매개변수
    temperature: Optional[float] = Field(
        default=0.3,
        description="생성 창의성 (0.0 = 결정적, 1.0 = 창의적)",
        ge=0.0,
        le=2.0,
    )

    top_p: Optional[float] = Field(
        default=0.95, description="다양성 제어 (0.0-1.0)", ge=0.0, le=1.0
    )

    max_tokens: Optional[int] = Field(
        default=1024, description="최대 토큰 수", ge=1, le=4096
    )

    # 사용자 선택 옵션 (vLLM user_select_options에 매핑됨)
    programming_level: Optional[ProgrammingLevel] = Field(
        default=ProgrammingLevel.INTERMEDIATE, description="프로그래밍 기술 수준"
    )

    explanation_detail: Optional[ExplanationDetail] = Field(
        default=ExplanationDetail.STANDARD, description="설명 상세도"
    )

    code_style: Optional[CodeStyle] = Field(
        default=CodeStyle.PYTHONIC, description="원하는 코드 스타일"
    )

    include_comments: Optional[bool] = Field(
        default=True, description="주석 포함 여부")

    include_docstring: Optional[bool] = Field(
        default=True, description="독스트링 포함 여부"
    )

    include_type_hints: Optional[bool] = Field(
        default=True, description="타입 힌트 포함 여부"
    )

    # 추가 메타데이터
    language: Optional[str] = Field(
        default="python", description="프로그래밍 언어 (현재는 Python만 지원)"
    )

    project_context: Optional[str] = Field(
        default="", description="프로젝트 컨텍스트 정보", max_length=500
    )

    @validator("prompt")
    def validate_prompt(cls, v):
        """프롬프트 검증"""
        if not v or not v.strip():
            raise ValueError("프롬프트는 비어있을 수 없습니다")
        return v.strip()

    @validator("context")
    def validate_context(cls, v):
        """컨텍스트 검증"""
        if v is None:
            return ""
        return v.strip()

    @validator("language")
    def validate_language(cls, v):
        """언어 검증"""
        if v and v.lower() not in ["python", "py"]:
            raise ValueError("현재는 Python만 지원합니다")
        return "python"


class CodeGenerationResponse(BaseModel):
    """vLLM 서버로부터의 코드 생성 응답"""

    success: bool = Field(..., description="요청 성공 여부")

    generated_code: str = Field(..., description="생성된 코드")

    explanation: Optional[str] = Field(default="", description="코드 설명")

    model_used: str = Field(
        ...,
        description="실제 사용된 vLLM 모델 타입 (autocomplete, prompt, comment, error_fix)",
    )

    processing_time: float = Field(default=0.0, description="처리 시간 (초)")

    token_usage: Dict[str, int] = Field(
        default_factory=dict, description="토큰 사용량 정보"
    )

    error_message: Optional[str] = Field(
        default="", description="오류 메시지 (success=False인 경우)"
    )

    # vLLM 특화 메타데이터
    translation_applied: Optional[bool] = Field(
        default=False, description="한국어→영어 번역이 적용되었는지 여부"
    )

    confidence_score: Optional[float] = Field(
        default=None, description="생성 품질 신뢰도 (0.0-1.0)", ge=0.0, le=1.0
    )

    # 응답 메타데이터
    timestamp: datetime = Field(
        default_factory=datetime.now, description="응답 생성 시간"
    )

    request_id: Optional[str] = Field(default="", description="요청 추적 ID")


class StreamingChunk(BaseModel):
    """스트리밍 응답의 개별 청크"""

    type: Literal["data", "error", "done"] = Field(..., description="청크 타입")

    content: str = Field(..., description="청크 내용")

    sequence: int = Field(..., description="청크 순서")

    timestamp: datetime = Field(
        default_factory=datetime.now, description="청크 생성 시간"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="추가 메타데이터"
    )


class VLLMHealthStatus(BaseModel):
    """vLLM 서버 상태 정보"""

    status: Literal["healthy", "unhealthy", "error"] = Field(
        ..., description="서버 상태"
    )

    available_models: List[str] = Field(
        default_factory=list, description="사용 가능한 모델 목록"
    )

    server_details: Dict[str, Any] = Field(
        default_factory=dict, description="서버 상세 정보"
    )

    response_time: Optional[float] = Field(
        default=None, description="상태 확인 응답 시간 (초)"
    )

    last_check: datetime = Field(
        default_factory=datetime.now, description="마지막 상태 확인 시간"
    )

    error_message: Optional[str] = Field(
        default="", description="오류 메시지 (status=error인 경우)"
    )


class ModelMappingInfo(BaseModel):
    """HAPA 모델과 vLLM 모델 간 매핑 정보"""

    hapa_model: ModelType = Field(..., description="HAPA 모델 타입")

    vllm_model: str = Field(..., description="대응하는 vLLM 모델 타입")

    translation_strategy: str = Field(
        ..., description="번역 전략 (none, full, comment_only)"
    )

    description: str = Field(..., description="모델 설명")

    recommended_use: List[str] = Field(
        default_factory=list, description="권장 사용 사례"
    )


class CodeGenerationStats(BaseModel):
    """코드 생성 통계 정보"""

    total_requests: int = Field(default=0, description="총 요청 수")

    successful_requests: int = Field(default=0, description="성공한 요청 수")

    average_response_time: float = Field(
        default=0.0, description="평균 응답 시간 (초)")

    model_usage: Dict[str, int] = Field(
        default_factory=dict, description="모델별 사용 횟수"
    )

    error_rate: float = Field(default=0.0, description="오류율 (0.0-1.0)")

    last_updated: datetime = Field(
        default_factory=datetime.now, description="마지막 업데이트 시간"
    )


# 이전 버전과의 호환성을 위한 별칭들
CompletionRequest = CodeGenerationRequest  # 기존 API 호환성
CompletionResponse = CodeGenerationResponse  # 기존 API 호환성


class StreamingGenerateRequest(BaseModel):
    """스트리밍 코드 생성 요청"""

    user_question: str = Field(
        ..., description="사용자 질문", min_length=1, max_length=2000
    )
    code_context: Optional[str] = Field(
        None, description="코드 컨텍스트", max_length=10000
    )
    language: str = Field(default="python", description="프로그래밍 언어")
    file_path: Optional[str] = Field(None, description="파일 경로")
    stream: bool = Field(default=True, description="스트리밍 여부")
    userProfile: Optional[UserProfile] = Field(None, description="사용자 프로필 정보")


class StreamingResponse(BaseModel):
    """스트리밍 응답 래퍼"""

    session_id: str = Field(..., description="세션 ID")
    total_chunks: Optional[int] = Field(None, description="전체 청크 수")
    completed: bool = Field(default=False, description="완료 여부")


class CodeValidationRequest(BaseModel):
    """코드 유효성 검사 요청 (강화된 검증)"""

    code: str = Field(...,
                      min_length=1,
                      max_length=50000,
                      description="검증할 코드")
    language: CodeLanguage = Field(CodeLanguage.PYTHON, description="코드 언어")
    strict_mode: bool = Field(False, description="엄격한 검증 모드")
    security_check: bool = Field(True, description="보안 검사 수행 여부")
    performance_check: bool = Field(True, description="성능 검사 수행 여부")

    @validator("code")
    def validate_code_content(cls, v):
        """코드 내용 기본 검증"""
        if not v or v.strip() == "":
            raise ValueError("코드는 비어있을 수 없습니다.")

        # 파일 크기 제한 (실제 바이트 크기)
        if len(v.encode("utf-8")) > 1024 * 1024:  # 1MB 제한
            raise ValueError("코드 크기가 1MB를 초과합니다.")

        return v.strip()


class CodeValidationResponse(BaseModel):
    """코드 유효성 검사 응답 (상세한 결과)"""

    is_valid: bool = Field(..., description="코드 유효성 여부")
    syntax_errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="문법 오류 목록"
    )
    security_issues: List[Dict[str, Any]] = Field(
        default_factory=list, description="보안 이슈 목록"
    )
    performance_warnings: List[Dict[str, Any]] = Field(
        default_factory=list, description="성능 경고 목록"
    )
    code_quality_score: float = Field(
        ..., ge=0.0, le=10.0, description="코드 품질 점수"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="개선 권장사항"
    )
    execution_safety: Literal["safe", "warning", "dangerous"] = Field(
        ..., description="실행 안전성 레벨"
    )
