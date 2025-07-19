import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.core.security import (
    APIKeyModel,
    check_permission,
    check_rate_limit_dependency,
    get_current_api_key,
)
from app.schemas.history import (
    ConversationEntry,
    ConversationSession,
    HistoryCreateRequest,
    HistoryResponse,
    HistorySearchRequest,
    HistoryStats,
    SessionCreateRequest,
    SessionUpdateRequest,
)
from app.services.history_service import history_service, settings_service

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# ====== 히스토리 관리 엔드포인트 ======


@router.post("/sessions",
             response_model=ConversationSession,
             summary="새 세션 생성")
async def create_session(
    request: SessionCreateRequest,
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/sessions", 50)
    ),
):
    """
    새로운 대화 세션을 생성합니다.

    **보안**: API Key 인증 필수, 시간당 50회 제한

    - **session_title**: 세션 제목 (선택사항)
    - **primary_language**: 주요 프로그래밍 언어 (선택사항)
    - **tags**: 태그 목록 (선택사항)
    - **project_name**: 프로젝트명 (선택사항)
    """
    try:
        logger.info(
            f"새 세션 생성 요청: {request.session_title} (사용자: {api_key.user_id})"
        )

        session = await history_service.create_session(
            request, user_id=api_key.user_id)

        logger.info(f"세션 생성 완료: {session.session_id} (사용자: {api_key.user_id})")
        return session

    except Exception as e:
        logger.error(f"세션 생성 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"세션 생성에 실패했습니다: {str(e)}"
        )


@router.post("/entries", response_model=HistoryResponse, summary="히스토리 엔트리 추가")
async def add_history_entry(
    request: HistoryCreateRequest,
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/entries", 100)
    ),
):
    """
    대화 세션에 새로운 엔트리를 추가합니다.

    **보안**: API Key 인증 필수, 시간당 100회 제한

    - **session_id**: 세션 ID
    - **conversation_type**: 대화 유형 (question, answer, feedback, error, system)
    - **content**: 대화 내용
    - **language**: 프로그래밍 언어 (선택사항)
    - **code_snippet**: 관련 코드 스니펫 (선택사항)
    - **file_name**: 파일명 (선택사항)
    - **line_number**: 라인 번호 (선택사항)
    """
    try:
        logger.info(f"히스토리 엔트리 추가 요청: {request.session_id} - {request.conversation_type} (사용자: {api_key.user_id})")

        response = await history_service.add_entry(request, user_id=api_key.user_id)

        logger.info(
            f"히스토리 엔트리 추가 완료: {response.entry_id} (사용자: {api_key.user_id})"
        )
        return response

    except Exception as e:
        logger.error(f"히스토리 엔트리 추가 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"히스토리 엔트리 추가에 실패했습니다: {str(e)}"
        )


@router.get("/sessions/{session_id}", summary="세션별 히스토리 조회")
async def get_session_history(
    session_id: str = Path(..., description="조회할 세션 ID"),
    limit: int = Query(50, description="조회할 엔트리 개수", ge=1, le=200),
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/sessions", 50)
    ),
) -> List[Dict[str, Any]]:
    """
    특정 세션의 대화 히스토리를 조회합니다.

    **보안**: API Key 인증 필수, 시간당 50회 제한

    Args:
        session_id: 조회할 세션 ID
        limit: 조회할 엔트리 개수 (1-200, 기본값: 50)

    Returns:
        해당 세션의 대화 엔트리 리스트
    """
    try:
        logger.info(
            f"세션별 히스토리 조회 요청: {session_id} (사용자: {api_key.user_id})"
        )

        history = await history_service.get_session_history(
            session_id, limit, user_id=api_key.user_id
        )

        logger.info(f"세션 {session_id} 히스토리 조회 성공: {len(history)}개 (사용자: {api_key.user_id})")
        return history

    except Exception as e:
        logger.error(f"세션별 히스토리 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"세션별 히스토리 조회에 실패했습니다: {str(e)}"
        )


@router.get("/sessions", summary="최근 세션 목록 조회")
async def get_recent_sessions(
    limit: int = Query(20, description="조회할 세션 개수", ge=1, le=100),
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/sessions", 30)
    ),
) -> List[Dict[str, Any]]:
    """
    최근 대화 세션 목록을 조회합니다.

    **보안**: API Key 인증 필수, 시간당 30회 제한

    Args:
        limit: 조회할 세션 개수 (1-100, 기본값: 20)

    Returns:
        최신순으로 정렬된 세션 리스트
    """
    try:
        logger.info(f"최근 세션 목록 조회 요청: {limit}개 (사용자: {api_key.user_id})")

        sessions = await history_service.get_recent_sessions(
            limit, user_id=api_key.user_id)

        logger.info(
            f"최근 세션 목록 조회 성공: {len(sessions)}개 (사용자: {api_key.user_id})"
        )
        return sessions

    except Exception as e:
        logger.error(f"최근 세션 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"최근 세션 목록 조회에 실패했습니다: {str(e)}"
        )


@router.post("/search", summary="히스토리 검색")
async def search_history(
    request: HistorySearchRequest,
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/search", 20)),
) -> List[Dict[str, Any]]:
    """
    대화 히스토리를 검색합니다.

    **보안**: API Key 인증 필수, 시간당 20회 제한

    - **query**: 검색 쿼리
    - **session_ids**: 검색할 세션 ID 목록 (선택사항)
    - **language**: 언어 필터 (선택사항)
    - **conversation_type**: 대화 유형 필터 (선택사항)
    - **date_from**: 시작 날짜 (선택사항)
    - **date_to**: 종료 날짜 (선택사항)
    - **limit**: 검색 결과 제한 (1-100, 기본값: 20)
    """
    try:
        logger.info(f"히스토리 검색 요청: {request.query} (사용자: {api_key.user_id})")

        results = await history_service.search_history(
            request, user_id=api_key.user_id)

        logger.info(
            f"히스토리 검색 완료: {len(results)}개 결과 (사용자: {api_key.user_id})"
        )
        return results

    except Exception as e:
        logger.error(f"히스토리 검색 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"히스토리 검색에 실패했습니다: {str(e)}"
        )


