import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.error_handling import (
    EnhancedErrorResponse,
    ErrorCategory,
    ErrorPattern,
    ErrorSeverity,
    ErrorSummary,
    StandardErrorCode,
)
from app.services.error_handling_service import error_handling_service

logger = logging.getLogger(__name__)
router = APIRouter()


def setup_error_handlers(app: FastAPI):
    """
    FastAPI 애플리케이션에 글로벌 오류 핸들러를 설정합니다.
    
    Args:
        app: FastAPI 애플리케이션 인스턴스
    """
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """HTTP 예외 처리"""
        error_code = _map_status_to_error_code(exc.status_code)
        
        # 오류 로깅
        await error_handling_service.log_error(
            error_code=error_code,
            message=str(exc.detail),
            user_id=getattr(request.state, 'user_id', 'anonymous'),
            request_data={
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
            },
            severity=_get_severity_for_status(exc.status_code)
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": error_code.value,
                "message": exc.detail,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """요청 검증 오류 처리"""
        error_code = StandardErrorCode.VALIDATION_FAILED
        
        # 오류 로깅
        await error_handling_service.log_error(
            error_code=error_code,
            message="Request validation failed",
            user_id=getattr(request.state, 'user_id', 'anonymous'),
            request_data={
                "method": request.method,
                "url": str(request.url),
                "validation_errors": exc.errors(),
            },
            severity=ErrorSeverity.MEDIUM
        )
        
        return JSONResponse(
            status_code=422,
            content={
                "error_code": error_code.value,
                "message": "Request validation failed",
                "details": exc.errors(),
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """일반 예외 처리"""
        error_code = StandardErrorCode.INTERNAL_SERVER_ERROR
        
        # 오류 로깅
        await error_handling_service.log_error(
            error_code=error_code,
            message=str(exc),
            user_id=getattr(request.state, 'user_id', 'anonymous'),
            request_data={
                "method": request.method,
                "url": str(request.url),
                "exception_type": type(exc).__name__,
            },
            severity=ErrorSeverity.HIGH
        )
        
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error_code": error_code.value,
                "message": "Internal server error",
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path)
            }
        )


def _map_status_to_error_code(status_code: int) -> StandardErrorCode:
    """HTTP 상태 코드를 표준 오류 코드로 매핑"""
    mapping = {
        400: StandardErrorCode.BAD_REQUEST,
        401: StandardErrorCode.UNAUTHORIZED,
        403: StandardErrorCode.FORBIDDEN,
        404: StandardErrorCode.NOT_FOUND,
        405: StandardErrorCode.METHOD_NOT_ALLOWED,
        422: StandardErrorCode.VALIDATION_FAILED,
        429: StandardErrorCode.RATE_LIMIT_EXCEEDED,
        500: StandardErrorCode.INTERNAL_SERVER_ERROR,
        502: StandardErrorCode.BAD_GATEWAY,
        503: StandardErrorCode.SERVICE_UNAVAILABLE,
        504: StandardErrorCode.GATEWAY_TIMEOUT,
    }
    return mapping.get(status_code, StandardErrorCode.INTERNAL_SERVER_ERROR)


def _get_severity_for_status(status_code: int) -> ErrorSeverity:
    """HTTP 상태 코드에 따른 심각도 결정"""
    if status_code >= 500:
        return ErrorSeverity.HIGH
    elif status_code >= 400:
        return ErrorSeverity.MEDIUM
    else:
        return ErrorSeverity.LOW


