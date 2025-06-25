import redis.asyncio as redis
import json
import hashlib
import logging
from typing import Any, Optional, Dict, Union
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisService:
    """Redis 기반 캐시 서비스"""
    
    def __init__(self):
        self.redis_url = "redis://redis:6379"
        self.client: Optional[redis.Redis] = None
        self.connected = False
        self.default_ttl = settings.CACHE_TTL
        
    async def connect(self) -> bool:
        """Redis 서버에 연결"""
        try:
            self.client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # 연결 테스트
            await self.client.ping()
            self.connected = True
            logger.info("Redis 연결 성공")
            return True
            
        except Exception as e:
            logger.error(f"Redis 연결 실패: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Redis 연결 종료"""
        if self.client:
            await self.client.close()
            self.connected = False
            logger.info("Redis 연결 종료")
    
    def _generate_secure_key(self, key: str) -> str:
        """보안 강화된 키 생성 (SHA-256 + Salt)"""
        salt = "hapa_redis_salt_2024"
        return hashlib.sha256(f"{salt}:{key}".encode('utf-8')).hexdigest()
    
    async def set_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시에 값 저장"""
        if not self.connected or not self.client:
            logger.warning("Redis 연결되지 않음, 캐시 저장 실패")
            return False
            
        try:
            secure_key = self._generate_secure_key(key)
            ttl = ttl or self.default_ttl
            
            # 값을 JSON으로 직렬화
            cache_data = {
                "value": value,
                "created_at": datetime.utcnow().isoformat(),
                "key_original": key,
                "ttl": ttl
            }
            
            serialized_value = json.dumps(cache_data, ensure_ascii=False)
            await self.client.setex(secure_key, ttl, serialized_value)
            
            logger.debug(f"Redis 캐시 저장 성공: {key} (TTL: {ttl}초)")
            return True
            
        except Exception as e:
            logger.error(f"Redis 캐시 저장 실패: {key} - {e}")
            return False
    
    async def get_cache(self, key: str, default: Any = None) -> Any:
        """캐시에서 값 조회"""
        if not self.connected or not self.client:
            logger.debug("Redis 연결되지 않음, 캐시 조회 실패")
            return default
            
        try:
            secure_key = self._generate_secure_key(key)
            cached_data = await self.client.get(secure_key)
            
            if cached_data is None:
                logger.debug(f"Redis 캐시 미스: {key}")
                return default
            
            # JSON 역직렬화
            data = json.loads(cached_data)
            logger.debug(f"Redis 캐시 히트: {key}")
            return data["value"]
            
        except Exception as e:
            logger.error(f"Redis 캐시 조회 실패: {key} - {e}")
            return default
    
    async def delete_cache(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        if not self.connected or not self.client:
            return False
            
        try:
            secure_key = self._generate_secure_key(key)
            result = await self.client.delete(secure_key)
            logger.debug(f"Redis 캐시 삭제: {key} ({'성공' if result else '키 없음'})")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis 캐시 삭제 실패: {key} - {e}")
            return False
    
    async def exists_cache(self, key: str) -> bool:
        """캐시 키 존재 여부 확인"""
        if not self.connected or not self.client:
            return False
            
        try:
            secure_key = self._generate_secure_key(key)
            result = await self.client.exists(secure_key)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis 캐시 존재 확인 실패: {key} - {e}")
            return False
    
    async def clear_cache(self, pattern: str = "hapa_redis_salt_2024:*") -> int:
        """패턴에 맞는 캐시 일괄 삭제"""
        if not self.connected or not self.client:
            return 0
            
        try:
            # 패턴으로 키 검색
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted_count = await self.client.delete(*keys)
                logger.info(f"Redis 캐시 일괄 삭제: {deleted_count}개")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Redis 캐시 일괄 삭제 실패: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Redis 통계 정보 조회"""
        if not self.connected or not self.client:
            return {"connected": False}
            
        try:
            info = await self.client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
            
        except Exception as e:
            logger.error(f"Redis 통계 조회 실패: {e}")
            return {"connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """캐시 히트율 계산"""
        total = hits + misses
        return round((hits / total * 100), 2) if total > 0 else 0.0
    
    async def health_check(self) -> bool:
        """Redis 서버 상태 확인"""
        try:
            if not self.client:
                return False
            await self.client.ping()
            return True
        except:
            return False

# 글로벌 Redis 서비스 인스턴스
redis_service = RedisService()

# 편의 함수들
async def init_redis():
    """Redis 서비스 초기화"""
    return await redis_service.connect()

async def close_redis():
    """Redis 서비스 종료"""
    await redis_service.disconnect()

async def redis_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Redis 캐시 저장"""
    return await redis_service.set_cache(key, value, ttl)

async def redis_get(key: str, default: Any = None) -> Any:
    """Redis 캐시 조회"""
    return await redis_service.get_cache(key, default)

async def redis_delete(key: str) -> bool:
    """Redis 캐시 삭제"""
    return await redis_service.delete_cache(key)

async def redis_exists(key: str) -> bool:
    """Redis 캐시 존재 확인"""
    return await redis_service.exists_cache(key)

async def redis_clear(pattern: str = "*") -> int:
    """Redis 캐시 일괄 삭제"""
    return await redis_service.clear_cache(pattern)

async def redis_stats() -> Dict[str, Any]:
    """Redis 통계 정보"""
    return await redis_service.get_stats() 