@router.get("/stats", response_model=HistoryStats, summary="히스토리 통계 조회")
async def get_history_stats(
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/stats", 10)),
):
    """
    대화 히스토리 통계를 조회합니다.

    **보안**: API Key 인증 필수, 시간당 10회 제한

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
        logger.info(f"히스토리 통계 조회 요청 (사용자: {api_key.user_id})")

        stats = await history_service.get_stats(user_id=api_key.user_id)

        logger.info(f"히스토리 통계 조회 성공: 총 {stats.total_sessions}개 세션 (사용자: {api_key.user_id})")
        return stats

    except Exception as e:
        logger.error(f"히스토리 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"히스토리 통계 조회에 실패했습니다: {str(e)}"
        )


@router.delete("/sessions/{session_id}", summary="세션 삭제")
async def delete_session(
    session_id: str = Path(..., description="삭제할 세션 ID"),
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/delete", 10)),
) -> Dict[str, Any]:
    """
    특정 세션과 관련된 모든 데이터를 삭제합니다.

    **보안**: API Key 인증 필수, 시간당 10회 제한

    Args:
        session_id: 삭제할 세션 ID

    Returns:
        삭제 결과
    """
    try:
        logger.info(f"세션 삭제 요청: {session_id} (사용자: {api_key.user_id})")

        success = await history_service.delete_session(
            session_id, user_id=api_key.user_id)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        logger.info(f"세션 삭제 성공: {session_id} (사용자: {api_key.user_id})")
        return {
            "success": True,
            "message": f"세션 {session_id}이 성공적으로 삭제되었습니다.",
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 삭제 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"세션 삭제에 실패했습니다: {str(e)}"
        )


# ====== 사용자 설정 관리 엔드포인트 ======


@router.get("/settings", summary="사용자 설정 조회")
async def get_user_settings(
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/settings", 20)
    ),
) -> Dict[str, Any]:
    """
    사용자의 히스토리 관련 설정을 조회합니다.

    **보안**: API Key 인증 필수, 시간당 20회 제한

    Returns:
        사용자 설정 정보
    """
    try:
        logger.info(f"사용자 설정 조회 요청 (사용자: {api_key.user_id})")

        settings = settings_service.get_user_settings(user_id=api_key.user_id)

        logger.info(f"사용자 설정 조회 성공 (사용자: {api_key.user_id})")
        return settings

    except Exception as e:
        logger.error(f"사용자 설정 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"사용자 설정 조회에 실패했습니다: {str(e)}"
        )


@router.put("/settings", summary="사용자 설정 업데이트")
async def update_user_settings(
    settings: Dict[str, Any],
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/settings", 10)
    ),
) -> Dict[str, Any]:
    """
    사용자의 히스토리 관련 설정을 업데이트합니다.

    **보안**: API Key 인증 필수, 시간당 10회 제한

    Args:
        settings: 업데이트할 설정 정보

    Returns:
        업데이트 결과
    """
    try:
        logger.info(f"사용자 설정 업데이트 요청 (사용자: {api_key.user_id})")

        success = settings_service.update_user_settings(
            settings, user_id=api_key.user_id
        )

        if not success:
            raise HTTPException(status_code=400, detail="설정 업데이트에 실패했습니다.")

        logger.info(f"사용자 설정 업데이트 성공 (사용자: {api_key.user_id})")
        return {
            "success": True,
            "message": "설정이 성공적으로 업데이트되었습니다.",
            "updated_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 설정 업데이트 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"사용자 설정 업데이트에 실패했습니다: {str(e)}"
        )


@router.post("/settings/reset", summary="설정 초기화")
async def reset_settings(
    api_key: APIKeyModel = Depends(check_permission("history")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/reset", 5)),
) -> Dict[str, Any]:
    """
    사용자의 모든 설정을 기본값으로 초기화합니다.

    **보안**: API Key 인증 필수, 시간당 5회 제한

    Returns:
        초기화 결과
    """
    try:
        logger.info(f"설정 초기화 요청 (사용자: {api_key.user_id})")

        success = settings_service.reset_user_settings(user_id=api_key.user_id)

        if not success:
            raise HTTPException(status_code=400, detail="설정 초기화에 실패했습니다.")

        logger.info(f"설정 초기화 성공 (사용자: {api_key.user_id})")
        return {
            "success": True,
            "message": "모든 설정이 기본값으로 초기화되었습니다.",
            "reset_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"설정 초기화 실패: {e}")
        raise HTTPException(
            status_code=500, detail=f"설정 초기화에 실패했습니다: {str(e)}"
        )


# 헬스 체크 엔드포인트 (인증 불필요)
@router.get("/health", summary="히스토리/설정 서비스 상태 확인")
async def health_check() -> Dict[str, Any]:
    """
    히스토리/설정 서비스의 상태를 확인합니다.

    **보안**: 인증 불필요 (헬스 체크용)

    Returns:
        서비스 상태 정보
    """
    try:
        # 히스토리 통계로 서비스 상태 확인 (익명)
        stats = await history_service.get_health_stats()

        return {
            "status": "healthy",
            "service": "history",
            "version": "1.0.0",
            "total_sessions": stats.get("total_sessions", 0),
            "total_entries": stats.get("total_entries", 0),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"히스토리 서비스 상태 확인 실패: {e}")
        return {
            "status": "unhealthy",
            "service": "history",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
