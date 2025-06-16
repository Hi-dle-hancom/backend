from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Dict, Any
import logging
from app.schemas.feedback import (
    FeedbackRequest, 
    FeedbackResponse, 
    FeedbackStats, 
    FeedbackErrorResponse
)
from app.services.feedback_service import feedback_service

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

@router.post("/submit", response_model=FeedbackResponse, summary="피드백 제출")
async def submit_feedback(feedback: FeedbackRequest):
    """
    사용자 피드백을 제출합니다.
    
    - **feedback_type**: 피드백 유형 (like, dislike, rating, comment, bug_report)
    - **session_id**: 세션 ID (1-100자)
    - **question_id**: 질문 ID (1-100자)
    - **response_id**: 응답 ID (1-100자)
    - **rating**: 별점 (1-5, rating 타입일 때 필수)
    - **comment**: 텍스트 코멘트 (최대 1000자)
    - **platform**: 플랫폼 정보 (vscode, web 등)
    """
    try:
        logger.info(f"피드백 제출 요청: {feedback.feedback_type} - {feedback.session_id}")
        
        # 피드백 유형별 유효성 검사
        if feedback.feedback_type == "rating" and feedback.rating is None:
            raise HTTPException(
                status_code=400,
                detail="별점 피드백에는 rating 값이 필요합니다."
            )
        
        if feedback.feedback_type == "comment" and not feedback.comment:
            raise HTTPException(
                status_code=400,
                detail="코멘트 피드백에는 comment 값이 필요합니다."
            )
        
        # 피드백 저장
        result = feedback_service.save_feedback(feedback)
        
        logger.info(f"피드백 저장 성공: {result.feedback_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"피드백 제출 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"피드백 제출에 실패했습니다: {str(e)}"
        )

@router.get("/stats", response_model=FeedbackStats, summary="피드백 통계 조회")
async def get_feedback_stats():
    """
    전체 피드백 통계를 조회합니다.
    
    Returns:
        - **total_feedback**: 총 피드백 수
        - **like_count**: 좋아요 수
        - **dislike_count**: 싫어요 수
        - **average_rating**: 평균 별점
        - **comment_count**: 코멘트 수
    """
    try:
        logger.info("피드백 통계 조회 요청")
        
        stats = feedback_service.get_feedback_stats()
        
        logger.info(f"피드백 통계 조회 성공: 총 {stats.total_feedback}개")
        return stats
        
    except Exception as e:
        logger.error(f"피드백 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"피드백 통계 조회에 실패했습니다: {str(e)}"
        )

@router.get("/session/{session_id}", summary="세션별 피드백 조회")
async def get_feedback_by_session(
    session_id: str = Path(..., description="조회할 세션 ID", min_length=1, max_length=100)
) -> List[Dict[str, Any]]:
    """
    특정 세션의 모든 피드백을 조회합니다.
    
    Args:
        session_id: 조회할 세션 ID
        
    Returns:
        해당 세션의 피드백 리스트
    """
    try:
        logger.info(f"세션별 피드백 조회 요청: {session_id}")
        
        feedback_list = feedback_service.get_feedback_by_session(session_id)
        
        logger.info(f"세션 {session_id} 피드백 조회 성공: {len(feedback_list)}개")
        return feedback_list
        
    except Exception as e:
        logger.error(f"세션별 피드백 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션별 피드백 조회에 실패했습니다: {str(e)}"
        )

@router.get("/recent", summary="최근 피드백 조회")
async def get_recent_feedback(
    limit: int = Query(10, description="조회할 피드백 개수", ge=1, le=100)
) -> List[Dict[str, Any]]:
    """
    최근 피드백을 조회합니다.
    
    Args:
        limit: 조회할 피드백 개수 (1-100, 기본값: 10)
        
    Returns:
        최신순으로 정렬된 피드백 리스트
    """
    try:
        logger.info(f"최근 피드백 조회 요청: {limit}개")
        
        recent_feedback = feedback_service.get_recent_feedback(limit)
        
        logger.info(f"최근 피드백 조회 성공: {len(recent_feedback)}개")
        return recent_feedback
        
    except Exception as e:
        logger.error(f"최근 피드백 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"최근 피드백 조회에 실패했습니다: {str(e)}"
        )

@router.delete("/{feedback_id}", summary="피드백 삭제")
async def delete_feedback(
    feedback_id: str = Path(..., description="삭제할 피드백 ID", min_length=1, max_length=50)
) -> Dict[str, Any]:
    """
    특정 피드백을 삭제합니다.
    
    Args:
        feedback_id: 삭제할 피드백 ID
        
    Returns:
        삭제 결과
    """
    try:
        logger.info(f"피드백 삭제 요청: {feedback_id}")
        
        success = feedback_service.delete_feedback(feedback_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"피드백을 찾을 수 없습니다: {feedback_id}"
            )
        
        logger.info(f"피드백 삭제 성공: {feedback_id}")
        return {
            "success": True,
            "message": f"피드백 {feedback_id}이 성공적으로 삭제되었습니다.",
            "feedback_id": feedback_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"피드백 삭제 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"피드백 삭제에 실패했습니다: {str(e)}"
        )

# 헬스 체크 엔드포인트
@router.get("/health", summary="피드백 서비스 상태 확인")
async def feedback_health_check() -> Dict[str, Any]:
    """
    피드백 서비스의 상태를 확인합니다.
    
    Returns:
        서비스 상태 정보
    """
    try:
        # 피드백 통계로 서비스 상태 확인
        stats = feedback_service.get_feedback_stats()
        
        return {
            "status": "healthy",
            "service": "feedback",
            "total_feedback": stats.total_feedback,
            "data_directory": feedback_service.data_dir,
            "feedback_file_exists": feedback_service.feedback_file
        }
        
    except Exception as e:
        logger.error(f"피드백 서비스 헬스 체크 실패: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"피드백 서비스가 정상적으로 동작하지 않습니다: {str(e)}"
        ) 