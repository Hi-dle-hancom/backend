from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum

class ConversationType(str, Enum):
    """대화 유형"""
    QUESTION = "question"      # 사용자 질문
    ANSWER = "answer"          # AI 응답
    FEEDBACK = "feedback"      # 피드백
    ERROR = "error"           # 오류
    SYSTEM = "system"         # 시스템 메시지

class ConversationStatus(str, Enum):
    """대화 상태"""
    ACTIVE = "active"         # 활성 세션
    COMPLETED = "completed"   # 완료된 세션
    PAUSED = "paused"        # 일시 정지
    ARCHIVED = "archived"    # 보관됨
    DELETED = "deleted"      # 삭제됨

class ConversationEntry(BaseModel):
    """대화 엔트리 모델"""
    entry_id: str = Field(..., description="엔트리 고유 ID", max_length=50)
    session_id: str = Field(..., description="세션 ID", max_length=100)
    conversation_type: ConversationType = Field(..., description="대화 유형")
    content: str = Field(..., description="대화 내용", max_length=10000)
    
    # 메타데이터
    language: Optional[str] = Field(None, description="프로그래밍 언어", max_length=50)
    code_snippet: Optional[str] = Field(None, description="관련 코드 스니펫", max_length=5000)
    file_name: Optional[str] = Field(None, description="파일명", max_length=255)
    line_number: Optional[int] = Field(None, description="라인 번호", ge=1)
    
    # 응답 관련 (AI 응답일 경우)
    response_time: Optional[float] = Field(None, description="응답 시간 (초)", ge=0)
    confidence_score: Optional[float] = Field(None, description="신뢰도 점수 (0-1)", ge=0, le=1)
    
    # 타임스탬프
    timestamp: datetime = Field(..., description="생성 시간")
    updated_at: Optional[datetime] = Field(None, description="수정 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "entry_id": "entry_001",
                "session_id": "session_123",
                "conversation_type": "question",
                "content": "파이썬에서 리스트를 정렬하는 함수를 만들어주세요",
                "language": "python",
                "code_snippet": None,
                "file_name": "main.py",
                "line_number": 10,
                "timestamp": "2025-01-10T10:30:00Z"
            }
        }

class ConversationSession(BaseModel):
    """대화 세션 모델"""
    session_id: str = Field(..., description="세션 고유 ID", max_length=100)
    session_title: Optional[str] = Field(None, description="세션 제목", max_length=200)
    status: ConversationStatus = Field(..., description="세션 상태")
    
    # 세션 통계
    total_entries: int = Field(0, description="총 대화 엔트리 수", ge=0)
    question_count: int = Field(0, description="질문 수", ge=0)
    answer_count: int = Field(0, description="답변 수", ge=0)
    
    # 세션 메타데이터
    primary_language: Optional[str] = Field(None, description="주요 프로그래밍 언어")
    tags: List[str] = Field(default=[], description="태그 목록")
    project_name: Optional[str] = Field(None, description="프로젝트명", max_length=100)
    
    # 타임스탬프
    created_at: datetime = Field(..., description="세션 생성 시간")
    updated_at: datetime = Field(..., description="세션 수정 시간")
    last_activity: datetime = Field(..., description="마지막 활동 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "session_title": "Python 리스트 정렬 구현",
                "status": "active",
                "total_entries": 8,
                "question_count": 4,
                "answer_count": 4,
                "primary_language": "python",
                "tags": ["sorting", "algorithm", "python"],
                "project_name": "my-project",
                "created_at": "2025-01-10T10:00:00Z",
                "updated_at": "2025-01-10T11:00:00Z",
                "last_activity": "2025-01-10T11:00:00Z"
            }
        }

