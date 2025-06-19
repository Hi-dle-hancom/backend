from fastapi import APIRouter
from app.api.endpoints import code_generation, feedback, validation, history, cache, users

# API 라우터 생성
api_router = APIRouter()
 
# 각 엔드포인트 라우터 추가
api_router.include_router(code_generation.router, prefix="/code", tags=["code_generation"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(validation.router, prefix="/validation", tags=["validation"])
api_router.include_router(history.router, prefix="/history", tags=["history_and_settings"])
api_router.include_router(cache.router, prefix="/cache", tags=["cache-management"])
api_router.include_router(users.router, prefix="/users", tags=["user_management"]) 