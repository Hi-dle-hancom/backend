"""
HAPA 실무 로깅 분석 대시보드 API
- 실시간 로그 통계 조회
- 비즈니스 메트릭 분석
- 성능 인사이트 제공
- 비용 추적 대시보드
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.production_logging_strategy import production_logger
from app.core.security import APIKeyModel, check_permission, get_current_api_key
from app.middleware.enhanced_logging_middleware import EnhancedLoggingMiddleware
from app.services.enhanced_ai_logging import enhanced_ai_logger

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard/overview")
async def get_dashboard_overview(
    hours: int = Query(24, description="조회할 시간 범위 (시간)", ge=1, le=168),
    api_key: APIKeyModel = Depends(check_permission("analytics")),
) -> Dict[str, Any]:
    """
    실무 대시보드 개요 정보를 조회합니다.
    - 전체적인 시스템 상태
    - 핵심 비즈니스 메트릭
    - 실시간 성능 지표
    """

    try:
        # AI 비용 요약 조회
        cost_summary = enhanced_ai_logger.get_cost_summary(
            days=max(1, hours // 24))

        # 성능 인사이트 조회
        performance_insights = enhanced_ai_logger.get_performance_insights()

        # 시스템 메트릭 계산
        current_time = datetime.utcnow()
        period_start = current_time - timedelta(hours=hours)

        overview = {
            "dashboard_metadata": {
                "generated_at": current_time.isoformat() + "Z",
                "period_hours": hours,
                "period_start": period_start.isoformat() + "Z",
                "period_end": current_time.isoformat() + "Z",
            },
            "business_metrics": {
                "total_ai_operations": cost_summary.get("total_operations", 0),
                "total_ai_cost": round(cost_summary.get("total_cost", 0), 4),
                "average_cost_per_operation": round(
                    cost_summary.get("average_cost_per_operation", 0), 6
                ),
                "cost_trend": _calculate_cost_trend(cost_summary),
            },
            "performance_metrics": {
                "active_operations": performance_insights.get("active_operations", 0),
                "models_in_use": performance_insights.get("models_in_use", []),
                "operation_types_active": performance_insights.get(
                    "operation_types_active", []
                ),
            },
            "operational_health": {
                "logging_system": "healthy",
                "cost_tracking": performance_insights.get(
                    "cost_tracking_enabled", False
                ),
                "ai_services": (
                    "operational"
                    if performance_insights.get("active_operations", 0) >= 0
                    else "degraded"
                ),
            },
        }

        return overview

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"대시보드 개요 조회 실패: {str(e)}"
        )


@router.get("/performance/detailed")
async def get_detailed_performance_metrics(
    api_key: APIKeyModel = Depends(check_permission("analytics")),
) -> Dict[str, Any]:
    """
    상세 성능 메트릭을 조회합니다.
    - API별 응답 시간 분석
    - 에러율 및 성공률 통계
    - 캐시 효율성 분석
    """

    try:
        # 미들웨어에서 성능 요약 조회
        # 실제 구현에서는 미들웨어 인스턴스에 접근하는 방법이 필요
        # 임시로 모의 데이터 반환

        performance_data = {
            "api_performance": {
                "/api/v1/generate": {
                    "avg_response_time_ms": 2847.3,
                    "total_requests": 1234,
                    "error_rate": 0.023,
                    "last_activity": datetime.utcnow().timestamp(),
                    "performance_category": "good",
                },
                "/api/v1/complete": {
                    "avg_response_time_ms": 456.7,
                    "total_requests": 5678,
                    "error_rate": 0.012,
                    "last_activity": datetime.utcnow().timestamp(),
                    "performance_category": "excellent",
                },
            },
            "system_performance": {
                "overall_health": "good",
                "avg_cpu_usage": 45.6,
                "memory_usage_percent": 67.8,
                "cache_hit_rate": 0.832,
            },
            "user_experience": {
                "fast_responses_percent": 78.5,  # <1초
                "acceptable_responses_percent": 19.2,  # 1-3초
                "slow_responses_percent": 2.3,  # >3초
            },
        }

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "performance_data": performance_data,
            "insights": _generate_performance_insights(performance_data),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성능 메트릭 조회 실패: {str(e)}")


@router.get("/costs/analysis")
async def get_cost_analysis(
    days: int = Query(7, description="분석할 일수", ge=1, le=90),
    breakdown_by: str = Query(
        "model", description="분석 기준", regex="^(model|operation|daily)$"
    ),
    api_key: APIKeyModel = Depends(check_permission("analytics")),
) -> Dict[str, Any]:
    """
    AI 비용 상세 분석을 제공합니다.
    - 모델별, 작업별, 일별 비용 분석
    - 비용 최적화 권장사항
    - 예산 대비 사용률
    """

    try:
        cost_summary = enhanced_ai_logger.get_cost_summary(days=days)

        analysis = {
            "period_summary": cost_summary["period"],
            "total_metrics": {
                "total_cost": cost_summary["total_cost"],
                "total_operations": cost_summary["total_operations"],
                "average_cost_per_operation": cost_summary[
                    "average_cost_per_operation"
                ],
                "daily_average_cost": (
                    cost_summary["total_cost"] / days if days > 0 else 0
                ),
            },
        }

        # 분석 기준에 따른 상세 데이터
        if breakdown_by == "model":
            analysis["breakdown"] = cost_summary["model_breakdown"]
            analysis["insights"] = _generate_model_cost_insights(
                cost_summary["model_breakdown"]
            )

        elif breakdown_by == "operation":
            analysis["breakdown"] = cost_summary["operation_type_breakdown"]
            analysis["insights"] = _generate_operation_cost_insights(
                cost_summary["operation_type_breakdown"]
            )

        elif breakdown_by == "daily":
            analysis["breakdown"] = cost_summary["daily_breakdown"]
            analysis["insights"] = _generate_daily_cost_insights(
                cost_summary["daily_breakdown"]
            )

        # 비용 최적화 권장사항
        analysis["optimization_recommendations"] = (
            _generate_cost_optimization_recommendations(cost_summary)
        )

        return analysis

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"비용 분석 실패: {str(e)}")


@router.get("/logs/realtime")
async def get_realtime_log_stream(
    log_level: str = Query(
        "INFO", description="로그 레벨 필터", regex="^(DEBUG|INFO|WARNING|ERROR)$"
    ),
    api_category: Optional[str] = Query(None, description="API 카테고리 필터"),
    limit: int = Query(100, description="최대 로그 수", ge=1, le=1000),
    api_key: APIKeyModel = Depends(check_permission("analytics")),
) -> Dict[str, Any]:
    """
    실시간 로그 스트림을 조회합니다.
    - 최근 로그 엔트리 조회
    - 필터링 및 검색 기능
    - 실시간 알림 대상 로그 식별
    """

    try:
        # 실제 구현에서는 로그 저장소에서 조회
        # 임시로 모의 데이터 반환

        mock_logs = [
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=i)).isoformat()
                + "Z",
                "event_type": (
                    "api_response_end" if i % 2 == 0 else "ai_operation_start"
                ),
                "log_level": "INFO",
                "endpoint": "/api/v1/generate" if i % 3 == 0 else "/api/v1/complete",
                "duration_ms": 2000 + (i * 100),
                "status_code": 200 if i % 10 != 0 else 500,
                "user_id_hash": f"user_{i % 5}",
                "business_critical": i % 3 == 0,
            }
            for i in range(min(limit, 50))
        ]

        # 필터 적용
        filtered_logs = [
            log
            for log in mock_logs
            if log["log_level"] == log_level
            and (api_category is None or api_category in log.get("endpoint", ""))
        ]

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "filters_applied": {
                "log_level": log_level,
                "api_category": api_category,
                "limit": limit,
            },
            "total_matching_logs": len(filtered_logs),
            "logs": filtered_logs[:limit],
            "summary": {
                "error_count": len(
                    [log for log in filtered_logs if log.get("status_code", 200) >= 400]
                ),
                "avg_response_time": (
                    sum(log.get("duration_ms", 0) for log in filtered_logs)
                    / len(filtered_logs)
                    if filtered_logs
                    else 0
                ),
                "business_critical_count": len(
                    [
                        log
                        for log in filtered_logs
                        if log.get("business_critical", False)
                    ]
                ),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"실시간 로그 조회 실패: {str(e)}")


@router.get("/search")
async def search_logs(
    query: str = Query(..., description="검색어", min_length=3),
    start_time: Optional[datetime] = Query(None, description="검색 시작 시간"),
    end_time: Optional[datetime] = Query(None, description="검색 종료 시간"),
    log_types: Optional[List[str]] = Query(None, description="로그 타입 필터"),
    api_key: APIKeyModel = Depends(check_permission("analytics")),
) -> Dict[str, Any]:
    """
    로그 검색 기능을 제공합니다.
    - 키워드 기반 검색
    - 시간 범위 필터링
    - 로그 타입별 필터링
    """

    try:
        # 검색 파라미터 검증
        if not start_time:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if not end_time:
            end_time = datetime.utcnow()

        if start_time >= end_time:
            raise HTTPException(
                status_code=400, detail="시작 시간은 종료 시간보다 이전이어야 합니다."
            )

        # 실제 구현에서는 Elasticsearch나 로그 저장소에서 검색
        # 임시로 모의 검색 결과 반환

        search_results = {
            "search_metadata": {
                "query": query,
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z",
                "log_types_filter": log_types,
                "search_duration_ms": 45.6,
            },
            "results": [
                {
                    "timestamp": "2024-12-28T10:30:15Z",
                    "event_type": "ai_operation_end",
                    "operation_id": "req_123_generate_1703761815000",
                    "match_reason": f"Contains '{query}' in operation logs",
                    "context": {
                        "endpoint": "/api/v1/generate",
                        "duration_ms": 2847,
                        "status": "success",
                    },
                }
            ],
            "statistics": {
                "total_matches": 1,
                "matches_by_type": {
                    "ai_operation": 1,
                    "api_request": 0,
                    "error_event": 0,
                },
                "time_distribution": {
                    "last_hour": 1,
                    "last_6_hours": 1,
                    "last_24_hours": 1,
                },
            },
        }

        return search_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"로그 검색 실패: {str(e)}")


# 헬퍼 함수들


def _calculate_cost_trend(cost_summary: Dict[str, Any]) -> str:
    """비용 트렌드 계산"""
    daily_breakdown = cost_summary.get("daily_breakdown", {})

    if len(daily_breakdown) < 2:
        return "insufficient_data"

    # 최근 2일의 비용 비교
    dates = sorted(daily_breakdown.keys())
    if len(dates) >= 2:
        recent_cost = daily_breakdown[dates[-1]]["total_cost"]
        previous_cost = daily_breakdown[dates[-2]]["total_cost"]

        if recent_cost > previous_cost * 1.1:
            return "increasing"
        elif recent_cost < previous_cost * 0.9:
            return "decreasing"

    return "stable"


def _generate_performance_insights(
        performance_data: Dict[str, Any]) -> List[str]:
    """성능 인사이트 생성"""
    insights = []

    api_perf = performance_data.get("api_performance", {})

    # 느린 API 식별
    slow_apis = [
        endpoint
        for endpoint, metrics in api_perf.items()
        if metrics.get("avg_response_time_ms", 0) > 2000
    ]

    if slow_apis:
        insights.append(f"느린 응답시간 API 감지: {', '.join(slow_apis)}")

    # 에러율 분석
    high_error_apis = [
        endpoint
        for endpoint, metrics in api_perf.items()
        if metrics.get("error_rate", 0) > 0.05
    ]

    if high_error_apis:
        insights.append(f"높은 에러율 API: {', '.join(high_error_apis)}")

    # 캐시 효율성
    cache_hit_rate = performance_data.get("system_performance", {}).get(
        "cache_hit_rate", 0
    )
    if cache_hit_rate < 0.7:
        insights.append("캐시 적중률이 낮습니다. 캐시 전략 검토가 필요합니다.")

    return insights


def _generate_model_cost_insights(
        model_breakdown: Dict[str, Any]) -> List[str]:
    """모델별 비용 인사이트 생성"""
    insights = []

    if not model_breakdown:
        return ["모델 사용 데이터가 없습니다."]

    # 가장 비싼 모델 식별
    most_expensive = max(model_breakdown.items(), key=lambda x: x[1]["cost"])
    insights.append(
        f"가장 비용이 높은 모델: {most_expensive[0]} (${most_expensive[1]['cost']:.4f})"
    )

    # 효율성 분석
    for model, data in model_breakdown.items():
        if data["count"] > 0:
            cost_per_operation = data["cost"] / data["count"]
            if cost_per_operation > 0.01:  # $0.01 이상
                insights.append(
                    f"{model}: 작업당 높은 비용 (${cost_per_operation:.4f}/작업)"
                )

    return insights


def _generate_operation_cost_insights(
        operation_breakdown: Dict[str, Any]) -> List[str]:
    """작업별 비용 인사이트 생성"""
    insights = []

    if not operation_breakdown:
        return ["작업 데이터가 없습니다."]

    # 비용 효율성이 낮은 작업 유형 식별
    for op_type, data in operation_breakdown.items():
        if data["count"] > 10:  # 충분한 샘플
            cost_per_operation = data["cost"] / data["count"]
            if cost_per_operation > 0.005:
                insights.append(
                    f"{op_type} 작업: 비용 최적화 필요 (${cost_per_operation:.4f}/작업)"
                )

    return insights


def _generate_daily_cost_insights(
        daily_breakdown: Dict[str, Any]) -> List[str]:
    """일별 비용 인사이트 생성"""
    insights = []

    if len(daily_breakdown) < 2:
        return ["일별 트렌드 분석을 위한 데이터가 부족합니다."]

    dates = sorted(daily_breakdown.keys())
    costs = [daily_breakdown[date]["total_cost"] for date in dates]

    # 급격한 비용 증가 감지
    for i in range(1, len(costs)):
        if costs[i] > costs[i - 1] * 2:
            insights.append(f"{dates[i]}: 전일 대비 비용 급증 (${costs[i]:.4f})")

    return insights


def _generate_cost_optimization_recommendations(
    cost_summary: Dict[str, Any]
) -> List[str]:
    """비용 최적화 권장사항 생성"""
    recommendations = []

    # 캐시 활용도 증대
    recommendations.append("캐시 활용도를 높여 중복 AI 호출을 줄이세요.")

    # 모델 선택 최적화
    model_breakdown = cost_summary.get("model_breakdown", {})
    if "gpt-4-turbo" in model_breakdown:
        recommendations.append("간단한 작업에는 GPT-3.5-turbo 사용을 고려하세요.")

    # 배치 처리
    if cost_summary.get("total_operations", 0) > 1000:
        recommendations.append("작업을 배치로 묶어서 처리하여 효율성을 높이세요.")

    return recommendations