class HistoryCreateRequest(BaseModel):
    """히스토리 생성 요청 모델"""
    session_id: str = Field(..., description="세션 ID", min_length=1, max_length=100)
    conversation_type: ConversationType = Field(..., description="대화 유형")
    content: str = Field(..., description="대화 내용", min_length=1, max_length=10000)
    
    # 선택적 메타데이터
    language: Optional[str] = Field(None, description="프로그래밍 언어")
    code_snippet: Optional[str] = Field(None, description="관련 코드 스니펫")
    file_name: Optional[str] = Field(None, description="파일명")
    line_number: Optional[int] = Field(None, description="라인 번호", ge=1)
    response_time: Optional[float] = Field(None, description="응답 시간 (초)")
    confidence_score: Optional[float] = Field(None, description="신뢰도 점수", ge=0, le=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "conversation_type": "question",
                "content": "파이썬에서 리스트를 정렬하는 함수를 만들어주세요",
                "language": "python",
                "file_name": "main.py",
                "line_number": 10
            }
        }

class HistoryResponse(BaseModel):
    """히스토리 응답 모델"""
    success: bool = Field(..., description="요청 성공 여부")
    entry_id: Optional[str] = Field(None, description="생성된 엔트리 ID")
    session_id: str = Field(..., description="세션 ID")
    message: str = Field(..., description="응답 메시지")
    timestamp: datetime = Field(..., description="처리 시간")

class SessionCreateRequest(BaseModel):
    """세션 생성 요청 모델"""
    session_title: Optional[str] = Field(None, description="세션 제목", max_length=200)
    primary_language: Optional[str] = Field(None, description="주요 프로그래밍 언어")
    tags: List[str] = Field(default=[], description="태그 목록", max_length=10)
    project_name: Optional[str] = Field(None, description="프로젝트명", max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_title": "Python 리스트 정렬 구현",
                "primary_language": "python",
                "tags": ["sorting", "algorithm"],
                "project_name": "my-project"
            }
        }

class SessionUpdateRequest(BaseModel):
    """세션 수정 요청 모델"""
    session_title: Optional[str] = Field(None, description="세션 제목", max_length=200)
    status: Optional[ConversationStatus] = Field(None, description="세션 상태")
    primary_language: Optional[str] = Field(None, description="주요 프로그래밍 언어")
    tags: Optional[List[str]] = Field(None, description="태그 목록", max_length=10)
    project_name: Optional[str] = Field(None, description="프로젝트명", max_length=100)

class HistoryStats(BaseModel):
    """히스토리 통계 모델"""
    total_sessions: int = Field(..., description="총 세션 수")
    active_sessions: int = Field(..., description="활성 세션 수")
    total_entries: int = Field(..., description="총 대화 엔트리 수")
    total_questions: int = Field(..., description="총 질문 수")
    total_answers: int = Field(..., description="총 답변 수")
    
    # 언어별 분포
    language_distribution: Dict[str, int] = Field(..., description="언어별 세션 수")
    
    # 활동 통계
    sessions_today: int = Field(..., description="오늘 생성된 세션 수")
    sessions_this_week: int = Field(..., description="이번 주 생성된 세션 수")
    average_session_length: float = Field(..., description="평균 세션 길이 (대화 수)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_sessions": 25,
                "active_sessions": 8,
                "total_entries": 150,
                "total_questions": 75,
                "total_answers": 75,
                "language_distribution": {"python": 15, "javascript": 10},
                "sessions_today": 3,
                "sessions_this_week": 12,
                "average_session_length": 6.0
            }
        }

class HistorySearchRequest(BaseModel):
    """히스토리 검색 요청 모델"""
    query: str = Field(..., description="검색 쿼리", min_length=1, max_length=100)
    session_ids: Optional[List[str]] = Field(None, description="검색할 세션 ID 목록")
    language: Optional[str] = Field(None, description="언어 필터")
    conversation_type: Optional[ConversationType] = Field(None, description="대화 유형 필터")
    date_from: Optional[datetime] = Field(None, description="시작 날짜")
    date_to: Optional[datetime] = Field(None, description="종료 날짜")
    limit: int = Field(20, description="검색 결과 제한", ge=1, le=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "정렬 알고리즘",
                "language": "python",
                "conversation_type": "question",
                "limit": 10
            }
        }

# 에러 응답 모델
class HistoryErrorResponse(BaseModel):
    """히스토리 에러 응답 모델"""
    error_message: str = Field(..., description="에러 메시지")
    error_code: str = Field(..., description="에러 코드")
    session_id: Optional[str] = Field(None, description="관련 세션 ID")
    error_details: Optional[dict] = Field(None, description="상세 에러 정보") 