@router.get("/summary", response_model=ErrorSummary, summary="오류 요약 통계")
async def get_error_summary(
    hours: int = Query(
        24, description="분석 시간 범위(시간)", ge=1, le=168
    ),  # 최대 1주일
    request: Request = None,
):
    """
    지정된 시간 범위 내의 오류 발생 패턴과 통계를 분석합니다.

    **주요 기능:**
    - Client vs Server 에러 분류
    - 오류 빈도 및 패턴 분석
    - 영향받은 사용자 수 추적
    - 심각도별 분류

    **반환 정보:**
    - 총 오류 수 및 카테고리별 분류
    - 상위 20개 오류 패턴
    - 평균 해결 시간
    """
    try:
        logger.info(f"오류 요약 통계 요청: 최근 {hours}시간")

        # 시간 범위 설정
        time_range = timedelta(hours=hours)

        # 오류 요약 생성
        summary = error_handling_service.get_error_summary(time_range)

        logger.info(
            f"오류 요약 통계 생성 완료: 총 {summary.total_errors}개 오류",
            extra={
                "total_errors": summary.total_errors,
                "client_errors": summary.client_errors,
                "server_errors": summary.server_errors,
                "time_range_hours": hours,
            },
        )

        return summary

    except Exception as e:
        logger.error(f"오류 요약 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="오류 통계 조회에 실패했습니다.")


@router.get("/patterns", response_model=List[ErrorPattern], summary="오류 패턴 분석")
async def get_error_patterns(
    limit: int = Query(20, description="반환할 패턴 수", ge=1, le=100),
    severity: Optional[ErrorSeverity] = Query(None, description="심각도 필터"),
    category: Optional[ErrorCategory] = Query(None, description="카테고리 필터"),
    hours: int = Query(24, description="분석 시간 범위(시간)", ge=1, le=168),
):
    """
    오류 발생 패턴을 분석하여 빈도순으로 반환합니다.

    **분석 항목:**
    - 오류 코드별 발생 빈도
    - 최초/최근 발생 시간
    - 영향받은 사용자 수
    - 평균 해결 시간

    **필터링 옵션:**
    - 심각도 (low, medium, high, critical)
    - 카테고리 (client_error, server_error, validation_error 등)
    """
    try:
        logger.info(f"오류 패턴 분석 요청: limit={limit}, severity={severity}, category={category}")

        # 전체 요약 데이터 가져오기
        time_range = timedelta(hours=hours)
        summary = error_handling_service.get_error_summary(time_range)

        patterns = summary.patterns

        # 필터링 적용
        if severity:
            # 패턴에 심각도 정보를 기반으로 필터링
            filtered_patterns = []
            for pattern in patterns:
                # 오류 코드별 기본 심각도 매핑
                pattern_severity = _get_severity_for_error_code(
                    pattern.error_code)
                if pattern_severity == severity:
                    filtered_patterns.append(pattern)
            patterns = filtered_patterns
            logger.info(f"심각도 필터 적용: {severity.value} (결과: {len(patterns)}개)")

        if category:
            # 카테고리별 필터링 (오류 코드 패턴 기반)
            if category == ErrorCategory.CLIENT_ERROR:
                patterns = [
                    p for p in patterns if p.error_code.value.startswith(
                        ("E4", "V"))]
            elif category == ErrorCategory.SERVER_ERROR:
                patterns = [
                    p for p in patterns if p.error_code.value.startswith(
                        ("E5", "B"))]
            elif category == ErrorCategory.VALIDATION_ERROR:
                patterns = [
                    p for p in patterns if p.error_code.value.startswith("V")]

        # 제한된 수만 반환
        patterns = patterns[:limit]

        logger.info(f"오류 패턴 분석 완료: {len(patterns)}개 패턴 반환")
        return patterns

    except Exception as e:
        logger.error(f"오류 패턴 분석 실패: {e}")
        raise HTTPException(status_code=500, detail="오류 패턴 분석에 실패했습니다.")


@router.get("/health", summary="오류 처리 시스템 상태")
async def get_error_handling_health():
    """
    오류 처리 시스템의 상태를 확인합니다.

    **확인 항목:**
    - 최근 오류 발생률
    - 심각한 오류 여부
    - 시스템 알림 상태
    """
    try:
        # 최근 1시간 오류 요약
        recent_summary = error_handling_service.get_error_summary(
            timedelta(hours=1))

        # 상태 평가
        status = "healthy"
        alerts = []

        # 심각한 오류 확인
        if recent_summary.critical_errors > 0:
            status = "warning"
            alerts.append(f"심각한 오류 {recent_summary.critical_errors}개 감지")

        # 서버 오류 비율 확인
        if recent_summary.total_errors > 0:
            server_error_ratio = (
                recent_summary.server_errors / recent_summary.total_errors
            )
            if server_error_ratio > 0.5:  # 50% 이상이 서버 오류
                status = "critical"
                alerts.append(f"서버 오류 비율 {server_error_ratio:.1%}")

        # 오류 급증 확인 (임계치 기반)
        if recent_summary.total_errors > 100:  # 1시간에 100개 이상
            status = "warning"
            alerts.append(f"오류 급증 감지: {recent_summary.total_errors}개/시간")

        health_data = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "recent_errors": {
                "total": recent_summary.total_errors,
                "client_errors": recent_summary.client_errors,
                "server_errors": recent_summary.server_errors,
                "critical_errors": recent_summary.critical_errors,
            },
            "alerts": alerts,
            "monitoring": {
                "error_tracking": "active",
                "pattern_analysis": "active",
                "alerting": "active",
            },
        }

        logger.info(f"오류 처리 시스템 상태: {status}")
        return health_data

    except Exception as e:
        logger.error(f"오류 처리 시스템 상태 확인 실패: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": "상태 확인에 실패했습니다.",
            "monitoring": {
                "error_tracking": "unknown",
                "pattern_analysis": "unknown",
                "alerting": "unknown",
            },
        }


