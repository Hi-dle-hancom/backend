"""
Enhanced Code Generation API 라우터 설정

이 파일은 FastAPI 애플리케이션의 API 라우터를 설정하는 역할을 합니다.
여기에 정의된 라우터는 각 엔드포인트 모듈에서 정의된 엔드포인트를 포함하며,
FastAPI 애플리케이션에 등록되어 실제 요청을 처리하는 역할을 합니다.

이 파일은 애플리케이션의 메인 라우터 설정을 담당하며,
각 엔드포인트 모듈에서 정의된 엔드포인트를 참조하여 라우팅을 설정합니다.
"""

from fastapi import FastAPI
from fastapi import APIRouter

from app.api.endpoints import (
    analytics_dashboard,
    cache,
    code_generation,
    custom_agents,
    error_monitoring,
    feedback,
    history,
    metrics,
    users,
    validation,
)

# API 라우터 생성
api_router = APIRouter()

# 각 엔드포인트 라우터 추가
api_router.include_router(code_generation.router, tags=["Code Generation (Enhanced 통합)"])
api_router.include_router(
    feedback.router,
    prefix="/feedback",
    tags=["Feedback"])
api_router.include_router(
    validation.router,
    prefix="/validation",
    tags=["Validation"])
api_router.include_router(history.router, prefix="/history", tags=["History"])
api_router.include_router(cache.router, prefix="/cache", tags=["Cache"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(
    custom_agents.router, prefix="/agents", tags=["Custom Agents"]
)
api_router.include_router(
    error_monitoring.router,
    prefix="/error-monitoring",
    tags=["Error Monitoring"])
api_router.include_router(
    analytics_dashboard.router, prefix="/analytics", tags=["Analytics"]
)

# 메트릭 엔드포인트 (API 버전 prefix 없이 직접 등록)


def add_metrics_router(app: FastAPI):
    """메트릭 라우터를 앱에 직접 추가합니다."""
    app.include_router(metrics.router, tags=["monitoring"])
