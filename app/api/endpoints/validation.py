from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Dict, Any
import logging
import time
import os
import uuid
from datetime import datetime
from app.schemas.validation import (
    CodeValidationRequest,
    CodeValidationResponse,
    BatchValidationRequest,
    BatchValidationResponse,
    ValidationStats,
    ValidationErrorResponse,
    ValidationStatus
)
from app.services.validation_service import validation_service

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

@router.post("/validate", response_model=CodeValidationResponse, summary="코드 검증")
async def validate_code(request: CodeValidationRequest):
    """
    코드를 검증합니다.
    
    - **code**: 검증할 코드 (1-10000자)
    - **language**: 프로그래밍 언어 (python, javascript, typescript 등)
    - **file_name**: 파일명 (선택사항)
    - **check_execution**: 실행 가능성 검사 여부 (기본값: True)
    - **check_style**: 코딩 스타일 검사 여부 (기본값: False)
    - **session_id**: 세션 ID (선택사항)
    - **context**: 코드 컨텍스트 (선택사항)
    
    Returns:
        코드 검증 결과 (문법 오류, 실행 결과, 코드 구조 분석 등)
    """
    try:
        logger.info(f"코드 검증 요청: {request.language} - 길이: {len(request.code)}자")
        
        # 코드 길이 검증
        if len(request.code.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="검증할 코드가 비어있습니다."
            )
        
        # 지원하지 않는 언어 체크
        supported_languages = ["python", "javascript", "typescript", "java", "cpp", "csharp"]
        if request.language not in supported_languages:
            # 경고는 주지만 기본적으로 Python으로 처리
            logger.warning(f"지원하지 않는 언어: {request.language}, Python으로 처리")
            request.language = "python"
        
        # 코드 검증 수행
        result = validation_service.validate_code(request)
        
        logger.info(f"코드 검증 완료: {result.validation_id} - 상태: {result.status}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"코드 검증 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"코드 검증에 실패했습니다: {str(e)}"
        )

@router.post("/validate/batch", response_model=BatchValidationResponse, summary="배치 코드 검증")
async def validate_code_batch(request: BatchValidationRequest):
    """
    여러 코드 스니펫을 한 번에 검증합니다.
    
    - **code_snippets**: 검증할 코드 스니펫 목록 (1-10개)
    - **common_language**: 공통 프로그래밍 언어
    - **session_id**: 세션 ID (선택사항)
    
    Returns:
        배치 검증 결과 (개별 검증 결과의 집합)
    """
    try:
        logger.info(f"배치 코드 검증 요청: {len(request.code_snippets)}개 스니펫")
        
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        results = []
        start_time = time.time()
        
        for i, snippet in enumerate(request.code_snippets):
            try:
                # 개별 검증 요청 생성
                validation_request = CodeValidationRequest(
                    code=snippet.get("code", ""),
                    language=snippet.get("language", request.common_language),
                    file_name=snippet.get("file_name"),
                    check_execution=snippet.get("check_execution", True),
                    check_style=snippet.get("check_style", False),
                    session_id=request.session_id,
                    context=snippet.get("context")
                )
                
                # 개별 검증 수행
                result = validation_service.validate_code(validation_request)
                results.append(result)
                
            except Exception as e:
                logger.warning(f"배치 검증 중 스니펫 {i} 검증 실패: {e}")
                # 실패한 스니펫도 결과에 포함
                error_result = CodeValidationResponse(
                    validation_id=f"val_error_{i}",
                    status=ValidationStatus.ERROR,
                    is_valid=False,
                    is_executable=False,
                    issues=[],
                    total_issues=1,
                    error_count=1,
                    warning_count=0,
                    lines_of_code=0,
                    functions_count=0,
                    classes_count=0,
                    validation_time=0.0,
                    timestamp=datetime.now()
                )
                results.append(error_result)
        
        total_validation_time = time.time() - start_time
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = len(results) - valid_count
        
        response = BatchValidationResponse(
            batch_id=batch_id,
            total_snippets=len(request.code_snippets),
            valid_count=valid_count,
            invalid_count=invalid_count,
            results=results,
            total_validation_time=total_validation_time,
            timestamp=datetime.now()
        )
        
        logger.info(f"배치 코드 검증 완료: {batch_id} - 성공: {valid_count}, 실패: {invalid_count}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"배치 코드 검증 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"배치 코드 검증에 실패했습니다: {str(e)}"
        )

@router.get("/stats", response_model=ValidationStats, summary="검증 통계 조회")
async def get_validation_stats():
    """
    코드 검증 통계를 조회합니다.
    
    Returns:
        - **total_validations**: 총 검증 수
        - **valid_code_count**: 유효한 코드 수
        - **invalid_code_count**: 무효한 코드 수
        - **average_validation_time**: 평균 검증 시간
        - **most_common_issues**: 가장 흔한 이슈 유형
        - **language_distribution**: 언어별 검증 수 분포
    """
    try:
        logger.info("검증 통계 조회 요청")
        
        stats = validation_service.get_validation_stats()
        
        logger.info(f"검증 통계 조회 성공: 총 {stats.total_validations}개")
        return stats
        
    except Exception as e:
        logger.error(f"검증 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검증 통계 조회에 실패했습니다: {str(e)}"
        )