@router.get("/codes", summary="지원되는 오류 코드 목록")
async def get_error_codes():
    """
    시스템에서 사용하는 모든 표준 오류 코드와 설명을 반환합니다.

    **카테고리:**
    - Client Errors (E4xxx): 클라이언트 측 오류
    - Server Errors (E5xxx): 서버 측 오류
    - Validation Errors (Vxxxx): 유효성 검사 오류
    - Business Errors (Bxxxx): 비즈니스 로직 오류
    """
    try:
        error_codes = []

        for code in StandardErrorCode:
            # 카테고리 분류
            if code.value.startswith("E4"):
                category = "Client Error"
                description = "클라이언트 측 오류"
            elif code.value.startswith("E5"):
                category = "Server Error"
                description = "서버 측 오류"
            elif code.value.startswith("V"):
                category = "Validation Error"
                description = "유효성 검사 오류"
            elif code.value.startswith("B"):
                category = "Business Error"
                description = "비즈니스 로직 오류"
            else:
                category = "Unknown"
                description = "분류되지 않은 오류"

            error_codes.append(
                {
                    "code": code.value,
                    "name": code.name,
                    "category": category,
                    "description": description,
                    "http_status": _get_http_status_for_code(code),
                }
            )

        logger.info(f"오류 코드 목록 조회: {len(error_codes)}개 코드")
        return {
            "total_codes": len(error_codes),
            "categories": {
                "client_errors": len(
                    [c for c in error_codes if c["category"] == "Client Error"]
                ),
                "server_errors": len(
                    [c for c in error_codes if c["category"] == "Server Error"]
                ),
                "validation_errors": len(
                    [c for c in error_codes if c["category"] == "Validation Error"]
                ),
                "business_errors": len(
                    [c for c in error_codes if c["category"] == "Business Error"]
                ),
            },
            "codes": error_codes,
        }

    except Exception as e:
        logger.error(f"오류 코드 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail="오류 코드 목록 조회에 실패했습니다."
        )


@router.post("/test-error", summary="오류 테스트 엔드포인트 (개발용)")
async def test_error_handling(
    error_type: str = Query(..., description="테스트할 오류 타입"),
    message: str = Query("테스트 오류", description="오류 메시지"),
):
    """
    오류 처리 시스템을 테스트하기 위한 개발용 엔드포인트입니다.

    **지원하는 오류 타입:**
    - `validation`: 유효성 검사 오류
    - `not_found`: 404 오류
    - `server_error`: 500 오류
    - `rate_limit`: 429 오류
    - `unauthorized`: 401 오류
    """
    logger.warning(f"오류 테스트 요청: {error_type} - {message}")

    if error_type == "validation":
        raise HTTPException(status_code=422, detail=message)
    elif error_type == "not_found":
        raise HTTPException(status_code=404, detail=message)
    elif error_type == "server_error":
        raise HTTPException(status_code=500, detail=message)
    elif error_type == "rate_limit":
        raise HTTPException(status_code=429, detail=message)
    elif error_type == "unauthorized":
        raise HTTPException(status_code=401, detail=message)
    elif error_type == "exception":
        # 일반 예외 발생
        raise ValueError(message)
    else:
        raise HTTPException(
            status_code=400, detail=f"지원하지 않는 오류 타입: {error_type}"
        )


