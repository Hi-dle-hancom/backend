"""
HAPA 백엔드 메트릭 엔드포인트
Prometheus 호환 메트릭을 제공합니다.
"""

import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

import psutil
from fastapi import APIRouter, Response, Query, Depends
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from fastapi.security import OAuth2PasswordRequestForm

from app.core.rate_limiter import limiter
from app.core.security import get_api_key, get_current_user
from app.core.structured_logger import StructuredLogger

logger = StructuredLogger("metrics")

router = APIRouter(tags=["metrics"])

# 메트릭 정의
REQUEST_COUNT = Counter(
    "hapa_requests_total", "Total number of requests", [
        "method", "endpoint", "status"])

REQUEST_DURATION = Histogram(
    "hapa_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)

ACTIVE_CONNECTIONS = Gauge(
    "hapa_active_connections",
    "Number of active connections")

CACHE_HITS = Counter("hapa_cache_hits_total", "Total number of cache hits")

CACHE_MISSES = Counter(
    "hapa_cache_misses_total",
    "Total number of cache misses")

AI_MODEL_REQUESTS = Counter(
    "hapa_ai_model_requests_total",
    "Total number of AI model requests",
    ["model_type", "status"],
)

AI_MODEL_RESPONSE_TIME = Histogram(
    "hapa_ai_model_response_time_seconds",
    "AI model response time in seconds",
    ["model_type"],
)

SYSTEM_CPU_USAGE = Gauge(
    "hapa_system_cpu_usage_percent",
    "System CPU usage percentage")

SYSTEM_MEMORY_USAGE = Gauge(
    "hapa_system_memory_usage_bytes", "System memory usage in bytes"
)

SYSTEM_DISK_USAGE = Gauge(
    "hapa_system_disk_usage_bytes",
    "System disk usage in bytes")

ERROR_COUNT = Counter(
    "hapa_errors_total", "Total number of errors", ["error_type", "endpoint"]
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
    disk = psutil.disk_usage("/")
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

    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)


@router.get("/health/detailed")
async def get_detailed_health() -> Dict[str, Any]:
    """
    상세한 시스템 상태 정보를 반환합니다.

    Returns:
        Dict[str, Any]: 상세 상태 정보
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "system": {
            "cpu": {"usage_percent": cpu_percent, "count": psutil.cpu_count()},
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100,
            },
        },
        "application": {
            "uptime_seconds": time.time() - psutil.Process().create_time(),
            "pid": psutil.Process().pid,
        },
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


def record_ai_model_request(
        model_type: str,
        status: str,
        response_time: float):
    """AI 모델 요청을 기록합니다."""
    AI_MODEL_REQUESTS.labels(model_type=model_type, status=status).inc()
    AI_MODEL_RESPONSE_TIME.labels(model_type=model_type).observe(response_time)


def record_error(error_type: str, endpoint: str):
    """에러를 기록합니다."""
    ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()


def set_active_connections(count: int):
    """활성 연결 수를 설정합니다."""
    ACTIVE_CONNECTIONS.set(count)


@router.get("/ai-performance", response_model=Dict[str, Any], summary="AI 모델 성능 메트릭 조회")
@limiter.limit("10/minute")
async def get_ai_performance_metrics(
    time_window_hours: int = Query(default=24, ge=1, le=168, description="조회 시간 범위 (시간)"),
    api_key: str = Depends(get_api_key),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    AI 모델 성능 메트릭 및 임계값 모니터링 API
    
    **제공 정보:**
    - 📊 **응답 시간 통계**: 평균, 최대, P95, 임계값 준수율
    - 🚀 **토큰 생성 속도**: 평균 tokens/second, 모델별 성능
    - 🎯 **성공률 추적**: 모델별 성공률, 오류 패턴 분석
    - ⚠️ **임계값 위반**: 실시간 알림, 성능 등급
    - 💡 **개선 권장사항**: AI 기반 성능 최적화 제안
    
    **임계값 기준:**
    - 응답시간: 우수(1초), 양호(2초), 허용(5초), 부족(10초+)
    - 토큰속도: 우수(50+), 양호(30+), 허용(15+), 부족(5+ tokens/sec)
    - 성공률: 우수(98%+), 양호(95%+), 허용(90%+), 부족(80%+)
    """
    try:
        from app.services.performance_profiler import ai_performance_metrics
        from app.services.enhanced_ai_model import enhanced_ai_service
        
        user_id = current_user.get("user_id", "admin")
        
        logger.info(
            f"AI 성능 메트릭 조회 요청",
            extra={
                "user_id": user_id,
                "time_window_hours": time_window_hours,
            }
        )
        
        # 성능 요약 보고서 생성
        performance_summary = ai_performance_metrics.get_performance_summary(time_window_hours)
        
        # 백엔드 상태 정보 조회
        backend_status = await enhanced_ai_service.get_backend_status()
        
        # 응답 데이터 구성
        response_data = {
            "success": True,
            "time_window": {
                "hours": time_window_hours,
                "start_time": (datetime.now() - timedelta(hours=time_window_hours)).isoformat(),
                "end_time": datetime.now().isoformat()
            },
            "overview": performance_summary["overview"],
            "performance_metrics": {
                "response_time": {
                    "stats": performance_summary["response_time_stats"],
                    "threshold_compliance": performance_summary["threshold_compliance"]["response_time_compliance"],
                    "target": 2.0,
                    "status": _get_metric_status(
                        performance_summary["response_time_stats"].get("avg", 0),
                        "response_time"
                    )
                },
                "token_generation_speed": {
                    "stats": performance_summary["token_speed_stats"],
                    "threshold_compliance": performance_summary["threshold_compliance"]["token_speed_compliance"],
                    "target": 30.0,
                    "status": _get_metric_status(
                        performance_summary["token_speed_stats"].get("avg", 0),
                        "token_speed"
                    )
                },
                "success_rate": {
                    "overall": performance_summary["threshold_compliance"]["success_rate_compliance"],
                    "target": 0.95,
                    "status": _get_metric_status(
                        performance_summary["threshold_compliance"]["success_rate_compliance"],
                        "success_rate"
                    )
                }
            },
            "model_performance": performance_summary["model_performance"],
            "backend_status": {
                "current_backend": backend_status["current_backend"],
                "vllm_available": backend_status["backends"]["vllm"]["available"],
                "backend_type": "vllm_only"
            },
            "alerts": backend_status["performance_metrics"]["alerts"],
            "recommendations": performance_summary["recommendations"],
            "threshold_violations": {
                "total": performance_summary["overview"]["total_violations"],
                "critical": performance_summary["overview"]["critical_violations"]
            }
        }
        
        # 성공 로깅
        logger.info(
            f"AI 성능 메트릭 조회 성공",
            extra={
                "user_id": user_id,
                "total_operations": performance_summary["overview"]["total_operations"],
                "total_violations": performance_summary["overview"]["total_violations"],
                "response_time_avg": performance_summary["response_time_stats"].get("avg", 0),
                "token_speed_avg": performance_summary["token_speed_stats"].get("avg", 0),
            }
        )
        
        return response_data
        
    except Exception as e:
        error_msg = f"AI 성능 메트릭 조회 실패: {str(e)}"
        
        logger.error(
            error_msg,
            extra={
                "user_id": user_id,
                "time_window_hours": time_window_hours,
                "exception": str(e),
            }
        )
        
        return {
            "success": False,
            "error_message": "성능 메트릭 조회 중 오류가 발생했습니다",
            "time_window": {
                "hours": time_window_hours,
                "start_time": (datetime.now() - timedelta(hours=time_window_hours)).isoformat(),
                "end_time": datetime.now().isoformat()
            }
        }


def _get_metric_status(value: float, metric_type: str) -> str:
    """메트릭 값에 따른 상태 반환"""
    from app.services.performance_profiler import AIPerformanceThresholds
    
    if metric_type == "response_time":
        if value <= AIPerformanceThresholds.RESPONSE_TIME_EXCELLENT:
            return "excellent"
        elif value <= AIPerformanceThresholds.RESPONSE_TIME_GOOD:
            return "good"
        elif value <= AIPerformanceThresholds.RESPONSE_TIME_ACCEPTABLE:
            return "acceptable"
        else:
            return "poor"
    
    elif metric_type == "token_speed":
        if value >= AIPerformanceThresholds.TOKEN_SPEED_EXCELLENT:
            return "excellent"
        elif value >= AIPerformanceThresholds.TOKEN_SPEED_GOOD:
            return "good"
        elif value >= AIPerformanceThresholds.TOKEN_SPEED_ACCEPTABLE:
            return "acceptable"
        else:
            return "poor"
    
    elif metric_type == "success_rate":
        if value >= AIPerformanceThresholds.SUCCESS_RATE_EXCELLENT:
            return "excellent"
        elif value >= AIPerformanceThresholds.SUCCESS_RATE_GOOD:
            return "good"
        elif value >= AIPerformanceThresholds.SUCCESS_RATE_ACCEPTABLE:
            return "acceptable"
        else:
            return "poor"
    
    return "unknown"


@router.get("/ai-performance/alerts", response_model=Dict[str, Any], summary="AI 성능 알림 조회")
@limiter.limit("30/minute")
async def get_ai_performance_alerts(
    severity: Optional[str] = Query(default=None, description="알림 심각도 필터 (critical, warning)"),
    api_key: str = Depends(get_api_key),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    AI 모델 성능 알림 조회 API
    
    **알림 유형:**
    - 🔴 **Critical**: 응답시간 10초+, 토큰속도 5 tokens/sec 미만, 성공률 80% 미만
    - 🟡 **Warning**: 응답시간 5초+, 토큰속도 15 tokens/sec 미만, 성공률 90% 미만
    
    **알림 정보:**
    - 실시간 성능 임계값 위반 
    - 모델별 성능 저하 감지
    - 시스템 리소스 부족 경고
    """
    try:
        from app.services.performance_profiler import ai_performance_metrics
        
        user_id = current_user.get("user_id", "admin")
        
        # 최근 24시간 위반 사항 조회
        recent_violations = [
            v for v in ai_performance_metrics.metrics_data["threshold_violations"]
            if (datetime.now() - v["timestamp"]).total_seconds() < 86400  # 24시간
        ]
        
        # 심각도 필터링
        filtered_alerts = []
        for violation_record in recent_violations:
            for violation in violation_record["violations"]:
                if severity is None or violation["severity"] == severity:
                    filtered_alerts.append({
                        "timestamp": violation_record["timestamp"].isoformat(),
                        "model": violation_record["model"],
                        "operation": violation_record["operation"],
                        "severity": violation["severity"],
                        "type": violation["type"],
                        "value": violation["value"],
                        "threshold": violation["threshold"],
                        "message": violation["message"]
                    })
        
        # 최신순 정렬
        filtered_alerts.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "success": True,
            "total_alerts": len(filtered_alerts),
            "severity_filter": severity,
            "alerts": filtered_alerts[:50],  # 최대 50개 제한
            "summary": {
                "critical_count": len([a for a in filtered_alerts if a["severity"] == "critical"]),
                "warning_count": len([a for a in filtered_alerts if a["severity"] == "warning"]),
                "most_common_issue": _get_most_common_issue(filtered_alerts)
            }
        }
        
    except Exception as e:
        logger.error(f"AI 성능 알림 조회 실패: {e}")
        return {
            "success": False,
            "error_message": "성능 알림 조회 중 오류가 발생했습니다",
            "total_alerts": 0,
            "alerts": []
        }


def _get_most_common_issue(alerts: List[Dict[str, Any]]) -> Optional[str]:
    """가장 빈번한 성능 이슈 타입 반환"""
    if not alerts:
        return None
    
    issue_counts = {}
    for alert in alerts:
        issue_type = alert["type"]
        issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
    
    most_common = max(issue_counts.items(), key=lambda x: x[1])
    return most_common[0] if most_common[1] > 0 else None
