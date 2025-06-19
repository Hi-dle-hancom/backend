from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from enum import Enum

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
    pythonSkillLevel: PythonSkillLevel = Field(default=PythonSkillLevel.INTERMEDIATE, description="Python 스킬 수준")
    codeOutputStructure: CodeOutputStructure = Field(default=CodeOutputStructure.STANDARD, description="코드 출력 구조")
    explanationStyle: ExplanationStyle = Field(default=ExplanationStyle.STANDARD, description="설명 스타일")
    projectContext: ProjectContext = Field(default=ProjectContext.GENERAL_PURPOSE, description="프로젝트 컨텍스트")
    errorHandlingPreference: ErrorHandlingPreference = Field(default=ErrorHandlingPreference.BASIC, description="오류 처리 선호도")
    preferredLanguageFeatures: List[PythonLanguageFeature] = Field(default=[PythonLanguageFeature.TYPE_HINTS, PythonLanguageFeature.F_STRINGS], description="선호하는 Python 언어 기능")

class ErrorResponse(BaseModel):
    """표준 오류 응답 모델"""
    status: str = Field("error", description="응답 상태 (항상 error)")
    error_message: str = Field(..., description="오류 메시지")
    error_code: Optional[str] = Field(None, description="오류 코드 (선택사항)")
    error_details: Optional[Dict[str, Any]] = Field(None, description="상세 오류 정보 (선택사항)")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """상태 값은 항상 error여야 합니다."""
        return "error"

class ValidationErrorResponse(ErrorResponse):
    """유효성 검사 오류 응답 모델"""
    error_code: str = Field("VALIDATION_ERROR", description="유효성 검사 오류 코드")
    error_details: Dict[str, List[str]] = Field(..., description="필드별 유효성 검사 오류 목록")

class CodeGenerationRequest(BaseModel):
    """코드 생성 요청 모델"""
    user_question: str = Field(..., min_length=1, max_length=10000, description="사용자가 요청한 질문 또는 코드 생성 요청")
    code_context: Optional[str] = Field(None, max_length=50000, description="현재 편집 중인 코드 컨텍스트")
    language: Optional[str] = Field("python", description="프로그래밍 언어 (현재 Python만 지원)")
    file_path: Optional[str] = Field(None, max_length=1000, description="현재 편집 중인 파일 경로")
    userProfile: Optional[UserProfile] = Field(None, description="사용자 프로필 정보")
    
    @field_validator('user_question')
    @classmethod
    def validate_user_question(cls, v):
        """사용자 질문 유효성 검사"""
        if not v or not v.strip():
            raise ValueError('사용자 질문은 비어있을 수 없습니다.')
        return v.strip()
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        """프로그래밍 언어 유효성 검사"""
        if v is None:
            return "python"  # 기본값 설정
        
        v = v.strip().lower()
        if v != "python":
            raise ValueError('현재 Python 언어만 지원됩니다.')
        
        return v
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """파일 경로 유효성 검사"""
        if v is None:
            return None
        
        v = v.strip()
        if not v:
            return None
            
        # 기본적인 파일 경로 형식 검사
        invalid_chars = ['<', '>', '|', '*', '?']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'파일 경로에 유효하지 않은 문자가 포함되어 있습니다: {char}')
        
        # Python 파일 확장자 권장 (필수는 아님)
        if v and not v.endswith('.py'):
            # 경고만 로그에 남기고 허용
            pass
        
        return v

class CodeGenerationResponse(BaseModel):
    """코드 생성 응답 모델"""
    generated_code: str = Field(..., description="생성된 Python 코드")
    explanation: Optional[str] = Field(None, description="생성된 코드에 대한 설명")
    status: str = Field("success", description="응답 상태 (success 또는 error)")
    error_message: Optional[str] = Field(None, description="오류 발생 시 오류 메시지")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """상태 값 유효성 검사"""
        if v not in ['success', 'error']:
            raise ValueError('상태는 success 또는 error여야 합니다.')
        return v

class CompletionRequest(BaseModel):
    """코드 완성 요청 모델"""
    prefix: str = Field(..., min_length=1, max_length=5000, description="완성을 위한 Python 코드 접두사")
    language: str = Field("python", description="프로그래밍 언어 (Python 고정)")
    cursor_position: Optional[int] = Field(None, ge=0, description="현재 커서 위치")
    file_path: Optional[str] = Field(None, max_length=1000, description="현재 편집 중인 파일 경로")
    
    @field_validator('prefix')
    @classmethod
    def validate_prefix(cls, v):
        """코드 접두사 유효성 검사"""
        if not v or not v.strip():
            raise ValueError('코드 접두사는 비어있을 수 없습니다.')
        return v.strip()
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        """프로그래밍 언어 유효성 검사"""
        if not v or not v.strip():
            v = "python"  # 기본값 설정
        
        v = v.strip().lower()
        if v != "python":
            raise ValueError('현재 Python 언어만 지원됩니다.')
        
        return v
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """파일 경로 유효성 검사"""
        if v is None:
            return None
        
        v = v.strip()
        if not v:
            return None
            
        # 기본적인 파일 경로 형식 검사
        invalid_chars = ['<', '>', '|', '*', '?']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'파일 경로에 유효하지 않은 문자가 포함되어 있습니다: {char}')
        
        return v

class CompletionResponse(BaseModel):
    """코드 완성 응답 모델"""
    completions: List[str] = Field(..., description="제안된 Python 코드 완성 목록")
    status: str = Field("success", description="응답 상태")
    error_message: Optional[str] = Field(None, description="오류 발생 시 오류 메시지")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """상태 값 유효성 검사"""
        if v not in ['success', 'error']:
            raise ValueError('상태는 success 또는 error여야 합니다.')
        return v
    
    @field_validator('completions')
    @classmethod
    def validate_completions(cls, v):
        """코드 완성 제안 유효성 검사"""
        if not isinstance(v, list):
            raise ValueError('completions는 리스트여야 합니다.')
        
        # 빈 리스트도 허용 (오류 상황에서 발생할 수 있음)
        if len(v) > 10:  # 최대 10개 제한
            raise ValueError('코드 완성 제안은 최대 10개까지만 허용됩니다.')
        
        return v

class StreamingGenerateRequest(BaseModel):
    """스트리밍 코드 생성 요청"""
    user_question: str = Field(..., description="사용자 질문", min_length=1, max_length=2000)
    code_context: Optional[str] = Field(None, description="코드 컨텍스트", max_length=10000)
    language: str = Field(default="python", description="프로그래밍 언어")
    file_path: Optional[str] = Field(None, description="파일 경로")
    stream: bool = Field(default=True, description="스트리밍 여부")
    userProfile: Optional[UserProfile] = Field(None, description="사용자 프로필 정보")

class StreamingChunk(BaseModel):
    """스트리밍 응답 청크"""
    type: str = Field(..., description="청크 타입: 'token', 'code', 'explanation', 'done'")
    content: str = Field(..., description="청크 내용")
    timestamp: datetime = Field(default_factory=datetime.now, description="타임스탬프")
    sequence: int = Field(..., description="순서 번호")

class StreamingResponse(BaseModel):
    """스트리밍 응답 래퍼"""
    session_id: str = Field(..., description="세션 ID")
    total_chunks: Optional[int] = Field(None, description="전체 청크 수")
    completed: bool = Field(default=False, description="완료 여부") 