@router.get("/history/{session_id}", summary="세션별 검증 이력 조회")
async def get_validation_history(
    session_id: str = Path(..., description="조회할 세션 ID", min_length=1, max_length=100),
    limit: int = Query(10, description="조회할 이력 개수", ge=1, le=100)
) -> List[Dict[str, Any]]:
    """
    특정 세션의 코드 검증 이력을 조회합니다.
    
    Args:
        session_id: 조회할 세션 ID
        limit: 조회할 이력 개수 (1-100, 기본값: 10)
        
    Returns:
        해당 세션의 검증 이력 리스트
    """
    try:
        logger.info(f"세션별 검증 이력 조회 요청: {session_id}")
        
        all_validations = validation_service._load_validation_data()
        
        # 세션별 필터링
        session_validations = [
            v for v in all_validations 
            if v.get("session_id") == session_id
        ]
        
        # 최신순 정렬 및 제한
        session_validations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        limited_validations = session_validations[:limit]
        
        logger.info(f"세션 {session_id} 검증 이력 조회 성공: {len(limited_validations)}개")
        return limited_validations
        
    except Exception as e:
        logger.error(f"세션별 검증 이력 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션별 검증 이력 조회에 실패했습니다: {str(e)}"
        )

@router.get("/recent", summary="최근 검증 이력 조회")
async def get_recent_validations(
    limit: int = Query(20, description="조회할 검증 개수", ge=1, le=100),
    language: str = Query(None, description="필터링할 언어")
) -> List[Dict[str, Any]]:
    """
    최근 코드 검증 이력을 조회합니다.
    
    Args:
        limit: 조회할 검증 개수 (1-100, 기본값: 20)
        language: 필터링할 언어 (선택사항)
        
    Returns:
        최신순으로 정렬된 검증 이력 리스트
    """
    try:
        logger.info(f"최근 검증 이력 조회 요청: {limit}개, 언어: {language}")
        
        all_validations = validation_service._load_validation_data()
        
        # 언어별 필터링 (옵션)
        if language:
            filtered_validations = [
                v for v in all_validations 
                if v.get("language") == language
            ]
        else:
            filtered_validations = all_validations
        
        # 최신순 정렬 및 제한
        filtered_validations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        recent_validations = filtered_validations[:limit]
        
        logger.info(f"최근 검증 이력 조회 성공: {len(recent_validations)}개")
        return recent_validations
        
    except Exception as e:
        logger.error(f"최근 검증 이력 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"최근 검증 이력 조회에 실패했습니다: {str(e)}"
        )

@router.delete("/history/{validation_id}", summary="검증 이력 삭제")
async def delete_validation_history(
    validation_id: str = Path(..., description="삭제할 검증 ID", min_length=1, max_length=50)
) -> Dict[str, Any]:
    """
    특정 검증 이력을 삭제합니다.
    
    Args:
        validation_id: 삭제할 검증 ID
        
    Returns:
        삭제 결과
    """
    try:
        logger.info(f"검증 이력 삭제 요청: {validation_id}")
        
        all_validations = validation_service._load_validation_data()
        original_count = len(all_validations)
        
        # 해당 ID의 검증 이력 제거
        filtered_validations = [
            v for v in all_validations 
            if v.get("validation_id") != validation_id
        ]
        
        if len(filtered_validations) == original_count:
            raise HTTPException(
                status_code=404,
                detail=f"검증 이력을 찾을 수 없습니다: {validation_id}"
            )
        
        # 데이터 저장
        validation_service._save_validation_data(filtered_validations)
        
        logger.info(f"검증 이력 삭제 성공: {validation_id}")
        return {
            "success": True,
            "message": f"검증 이력 {validation_id}이 성공적으로 삭제되었습니다.",
            "validation_id": validation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"검증 이력 삭제 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검증 이력 삭제에 실패했습니다: {str(e)}"
        )

# 헬스 체크 엔드포인트
@router.get("/health", summary="검증 서비스 상태 확인")
async def validation_health_check() -> Dict[str, Any]:
    """
    검증 서비스의 상태를 확인합니다.
    
    Returns:
        서비스 상태 정보
    """
    try:
        # 검증 통계로 서비스 상태 확인
        stats = validation_service.get_validation_stats()
        
        return {
            "status": "healthy",
            "service": "validation",
            "total_validations": stats.total_validations,
            "data_directory": validation_service.data_dir,
            "validation_file_exists": os.path.exists(validation_service.validation_file),
            "supported_languages": ["python", "javascript", "typescript", "java", "cpp", "csharp"]
        }
        
    except Exception as e:
        logger.error(f"검증 서비스 헬스 체크 실패: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"검증 서비스가 정상적으로 동작하지 않습니다: {str(e)}"
        ) 