from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Dict, Any
import logging
from datetime import datetime
from app.schemas.history import (
    HistoryCreateRequest, HistoryResponse, SessionCreateRequest,
    SessionUpdateRequest, HistoryStats, HistorySearchRequest,
    ConversationSession, ConversationEntry
)
from app.services.history_service import history_service, settings_service

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# ====== 히스토리 관리 엔드포인트 ======

@router.post("/sessions", response_model=ConversationSession, summary="새 세션 생성")
async def create_session(request: SessionCreateRequest):
    """
    새로운 대화 세션을 생성합니다.
    
    - **session_title**: 세션 제목 (선택사항)
    - **primary_language**: 주요 프로그래밍 언어 (선택사항)
    - **tags**: 태그 목록 (선택사항)
    - **project_name**: 프로젝트명 (선택사항)
    """
    try:
        logger.info(f"새 세션 생성 요청: {request.session_title}")
        
        session = history_service.create_session(request)
        
        logger.info(f"세션 생성 완료: {session.session_id}")
        return session
        
    except Exception as e:
        logger.error(f"세션 생성 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 생성에 실패했습니다: {str(e)}"
        )

@router.post("/entries", response_model=HistoryResponse, summary="히스토리 엔트리 추가")
async def add_history_entry(request: HistoryCreateRequest):
    """
    대화 세션에 새로운 엔트리를 추가합니다.
    
    - **session_id**: 세션 ID
    - **conversation_type**: 대화 유형 (question, answer, feedback, error, system)
    - **content**: 대화 내용
    - **language**: 프로그래밍 언어 (선택사항)
    - **code_snippet**: 관련 코드 스니펫 (선택사항)
    - **file_name**: 파일명 (선택사항)
    - **line_number**: 라인 번호 (선택사항)
    """
    try:
        logger.info(f"히스토리 엔트리 추가 요청: {request.session_id} - {request.conversation_type}")
        
        response = history_service.add_entry(request)
        
        logger.info(f"히스토리 엔트리 추가 완료: {response.entry_id}")
        return response
        
    except Exception as e:
        logger.error(f"히스토리 엔트리 추가 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"히스토리 엔트리 추가에 실패했습니다: {str(e)}"
        )

@router.get("/sessions/{session_id}", summary="세션별 히스토리 조회")
async def get_session_history(
    session_id: str = Path(..., description="조회할 세션 ID"),
    limit: int = Query(50, description="조회할 엔트리 개수", ge=1, le=200)
) -> List[Dict[str, Any]]:
    """
    특정 세션의 대화 히스토리를 조회합니다.
    
    Args:
        session_id: 조회할 세션 ID
        limit: 조회할 엔트리 개수 (1-200, 기본값: 50)
        
    Returns:
        해당 세션의 대화 엔트리 리스트
    """
    try:
        logger.info(f"세션별 히스토리 조회 요청: {session_id}")
        
        history = history_service.get_session_history(session_id, limit)
        
        logger.info(f"세션 {session_id} 히스토리 조회 성공: {len(history)}개")
        return history
        
    except Exception as e:
        logger.error(f"세션별 히스토리 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션별 히스토리 조회에 실패했습니다: {str(e)}"
        )

@router.get("/sessions", summary="최근 세션 목록 조회")
async def get_recent_sessions(
    limit: int = Query(20, description="조회할 세션 개수", ge=1, le=100)
) -> List[Dict[str, Any]]:
    """
    최근 대화 세션 목록을 조회합니다.
    
    Args:
        limit: 조회할 세션 개수 (1-100, 기본값: 20)
        
    Returns:
        최신순으로 정렬된 세션 리스트
    """
    try:
        logger.info(f"최근 세션 목록 조회 요청: {limit}개")
        
        sessions = history_service.get_recent_sessions(limit)
        
        logger.info(f"최근 세션 목록 조회 성공: {len(sessions)}개")
        return sessions
        
    except Exception as e:
        logger.error(f"최근 세션 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"최근 세션 목록 조회에 실패했습니다: {str(e)}"
        )

@router.post("/search", summary="히스토리 검색")
async def search_history(request: HistorySearchRequest) -> List[Dict[str, Any]]:
    """
    대화 히스토리를 검색합니다.
    
    - **query**: 검색 쿼리
    - **session_ids**: 검색할 세션 ID 목록 (선택사항)
    - **language**: 언어 필터 (선택사항)
    - **conversation_type**: 대화 유형 필터 (선택사항)
    - **date_from**: 시작 날짜 (선택사항)
    - **date_to**: 종료 날짜 (선택사항)
    - **limit**: 검색 결과 제한 (1-100, 기본값: 20)
    """
    try:
        logger.info(f"히스토리 검색 요청: {request.query}")
        
        results = history_service.search_history(request)
        
        logger.info(f"히스토리 검색 완료: {len(results)}개 결과")
        return results
        
    except Exception as e:
        logger.error(f"히스토리 검색 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"히스토리 검색에 실패했습니다: {str(e)}"
        )

@router.get("/stats", response_model=HistoryStats, summary="히스토리 통계 조회")
async def get_history_stats():
    """
    대화 히스토리 통계를 조회합니다.
    
    Returns:
        - **total_sessions**: 총 세션 수
        - **active_sessions**: 활성 세션 수
        - **total_entries**: 총 대화 엔트리 수
        - **total_questions**: 총 질문 수
        - **total_answers**: 총 답변 수
        - **language_distribution**: 언어별 세션 수 분포
        - **sessions_today**: 오늘 생성된 세션 수
        - **sessions_this_week**: 이번 주 생성된 세션 수
        - **average_session_length**: 평균 세션 길이
    """
    try:
        logger.info("히스토리 통계 조회 요청")
        
        stats = history_service.get_stats()
        
        logger.info(f"히스토리 통계 조회 성공: 총 {stats.total_sessions}개 세션")
        return stats
        
    except Exception as e:
        logger.error(f"히스토리 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"히스토리 통계 조회에 실패했습니다: {str(e)}"
        )

