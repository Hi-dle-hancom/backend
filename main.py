from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn
import time
from contextlib import asynccontextmanager
from typing import Any, Dict
from app.api.api import api_router
from app.core.config import settings
from app.schemas.code_generation import ErrorResponse, ValidationErrorResponse
from app.core.logging_config import setup_logging, api_monitor, performance_monitor, get_prometheus_metrics
from app.core.security import create_demo_api_key

# 로깅 시스템 초기화
setup_logging()

# 애플리케이션 수명주기 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행되는 로직"""
    # 시작 시 실행
    api_monitor.logger.info("HAPA 백엔드 서버 시작")
    
    # 데모 API Key 생성 (개발 환경에서만)
    if settings.DEBUG:
        demo_key = create_demo_api_key()
        if demo_key:
            api_monitor.logger.info(
                "데모 API Key 사용 가능", 
                api_key=demo_key["api_key"]
            )
    
    yield
    
    # 종료 시 실행
    api_monitor.logger.info("HAPA 백엔드 서버 종료")

# FastAPI 애플리케이션 인스턴스 생성 (최적화됨)
app = FastAPI(
    title="HAPA (Hancom AI Python Assistant) API",
    description="VSCode 확장을 위한 최적화된 AI 코딩 어시스턴트 백엔드 API",
    version="0.4.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 환경에서는 모든 오리진 허용, 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 유효성 검사 오류 핸들러 (422 오류)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Pydantic 유효성 검사 실패 시 표준 오류 응답을 반환합니다.
    """
    api_monitor.logger.warning(
        f"유효성 검사 실패: {request.url.path}",
        errors=exc.errors(),
        client_ip=request.client.host if request.client else "unknown"
    )
    
    # 필드별 오류 메시지 정리
    error_details = {}
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"][1:])  # 'body' 제외
        if field_path not in error_details:
            error_details[field_path] = []
        error_details[field_path].append(error["msg"])
    
    # 주요 오류 메시지 추출
    main_error_msg = exc.errors()[0]["msg"] if exc.errors() else "유효성 검사에 실패했습니다."
    
    error_response = ValidationErrorResponse(
        error_message=f"요청 데이터 유효성 검사에 실패했습니다: {main_error_msg}",
        error_details=error_details
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response.model_dump()
    )

# HTTP 예외 핸들러
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    HTTPException 발생 시 표준 오류 응답을 반환합니다.
    """
    api_monitor.logger.warning(
        f"HTTP 예외 발생: {request.url.path}",
        status_code=exc.status_code,
        detail=exc.detail,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    # 상태 코드별 오류 코드 매핑
    error_code_mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED", 
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE"
    }
    
    error_response = ErrorResponse(
        error_message=str(exc.detail),
        error_code=error_code_mapping.get(exc.status_code, "HTTP_ERROR")
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )

# 일반 예외 핸들러 (500 오류)
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    예상치 못한 모든 내부 서버 오류를 처리합니다.
    민감한 정보가 노출되지 않도록 일반적인 오류 메시지를 반환합니다.
    """
    api_monitor.log_error(
        exc,
        {
            "request_path": str(request.url.path),
            "request_method": request.method,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )
    
    # 개발 환경에서는 상세한 오류 정보 포함
    if settings.DEBUG:
        error_message = f"내부 서버 오류가 발생했습니다: {type(exc).__name__}: {str(exc)}"
        error_details = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "request_path": str(request.url.path),
            "request_method": request.method
        }
    else:
        error_message = "내부 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        error_details = None
    
    error_response = ErrorResponse(
        error_message=error_message,
        error_code="INTERNAL_SERVER_ERROR",
        error_details=error_details
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )

# API 라우터 추가
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# 루트 엔드포인트 설정 (테스트용)
@app.get("/")
async def root():
    return {"message": "AI Coding Assistant Backend API is running!"}

# 헬스 체크 엔드포인트 (강화됨)
@app.get("/health")
async def health_check():
    """
    서버 상태를 확인하는 헬스 체크 엔드포인트입니다.
    """
    health_status = performance_monitor.get_health_status()
    
    return {
        "status": health_status["status"],
        "message": f"HAPA 백엔드 API is {health_status['status']}",
        "version": "0.4.0",
        "timestamp": health_status["timestamp"],
        "system_info": health_status["system"],
        "performance_metrics": health_status["application"]
    }

# 성능 통계 엔드포인트
@app.get("/stats")
async def performance_stats():
    """
    성능 통계 정보를 반환합니다.
    """
    return {
        "performance": performance_monitor.get_health_status(),
        "response_times": response_timer.get_performance_stats()
    }

# Prometheus 메트릭 엔드포인트
@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Prometheus 형식의 메트릭을 반환합니다.
    """
    return get_prometheus_metrics()

# 서버 실행을 위한 코드 (직접 실행 시 사용)
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 