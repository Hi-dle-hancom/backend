from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from app.core.security import check_permission, APIKeyModel
from app.services.cache_service import cache_info, cache_stats, cache_clear
from app.services.inference import ai_model_service

router = APIRouter()

@router.get("/stats", response_model=Dict[str, Any])
async def get_cache_stats(
    api_key: APIKeyModel = Depends(check_permission("admin"))
):
    """
    캐시 통계 정보를 반환합니다.
    
    관리자 권한이 필요합니다.
    """
    try:
        stats = cache_stats()
        return {
            "status": "success",
            "cache_stats": stats,
            "ai_service_stats": ai_model_service.get_cache_stats()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"캐시 통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/info", response_model=Dict[str, Any])
async def get_cache_info(
    api_key: APIKeyModel = Depends(check_permission("admin"))
):
    """
    상세 캐시 정보를 반환합니다.
    
    관리자 권한이 필요합니다.
    """
    try:
        info = cache_info()
        return {
            "status": "success",
            "cache_info": info
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"캐시 정보 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.delete("/clear")
async def clear_cache(
    api_key: APIKeyModel = Depends(check_permission("admin"))
):
    """
    모든 캐시를 삭제합니다.
    
    관리자 권한이 필요합니다.
    """
    try:
        success = cache_clear()
        ai_cache_cleared = ai_model_service.clear_cache()
        
        if success:
            return {
                "status": "success",
                "message": "모든 캐시가 성공적으로 삭제되었습니다.",
                "system_cache_cleared": success,
                "ai_cache_cleared": ai_cache_cleared
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="캐시 삭제에 실패했습니다."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"캐시 삭제 중 오류가 발생했습니다: {str(e)}"
        ) 