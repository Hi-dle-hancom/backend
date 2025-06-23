"""
HAPA 백엔드 메트릭 엔드포인트
Prometheus 호환 메트릭을 제공합니다.
"""
from fastapi import APIRouter, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY
)
import psutil
import time
from typing import Dict, Any

router = APIRouter(tags=["metrics"])

# 메트릭 정의
REQUEST_COUNT = Counter(
    'hapa_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'hapa_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'hapa_active_connections',
    'Number of active connections'
)

CACHE_HITS = Counter(
    'hapa_cache_hits_total',
    'Total number of cache hits'
)

CACHE_MISSES = Counter(
    'hapa_cache_misses_total',
    'Total number of cache misses'
)

AI_MODEL_REQUESTS = Counter(
    'hapa_ai_model_requests_total',
    'Total number of AI model requests',
    ['model_type', 'status']
)

AI_MODEL_RESPONSE_TIME = Histogram(
    'hapa_ai_model_response_time_seconds',
    'AI model response time in seconds',
    ['model_type']
)

SYSTEM_CPU_USAGE = Gauge(
    'hapa_system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'hapa_system_memory_usage_bytes',
    'System memory usage in bytes'
)

SYSTEM_DISK_USAGE = Gauge(
    'hapa_system_disk_usage_bytes',
    'System disk usage in bytes'
)

ERROR_COUNT = Counter(
    'hapa_errors_total',
    'Total number of errors',
    ['error_type', 'endpoint']
)

def update_system_metrics():
    """시스템 메트릭을 업데이트합니다."""
    # CPU 사용률
    cpu_percent = psutil.cpu_percent(interval=1)
    SYSTEM_CPU_USAGE.set(cpu_percent)
    
    # 메모리 사용률
    memory = psutil.virtual_memory()
    SYSTEM_MEMORY_USAGE.set(memory.used)
    
    # 디스크 사용률
    disk = psutil.disk_usage('/')
    SYSTEM_DISK_USAGE.set(disk.used)

@router.get("/metrics")
async def get_metrics():
    """
    Prometheus 호환 메트릭을 반환합니다.
    
    Returns:
        Response: Prometheus 메트릭 데이터
    """
    # 시스템 메트릭 업데이트
    update_system_metrics()
    
    # Prometheus 메트릭 생성
    metrics_data = generate_latest(REGISTRY)
    
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/health/detailed")
async def get_detailed_health() -> Dict[str, Any]:
    """
    상세한 시스템 상태 정보를 반환합니다.
    
    Returns:
        Dict[str, Any]: 상세 상태 정보
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "system": {
            "cpu": {
                "usage_percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100
            }
        },
        "application": {
            "uptime_seconds": time.time() - psutil.Process().create_time(),
            "pid": psutil.Process().pid
        }
    }

# 메트릭 수집을 위한 헬퍼 함수들
def record_request(method: str, endpoint: str, status: int, duration: float):
    """요청 메트릭을 기록합니다."""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

def record_cache_hit():
    """캐시 히트를 기록합니다."""
    CACHE_HITS.inc()

def record_cache_miss():
    """캐시 미스를 기록합니다."""
    CACHE_MISSES.inc()

def record_ai_model_request(model_type: str, status: str, response_time: float):
    """AI 모델 요청을 기록합니다."""
    AI_MODEL_REQUESTS.labels(model_type=model_type, status=status).inc()
    AI_MODEL_RESPONSE_TIME.labels(model_type=model_type).observe(response_time)

def record_error(error_type: str, endpoint: str):
    """에러를 기록합니다."""
    ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()

def set_active_connections(count: int):
    """활성 연결 수를 설정합니다."""
    ACTIVE_CONNECTIONS.set(count) 