def _get_severity_for_error_code(
        error_code: StandardErrorCode) -> ErrorSeverity:
    """오류 코드에 대응하는 심각도 반환"""
    severity_mapping = {
        # Critical 레벨 - 시스템 전체에 영향
        StandardErrorCode.INTERNAL_SERVER_ERROR: ErrorSeverity.CRITICAL,
        StandardErrorCode.DATABASE_ERROR: ErrorSeverity.CRITICAL,
        StandardErrorCode.INSUFFICIENT_RESOURCES: ErrorSeverity.CRITICAL,
        # High 레벨 - 서비스 장애
        StandardErrorCode.SERVICE_UNAVAILABLE: ErrorSeverity.HIGH,
        StandardErrorCode.TIMEOUT_ERROR: ErrorSeverity.HIGH,
        StandardErrorCode.EXTERNAL_API_ERROR: ErrorSeverity.HIGH,
        # Medium 레벨 - 사용자 경험 저하
        StandardErrorCode.RATE_LIMIT_EXCEEDED: ErrorSeverity.MEDIUM,
        StandardErrorCode.UNAUTHORIZED: ErrorSeverity.MEDIUM,
        StandardErrorCode.FORBIDDEN: ErrorSeverity.MEDIUM,
        # Low 레벨 - 사용자 입력 오류
        StandardErrorCode.INVALID_REQUEST: ErrorSeverity.LOW,
        StandardErrorCode.INVALID_PARAMETERS: ErrorSeverity.LOW,
        StandardErrorCode.MISSING_REQUIRED_FIELD: ErrorSeverity.LOW,
        StandardErrorCode.INVALID_FORMAT: ErrorSeverity.LOW,
        StandardErrorCode.VALIDATION_FAILED: ErrorSeverity.LOW,
        StandardErrorCode.RESOURCE_NOT_FOUND: ErrorSeverity.LOW,
        StandardErrorCode.CONFLICT: ErrorSeverity.LOW,
    }
    return severity_mapping.get(error_code, ErrorSeverity.MEDIUM)


def _get_http_status_for_code(error_code: StandardErrorCode) -> int:
    """오류 코드에 대응하는 HTTP 상태 코드 반환"""
    status_mapping = {
        StandardErrorCode.INVALID_REQUEST: 400,
        StandardErrorCode.INVALID_PARAMETERS: 400,
        StandardErrorCode.MISSING_REQUIRED_FIELD: 400,
        StandardErrorCode.INVALID_FORMAT: 400,
        StandardErrorCode.UNAUTHORIZED: 401,
        StandardErrorCode.FORBIDDEN: 403,
        StandardErrorCode.RESOURCE_NOT_FOUND: 404,
        StandardErrorCode.CONFLICT: 409,
        StandardErrorCode.VALIDATION_FAILED: 422,
        StandardErrorCode.RATE_LIMIT_EXCEEDED: 429,
        StandardErrorCode.INTERNAL_SERVER_ERROR: 500,
        StandardErrorCode.DATABASE_ERROR: 500,
        StandardErrorCode.EXTERNAL_API_ERROR: 502,
        StandardErrorCode.SERVICE_UNAVAILABLE: 503,
        StandardErrorCode.TIMEOUT_ERROR: 504,
        StandardErrorCode.SCHEMA_VALIDATION_ERROR: 422,
        StandardErrorCode.TYPE_MISMATCH: 422,
        StandardErrorCode.RANGE_VIOLATION: 422,
        StandardErrorCode.BUSINESS_RULE_VIOLATION: 422,
        StandardErrorCode.INSUFFICIENT_RESOURCES: 507,
        StandardErrorCode.OPERATION_NOT_ALLOWED: 403,
    }
    return status_mapping.get(error_code, 500)
