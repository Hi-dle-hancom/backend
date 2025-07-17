from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class FeedbackType(str, Enum):
    """피드백 유형"""

    LIKE = "like"  # 좋아요
    DISLIKE = "dislike"  # 싫어요
    RATING = "rating"  # 별점 평가
    COMMENT = "comment"  # 텍스트 코멘트
    BUG_REPORT = "bug_report"  # 버그 신고


class FeedbackRequest(BaseModel):
    """피드백 요청 모델"""

    feedback_type: FeedbackType = Field(..., description="피드백 유형")
    session_id: str = Field(..., description="세션 ID",
                            min_length=1, max_length=100)
    question_id: str = Field(..., description="질문 ID",
                             min_length=1, max_length=100)
    response_id: str = Field(..., description="응답 ID",
                             min_length=1, max_length=100)

    # 피드백 내용
    rating: Optional[int] = Field(None, description="별점 (1-5)", ge=1, le=5)
    comment: Optional[str] = Field(
        None, description="텍스트 코멘트", max_length=1000)

    # 메타데이터
    user_agent: Optional[str] = Field(None, description="사용자 에이전트")
    platform: Optional[str] = Field(None, description="플랫폼 (vscode, web)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "feedback_type": "rating",
                "session_id": "session_123",
                "question_id": "q_456",
                "response_id": "r_789",
                "rating": 5,
                "comment": "매우 유용한 코드였습니다!",
                "platform": "vscode",
            }
        }
    )


class FeedbackResponse(BaseModel):
    """피드백 응답 모델"""

    success: bool = Field(..., description="피드백 저장 성공 여부")
    feedback_id: str = Field(..., description="생성된 피드백 ID")
    message: str = Field(..., description="응답 메시지")
    timestamp: datetime = Field(..., description="피드백 생성 시간")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "feedback_id": "fb_001",
                "message": "피드백이 성공적으로 저장되었습니다.",
                "timestamp": "2025-01-10T10:30:00Z",
            }
        }
    )


class FeedbackStats(BaseModel):
    """피드백 통계 모델"""

    total_feedback: int = Field(..., description="총 피드백 수", ge=0)
    like_count: int = Field(..., description="좋아요 수", ge=0)
    dislike_count: int = Field(..., description="싫어요 수", ge=0)
    average_rating: Optional[float] = Field(None, description="평균 별점", ge=0.0, le=5.0)
    comment_count: int = Field(..., description="코멘트 수", ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_feedback": 150,
                "like_count": 120,
                "dislike_count": 30,
                "average_rating": 4.2,
                "comment_count": 85,
            }
        }
    )


# 에러 응답 모델
class FeedbackErrorResponse(BaseModel):
    """피드백 에러 응답 모델"""

    error_message: str = Field(..., description="에러 메시지")
    error_code: str = Field(..., description="에러 코드")
    error_details: Optional[dict] = Field(None, description="상세 에러 정보")
