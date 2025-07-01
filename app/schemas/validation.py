from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """검증 상태"""

    VALID = "valid"  # 유효한 코드
    INVALID = "invalid"  # 문법 오류
    WARNING = "warning"  # 경고 있음
    EXECUTABLE = "executable"  # 실행 가능
    ERROR = "error"  # 검증 실패


class ValidationSeverity(str, Enum):
    """검증 오류 심각도"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationIssue(BaseModel):
    """검증 이슈 모델"""

    line_number: int = Field(..., description="오류 발생 라인 번호", ge=1)
    column_number: Optional[int] = Field(None, description="오류 발생 컬럼 번호", ge=0)
    severity: ValidationSeverity = Field(..., description="오류 심각도")
    issue_type: str = Field(..., description="이슈 유형", max_length=100)
    message: str = Field(..., description="오류 메시지", max_length=500)
    suggestion: Optional[str] = Field(
        None, description="수정 제안", max_length=300)

    class Config:
        json_schema_extra = {
            "example": {
                "line_number": 5,
                "column_number": 12,
                "severity": "error",
                "issue_type": "SyntaxError",
                "message": "invalid syntax",
                "suggestion": "함수 정의에서 콜론(:)이 누락되었습니다.",
            }
        }


class CodeValidationRequest(BaseModel):
    """코드 검증 요청 모델"""

    code: str = Field(..., description="검증할 코드",
                      min_length=1, max_length=10000)
    language: str = Field(
        "python",
        description="프로그래밍 언어",
        pattern="^(python|javascript|typescript|java|cpp|csharp)$",
    )
    file_name: Optional[str] = Field(None, description="파일명", max_length=255)
    check_execution: bool = Field(True, description="실행 가능성 검사 여부")
    check_style: bool = Field(False, description="코딩 스타일 검사 여부")

    # 메타데이터
    session_id: Optional[str] = Field(
        None, description="세션 ID", max_length=100)
    context: Optional[str] = Field(
        None, description="코드 컨텍스트", max_length=2000)

    class Config:
        json_schema_extra = {
            "example": {
                "code": "def hello_world():\n    print('Hello, World!')",
                "language": "python",
                "file_name": "test.py",
                "check_execution": True,
                "check_style": False,
                "session_id": "session_123",
            }
        }


class CodeValidationResponse(BaseModel):
    """코드 검증 응답 모델"""

    validation_id: str = Field(..., description="검증 ID")
    status: ValidationStatus = Field(..., description="전체 검증 상태")
    is_valid: bool = Field(..., description="코드 유효성")
    is_executable: bool = Field(..., description="실행 가능성")

    # 검증 결과
    issues: List[ValidationIssue] = Field(default=[], description="발견된 이슈 목록")
    total_issues: int = Field(..., description="총 이슈 개수")
    error_count: int = Field(..., description="오류 개수")
    warning_count: int = Field(..., description="경고 개수")

    # 코드 분석 결과
    lines_of_code: int = Field(..., description="코드 라인 수")
    cyclomatic_complexity: Optional[int] = Field(None, description="순환 복잡도")
    functions_count: int = Field(0, description="함수 개수")
    classes_count: int = Field(0, description="클래스 개수")

    # 실행 결과 (safe execution)
    execution_result: Optional[str] = Field(None, description="안전 실행 결과")
    execution_error: Optional[str] = Field(None, description="실행 오류")
    execution_time: Optional[float] = Field(None, description="실행 시간 (초)")

    # 메타데이터
    validation_time: float = Field(..., description="검증 소요 시간 (초)")
    timestamp: datetime = Field(..., description="검증 시간")

    class Config:
        json_schema_extra = {
            "example": {
                "validation_id": "val_001",
                "status": "valid",
                "is_valid": True,
                "is_executable": True,
                "issues": [],
                "total_issues": 0,
                "error_count": 0,
                "warning_count": 0,
                "lines_of_code": 2,
                "functions_count": 1,
                "classes_count": 0,
                "execution_result": "Hello, World!",
                "validation_time": 0.15,
                "timestamp": "2025-01-10T10:30:00Z",
            }
        }


class BatchValidationRequest(BaseModel):
    """배치 코드 검증 요청 모델"""

    code_snippets: List[Dict[str, Any]] = Field(
        ..., description="검증할 코드 스니펫 목록", min_length=1, max_length=10
    )
    common_language: str = Field("python", description="공통 프로그래밍 언어")
    session_id: Optional[str] = Field(None, description="세션 ID")

    class Config:
        json_schema_extra = {
            "example": {
                "code_snippets": [
                    {"id": "1", "code": "def func1(): pass"},
                    {"id": "2", "code": "class MyClass: pass"},
                ],
                "common_language": "python",
                "session_id": "session_123",
            }
        }


class BatchValidationResponse(BaseModel):
    """배치 코드 검증 응답 모델"""

    batch_id: str = Field(..., description="배치 검증 ID")
    total_snippets: int = Field(..., description="총 코드 스니펫 수")
    valid_count: int = Field(..., description="유효한 코드 수")
    invalid_count: int = Field(..., description="무효한 코드 수")
    results: List[CodeValidationResponse] = Field(..., description="개별 검증 결과")
    total_validation_time: float = Field(..., description="총 검증 시간 (초)")
    timestamp: datetime = Field(..., description="배치 검증 시간")


class ValidationStats(BaseModel):
    """검증 통계 모델"""

    total_validations: int = Field(..., description="총 검증 수")
    valid_code_count: int = Field(..., description="유효한 코드 수")
    invalid_code_count: int = Field(..., description="무효한 코드 수")
    average_validation_time: float = Field(..., description="평균 검증 시간 (초)")
    most_common_issues: List[str] = Field(..., description="가장 흔한 이슈 유형")
    language_distribution: Dict[str, int] = Field(..., description="언어별 검증 수")

    class Config:
        json_schema_extra = {
            "example": {
                "total_validations": 500,
                "valid_code_count": 450,
                "invalid_code_count": 50,
                "average_validation_time": 0.23,
                "most_common_issues": [
                    "SyntaxError",
                    "NameError",
                    "IndentationError"],
                "language_distribution": {
                    "python": 480,
                    "javascript": 20},
            }}


# 에러 응답 모델
class ValidationErrorResponse(BaseModel):
    """검증 에러 응답 모델"""

    error_message: str = Field(..., description="에러 메시지")
    error_code: str = Field(..., description="에러 코드")
    validation_id: Optional[str] = Field(None, description="검증 ID")
    error_details: Optional[dict] = Field(None, description="상세 에러 정보")