@router.delete("/sessions/{session_id}", summary="세션 삭제")
async def delete_session(
    session_id: str = Path(..., description="삭제할 세션 ID")
) -> Dict[str, Any]:
    """
    특정 세션과 관련된 모든 데이터를 삭제합니다.
    
    Args:
        session_id: 삭제할 세션 ID
        
    Returns:
        삭제 결과
    """
    try:
        logger.info(f"세션 삭제 요청: {session_id}")
        
        success = history_service.delete_session(session_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )
        
        logger.info(f"세션 삭제 성공: {session_id}")
        return {
            "success": True,
            "message": f"세션 {session_id}이 성공적으로 삭제되었습니다.",
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 삭제 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 삭제에 실패했습니다: {str(e)}"
        )

# ====== 설정 관리 엔드포인트 ======

@router.get("/settings", summary="사용자 설정 조회")
async def get_user_settings() -> Dict[str, Any]:
    """
    사용자 설정을 조회합니다.
    
    Returns:
        사용자 설정 정보
    """
    try:
        logger.info("사용자 설정 조회 요청")
        
        settings = settings_service.get_settings()
        
        logger.info("사용자 설정 조회 성공")
        return {
            "success": True,
            "settings": settings,
            "message": "설정이 성공적으로 조회되었습니다."
        }
        
    except Exception as e:
        logger.error(f"사용자 설정 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"사용자 설정 조회에 실패했습니다: {str(e)}"
        )

@router.put("/settings", summary="사용자 설정 업데이트")
async def update_user_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 설정을 업데이트합니다.
    
    - **ai_model**: AI 모델 (gpt-3.5-turbo, gpt-4 등)
    - **response_length**: 응답 길이 (short, medium, long)
    - **default_language**: 기본 프로그래밍 언어
    - **auto_save**: 자동 저장 여부
    - **dark_mode**: 다크 모드 여부
    - **code_completion**: 코드 완성 기능 여부
    - **max_history**: 최대 히스토리 개수
    - **notification_enabled**: 알림 기능 여부
    """
    try:
        logger.info(f"사용자 설정 업데이트 요청: {list(settings.keys())}")
        
        # 설정 유효성 검사
        valid_ai_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "claude-3", "local-model"]
        valid_response_lengths = ["short", "medium", "long"]
        
        if "ai_model" in settings and settings["ai_model"] not in valid_ai_models:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 AI 모델입니다: {settings['ai_model']}"
            )
        
        if "response_length" in settings and settings["response_length"] not in valid_response_lengths:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 응답 길이입니다: {settings['response_length']}"
            )
        
        if "max_history" in settings:
            try:
                max_history = int(settings["max_history"])
                if max_history < 10 or max_history > 1000:
                    raise ValueError("범위 초과")
                settings["max_history"] = max_history
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail="max_history는 10-1000 사이의 정수여야 합니다."
                )
        
        updated_settings = settings_service.update_settings(settings)
        
        logger.info("사용자 설정 업데이트 성공")
        return {
            "success": True,
            "settings": updated_settings,
            "message": "설정이 성공적으로 업데이트되었습니다."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 설정 업데이트 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"사용자 설정 업데이트에 실패했습니다: {str(e)}"
        )

@router.post("/settings/reset", summary="설정 초기화")
async def reset_settings() -> Dict[str, Any]:
    """
    사용자 설정을 기본값으로 초기화합니다.
    
    Returns:
        초기화된 설정 정보
    """
    try:
        logger.info("설정 초기화 요청")
        
        default_settings = {
            "ai_model": "gpt-3.5-turbo",
            "response_length": "medium", 
            "default_language": "python",
            "auto_save": True,
            "dark_mode": False,
            "code_completion": True,
            "max_history": 100,
            "notification_enabled": True
        }
        
        reset_settings = settings_service.update_settings(default_settings)
        
        logger.info("설정 초기화 성공")
        return {
            "success": True,
            "settings": reset_settings,
            "message": "설정이 기본값으로 초기화되었습니다."
        }
        
    except Exception as e:
        logger.error(f"설정 초기화 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"설정 초기화에 실패했습니다: {str(e)}"
        )

# 헬스 체크 엔드포인트
@router.get("/health", summary="히스토리/설정 서비스 상태 확인")
async def health_check() -> Dict[str, Any]:
    """
    히스토리 및 설정 서비스의 상태를 확인합니다.
    
    Returns:
        서비스 상태 정보
    """
    try:
        # 히스토리 통계로 서비스 상태 확인
        history_stats = history_service.get_stats()
        settings = settings_service.get_settings()
        
        return {
            "status": "healthy",
            "services": ["history", "settings"],
            "history_stats": {
                "total_sessions": history_stats.total_sessions,
                "total_entries": history_stats.total_entries
            },
            "settings_configured": len(settings) > 0,
            "data_directories": {
                "history": history_service.data_dir,
                "settings": settings_service.data_dir
            }
        }
        
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"서비스가 정상적으로 동작하지 않습니다: {str(e)}"
        ) 