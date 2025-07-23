import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.redis_service import RedisService, redis_service
import json

class TestRedisService:
    """Redis 서비스 테스트 클래스"""
    
    @pytest.fixture
    def redis_service_instance(self):
        """테스트용 Redis 서비스 인스턴스"""
        return RedisService()
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis 클라이언트"""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.setex.return_value = True
        mock_client.get.return_value = None
        mock_client.delete.return_value = 1
        mock_client.exists.return_value = 1
        mock_client.info.return_value = {
            "used_memory_human": "1.2M",
            "connected_clients": 5,
            "total_commands_processed": 1000,
            "keyspace_hits": 800,
            "keyspace_misses": 200
        }
        return mock_client
    
    @pytest.mark.asyncio
    async def test_connect_success(self, redis_service_instance, mock_redis_client):
        """Redis 연결 성공 테스트"""
        with patch('redis.asyncio.from_url', return_value=mock_redis_client):
            result = await redis_service_instance.connect()
            
            assert result is True
            assert redis_service_instance.connected is True
            assert redis_service_instance.client is not None
            mock_redis_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, redis_service_instance):
        """Redis 연결 실패 테스트"""
        with patch('redis.asyncio.from_url', side_effect=Exception("Connection failed")):
            result = await redis_service_instance.connect()
            
            assert result is False
            assert redis_service_instance.connected is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self, redis_service_instance, mock_redis_client):
        """Redis 연결 종료 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        
        await redis_service_instance.disconnect()
        
        assert redis_service_instance.connected is False
        mock_redis_client.close.assert_called_once()
    
    def test_generate_secure_key(self, redis_service_instance):
        """보안 키 생성 테스트"""
        key1 = redis_service_instance._generate_secure_key("test_key")
        key2 = redis_service_instance._generate_secure_key("test_key")
        key3 = redis_service_instance._generate_secure_key("different_key")
        
        # 같은 입력에 대해 같은 결과
        assert key1 == key2
        # 다른 입력에 대해 다른 결과
        assert key1 != key3
        # SHA-256 해시 길이 (64자)
        assert len(key1) == 64
        # 솔트가 포함되어야 함
        salt_hash = redis_service_instance._generate_secure_key("")
        assert salt_hash != ""
    
    @pytest.mark.asyncio
    async def test_set_cache_success(self, redis_service_instance, mock_redis_client):
        """캐시 저장 성공 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        
        result = await redis_service_instance.set_cache("test_key", {"data": "value"}, 3600)
        
        assert result is True
        mock_redis_client.setex.assert_called_once()
        
        # setex 호출 인자 확인
        call_args = mock_redis_client.setex.call_args
        assert call_args[0][1] == 3600  # TTL
        
        # JSON 직렬화된 데이터 확인
        serialized_data = call_args[0][2]
        data = json.loads(serialized_data)
        assert data["value"] == {"data": "value"}
        assert "created_at" in data
        assert data["ttl"] == 3600
    
    @pytest.mark.asyncio
    async def test_set_cache_not_connected(self, redis_service_instance):
        """연결되지 않은 상태에서 캐시 저장 테스트"""
        redis_service_instance.connected = False
        
        result = await redis_service_instance.set_cache("test_key", "value")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_cache_success(self, redis_service_instance, mock_redis_client):
        """캐시 조회 성공 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        
        # Mock 응답 데이터 설정
        cache_data = {
            "value": {"data": "cached_value"},
            "created_at": "2024-01-01T00:00:00",
            "ttl": 3600
        }
        mock_redis_client.get.return_value = json.dumps(cache_data)
        
        result = await redis_service_instance.get_cache("test_key", "default")
        
        assert result == {"data": "cached_value"}
        mock_redis_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, redis_service_instance, mock_redis_client):
        """캐시 미스 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        mock_redis_client.get.return_value = None
        
        result = await redis_service_instance.get_cache("nonexistent_key", "default")
        
        assert result == "default"
    
    @pytest.mark.asyncio
    async def test_get_cache_not_connected(self, redis_service_instance):
        """연결되지 않은 상태에서 캐시 조회 테스트"""
        redis_service_instance.connected = False
        
        result = await redis_service_instance.get_cache("test_key", "default")
        
        assert result == "default"
    
    @pytest.mark.asyncio
    async def test_delete_cache_success(self, redis_service_instance, mock_redis_client):
        """캐시 삭제 성공 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        mock_redis_client.delete.return_value = 1
        
        result = await redis_service_instance.delete_cache("test_key")
        
        assert result is True
        mock_redis_client.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_cache_key_not_found(self, redis_service_instance, mock_redis_client):
        """존재하지 않는 키 삭제 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        mock_redis_client.delete.return_value = 0
        
        result = await redis_service_instance.delete_cache("nonexistent_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_exists_cache_true(self, redis_service_instance, mock_redis_client):
        """캐시 키 존재 확인 - 존재하는 경우"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        mock_redis_client.exists.return_value = 1
        
        result = await redis_service_instance.exists_cache("test_key")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_exists_cache_false(self, redis_service_instance, mock_redis_client):
        """캐시 키 존재 확인 - 존재하지 않는 경우"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        mock_redis_client.exists.return_value = 0
        
        result = await redis_service_instance.exists_cache("nonexistent_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_clear_cache_success(self, redis_service_instance, mock_redis_client):
        """캐시 일괄 삭제 성공 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        
        # scan_iter Mock 설정
        async def mock_scan_iter(match):
            keys = ["key1", "key2", "key3"]
            for key in keys:
                yield key
        
        mock_redis_client.scan_iter.return_value = mock_scan_iter("pattern")
        mock_redis_client.delete.return_value = 3
        
        result = await redis_service_instance.clear_cache("pattern")
        
        assert result == 3
        mock_redis_client.delete.assert_called_once_with("key1", "key2", "key3")
    
    @pytest.mark.asyncio
    async def test_get_stats_success(self, redis_service_instance, mock_redis_client):
        """Redis 통계 조회 성공 테스트"""
        redis_service_instance.client = mock_redis_client
        redis_service_instance.connected = True
        
        stats = await redis_service_instance.get_stats()
        
        assert stats["connected"] is True
        assert stats["used_memory"] == "1.2M"
        assert stats["connected_clients"] == 5
        assert stats["hit_rate"] == 80.0  # 800 / (800 + 200) * 100
    
    @pytest.mark.asyncio
    async def test_get_stats_not_connected(self, redis_service_instance):
        """연결되지 않은 상태에서 통계 조회 테스트"""
        redis_service_instance.connected = False
        
        stats = await redis_service_instance.get_stats()
        
        assert stats["connected"] is False
    
    def test_calculate_hit_rate(self, redis_service_instance):
        """히트율 계산 테스트"""
        # 정상적인 히트율 계산
        hit_rate = redis_service_instance._calculate_hit_rate(80, 20)
        assert hit_rate == 80.0
        
        # 모든 값이 0인 경우
        hit_rate = redis_service_instance._calculate_hit_rate(0, 0)
        assert hit_rate == 0.0
        
        # 미스만 있는 경우
        hit_rate = redis_service_instance._calculate_hit_rate(0, 100)
        assert hit_rate == 0.0
        
        # 히트만 있는 경우
        hit_rate = redis_service_instance._calculate_hit_rate(100, 0)
        assert hit_rate == 100.0
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, redis_service_instance, mock_redis_client):
        """헬스 체크 성공 테스트"""
        redis_service_instance.client = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        result = await redis_service_instance.health_check()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, redis_service_instance, mock_redis_client):
        """헬스 체크 실패 테스트"""
        redis_service_instance.client = mock_redis_client
        mock_redis_client.ping.side_effect = Exception("Connection lost")
        
        result = await redis_service_instance.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_no_client(self, redis_service_instance):
        """클라이언트가 없는 상태에서 헬스 체크 테스트"""
        redis_service_instance.client = None
        
        result = await redis_service_instance.health_check()
        
        assert result is False


class TestRedisServiceModule:
    """Redis 서비스 모듈 레벨 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_module_functions(self):
        """모듈 레벨 편의 함수 테스트"""
        from app.services.redis_service import (
            redis_set, redis_get, redis_delete, 
            redis_exists, redis_clear, redis_stats
        )
        
        # Mock을 사용한 함수 테스트
        with patch.object(redis_service, 'set_cache', return_value=True) as mock_set:
            result = await redis_set("key", "value", 3600)
            assert result is True
            mock_set.assert_called_once_with("key", "value", 3600)
        
        with patch.object(redis_service, 'get_cache', return_value="value") as mock_get:
            result = await redis_get("key", "default")
            assert result == "value"
            mock_get.assert_called_once_with("key", "default")


if __name__ == "__main__":
    pytest.main([__file__]) 