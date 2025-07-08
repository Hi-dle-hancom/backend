import logging
from typing import Any, Dict, Optional
import time
import asyncio

from app.services.cache_service import PersistentCache
from app.services.redis_service import redis_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class SmartHybridCacheService:
    """스마트 하이브리드 캐시 시스템 - 단일 진입점 최적화"""

    def __init__(self):
        self.redis = redis_service
        # 통일된 데이터 경로로 파일 캐시 초기화
        cache_dir = f"{settings.get_absolute_data_dir}/cache"
        self.file_cache = PersistentCache(cache_dir=cache_dir)
        self.redis_available = False
        self.last_health_check = 0
        self.health_check_interval = 60  # 60초마다 헬스 체크
        
        # TTL 정책 매핑
        self.ttl_policies = {
            "short": 300,     # 5분 - 자주 변경되는 데이터
            "medium": 1800,   # 30분 - 일반적인 데이터  
            "long": 7200,     # 2시간 - 안정적인 데이터
            "extended": 86400 # 24시간 - 거의 변경되지 않는 데이터
        }
        
        # 성능 메트릭
        self.metrics = {
            "redis_hits": 0,
            "file_hits": 0,
            "misses": 0,
            "failovers": 0,
            "last_reset": time.time()
        }

    async def init(self) -> bool:
        """스마트 하이브리드 캐시 초기화"""
        await self._health_check()
        logger.info(f"스마트 하이브리드 캐시 초기화: Redis {'사용 가능' if self.redis_available else '사용 불가'}")
        return True

    async def _health_check(self) -> bool:
        """정기적인 헬스 체크"""
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return self.redis_available
            
        try:
            self.redis_available = await self.redis.health_check()
            self.last_health_check = current_time
            
            if not self.redis_available:
                logger.warning("Redis 서버 사용 불가 - 파일 캐시로 페일오버")
                self.metrics["failovers"] += 1
                
        except Exception as e:
            logger.error(f"헬스 체크 실패: {e}")
            self.redis_available = False
            
        return self.redis_available

    async def set(self, key: str, value: Any, ttl: Optional[int] = None, policy: str = "medium") -> bool:
        """스마트 캐시 저장 - TTL 정책 지원"""
        await self._health_check()
        
        # TTL 정책 적용
        if ttl is None:
            ttl = self.ttl_policies.get(policy, self.ttl_policies["medium"])
            
        redis_success = False
        file_success = False

        # Redis 우선 저장
        if self.redis_available:
            try:
                redis_success = await self.redis.set_cache(key, value, ttl)
                if redis_success:
                    logger.debug(f"스마트 캐시: Redis 저장 성공 - {key} (TTL: {ttl}s)")
            except Exception as e:
                logger.warning(f"Redis 저장 실패, 파일 캐시 백업: {e}")
                self.redis_available = False
                self.metrics["failovers"] += 1

        # 파일 캐시 백업 저장
        try:
            file_success = self.file_cache.set(key, value, ttl, policy)
            if file_success:
                logger.debug(f"스마트 캐시: 파일 캐시 저장 성공 - {key}")
        except Exception as e:
            logger.error(f"파일 캐시 저장 실패: {e}")

        return redis_success or file_success

    async def get(self, key: str, default: Any = None) -> Any:
        """스마트 캐시 조회 - 성능 메트릭 수집"""
        await self._health_check()
        
        # Redis 우선 조회
        if self.redis_available:
            try:
                value = await self.redis.get_cache(key, None)
                if value is not None:
                    self.metrics["redis_hits"] += 1
                    logger.debug(f"스마트 캐시: Redis 히트 - {key}")
                    return value
            except Exception as e:
                logger.warning(f"Redis 조회 실패: {e}")
                self.redis_available = False

        # 파일 캐시 조회
        try:
            value = self.file_cache.get(key, default)
            if value != default:
                self.metrics["file_hits"] += 1
                logger.debug(f"스마트 캐시: 파일 캐시 히트 - {key}")
                
                # Redis 복구 시 자동 동기화
                if self.redis_available:
                    try:
                        await self.redis.set_cache(key, value)
                        logger.debug(f"스마트 캐시: Redis 자동 동기화 - {key}")
                    except:
                        pass
                        
                return value
            else:
                self.metrics["misses"] += 1
                
        except Exception as e:
            logger.error(f"파일 캐시 조회 실패: {e}")
            self.metrics["misses"] += 1
            
        return default

    async def delete(self, key: str) -> bool:
        """스마트 캐시 삭제 - 모든 백엔드에서 제거"""
        await self._health_check()
        
        redis_success = False
        file_success = False

        # Redis에서 삭제
        if self.redis_available:
            try:
                redis_success = await self.redis.delete_cache(key)
                logger.debug(f"스마트 캐시: Redis 삭제 - {key}")
            except Exception as e:
                logger.warning(f"Redis 삭제 실패: {e}")

        # 파일 캐시에서 삭제
        try:
            file_success = self.file_cache.delete(key)
            logger.debug(f"스마트 캐시: 파일 캐시 삭제 - {key}")
        except Exception as e:
            logger.error(f"파일 캐시 삭제 실패: {e}")

        return redis_success or file_success

    async def exists(self, key: str) -> bool:
        """스마트 캐시 키 존재 확인"""
        await self._health_check()
        
        # Redis 확인
        if self.redis_available:
            try:
                if await self.redis.exists_cache(key):
                    return True
            except Exception as e:
                logger.warning(f"Redis 존재 확인 실패: {e}")

        # 파일 캐시 확인
        try:
            return self.file_cache.exists(key)
        except Exception as e:
            logger.error(f"파일 캐시 존재 확인 실패: {e}")
            return False

    async def clear(self) -> bool:
        """전체 캐시 클리어"""
        await self._health_check()
        
        redis_success = False
        file_success = False

        # Redis 클리어
        if self.redis_available:
            try:
                await self.redis.clear_cache()
                redis_success = True
                logger.info("스마트 캐시: Redis 전체 클리어 완료")
            except Exception as e:
                logger.warning(f"Redis 클리어 실패: {e}")

        # 파일 캐시 클리어
        try:
            file_success = self.file_cache.clear()
            logger.info("스마트 캐시: 파일 캐시 전체 클리어 완료")
        except Exception as e:
            logger.error(f"파일 캐시 클리어 실패: {e}")

        # 메트릭 리셋
        self.reset_metrics()
        
        return redis_success or file_success

    async def get_stats(self) -> Dict[str, Any]:
        """통합 캐시 통계 정보"""
        await self._health_check()
        
        stats = {
            "smart_hybrid_cache": {
                "redis_available": self.redis_available,
                "file_cache_available": True,
                "last_health_check": self.last_health_check,
                "health_check_interval": self.health_check_interval,
            },
            "performance_metrics": self.get_performance_metrics()
        }

        # Redis 통계
        if self.redis_available:
            try:
                redis_stats = await self.redis.get_stats()
                stats["redis"] = redis_stats
            except Exception as e:
                logger.warning(f"Redis 통계 조회 실패: {e}")
                stats["redis"] = {"error": str(e)}

        # 파일 캐시 통계
        try:
            file_stats = self.file_cache.get_advanced_stats()
            stats["file_cache"] = file_stats
        except Exception as e:
            logger.error(f"파일 캐시 통계 조회 실패: {e}")
            stats["file_cache"] = {"error": str(e)}

        return stats

    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 반환"""
        total_requests = self.metrics["redis_hits"] + self.metrics["file_hits"] + self.metrics["misses"]
        
        if total_requests > 0:
            redis_hit_rate = self.metrics["redis_hits"] / total_requests
            file_hit_rate = self.metrics["file_hits"] / total_requests
            overall_hit_rate = (self.metrics["redis_hits"] + self.metrics["file_hits"]) / total_requests
        else:
            redis_hit_rate = file_hit_rate = overall_hit_rate = 0.0
            
        return {
            "total_requests": total_requests,
            "redis_hits": self.metrics["redis_hits"],
            "file_hits": self.metrics["file_hits"],
            "misses": self.metrics["misses"],
            "failovers": self.metrics["failovers"],
            "redis_hit_rate": round(redis_hit_rate, 3),
            "file_hit_rate": round(file_hit_rate, 3),
            "overall_hit_rate": round(overall_hit_rate, 3),
            "uptime_seconds": int(time.time() - self.metrics["last_reset"])
        }

    def reset_metrics(self):
        """성능 메트릭 리셋"""
        self.metrics = {
            "redis_hits": 0,
            "file_hits": 0,
            "misses": 0,
            "failovers": 0,
            "last_reset": time.time()
        }
        logger.info("스마트 캐시 성능 메트릭 리셋 완료")

    async def health_check(self) -> Dict[str, Any]:
        """종합 헬스 체크"""
        await self._health_check()
        
        redis_healthy = False
        file_healthy = False

        # Redis 헬스 체크
        try:
            redis_healthy = await self.redis.health_check()
            self.redis_available = redis_healthy
        except Exception as e:
            logger.warning(f"Redis 헬스 체크 실패: {e}")

        # 파일 캐시 헬스 체크 (간단한 읽기/쓰기 테스트)
        try:
            test_key = "health_check_test"
            test_value = {"test": True, "timestamp": time.time()}
            file_healthy = (
                self.file_cache.set(test_key, test_value, 5)
                and self.file_cache.get(test_key) == test_value
            )
            self.file_cache.delete(test_key)
        except Exception as e:
            logger.error(f"파일 캐시 헬스 체크 실패: {e}")

        performance = self.get_performance_metrics()
        
        return {
            "timestamp": time.time(),
            "backends": {
                "redis": {
                    "healthy": redis_healthy,
                    "available": self.redis_available,
                },
                "file_cache": {
                    "healthy": file_healthy,
                    "available": True
                }
            },
            "overall_healthy": redis_healthy or file_healthy,
            "performance_summary": {
                "total_requests": performance["total_requests"],
                "overall_hit_rate": performance["overall_hit_rate"],
                "failovers": performance["failovers"]
            },
            "recommendations": self._get_health_recommendations(performance, redis_healthy, file_healthy)
        }

    def _get_health_recommendations(self, performance: Dict, redis_healthy: bool, file_healthy: bool) -> list:
        """헬스 체크 기반 권장사항 생성"""
        recommendations = []
        
        if not redis_healthy:
            recommendations.append("Redis 서버 연결 상태를 확인하세요")
            
        if not file_healthy:
            recommendations.append("파일 캐시 디스크 공간 및 권한을 확인하세요")
            
        if performance["overall_hit_rate"] < 0.7:
            recommendations.append("캐시 히트율이 낮습니다. TTL 정책을 검토하세요")
            
        if performance["failovers"] > 10:
            recommendations.append("Redis 페일오버가 빈번합니다. 네트워크 상태를 확인하세요")
            
        if not recommendations:
            recommendations.append("캐시 시스템이 정상적으로 작동 중입니다")
            
        return recommendations


# 글로벌 스마트 하이브리드 캐시 인스턴스 (단일 진입점)
smart_cache = SmartHybridCacheService()


# 편의 함수들 - 단일 진입점 제공
async def cache_set(key: str, value: Any, ttl: Optional[int] = None, policy: str = "medium") -> bool:
    """스마트 하이브리드 캐시 저장"""
    return await smart_cache.set(key, value, ttl, policy)


async def cache_get(key: str, default: Any = None) -> Any:
    """스마트 하이브리드 캐시 조회"""
    return await smart_cache.get(key, default)


async def cache_delete(key: str) -> bool:
    """스마트 하이브리드 캐시 삭제"""
    return await smart_cache.delete(key)


async def cache_exists(key: str) -> bool:
    """스마트 하이브리드 캐시 키 존재 확인"""
    return await smart_cache.exists(key)


async def cache_clear() -> bool:
    """스마트 하이브리드 캐시 전체 클리어"""
    return await smart_cache.clear()


async def cache_stats() -> Dict[str, Any]:
    """스마트 하이브리드 캐시 통계"""
    return await smart_cache.get_stats()


async def cache_health() -> Dict[str, Any]:
    """스마트 하이브리드 캐시 헬스 체크"""
    return await smart_cache.health_check()


# 레거시 호환성을 위한 별칭 (향후 제거 예정)
hybrid_cache = smart_cache
