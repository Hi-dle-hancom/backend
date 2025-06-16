import cProfile
import pstats
import time
import logging
from functools import wraps
from typing import Callable, Any, Dict
from contextlib import contextmanager
import tracemalloc
import psutil
import os

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
                "timestamp": time.time()
            }
            
            logger.info(f"[PERFORMANCE] {function_name}: {execution_time:.4f}s, Memory: {memory_diff/1024/1024:.2f}MB")

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
    
    def run_cprofile_analysis(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """cProfile을 사용한 상세 함수 분석"""
        profiler = cProfile.Profile()
        
        try:
            profiler.enable()
            result = func(*args, **kwargs)
            profiler.disable()
            
            # 통계 생성
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumulative')
            
            # 상위 10개 함수 추출
            stats.print_stats(10)
            
            # 결과 반환
            return {
                "result": result,
                "profile_stats": self._extract_profile_stats(stats)
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
            "stats_output": stats_output[:1000]  # 처음 1000자만
        }
    
    def get_bottleneck_analysis(self) -> Dict[str, Any]:
        """병목 지점 분석 결과 반환"""
        if not self.profile_data:
            return {"message": "프로파일링 데이터가 없습니다."}
        
        # 실행 시간 기준 정렬
        sorted_by_time = sorted(
            self.profile_data.items(),
            key=lambda x: x[1]["execution_time"],
            reverse=True
        )
        
        # 메모리 사용량 기준 정렬
        sorted_by_memory = sorted(
            self.profile_data.items(),
            key=lambda x: x[1]["memory_used"],
            reverse=True
        )
        
        return {
            "slowest_functions": sorted_by_time[:5],
            "memory_intensive_functions": sorted_by_memory[:5],
            "total_functions_profiled": len(self.profile_data),
            "recommendations": self._generate_optimization_recommendations(sorted_by_time, sorted_by_memory)
        }
    
    def _generate_optimization_recommendations(self, time_sorted: list, memory_sorted: list) -> list:
        """성능 최적화 권장사항 생성"""
        recommendations = []
        
        # 느린 함수에 대한 권장사항
        if time_sorted and time_sorted[0][1]["execution_time"] > 1.0:
            recommendations.append({
                "type": "execution_time",
                "function": time_sorted[0][0],
                "issue": f"실행 시간이 {time_sorted[0][1]['execution_time']:.2f}초로 느림",
                "suggestion": "캐싱, 배치 처리, 또는 비동기 처리 고려"
            })
        
        # 메모리 집약적 함수에 대한 권장사항
        if memory_sorted and memory_sorted[0][1]["memory_used"] > 100 * 1024 * 1024:  # 100MB
            recommendations.append({
                "type": "memory_usage",
                "function": memory_sorted[0][0],
                "issue": f"메모리 사용량이 {memory_sorted[0][1]['memory_used']/1024/1024:.2f}MB로 높음",
                "suggestion": "제너레이터 사용, 메모리 풀링, 또는 스트리밍 처리 고려"
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
            
            self.response_times.append({
                "endpoint": endpoint,
                "method": method,
                "response_time": response_time,
                "timestamp": time.time()
            })
            
            logger.info(f"[API_RESPONSE_TIME] {method} {endpoint}: {response_time:.4f}s")
    
    def get_average_response_time(self, endpoint: str = None) -> float:
        """평균 응답 시간 계산"""
        if endpoint:
            filtered_times = [
                rt["response_time"] for rt in self.response_times 
                if rt["endpoint"] == endpoint
            ]
        else:
            filtered_times = [rt["response_time"] for rt in self.response_times]
        
        return sum(filtered_times) / len(filtered_times) if filtered_times else 0.0
    
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
            "last_24h_requests": len([
                rt for rt in self.response_times 
                if time.time() - rt["timestamp"] < 86400
            ])
        }

# 전역 인스턴스
profiler = PerformanceProfiler()
response_timer = ResponseTimeLogger() 