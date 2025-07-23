import cProfile
import logging
import os
import pstats
import time
import tracemalloc
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List
from datetime import datetime, timedelta

import psutil

logger = logging.getLogger(__name__)


class PerformanceProfiler:
    """API 응답 속도 및 성능 분석을 위한 프로파일링 클래스"""

    def __init__(self):
        self.profile_data = {}
        self.memory_tracker = MemoryTracker()

    @contextmanager
    def profile_function(self, function_name: str):
        """함수 실행 시간 및 메모리 사용량 프로파일링"""
        start_time = time.perf_counter()
        start_memory = self.memory_tracker.get_current_memory()

        # 메모리 추적 시작
        tracemalloc.start()

        try:
            yield
        finally:
            # 실행 시간 측정
            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # 메모리 사용량 측정
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            end_memory = self.memory_tracker.get_current_memory()
            memory_diff = end_memory - start_memory

            # 프로파일 데이터 저장
            self.profile_data[function_name] = {
                "execution_time": execution_time,
                "memory_used": memory_diff,
                "peak_memory": peak,
                "timestamp": time.time(),
            }

            logger.info(
                f"[PERFORMANCE] {function_name}: {execution_time:.4f}s, Memory: {memory_diff / 1024 / 1024:.2f}MB"
            )

    def profile_decorator(self, function_name: str = None):
        """데코레이터를 통한 함수 프로파일링"""

        def decorator(func: Callable) -> Callable:
            name = function_name or f"{func.__module__}.{func.__name__}"

            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.profile_function(name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def run_cprofile_analysis(self, func: Callable,
                              *args, **kwargs) -> Dict[str, Any]:
        """cProfile을 사용한 상세 함수 분석"""
        profiler = cProfile.Profile()

        try:
            profiler.enable()
            result = func(*args, **kwargs)
            profiler.disable()

            # 통계 생성
            stats = pstats.Stats(profiler)
            stats.sort_stats("cumulative")

            # 상위 10개 함수 추출
            stats.print_stats(10)

            # 결과 반환
            return {
                "result": result,
                "profile_stats": self._extract_profile_stats(stats),
            }

        except Exception as e:
            logger.error(f"cProfile 분석 실패: {e}")
            return {"result": None, "error": str(e)}

    def _extract_profile_stats(self, stats: pstats.Stats) -> Dict[str, Any]:
        """pstats에서 주요 성능 지표 추출"""
        # 통계를 문자열로 캡처
        import io

        s = io.StringIO()
        stats.print_stats(s)
        stats_output = s.getvalue()

        return {
            "total_calls": stats.total_calls,
            "primitive_calls": stats.prim_calls,
            "total_time": stats.total_tt,
            "stats_output": stats_output[:1000],  # 처음 1000자만
        }

    def get_bottleneck_analysis(self) -> Dict[str, Any]:
        """병목 지점 분석 결과 반환"""
        if not self.profile_data:
            return {"message": "프로파일링 데이터가 없습니다."}

        # 실행 시간 기준 정렬
        sorted_by_time = sorted(
            self.profile_data.items(),
            key=lambda x: x[1]["execution_time"],
            reverse=True,
        )

        # 메모리 사용량 기준 정렬
        sorted_by_memory = sorted(
            self.profile_data.items(),
            key=lambda x: x[1]["memory_used"],
            reverse=True)

        return {
            "slowest_functions": sorted_by_time[:5],
            "memory_intensive_functions": sorted_by_memory[:5],
            "total_functions_profiled": len(self.profile_data),
            "recommendations": self._generate_optimization_recommendations(
                sorted_by_time, sorted_by_memory
            ),
        }

    def _generate_optimization_recommendations(
        self, time_sorted: list, memory_sorted: list, memory_mb: float
    ) -> list:
        """성능 최적화 권장사항 생성"""
        recommendations = []

        # 느린 함수에 대한 권장사항
        if time_sorted and time_sorted[0][1]["execution_time"] > 1.0:
            recommendations.append(
                {
                    "type": "execution_time",
                    "function": time_sorted[0][0],
                    "issue": f"실행 시간이 {time_sorted[0][1]['execution_time']:.2f}초로 느림",
                    "suggestion": "캐싱, 배치 처리, 또는 비동기 처리 고려",
                })

        # 메모리 집약적 함수에 대한 권장사항
        if (memory_sorted and memory_sorted[0][1]
                ["memory_used"] > 100 * 1024 * 1024):  # 100MB
            recommendations.append(
                {
                    "type": "memory_usage",
                    "function": memory_sorted[0][0],
                    "memory_mb": memory_sorted[0][1]['memory_used'] / 1024 / 1024,
                    "issue": f"메모리 사용량이 {memory_mb:.2f}MB로 높음",
                    "suggestion": "제너레이터 사용, 메모리 풀링, 또는 스트리밍 처리 고려",
                })

        return recommendations


class MemoryTracker:
    """메모리 사용량 추적 클래스"""

    def __init__(self):
        self.process = psutil.Process(os.getpid())

    def get_current_memory(self) -> int:
        """현재 메모리 사용량 반환 (바이트)"""
        return self.process.memory_info().rss

    def get_memory_percent(self) -> float:
        """시스템 메모리 대비 사용 비율"""
        return self.process.memory_percent()


class ResponseTimeLogger:
    """API 응답 시간 로깅 클래스"""

    def __init__(self):
        self.response_times = []

    @contextmanager
    def log_response_time(self, endpoint: str, method: str = "POST"):
        """API 응답 시간 로깅"""
        start_time = time.perf_counter()

        try:
            yield
        finally:
            end_time = time.perf_counter()
            response_time = end_time - start_time

            self.response_times.append(
                {
                    "endpoint": endpoint,
                    "method": method,
                    "response_time": response_time,
                    "timestamp": time.time(),
                }
            )

            logger.info(f"[API_RESPONSE_TIME] {method} {endpoint}: {response_time:.4f}s")

    def get_average_response_time(self, endpoint: str = None) -> float:
        """평균 응답 시간 계산"""
        if endpoint:
            filtered_times = [
                rt["response_time"]
                for rt in self.response_times
                if rt["endpoint"] == endpoint
            ]
        else:
            filtered_times = [rt["response_time"]
                              for rt in self.response_times]

        return sum(filtered_times) / \
            len(filtered_times) if filtered_times else 0.0

    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        if not self.response_times:
            return {"message": "응답 시간 데이터가 없습니다."}

        times = [rt["response_time"] for rt in self.response_times]

        return {
            "total_requests": len(self.response_times),
            "average_response_time": sum(times) / len(times),
            "min_response_time": min(times),
            "max_response_time": max(times),
            "last_24h_requests": len(
                [
                    rt
                    for rt in self.response_times
                    if time.time() - rt["timestamp"] < 86400
                ]
            ),
        }


class AIPerformanceThresholds:
    """AI 모델 성능 임계값 정의"""
    
    # 응답 시간 임계값 (초)
    RESPONSE_TIME_EXCELLENT = 1.0
    RESPONSE_TIME_GOOD = 2.0  
    RESPONSE_TIME_ACCEPTABLE = 5.0
    RESPONSE_TIME_POOR = 10.0
    
    # 토큰 생성 속도 임계값 (tokens/second)
    TOKEN_SPEED_EXCELLENT = 50.0
    TOKEN_SPEED_GOOD = 30.0
    TOKEN_SPEED_ACCEPTABLE = 15.0
    TOKEN_SPEED_POOR = 5.0
    
    # 성공률 임계값 (%)
    SUCCESS_RATE_EXCELLENT = 0.98
    SUCCESS_RATE_GOOD = 0.95
    SUCCESS_RATE_ACCEPTABLE = 0.90
    SUCCESS_RATE_POOR = 0.80


class AIPerformanceMetrics:
    """AI 모델 성능 메트릭 수집 및 분석"""
    
    def __init__(self):
        self.metrics_data = {
            "response_times": [],
            "token_speeds": [],
            "success_rates": {},
            "model_performance": {},
            "threshold_violations": [],
            # vLLM 전용 확장 메트릭
            "vllm_metrics": {
                "model_switching": [],  # 모델 전환 기록
                "lora_adapter_usage": {},  # LoRA 어댑터 사용률
                "batch_processing": [],  # 배치 처리 성능
                "gpu_utilization": [],  # GPU 사용률 추적
                "memory_usage": [],  # vLLM 메모리 사용률
                "queue_lengths": [],  # 요청 대기열 길이
            },
            # 실시간 모니터링
            "real_time": {
                "active_requests": 0,
                "current_load": 0.0,
                "last_alert_time": None,
                "consecutive_failures": 0,
            },
            # 예측 분석
            "predictions": {
                "load_forecasts": [],
                "performance_trends": {},
                "anomaly_scores": [],
            }
        }
        
        # 실시간 알림 임계값
        self.alert_thresholds = {
            "critical_response_time": 15.0,  # 15초 이상 시 긴급 알림
            "error_rate_spike": 0.25,  # 25% 이상 오류율 시 알림
            "memory_usage_critical": 0.90,  # 90% 이상 메모리 사용 시 알림
            "token_speed_degradation": 3.0,  # 3 tokens/sec 이하 시 알림
            "consecutive_failures": 5,  # 연속 5회 실패 시 알림
        }
        
        # 성능 예측 설정
        self.prediction_window = 3600  # 1시간 예측 윈도우
        self.trend_analysis_points = 100  # 트렌드 분석용 데이터 포인트
        self.anomaly_threshold = 2.0  # 이상 감지 임계값 (표준편차 배수)
        
    def record_ai_operation(
        self,
        model_name: str,
        response_time: float,
        token_count: int,
        success: bool,
        operation_type: str = "generation"
    ):
        """AI 작업 성능 메트릭 기록"""
        timestamp = datetime.now()
        
        # 토큰 생성 속도 계산
        token_speed = token_count / max(response_time, 0.001)  # division by zero 방지
        
        # 전체 메트릭 업데이트
        self.metrics_data["response_times"].append({
            "timestamp": timestamp,
            "response_time": response_time,
            "model": model_name,
            "operation": operation_type
        })
        
        self.metrics_data["token_speeds"].append({
            "timestamp": timestamp,
            "token_speed": token_speed,
            "token_count": token_count,
            "model": model_name,
            "operation": operation_type
        })
        
        # 모델별 성능 추적
        if model_name not in self.metrics_data["model_performance"]:
            self.metrics_data["model_performance"][model_name] = {
                "total_operations": 0,
                "successful_operations": 0,
                "total_tokens": 0,
                "total_time": 0.0,
                "avg_response_time": 0.0,
                "avg_token_speed": 0.0,
                "success_rate": 0.0
            }
        
        model_metrics = self.metrics_data["model_performance"][model_name]
        model_metrics["total_operations"] += 1
        model_metrics["total_tokens"] += token_count
        model_metrics["total_time"] += response_time
        
        if success:
            model_metrics["successful_operations"] += 1
        
        # 평균값 재계산
        model_metrics["avg_response_time"] = (
            model_metrics["total_time"] / model_metrics["total_operations"]
        )
        model_metrics["avg_token_speed"] = (
            model_metrics["total_tokens"] / model_metrics["total_time"]
            if model_metrics["total_time"] > 0 else 0
        )
        model_metrics["success_rate"] = (
            model_metrics["successful_operations"] / model_metrics["total_operations"]
        )
        
        # 임계값 위반 검사
        self._check_threshold_violations(
            model_name, response_time, token_speed, 
            model_metrics["success_rate"], operation_type
        )
        
        # 실시간 모니터링 업데이트
        self._update_real_time_metrics(response_time, success, token_speed)
        
        # 이상 감지 분석
        self._detect_performance_anomalies(model_name, response_time, token_speed)
        
    def _check_threshold_violations(
        self, 
        model_name: str, 
        response_time: float, 
        token_speed: float,
        success_rate: float,
        operation_type: str
    ):
        """성능 임계값 위반 검사 및 기록"""
        violations = []
        
        # 응답 시간 검사
        if response_time > AIPerformanceThresholds.RESPONSE_TIME_POOR:
            violations.append({
                "type": "response_time",
                "severity": "critical",
                "value": response_time,
                "threshold": AIPerformanceThresholds.RESPONSE_TIME_POOR,
                "message": f"응답 시간이 임계값({AIPerformanceThresholds.RESPONSE_TIME_POOR}초)을 초과했습니다"
            })
        elif response_time > AIPerformanceThresholds.RESPONSE_TIME_ACCEPTABLE:
            violations.append({
                "type": "response_time", 
                "severity": "warning",
                "value": response_time,
                "threshold": AIPerformanceThresholds.RESPONSE_TIME_ACCEPTABLE,
                "message": f"응답 시간이 권장 임계값({AIPerformanceThresholds.RESPONSE_TIME_ACCEPTABLE}초)을 초과했습니다"
            })
        
        # 토큰 생성 속도 검사
        if token_speed < AIPerformanceThresholds.TOKEN_SPEED_POOR:
            violations.append({
                "type": "token_speed",
                "severity": "critical", 
                "value": token_speed,
                "threshold": AIPerformanceThresholds.TOKEN_SPEED_POOR,
                "message": f"토큰 생성 속도가 임계값({AIPerformanceThresholds.TOKEN_SPEED_POOR} tokens/sec) 미만입니다"
            })
        elif token_speed < AIPerformanceThresholds.TOKEN_SPEED_ACCEPTABLE:
            violations.append({
                "type": "token_speed",
                "severity": "warning",
                "value": token_speed, 
                "threshold": AIPerformanceThresholds.TOKEN_SPEED_ACCEPTABLE,
                "message": f"토큰 생성 속도가 권장 임계값({AIPerformanceThresholds.TOKEN_SPEED_ACCEPTABLE} tokens/sec) 미만입니다"
            })
        
        # 성공률 검사
        if success_rate < AIPerformanceThresholds.SUCCESS_RATE_POOR:
            violations.append({
                "type": "success_rate",
                "severity": "critical",
                "value": success_rate,
                "threshold": AIPerformanceThresholds.SUCCESS_RATE_POOR,
                "message": f"성공률이 임계값({AIPerformanceThresholds.SUCCESS_RATE_POOR*100:.1f}%) 미만입니다"
            })
        elif success_rate < AIPerformanceThresholds.SUCCESS_RATE_ACCEPTABLE:
            violations.append({
                "type": "success_rate",
                "severity": "warning", 
                "value": success_rate,
                "threshold": AIPerformanceThresholds.SUCCESS_RATE_ACCEPTABLE,
                "message": f"성공률이 권장 임계값({AIPerformanceThresholds.SUCCESS_RATE_ACCEPTABLE*100:.1f}%) 미만입니다"
            })
        
        # 위반 사항 기록
        if violations:
            violation_record = {
                "timestamp": datetime.now(),
                "model": model_name,
                "operation": operation_type,
                "violations": violations
            }
            self.metrics_data["threshold_violations"].append(violation_record)
            
            # 로그에 기록
            for violation in violations:
                logger.warning(
                    f"AI 성능 임계값 위반 - {model_name}",
                    extra={
                        "violation_type": violation["type"],
                        "severity": violation["severity"],
                        "value": violation["value"],
                        "threshold": violation["threshold"],
                        "message": violation["message"]
                    }
                )
    
    def get_performance_summary(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """성능 요약 보고서 생성"""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        # 시간 범위 내 데이터 필터링
        recent_response_times = [
            m for m in self.metrics_data["response_times"] 
            if m["timestamp"] >= cutoff_time
        ]
        recent_token_speeds = [
            m for m in self.metrics_data["token_speeds"]
            if m["timestamp"] >= cutoff_time
        ]
        recent_violations = [
            v for v in self.metrics_data["threshold_violations"]
            if v["timestamp"] >= cutoff_time
        ]
        
        summary = {
            "time_window_hours": time_window_hours,
            "overview": {
                "total_operations": len(recent_response_times),
                "total_violations": len(recent_violations),
                "critical_violations": len([
                    v for v in recent_violations 
                    if any(viol["severity"] == "critical" for viol in v["violations"])
                ])
            },
            "response_time_stats": self._calculate_stats([
                m["response_time"] for m in recent_response_times
            ]),
            "token_speed_stats": self._calculate_stats([
                m["token_speed"] for m in recent_token_speeds  
            ]),
            "model_performance": {},
            "threshold_compliance": self._calculate_compliance_rates(recent_violations),
            "recommendations": []
        }
        
        # 모델별 성능 요약
        for model_name, metrics in self.metrics_data["model_performance"].items():
            summary["model_performance"][model_name] = {
                "avg_response_time": metrics["avg_response_time"],
                "avg_token_speed": metrics["avg_token_speed"],
                "success_rate": metrics["success_rate"],
                "total_operations": metrics["total_operations"],
                "performance_grade": self._calculate_performance_grade(metrics)
            }
        
        # 성능 개선 권장사항 생성
        summary["recommendations"] = self._generate_recommendations(summary)
        
        return summary
    
    def _calculate_stats(self, values: List[float]) -> Dict[str, float]:
        """통계값 계산"""
        if not values:
            return {"min": 0, "max": 0, "avg": 0, "median": 0, "p95": 0}
        
        import statistics
        
        sorted_values = sorted(values)
        p95_index = int(len(sorted_values) * 0.95)
        
        return {
            "min": min(values),
            "max": max(values), 
            "avg": statistics.mean(values),
            "median": statistics.median(values),
            "p95": sorted_values[p95_index] if p95_index < len(sorted_values) else sorted_values[-1]
        }
    
    def _calculate_compliance_rates(self, violations: List[Dict]) -> Dict[str, float]:
        """임계값 준수율 계산"""
        if not violations:
            return {
                "response_time_compliance": 1.0,
                "token_speed_compliance": 1.0,
                "success_rate_compliance": 1.0,
                "overall_compliance": 1.0
            }
        
        total_operations = len(self.metrics_data["response_times"])
        if total_operations == 0:
            return {"overall_compliance": 1.0}
        
        violation_counts = {
            "response_time": 0,
            "token_speed": 0, 
            "success_rate": 0
        }
        
        for violation_record in violations:
            for violation in violation_record["violations"]:
                violation_type = violation["type"]
                if violation_type in violation_counts:
                    violation_counts[violation_type] += 1
        
        return {
            "response_time_compliance": 1.0 - (violation_counts["response_time"] / total_operations),
            "token_speed_compliance": 1.0 - (violation_counts["token_speed"] / total_operations),
            "success_rate_compliance": 1.0 - (violation_counts["success_rate"] / total_operations),
            "overall_compliance": 1.0 - (sum(violation_counts.values()) / (total_operations * 3))
        }
    
    def _calculate_performance_grade(self, metrics: Dict[str, Any]) -> str:
        """모델 성능 등급 계산"""
        response_time = metrics["avg_response_time"]
        token_speed = metrics["avg_token_speed"] 
        success_rate = metrics["success_rate"]
        
        # 각 메트릭별 점수 (0-100)
        time_score = 100
        if response_time > AIPerformanceThresholds.RESPONSE_TIME_EXCELLENT:
            time_score = 90
        if response_time > AIPerformanceThresholds.RESPONSE_TIME_GOOD:
            time_score = 70
        if response_time > AIPerformanceThresholds.RESPONSE_TIME_ACCEPTABLE:
            time_score = 50
        if response_time > AIPerformanceThresholds.RESPONSE_TIME_POOR:
            time_score = 20
        
        speed_score = 100
        if token_speed < AIPerformanceThresholds.TOKEN_SPEED_EXCELLENT:
            speed_score = 90
        if token_speed < AIPerformanceThresholds.TOKEN_SPEED_GOOD:
            speed_score = 70
        if token_speed < AIPerformanceThresholds.TOKEN_SPEED_ACCEPTABLE:
            speed_score = 50
        if token_speed < AIPerformanceThresholds.TOKEN_SPEED_POOR:
            speed_score = 20
        
        success_score = success_rate * 100
        
        # 가중 평균 (응답시간 40%, 토큰속도 35%, 성공률 25%)
        overall_score = (time_score * 0.4 + speed_score * 0.35 + success_score * 0.25)
        
        if overall_score >= 90:
            return "A"
        elif overall_score >= 80:
            return "B"
        elif overall_score >= 70:
            return "C"
        elif overall_score >= 60:
            return "D"
        else:
            return "F"
    
    def _generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """성능 개선 권장사항 생성"""
        recommendations = []
        
        response_time_avg = summary["response_time_stats"].get("avg", 0)
        token_speed_avg = summary["token_speed_stats"].get("avg", 0)
        compliance = summary["threshold_compliance"]
        
        # 응답 시간 개선
        if response_time_avg > AIPerformanceThresholds.RESPONSE_TIME_GOOD:
            recommendations.append(
                f"평균 응답 시간({response_time_avg:.2f}초)이 목표치({AIPerformanceThresholds.RESPONSE_TIME_GOOD}초)를 초과합니다. "
                "vLLM 서버 리소스 확장이나 모델 최적화를 검토하세요."
            )
        
        # 토큰 생성 속도 개선
        if token_speed_avg < AIPerformanceThresholds.TOKEN_SPEED_GOOD:
            recommendations.append(
                f"평균 토큰 생성 속도({token_speed_avg:.1f} tokens/sec)가 목표치({AIPerformanceThresholds.TOKEN_SPEED_GOOD} tokens/sec) 미만입니다. "
                "GPU 성능 향상이나 배치 크기 조정을 고려하세요."
            )
        
        # 전체 준수율 개선
        if compliance.get("overall_compliance", 1.0) < 0.9:
            recommendations.append(
                f"전체 임계값 준수율({compliance.get('overall_compliance', 1.0)*100:.1f}%)이 90% 미만입니다. "
                "시스템 모니터링을 강화하고 성능 튜닝을 수행하세요."
            )
        
        # 모델별 권장사항
        for model_name, model_perf in summary["model_performance"].items():
            if model_perf["performance_grade"] in ["D", "F"]:
                recommendations.append(
                    f"{model_name} 모델의 성능 등급이 {model_perf['performance_grade']}입니다. "
                    "모델 교체나 하이퍼파라미터 조정을 검토하세요."
                )
        
        if not recommendations:
            recommendations.append("모든 성능 메트릭이 목표치를 만족합니다. 현재 설정을 유지하세요.")
        
        return recommendations

    def record_vllm_metrics(
        self,
        model_name: str,
        lora_adapter: str = None,
        batch_size: int = 1,
        gpu_memory_used: float = 0.0,
        queue_length: int = 0,
        processing_mode: str = "single"
    ):
        """vLLM 특화 메트릭 기록"""
        timestamp = datetime.now()
        
        # 모델 전환 기록
        if hasattr(self, '_last_model') and self._last_model != model_name:
            self.metrics_data["vllm_metrics"]["model_switching"].append({
                "timestamp": timestamp,
                "from_model": getattr(self, '_last_model', 'unknown'),
                "to_model": model_name,
                "switch_latency": 0.0  # 실제 구현에서는 측정된 값 사용
            })
        self._last_model = model_name
        
        # LoRA 어댑터 사용률 추적
        if lora_adapter:
            if lora_adapter not in self.metrics_data["vllm_metrics"]["lora_adapter_usage"]:
                self.metrics_data["vllm_metrics"]["lora_adapter_usage"][lora_adapter] = {
                    "usage_count": 0,
                    "total_tokens": 0,
                    "avg_response_time": 0.0,
                    "last_used": timestamp
                }
            
            adapter_stats = self.metrics_data["vllm_metrics"]["lora_adapter_usage"][lora_adapter]
            adapter_stats["usage_count"] += 1
            adapter_stats["last_used"] = timestamp
        
        # 배치 처리 성능
        self.metrics_data["vllm_metrics"]["batch_processing"].append({
            "timestamp": timestamp,
            "batch_size": batch_size,
            "processing_mode": processing_mode,
            "model": model_name
        })
        
        # GPU 메모리 사용률
        self.metrics_data["vllm_metrics"]["memory_usage"].append({
            "timestamp": timestamp,
            "gpu_memory_used": gpu_memory_used,
            "model": model_name
        })
        
        # 요청 대기열 길이
        self.metrics_data["vllm_metrics"]["queue_lengths"].append({
            "timestamp": timestamp,
            "queue_length": queue_length,
            "model": model_name
        })

    def _update_real_time_metrics(self, response_time: float, success: bool, token_speed: float):
        """실시간 모니터링 메트릭 업데이트"""
        real_time = self.metrics_data["real_time"]
        
        # 현재 부하 계산 (응답 시간 기반)
        load_factor = min(response_time / 2.0, 1.0)  # 2초를 기준으로 정규화
        real_time["current_load"] = (real_time["current_load"] * 0.9) + (load_factor * 0.1)
        
        # 연속 실패 카운트
        if not success:
            real_time["consecutive_failures"] += 1
        else:
            real_time["consecutive_failures"] = 0
        
        # 임계값 기반 실시간 알림 체크
        self._check_real_time_alerts(response_time, success, token_speed)

    def _check_real_time_alerts(self, response_time: float, success: bool, token_speed: float):
        """실시간 알림 조건 체크"""
        current_time = datetime.now()
        real_time = self.metrics_data["real_time"]
        
        # 마지막 알림으로부터 최소 간격 체크 (5분)
        if (real_time["last_alert_time"] and 
            (current_time - real_time["last_alert_time"]).total_seconds() < 300):
            return
        
        alerts = []
        
        # 긴급 응답 시간 알림
        if response_time > self.alert_thresholds["critical_response_time"]:
            alerts.append({
                "type": "critical_response_time",
                "severity": "critical",
                "message": f"응답 시간이 {response_time:.2f}초로 임계값({self.alert_thresholds['critical_response_time']}초)을 초과했습니다",
                "value": response_time,
                "timestamp": current_time
            })
        
        # 토큰 속도 저하 알림
        if token_speed < self.alert_thresholds["token_speed_degradation"]:
            alerts.append({
                "type": "token_speed_degradation", 
                "severity": "warning",
                "message": f"토큰 생성 속도가 {token_speed:.2f} tokens/sec로 임계값({self.alert_thresholds['token_speed_degradation']})을 하회했습니다",
                "value": token_speed,
                "timestamp": current_time
            })
        
        # 연속 실패 알림
        if real_time["consecutive_failures"] >= self.alert_thresholds["consecutive_failures"]:
            alerts.append({
                "type": "consecutive_failures",
                "severity": "critical",
                "message": f"연속 {real_time['consecutive_failures']}회 실패가 발생했습니다",
                "value": real_time["consecutive_failures"],
                "timestamp": current_time
            })
        
        # 알림 발송
        if alerts:
            self._send_alerts(alerts)
            real_time["last_alert_time"] = current_time

    def _send_alerts(self, alerts: List[Dict]):
        """알림 발송 (로깅 및 외부 시스템 연동)"""
        for alert in alerts:
            # 로그에 기록
            log_level = logging.CRITICAL if alert["severity"] == "critical" else logging.WARNING
            logger.log(
                log_level,
                f"vLLM 성능 알림: {alert['message']}",
                extra={
                    "alert_type": alert["type"],
                    "severity": alert["severity"],
                    "value": alert["value"],
                    "timestamp": alert["timestamp"].isoformat()
                }
            )
            
            # 외부 알림 시스템 연동 (실제 환경에서는 Slack, 이메일 등)
            # self._send_external_alert(alert)

    def _detect_performance_anomalies(self, model_name: str, response_time: float, token_speed: float):
        """성능 이상 감지"""
        # 최근 데이터 포인트 수집 (최근 50개)
        recent_response_times = [
            m["response_time"] for m in self.metrics_data["response_times"][-50:]
            if m["model"] == model_name
        ]
        
        recent_token_speeds = [
            m["token_speed"] for m in self.metrics_data["token_speeds"][-50:]
            if m["model"] == model_name
        ]
        
        if len(recent_response_times) < 10:  # 충분한 데이터가 없으면 스킵
            return
        
        # 이상 점수 계산 (Z-score 기반)
        import statistics
        
        # 응답 시간 이상 감지
        rt_mean = statistics.mean(recent_response_times)
        rt_stdev = statistics.stdev(recent_response_times) if len(recent_response_times) > 1 else 0
        
        if rt_stdev > 0:
            rt_zscore = abs(response_time - rt_mean) / rt_stdev
            if rt_zscore > self.anomaly_threshold:
                self.metrics_data["predictions"]["anomaly_scores"].append({
                    "timestamp": datetime.now(),
                    "model": model_name,
                    "metric": "response_time",
                    "value": response_time,
                    "zscore": rt_zscore,
                    "is_anomaly": True
                })
        
        # 토큰 속도 이상 감지
        if recent_token_speeds:
            ts_mean = statistics.mean(recent_token_speeds)
            ts_stdev = statistics.stdev(recent_token_speeds) if len(recent_token_speeds) > 1 else 0
            
            if ts_stdev > 0:
                ts_zscore = abs(token_speed - ts_mean) / ts_stdev
                if ts_zscore > self.anomaly_threshold:
                    self.metrics_data["predictions"]["anomaly_scores"].append({
                        "timestamp": datetime.now(),
                        "model": model_name,
                        "metric": "token_speed",
                        "value": token_speed,
                        "zscore": ts_zscore,
                        "is_anomaly": True
                    })

    def predict_performance_trend(self, model_name: str, forecast_minutes: int = 60) -> Dict[str, Any]:
        """성능 트렌드 예측"""
        # 최근 데이터 수집
        cutoff_time = datetime.now() - timedelta(hours=4)  # 4시간 데이터 기반 예측
        
        recent_data = [
            m for m in self.metrics_data["response_times"]
            if m["timestamp"] >= cutoff_time and m["model"] == model_name
        ]
        
        if len(recent_data) < 20:  # 충분한 데이터가 없으면 예측 불가
            return {
                "model": model_name,
                "prediction_available": False,
                "reason": "insufficient_data",
                "min_data_points": 20,
                "current_data_points": len(recent_data)
            }
        
        # 간단한 선형 트렌드 분석
        timestamps = [(m["timestamp"] - cutoff_time).total_seconds() for m in recent_data]
        response_times = [m["response_time"] for m in recent_data]
        
        # 최소자승법을 이용한 트렌드 계산
        n = len(timestamps)
        sum_x = sum(timestamps)
        sum_y = sum(response_times)
        sum_xy = sum(x * y for x, y in zip(timestamps, response_times))
        sum_x2 = sum(x * x for x in timestamps)
        
        # 기울기와 절편 계산
        if n * sum_x2 - sum_x * sum_x != 0:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            intercept = (sum_y - slope * sum_x) / n
        else:
            slope = 0
            intercept = sum_y / n if n > 0 else 0
        
        # 미래 예측
        future_seconds = forecast_minutes * 60
        predicted_response_time = intercept + slope * (timestamps[-1] + future_seconds)
        
        # 트렌드 분류
        if abs(slope) < 0.001:
            trend = "stable"
        elif slope > 0:
            trend = "degrading"
        else:
            trend = "improving"
        
        prediction = {
            "model": model_name,
            "prediction_available": True,
            "forecast_minutes": forecast_minutes,
            "current_avg_response_time": sum(response_times[-10:]) / 10,  # 최근 10개 평균
            "predicted_response_time": max(0, predicted_response_time),
            "trend": trend,
            "trend_slope": slope,
            "confidence": min(100, len(recent_data) * 2),  # 단순한 신뢰도 계산
            "data_points_used": len(recent_data),
            "prediction_timestamp": datetime.now()
        }
        
        # 예측 결과 저장
        self.metrics_data["predictions"]["performance_trends"][model_name] = prediction
        
        return prediction

    def get_vllm_performance_dashboard(self) -> Dict[str, Any]:
        """vLLM 성능 대시보드 데이터 생성"""
        current_time = datetime.now()
        
        # 최근 1시간 데이터
        one_hour_ago = current_time - timedelta(hours=1)
        
        # vLLM 특화 메트릭 요약
        vllm_metrics = self.metrics_data["vllm_metrics"]
        
        # 모델 전환 빈도
        recent_switches = [
            s for s in vllm_metrics["model_switching"]
            if s["timestamp"] >= one_hour_ago
        ]
        
        # GPU 메모리 사용률
        recent_memory = [
            m for m in vllm_metrics["memory_usage"]
            if m["timestamp"] >= one_hour_ago
        ]
        
        avg_memory_usage = (
            sum(m["gpu_memory_used"] for m in recent_memory) / len(recent_memory)
            if recent_memory else 0
        )
        
        # 대기열 길이 통계
        recent_queues = [
            q for q in vllm_metrics["queue_lengths"]
            if q["timestamp"] >= one_hour_ago
        ]
        
        avg_queue_length = (
            sum(q["queue_length"] for q in recent_queues) / len(recent_queues)
            if recent_queues else 0
        )
        
        # LoRA 어댑터 사용률
        adapter_stats = {}
        for adapter, stats in vllm_metrics["lora_adapter_usage"].items():
            if stats["last_used"] >= one_hour_ago:
                adapter_stats[adapter] = {
                    "usage_count": stats["usage_count"],
                    "avg_response_time": stats["avg_response_time"],
                    "last_used_minutes_ago": (current_time - stats["last_used"]).total_seconds() / 60
                }
        
        # 실시간 상태
        real_time = self.metrics_data["real_time"]
        
        # 성능 등급 계산
        performance_grade = self._calculate_vllm_performance_grade(
            avg_memory_usage, avg_queue_length, len(recent_switches)
        )
        
        return {
            "timestamp": current_time.isoformat(),
            "summary": {
                "performance_grade": performance_grade,
                "current_load": real_time["current_load"],
                "active_requests": real_time["active_requests"],
                "consecutive_failures": real_time["consecutive_failures"]
            },
            "vllm_metrics": {
                "model_switches_last_hour": len(recent_switches),
                "avg_gpu_memory_usage": avg_memory_usage,
                "avg_queue_length": avg_queue_length,
                "active_lora_adapters": len(adapter_stats),
                "lora_adapter_stats": adapter_stats
            },
            "predictions": {
                "performance_trends": self.metrics_data["predictions"]["performance_trends"],
                "anomaly_count_last_hour": len([
                    a for a in self.metrics_data["predictions"]["anomaly_scores"]
                    if a["timestamp"] >= one_hour_ago
                ])
            },
            "recommendations": self._generate_vllm_optimization_recommendations()
        }

    def _calculate_vllm_performance_grade(
        self, avg_memory_usage: float, avg_queue_length: float, model_switches: int
    ) -> str:
        """vLLM 성능 등급 계산"""
        score = 100
        
        # 메모리 사용률에 따른 점수 차감
        if avg_memory_usage > 0.9:
            score -= 30
        elif avg_memory_usage > 0.8:
            score -= 15
        elif avg_memory_usage > 0.7:
            score -= 5
        
        # 대기열 길이에 따른 점수 차감
        if avg_queue_length > 10:
            score -= 25
        elif avg_queue_length > 5:
            score -= 10
        elif avg_queue_length > 2:
            score -= 5
        
        # 모델 전환 빈도에 따른 점수 차감 (너무 빈번하면 비효율)
        if model_switches > 20:
            score -= 15
        elif model_switches > 10:
            score -= 5
        
        # 등급 분류
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        else:
            return "D"

    def _generate_vllm_optimization_recommendations(self) -> List[str]:
        """vLLM 최적화 권장사항 생성"""
        recommendations = []
        vllm_metrics = self.metrics_data["vllm_metrics"]
        
        # 최근 메모리 사용률 분석
        recent_memory = vllm_metrics["memory_usage"][-20:]  # 최근 20개
        if recent_memory:
            avg_memory = sum(m["gpu_memory_used"] for m in recent_memory) / len(recent_memory)
            
            if avg_memory > 0.9:
                recommendations.append("GPU 메모리 사용률이 높습니다. 배치 크기를 줄이거나 모델 분할을 고려하세요.")
            elif avg_memory > 0.8:
                recommendations.append("GPU 메모리 사용률이 높은 편입니다. 모니터링을 강화하세요.")
        
        # 대기열 길이 분석
        recent_queues = vllm_metrics["queue_lengths"][-20:]
        if recent_queues:
            avg_queue = sum(q["queue_length"] for q in recent_queues) / len(recent_queues)
            
            if avg_queue > 5:
                recommendations.append("요청 대기열이 길어지고 있습니다. 워커 프로세스 증설을 고려하세요.")
        
        # 모델 전환 분석
        recent_switches = vllm_metrics["model_switching"][-10:]
        if len(recent_switches) > 10:
            recommendations.append("모델 전환이 빈번합니다. 모델 로딩 캐시 최적화를 고려하세요.")
        
        # LoRA 어댑터 사용 분석
        adapter_usage = vllm_metrics["lora_adapter_usage"]
        if len(adapter_usage) > 5:
            underused_adapters = [
                name for name, stats in adapter_usage.items()
                if stats["usage_count"] < 10
            ]
            if underused_adapters:
                recommendations.append(f"사용률이 낮은 LoRA 어댑터가 있습니다: {', '.join(underused_adapters[:3])}")
        
        # 기본 권장사항
        if not recommendations:
            recommendations.append("현재 성능이 양호합니다. 정기적인 모니터링을 계속하세요.")
        
        return recommendations

    def reset_metrics(self):
        """메트릭 데이터 초기화 (강화된 버전)"""
        self.__init__()  # 전체 재초기화
        logger.info("AI 성능 메트릭이 초기화되었습니다 (vLLM 전용 메트릭 포함)")


# 전역 인스턴스
profiler = PerformanceProfiler()
response_timer = ResponseTimeLogger()

# 전역 AI 성능 메트릭 인스턴스
ai_performance_metrics = AIPerformanceMetrics()
