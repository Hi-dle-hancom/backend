from fastapi import APIRouter
from app.api.endpoints import code_generation, feedback, validation, history, cache, users, enhanced_code_generation, metrics

# API 라우터 생성
api_router = APIRouter()
 
# 각 엔드포인트 라우터 추가
api_router.include_router(code_generation.router, prefix="/code", tags=["code_generation"])
api_router.include_router(enhanced_code_generation.router, prefix="/code", tags=["enhanced_code_generation"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(validation.router, prefix="/validation", tags=["validation"])
api_router.include_router(history.router, prefix="/history", tags=["history_and_settings"])
api_router.include_router(cache.router, prefix="/cache", tags=["cache-management"])
api_router.include_router(users.router, prefix="/users", tags=["user_management"])

# 메트릭 엔드포인트 (API 버전 prefix 없이 직접 등록)
from fastapi import FastAPI

def add_metrics_router(app: FastAPI):
    """메트릭 라우터를 앱에 직접 추가합니다."""
    app.include_router(metrics.router, tags=["monitoring"]) 