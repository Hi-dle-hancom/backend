"""
HAPA (Hancom AI Python Assistant) Backend
메인 애플리케이션 엔트리 포인트
- vLLM 멀티 LoRA 서버 통합
- Enhanced AI 모델 서비스 지원
- 실시간 스트리밍 코드 생성
"""

import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Core imports
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.structured_logger import StructuredLogger
from app.core.settings_manager import get_settings

# API imports
from app.api.api import api_router

# Service imports
from app.services.enhanced_ai_model import enhanced_ai_service
from app.services.vllm_integration_service import vllm_service
from app.middleware.enhanced_logging_middleware import EnhancedLoggingMiddleware
from app.middleware.security_headers import add_security_middleware

# Exception handlers
from app.api.endpoints.error_monitoring import setup_error_handlers

logger = StructuredLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 라이프사이클 관리
    - 시작시: Enhanced AI 서비스 초기화
    - 종료시: 연결 정리
    """
    # === 시작 단계 ===
    logger.log_system_event("HAPA 백엔드 시작", "started", {
        "environment": settings.ENVIRONMENT,
        "vllm_server": settings.VLLM_SERVER_URL,
        "debug_mode": settings.DEBUG
    })

    try:
        # Enhanced AI 서비스 초기화
        logger.log_system_event("Enhanced AI 서비스 초기화", "started")
        await enhanced_ai_service.initialize()

        # vLLM 서버 연결 확인
        health_status = await vllm_service.check_health()
        if health_status["status"] == "healthy":
            logger.log_system_event("vLLM 서버 연결", "success", health_status)
        else:
            logger.log_system_event("vLLM 서버 연결", "failed", health_status)

        # 백엔드 상태 조회
        backend_status = await enhanced_ai_service.get_backend_status()
        logger.log_system_event("AI 백엔드 상태", "success", backend_status)

        logger.log_system_event("HAPA 백엔드 초기화", "completed", {
            "vllm_available": backend_status["vllm"]["available"],
            "backend_type": backend_status["backend_type"],
            "last_health_check": backend_status["last_health_check"]
        })

    except Exception as e:
        logger.log_error(e, "HAPA 백엔드 초기화")
        # 초기화 실패해도 서버는 시작 (graceful degradation)

    yield

    # === 종료 단계 ===
    logger.log_system_event("HAPA 백엔드 종료", "started")

    try:
        # Enhanced AI 서비스 정리
        await enhanced_ai_service.close()

        # vLLM 서비스 정리
        await vllm_service.close()

        logger.log_system_event("HAPA 백엔드 종료", "completed")

    except Exception as e:
        logger.log_error(e, "HAPA 백엔드 종료")


def create_application() -> FastAPI:
    """
    FastAPI 애플리케이션 생성 및 설정
    """
    # 로깅 설정
    setup_logging()

    # FastAPI 인스턴스 생성
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="""
        🚀 **HAPA (Hancom AI Python Assistant) API**

        **새로운 기능:**
        - 🤖 vLLM 멀티 LoRA 서버 통합
        - 📡 실시간 스트리밍 코드 생성
        - 🌐 한국어/영어 자동 번역
        - 🔄 듀얼 백엔드 (vLLM + Legacy AI)
        - 📊 성능 모니터링 및 분석

        **지원 모델:**
        - `autocomplete`: 코드 자동완성
        - `prompt`: 일반 코드 생성
        - `comment`: 주석/문서 생성
        - `error_fix`: 버그 수정
        """,
        openapi_url=(
            f"{settings.API_V1_PREFIX}/openapi.json"
            if settings.DEBUG else None
        ),
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan
    )

    # 보안 미들웨어 추가 (우선순위 높음)
    hapa_settings = get_settings()
    security_config = {
        "environment": hapa_settings.environment,
        "rate_limit_requests": hapa_settings.security.rate_limit_requests,
        "enable_csp": True,
        "enable_hsts": hapa_settings.security.ssl_enabled
    }
    add_security_middleware(app, security_config)

    # CORS 미들웨어 설정 (보안 강화)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=hapa_settings.security.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
        expose_headers=["X-Process-Time", "X-Rate-Limit-Remaining"]
    )

    # Enhanced 로깅 미들웨어 추가
    app.add_middleware(EnhancedLoggingMiddleware)

    # Trusted Host 미들웨어 (운영환경)
    if not hapa_settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=hapa_settings.security.allowed_hosts
        )

    # API 라우터 포함
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # 에러 핸들러 설정
    setup_error_handlers(app)

    # 루트 레벨 health 체크 (최우선 등록)
    @app.get("/health", tags=["Health"])
    async def health_check():
        """간단한 헬스 체크 - 인증 불필요"""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "HAPA Backend API",
            "version": "1.0.0"
        }

    # 상세 health 체크
    @app.get("/health/detailed", tags=["Health"])
    async def detailed_health_check():
        """상세 헬스 체크"""
        try:
            # vLLM 서버 상태 확인
            vllm_health = await vllm_service.check_health()

            # Enhanced AI 서비스 상태
            backend_status = await enhanced_ai_service.get_backend_status()

            return {
                "status": "healthy",
                "timestamp": time.time(),
                "service": "HAPA Backend API",
                "components": {
                    "vllm_server": {
                        "status": "healthy" if vllm_health["status"] == "healthy" else "degraded",
                        "details": vllm_health
                    },
                    "ai_backend": {
                        "status": "healthy",
                        "current_backend": backend_status["backend_type"],
                        "vllm_available": backend_status["vllm"]["available"]
                    }
                }
            }
        except Exception as e:
            logger.log_error(e, "상세 헬스 체크")
            return {
                "status": "degraded",
                "timestamp": time.time(),
                "error": str(e)
            }

    # 글로벌 미들웨어 - 요청 처리 시간 측정
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # 루트 엔드포인트 - vLLM 통합 상태 표시
    @app.get("/", tags=["Root"])
    async def root():
        """
        HAPA 백엔드 루트 엔드포인트
        vLLM 통합 상태 및 서비스 정보 제공
        """
        try:
            # 백엔드 상태 조회
            backend_status = await enhanced_ai_service.get_backend_status()

            return {
                "service": "HAPA (Hancom AI Python Assistant)",
                "version": "1.0.0",
                "status": "running",
                "timestamp": time.time(),
                "environment": settings.ENVIRONMENT,
                "ai_backends": {
                    "backend_type": backend_status["backend_type"],
                    "vllm": {
                        "available": backend_status["vllm"]["available"],
                        "server_url": settings.VLLM_SERVER_URL
                    }
                },
                "features": [
                    "실시간 스트리밍 코드 생성",
                    "한국어/영어 자동 번역",
                    "vLLM 멀티 LoRA 모델 지원",
                    "스마트 캐시 시스템",
                    "고성능 AI 추론"
                ],
                "endpoints": {
                    "docs": "/docs",
                    "health": "/api/v1/code/health",
                    "streaming": "/api/v1/code/generate/stream",
                    "sync": "/api/v1/code/generate"
                }
            }

        except Exception as e:
            logger.log_error(e, "루트 엔드포인트")
            return {
                "service": "HAPA (Hancom AI Python Assistant)",
                "status": "degraded",
                "error": "백엔드 상태 조회 실패"
            }

    # vLLM 통합 상태 엔드포인트
    @app.get("/vllm/status", tags=["vLLM Integration"])
    async def vllm_status():
        """
        vLLM 멀티 LoRA 서버 통합 상태 상세 조회
        """
        try:
            # vLLM 서버 상태
            health_status = await vllm_service.check_health()

            # 사용 가능한 모델
            models_info = await vllm_service.get_available_models()

            # 백엔드 상태
            backend_status = await enhanced_ai_service.get_backend_status()

            return {
                "vllm_integration": {
                    "server_health": health_status,
                    "available_models": models_info.get("available_models", []),
                    "server_details": models_info,
                    "backend_status": backend_status["vllm"],
                    "configuration": {
                        "server_url": settings.VLLM_SERVER_URL,
                        "timeout": settings.VLLM_TIMEOUT_SECONDS,
                        "max_retries": settings.VLLM_MAX_RETRIES,
                        "connection_pool_size": settings.VLLM_CONNECTION_POOL_SIZE
                    }
                },
                "timestamp": time.time()
            }

        except Exception as e:
            logger.log_error(e, "vLLM 상태 조회")
            return JSONResponse(
                status_code=500,
                content={"error": "vLLM 상태 조회 실패", "details": str(e)}
            )

    return app


app = create_application()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    ) 