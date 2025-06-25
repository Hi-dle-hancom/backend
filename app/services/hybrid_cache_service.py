import logging
from typing import Any, Optional, Dict
from app.services.redis_service import redis_service
from app.services.cache_service import PersistentCache

logger = logging.getLogger(__name__)

class HybridCacheService:
    """Redis 우선, 파일 캐시 백업 하이브리드 캐시 시스템"""
    
    def __init__(self):
        self.redis = redis_service
        self.file_cache = PersistentCache()
        self.redis_available = False
    
    async def init(self) -> bool:
        """하이브리드 캐시 초기화"""
        self.redis_available = await self.redis.health_check()
        logger.info(f"하이브리드 캐시 초기화: Redis {'사용 가능' if self.redis_available else '사용 불가'}")
        return True
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시에 값 저장 (Redis 우선, 파일 캐시 백업)"""
        redis_success = False
        file_success = False
        
        # Redis에 저장 시도
        if self.redis_available:
            try:
                redis_success = await self.redis.set_cache(key, value, ttl)
                if redis_success:
                    logger.debug(f"하이브리드 캐시: Redis 저장 성공 - {key}")
            except Exception as e:
                logger.warning(f"Redis 저장 실패, 파일 캐시로 백업: {e}")
                self.redis_available = False
        
        # 파일 캐시에 백업 저장
        try:
            file_success = self.file_cache.set(key, value, ttl)
            if file_success:
                logger.debug(f"하이브리드 캐시: 파일 캐시 저장 성공 - {key}")
        except Exception as e:
            logger.error(f"파일 캐시 저장 실패: {e}")
        
        return redis_success or file_success
    
    async def get(self, key: str, default: Any = None) -> Any:
        """캐시에서 값 조회 (Redis 우선, 파일 캐시 백업)"""
        # Redis에서 조회 시도
        if self.redis_available:
            try:
                value = await self.redis.get_cache(key, None)
                if value is not None:
                    logger.debug(f"하이브리드 캐시: Redis 히트 - {key}")
                    return value
            except Exception as e:
                logger.warning(f"Redis 조회 실패: {e}")
                self.redis_available = False
        
        # 파일 캐시에서 조회
        try:
            value = self.file_cache.get(key, default)
            if value != default:
                logger.debug(f"하이브리드 캐시: 파일 캐시 히트 - {key}")
                # Redis가 다시 사용 가능하면 Redis에도 저장
                if self.redis_available:
                    try:
                        await self.redis.set_cache(key, value)
                    except:
                        pass
            return value
        except Exception as e:
            logger.error(f"파일 캐시 조회 실패: {e}")
            return default
    
    async def delete(self, key: str) -> bool:
        """캐시에서 키 삭제 (Redis + 파일 캐시 모두)"""
        redis_success = False
        file_success = False
        
        # Redis에서 삭제
        if self.redis_available:
            try:
                redis_success = await self.redis.delete_cache(key)
            except Exception as e:
                logger.warning(f"Redis 삭제 실패: {e}")
        
        # 파일 캐시에서 삭제
        try:
            file_success = self.file_cache.delete(key)
        except Exception as e:
            logger.error(f"파일 캐시 삭제 실패: {e}")
        
        return redis_success or file_success
    
    async def exists(self, key: str) -> bool:
        """캐시 키 존재 여부 확인"""
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
        redis_success = False
        file_success = False
        
        # Redis 클리어
        if self.redis_available:
            try:
                await self.redis.clear_cache()
                redis_success = True
            except Exception as e:
                logger.warning(f"Redis 클리어 실패: {e}")
        
        # 파일 캐시 클리어
        try:
            file_success = self.file_cache.clear()
        except Exception as e:
            logger.error(f"파일 캐시 클리어 실패: {e}")
        
        return redis_success or file_success
    
    async def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보"""
        stats = {
            "hybrid_cache": {
                "redis_available": self.redis_available,
                "file_cache_available": True
            }
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
            file_stats = self.file_cache.get_stats()
            stats["file_cache"] = file_stats
        except Exception as e:
            logger.error(f"파일 캐시 통계 조회 실패: {e}")
            stats["file_cache"] = {"error": str(e)}
        
        return stats
    
    async def health_check(self) -> Dict[str, bool]:
        """캐시 시스템 헬스 체크"""
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
            test_value = "test"
            file_healthy = (
                self.file_cache.set(test_key, test_value, 1) and
                self.file_cache.get(test_key) == test_value
            )
            self.file_cache.delete(test_key)
        except Exception as e:
            logger.error(f"파일 캐시 헬스 체크 실패: {e}")
        
        return {
            "redis": redis_healthy,
            "file_cache": file_healthy,
            "overall": redis_healthy or file_healthy
        }

# 글로벌 하이브리드 캐시 인스턴스
hybrid_cache = HybridCacheService()

# 편의 함수들
async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """하이브리드 캐시 저장"""
    return await hybrid_cache.set(key, value, ttl)

async def cache_get(key: str, default: Any = None) -> Any:
    """하이브리드 캐시 조회"""
    return await hybrid_cache.get(key, default)

async def cache_delete(key: str) -> bool:
    """하이브리드 캐시 삭제"""
    return await hybrid_cache.delete(key)

async def cache_exists(key: str) -> bool:
    """하이브리드 캐시 존재 확인"""
    return await hybrid_cache.exists(key)

async def cache_clear() -> bool:
    """하이브리드 캐시 전체 클리어"""
    return await hybrid_cache.clear()

async def cache_stats() -> Dict[str, Any]:
    """하이브리드 캐시 통계"""
    return await hybrid_cache.get_stats()

async def cache_health() -> Dict[str, bool]:
    """하이브리드 캐시 헬스 체크"""
    return await hybrid_cache.health_check() 