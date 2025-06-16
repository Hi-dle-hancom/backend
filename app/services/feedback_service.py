import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from app.schemas.feedback import FeedbackRequest, FeedbackResponse, FeedbackStats, FeedbackType

# 로깅 설정
logger = logging.getLogger(__name__)

class FeedbackService:
    """피드백 데이터 처리 서비스"""
    
    def __init__(self, data_dir: str = "data/feedback"):
        """
        피드백 서비스 초기화
        
        Args:
            data_dir: 피드백 데이터를 저장할 디렉토리
        """
        self.data_dir = data_dir
        self.feedback_file = os.path.join(data_dir, "feedback.json")
        self._ensure_data_directory()
        self._load_feedback_data()
    
    def _ensure_data_directory(self):
        """데이터 디렉토리가 존재하는지 확인하고 생성"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.feedback_file):
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            logger.info(f"피드백 데이터 파일 생성: {self.feedback_file}")
    
    def _load_feedback_data(self) -> List[Dict[str, Any]]:
        """피드백 데이터를 JSON 파일에서 로드"""
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"피드백 데이터 로드 실패: {e}")
            return []
    
    def _save_feedback_data(self, feedback_data: List[Dict[str, Any]]):
        """피드백 데이터를 JSON 파일에 저장"""
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(feedback_data, f, ensure_ascii=False, indent=2, default=str)
            logger.info("피드백 데이터 저장 완료")
        except Exception as e:
            logger.error(f"피드백 데이터 저장 실패: {e}")
            raise Exception(f"피드백 데이터 저장에 실패했습니다: {e}")
    
    def save_feedback(self, feedback: FeedbackRequest) -> FeedbackResponse:
        """
        새로운 피드백을 저장합니다.
        
        Args:
            feedback: 피드백 요청 데이터
            
        Returns:
            피드백 응답 데이터
        """
        try:
            # 고유한 피드백 ID 생성
            feedback_id = f"fb_{uuid.uuid4().hex[:8]}"
            timestamp = datetime.now()
            
            # 피드백 데이터 구성
            feedback_data = {
                "feedback_id": feedback_id,
                "feedback_type": feedback.feedback_type.value,
                "session_id": feedback.session_id,
                "question_id": feedback.question_id,
                "response_id": feedback.response_id,
                "rating": feedback.rating,
                "comment": feedback.comment,
                "user_agent": feedback.user_agent,
                "platform": feedback.platform,
                "timestamp": timestamp.isoformat(),
                "created_at": timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 기존 피드백 데이터 로드
            all_feedback = self._load_feedback_data()
            
            # 새 피드백 추가
            all_feedback.append(feedback_data)
            
            # 데이터 저장
            self._save_feedback_data(all_feedback)
            
            logger.info(f"피드백 저장 완료: {feedback_id}")
            
            return FeedbackResponse(
                success=True,
                feedback_id=feedback_id,
                message="피드백이 성공적으로 저장되었습니다.",
                timestamp=timestamp
            )
            
        except Exception as e:
            logger.error(f"피드백 저장 실패: {e}")
            raise Exception(f"피드백 저장에 실패했습니다: {e}")
    
    def get_feedback_stats(self) -> FeedbackStats:
        """
        피드백 통계를 조회합니다.
        
        Returns:
            피드백 통계 데이터
        """
        try:
            all_feedback = self._load_feedback_data()
            
            # 기본 통계 계산
            total_feedback = len(all_feedback)
            like_count = sum(1 for f in all_feedback if f.get("feedback_type") == "like")
            dislike_count = sum(1 for f in all_feedback if f.get("feedback_type") == "dislike")
            comment_count = sum(1 for f in all_feedback if f.get("comment"))
            
            # 평균 별점 계산
            ratings = [f.get("rating") for f in all_feedback if f.get("rating") is not None]
            average_rating = sum(ratings) / len(ratings) if ratings else None
            
            return FeedbackStats(
                total_feedback=total_feedback,
                like_count=like_count,
                dislike_count=dislike_count,
                average_rating=round(average_rating, 2) if average_rating else None,
                comment_count=comment_count
            )
            
        except Exception as e:
            logger.error(f"피드백 통계 조회 실패: {e}")
            raise Exception(f"피드백 통계 조회에 실패했습니다: {e}")
    
    def get_feedback_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        특정 세션의 피드백을 조회합니다.
        
        Args:
            session_id: 세션 ID
            
        Returns:
            해당 세션의 피드백 리스트
        """
        try:
            all_feedback = self._load_feedback_data()
            session_feedback = [f for f in all_feedback if f.get("session_id") == session_id]
            
            logger.info(f"세션 {session_id}의 피드백 {len(session_feedback)}개 조회")
            return session_feedback
            
        except Exception as e:
            logger.error(f"세션별 피드백 조회 실패: {e}")
            raise Exception(f"세션별 피드백 조회에 실패했습니다: {e}")
    
    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        최근 피드백을 조회합니다.
        
        Args:
            limit: 조회할 피드백 개수
            
        Returns:
            최근 피드백 리스트
        """
        try:
            all_feedback = self._load_feedback_data()
            
            # 타임스탬프 기준 정렬 (최신순)
            sorted_feedback = sorted(
                all_feedback, 
                key=lambda x: x.get("timestamp", ""), 
                reverse=True
            )
            
            return sorted_feedback[:limit]
            
        except Exception as e:
            logger.error(f"최근 피드백 조회 실패: {e}")
            raise Exception(f"최근 피드백 조회에 실패했습니다: {e}")
    
    def delete_feedback(self, feedback_id: str) -> bool:
        """
        특정 피드백을 삭제합니다.
        
        Args:
            feedback_id: 삭제할 피드백 ID
            
        Returns:
            삭제 성공 여부
        """
        try:
            all_feedback = self._load_feedback_data()
            original_count = len(all_feedback)
            
            # 해당 ID의 피드백 제거
            filtered_feedback = [f for f in all_feedback if f.get("feedback_id") != feedback_id]
            
            if len(filtered_feedback) == original_count:
                logger.warning(f"삭제할 피드백을 찾을 수 없음: {feedback_id}")
                return False
            
            # 데이터 저장
            self._save_feedback_data(filtered_feedback)
            
            logger.info(f"피드백 삭제 완료: {feedback_id}")
            return True
            
        except Exception as e:
            logger.error(f"피드백 삭제 실패: {e}")
            raise Exception(f"피드백 삭제에 실패했습니다: {e}")

# 전역 피드백 서비스 인스턴스
feedback_service = FeedbackService() 