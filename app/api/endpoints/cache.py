import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import APIKeyModel, check_permission, get_current_api_key
from app.core.structured_logger import log_api_request, log_api_response
from app.services.cache_service import (
    cache_clear,
    cache_health_check,
    cache_info,
    cache_monitoring_status,
    cache_stats,
    cache_update_alert_thresholds,
)
from app.services.hybrid_cache_service import hybrid_cache
from app.services.inference import ai_model_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["cache"])


class CacheAlertThresholds(BaseModel):
    """캐시 알림 임계값 설정 모델"""

    memory_usage_mb: Optional[int] = None
    hit_rate_threshold: Optional[float] = None
    max_entries: Optional[int] = None


@router.get("/health")
async def get_cache_health(
    api_key: str = Depends(get_current_api_key),
) -> Dict[str, Any]:
    """캐시 시스템 헬스 체크"""
    start_time = time.time()

    try:
        log_api_request("GET", "/cache/health")

        # 하이브리드 캐시 헬스 체크
        health_status = await hybrid_cache.health_check()

        response_time = (time.time() - start_time) * 1000
        log_api_response("GET", "/cache/health", 200, response_time)

        return {
            "status": "healthy" if health_status["overall"] else "unhealthy",
            "checks": health_status,
            "response_time_ms": round(response_time, 2),
        }

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        log_api_response("GET", "/cache/health", 500, response_time)
        raise HTTPException(status_code=500, detail=f"캐시 헬스 체크 실패: {str(e)}")


@router.get("/stats")
async def get_cache_stats(
    api_key: str = Depends(get_current_api_key),
) -> Dict[str, Any]:
    """캐시 통계 정보 조회"""
    start_time = time.time()

    try:
        log_api_request("GET", "/cache/stats")

        # 캐시 통계 조회
        stats = await hybrid_cache.get_stats()

        response_time = (time.time() - start_time) * 1000
        log_api_response("GET", "/cache/stats", 200, response_time)

        return {
            "cache_stats": stats,
            "response_time_ms": round(
                response_time,
                2)}

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        log_api_response("GET", "/cache/stats", 500, response_time)
        raise HTTPException(status_code=500, detail=f"캐시 통계 조회 실패: {str(e)}")


@router.delete("/clear")
async def clear_cache(
    confirm: bool = Query(False, description="캐시 클리어 확인"),
    api_key: str = Depends(get_current_api_key),
) -> Dict[str, Any]:
    """전체 캐시 클리어 (관리자용)"""
    start_time = time.time()

    try:
        if not confirm:
            raise HTTPException(
                status_code=400,
                detail="캐시 클리어를 위해서는 confirm=true 파라미터가 필요합니다",
            )

        log_api_request("DELETE", "/cache/clear")

        # 캐시 클리어
        success = await hybrid_cache.clear()

        response_time = (time.time() - start_time) * 1000
        status_code = 200 if success else 500
        log_api_response("DELETE", "/cache/clear", status_code, response_time)

        if success:
            return {
                "status": "success",
                "message": "캐시가 성공적으로 클리어되었습니다",
                "response_time_ms": round(response_time, 2),
            }
        else:
            raise HTTPException(status_code=500, detail="캐시 클리어 실패")

    except HTTPException:
        raise
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        log_api_response("DELETE", "/cache/clear", 500, response_time)
        raise HTTPException(status_code=500, detail=f"캐시 클리어 실패: {str(e)}")


@router.post("/test")
async def test_cache_operations(
    api_key: str = Depends(get_current_api_key),
) -> Dict[str, Any]:
    """캐시 작동 테스트 (개발/테스트용)"""
    start_time = time.time()

    try:
        log_api_request("POST", "/cache/test")

        test_results = {}

        # 테스트 데이터
        test_key = "cache_test_key"
        test_value = {"test": "data", "timestamp": time.time()}

        # 1. 캐시 저장 테스트
        set_success = await hybrid_cache.set(test_key, test_value, 60)
        test_results["set_operation"] = {
            "success": set_success, "operation": "set"}

        # 2. 캐시 조회 테스트
        retrieved_value = await hybrid_cache.get(test_key, None)
        test_results["get_operation"] = {
            "success": retrieved_value == test_value,
            "operation": "get",
            "retrieved": retrieved_value is not None,
        }

        # 3. 캐시 존재 확인 테스트
        exists = await hybrid_cache.exists(test_key)
        test_results["exists_operation"] = {
            "success": exists, "operation": "exists"}

        # 4. 캐시 삭제 테스트
        delete_success = await hybrid_cache.delete(test_key)
        test_results["delete_operation"] = {
            "success": delete_success,
            "operation": "delete",
        }

        # 5. 삭제 후 조회 테스트
        after_delete = await hybrid_cache.get(test_key, "not_found")
        test_results["after_delete_check"] = {
            "success": after_delete == "not_found",
            "operation": "get_after_delete",
        }

        overall_success = all(result["success"]
                              for result in test_results.values())

        response_time = (time.time() - start_time) * 1000
        status_code = 200 if overall_success else 500
        log_api_response("POST", "/cache/test", status_code, response_time)

        return {
            "overall_success": overall_success,
            "test_results": test_results,
            "response_time_ms": round(response_time, 2),
        }

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        log_api_response("POST", "/cache/test", 500, response_time)
        raise HTTPException(status_code=500, detail=f"캐시 테스트 실패: {str(e)}")


@router.get("/key/{key}/exists")
async def check_key_exists(
    key: str, api_key: str = Depends(get_current_api_key)
) -> Dict[str, Any]:
    """특정 키의 존재 여부 확인"""
    start_time = time.time()

    try:
        log_api_request("GET", f"/cache/key/{key}/exists")

        exists = await hybrid_cache.exists(key)

        response_time = (time.time() - start_time) * 1000
        log_api_response("GET", f"/cache/key/{key}/exists", 200, response_time)

        return {
            "key": key,
            "exists": exists,
            "response_time_ms": round(response_time, 2),
        }

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        log_api_response("GET", f"/cache/key/{key}/exists", 500, response_time)
        raise HTTPException(status_code=500, detail=f"키 존재 확인 실패: {str(e)}")


@router.delete("/key/{key}")
async def delete_cache_key(
    key: str, api_key: str = Depends(get_current_api_key)
) -> Dict[str, Any]:
    """특정 키 삭제"""
    start_time = time.time()

    try:
        log_api_request("DELETE", f"/cache/key/{key}")

        success = await hybrid_cache.delete(key)

        response_time = (time.time() - start_time) * 1000
        status_code = 200 if success else 404
        log_api_response(
            "DELETE",
            f"/cache/key/{key}",
            status_code,
            response_time)

        if success:
            return {
                "key": key,
                "deleted": True,
                "response_time_ms": round(response_time, 2),
            }
        else:
            raise HTTPException(status_code=404, detail=f"키를 찾을 수 없습니다: {key}")

    except HTTPException:
        raise
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        log_api_response("DELETE", f"/cache/key/{key}", 500, response_time)
        raise HTTPException(status_code=500, detail=f"키 삭제 실패: {str(e)}")

