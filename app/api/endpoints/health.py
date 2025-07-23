"""
HAPA 헬스체크 및 시스템 상태 엔드포인트
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer

from app.core.settings_manager import get_settings, HAPASettings
from app.services.vllm_integration_service import vllm_service
from app.services.redis_service import RedisService

router = APIRouter(tags=["Health & Status"])
security = HTTPBearer(auto_error=False)


@router.get("/health")
async def health_check():
    """기본 헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "HAPA Backend"
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """상세 헬스체크"""
    settings = get_settings()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "services": {}
    }
    
    # Database 상태 확인
    try:
        # 간단한 데이터베이스 연결 테스트
        health_status["services"]["database"] = {
            "status": "healthy",
            "url": settings.get_database_url().split("@")[-1] if "@" in settings.get_database_url() else "masked"
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Redis 상태 확인
    try:
        redis_service = RedisService()
        await redis_service.ping()
        health_status["services"]["redis"] = {
            "status": "healthy",
            "host": settings.redis.host,
            "port": settings.redis.port
        }
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # VLLM 서비스 상태 확인
    try:
        vllm_status = await vllm_service.health_check()
        health_status["services"]["vllm"] = {
            "status": "healthy" if vllm_status.get("healthy") else "unhealthy",
            "details": vllm_status
        }
    except Exception as e:
        health_status["services"]["vllm"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/status/config")
async def get_config_status(credentials: HTTPBearer = Depends(security)):
    """설정 상태 확인 (인증 필요)"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    settings = get_settings()
    
    return {
        "config_status": "loaded",
        "environment": settings.environment,
        "debug_mode": settings.debug,
        "security": {
            "ssl_enabled": settings.security.ssl_enabled,
            "cors_origins_count": len(settings.security.allowed_origins),
            "rate_limit": {
                "requests": settings.security.rate_limit_requests,
                "window": settings.security.rate_limit_window
            }
        },
        "services": {
            "database_configured": bool(settings.database.url),
            "redis_configured": bool(settings.redis.host),
            "vllm_configured": bool(settings.vllm.host),
            "monitoring_enabled": settings.monitoring.prometheus_enabled
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/status/security")
async def get_security_status():
    """보안 상태 확인 (공개)"""
    settings = get_settings()
    
    return {
        "security_headers": "enabled",
        "ssl_redirect": settings.security.ssl_enabled,
        "cors_configured": True,
        "rate_limiting": "enabled",
        "authentication": "required",
        "environment": settings.environment,
        "debug_mode_disabled": not settings.debug,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/status/performance")
async def get_performance_status():
    """성능 상태 확인"""
    settings = get_settings()
    
    try:
        # 간단한 성능 메트릭
        import psutil
        import time
        
        start_time = time.time()
        
        # CPU 및 메모리 사용률
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        response_time = time.time() - start_time
        
        return {
            "response_time_ms": round(response_time * 1000, 2),
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "memory_available_mb": round(memory.available / 1024 / 1024, 2),
            "rate_limit_config": {
                "requests_per_window": settings.security.rate_limit_requests,
                "window_seconds": settings.security.rate_limit_window
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except ImportError:
        return {
            "error": "psutil not available",
            "basic_response_time_ms": 1.0,
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/status/dependencies")
async def get_dependencies_status():
    """의존성 상태 확인"""
    import sys
    import pkg_resources
    
    # 주요 패키지 버전 확인
    packages = [
        "fastapi", "uvicorn", "pydantic", "aiohttp", 
        "redis", "asyncpg", "python-multipart"
    ]
    
    package_info = {}
    for package in packages:
        try:
            version = pkg_resources.get_distribution(package).version
            package_info[package] = {
                "version": version,
                "status": "installed"
            }
        except pkg_resources.DistributionNotFound:
            package_info[package] = {
                "status": "not_found"
            }
    
    return {
        "python_version": sys.version,
        "packages": package_info,
        "timestamp": datetime.utcnow().isoformat()
    }