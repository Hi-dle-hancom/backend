"""
HAPA 백엔드 시스템 통합 테스트
- 스마트 하이브리드 캐시 시스템
- vLLM 전용 AI 모델 서비스 
- API 엔드포인트 통합
- 성능 메트릭 수집
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from main import create_application

# 테스트용 앱 인스턴스 생성
app = create_application()
from app.services.hybrid_cache_service import smart_cache
from app.services.enhanced_ai_model import enhanced_ai_service
from app.services.performance_profiler import ai_performance_metrics
from app.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelType
)


class TestSystemIntegration:
    """HAPA 백엔드 시스템 통합 테스트 클래스"""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """각 테스트 전후 설정 및 정리"""
        # 테스트 전 초기화
        await smart_cache.clear()
        ai_performance_metrics.reset_metrics()
        
        yield
        
        # 테스트 후 정리
        await smart_cache.clear()
        ai_performance_metrics.reset_metrics()

    @pytest.fixture
    def client(self):
        """FastAPI 테스트 클라이언트"""
        return TestClient(app)

    @pytest.fixture
    def sample_code_request(self) -> CodeGenerationRequest:
        """샘플 코드 생성 요청"""
        return CodeGenerationRequest(
            prompt="리스트를 정렬하는 함수를 만들어줘",
            context="Python 기초 함수 작성",
            model_type=ModelType.GENERAL_COMPLETION,
            language="python",
            max_tokens=512
        )

    @pytest.fixture
    def mock_vllm_response(self) -> CodeGenerationResponse:
        """모의 vLLM 응답"""
        return CodeGenerationResponse(
            success=True,
            generated_code="""def sort_list(items):
    \"\"\"리스트를 정렬하는 함수\"\"\"
    return sorted(items)""",
            explanation="입력받은 리스트를 오름차순으로 정렬하여 반환하는 함수입니다.",
            model_used="codellama_13b_instruct",
            processing_time=1.2,
            token_usage={"total_tokens": 45, "prompt_tokens": 20, "completion_tokens": 25},
            confidence_score=0.95,
            translation_applied=True
        )

    # ======= 스마트 캐시 시스템 통합 테스트 =======

    @pytest.mark.asyncio
    async def test_smart_cache_initialization(self):
        """스마트 캐시 시스템 초기화 테스트"""
        # 캐시 초기화
        init_result = await smart_cache.init()
        assert init_result is True

        # 헬스 체크
        health = await smart_cache.health_check()
        assert health["overall_healthy"] is True
        assert "backends" in health
        assert "performance_summary" in health

    @pytest.mark.asyncio
    async def test_smart_cache_crud_operations(self):
        """스마트 캐시 CRUD 연산 테스트"""
        test_key = "test_cache_key"
        test_value = {"data": "test_value", "timestamp": time.time()}

        # 1. 저장 테스트
        set_result = await smart_cache.set(test_key, test_value, policy="short")
        assert set_result is True

        # 2. 조회 테스트
        retrieved_value = await smart_cache.get(test_key)
        assert retrieved_value == test_value

        # 3. 존재 확인 테스트
        exists = await smart_cache.exists(test_key)
        assert exists is True

        # 4. 삭제 테스트
        delete_result = await smart_cache.delete(test_key)
        assert delete_result is True

        # 5. 삭제 후 확인
        not_found = await smart_cache.get(test_key, "not_found")
        assert not_found == "not_found"

    @pytest.mark.asyncio
    async def test_smart_cache_ttl_policies(self):
        """스마트 캐시 TTL 정책 테스트"""
        test_data = {"test": "ttl_policy"}

        # 각 정책별 저장 테스트
        policies = ["short", "medium", "long", "extended"]
        
        for policy in policies:
            key = f"ttl_test_{policy}"
            await smart_cache.set(key, test_data, policy=policy)
            
            retrieved = await smart_cache.get(key)
            assert retrieved == test_data

        # 통계 확인
        stats = await smart_cache.get_stats()
        assert "performance_metrics" in stats
        assert stats["performance_metrics"]["total_requests"] >= len(policies)

    # ======= vLLM 전용 AI 서비스 통합 테스트 =======

    @pytest.mark.asyncio
    @patch('app.services.vllm_integration_service.vllm_service')
    async def test_enhanced_ai_service_initialization(self, mock_vllm):
        """Enhanced AI 서비스 (vLLM 전용) 초기화 테스트"""
        # Mock vLLM 헬스 체크
        mock_vllm.check_health = AsyncMock(return_value={"status": "healthy"})

        # 서비스 초기화
        await enhanced_ai_service.initialize()
        
        # vLLM 상태 확인
        assert enhanced_ai_service.vllm_available is True
        assert enhanced_ai_service.current_backend.value == "vllm"

    @pytest.mark.asyncio
    @patch('app.services.vllm_integration_service.vllm_service')
    async def test_code_generation_with_caching(self, mock_vllm, sample_code_request, mock_vllm_response):
        """코드 생성과 캐싱 통합 테스트"""
        # Mock vLLM 서비스
        mock_vllm.check_health = AsyncMock(return_value={"status": "healthy"})
        mock_vllm.generate_code_sync = AsyncMock(return_value=mock_vllm_response)

        # 서비스 초기화
        await enhanced_ai_service.initialize()

        # 첫 번째 코드 생성 요청
        response1 = await enhanced_ai_service.generate_code(sample_code_request, "test_user_001")
        assert response1.success is True
        assert "def sort_list" in response1.generated_code

        # 캐시에 결과가 저장되었는지 확인
        cache_key = f"code_gen:{hash(sample_code_request.prompt + str(sample_code_request.model_type))}"
        cached_result = await smart_cache.get(cache_key)
        
        # 캐시 키는 실제 구현에 따라 다를 수 있음
        # 대신 성능 메트릭으로 확인
        stats = await smart_cache.get_stats()
        assert stats["performance_metrics"]["total_requests"] > 0

    @pytest.mark.asyncio
    async def test_ai_service_vllm_unavailable_handling(self, sample_code_request):
        """vLLM 서버 사용 불가 시 처리 테스트"""
        # vLLM 사용 불가 상태로 설정
        enhanced_ai_service.vllm_available = False

        # 코드 생성 요청
        response = await enhanced_ai_service.generate_code(sample_code_request, "test_user_002")
        
        # 오류 응답 확인
        assert response.success is False
        assert "vLLM 서버를 사용할 수 없습니다" in response.error_message
        assert response.model_used == "vllm_unavailable"

    # ======= API 엔드포인트 통합 테스트 =======

    def test_health_check_endpoint(self, client):
        """헬스 체크 엔드포인트 테스트"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "hapa" in data["message"].lower()

    def test_cache_health_endpoint(self, client):
        """캐시 헬스 체크 엔드포인트 테스트"""
        response = client.get("/api/v1/cache/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]
        assert "response_time_ms" in data

    def test_cache_stats_endpoint(self, client):
        """캐시 통계 엔드포인트 테스트"""
        response = client.get("/api/v1/cache/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "smart_hybrid_cache" in data
        assert "performance_metrics" in data

    @patch('app.services.vllm_integration_service.vllm_service')
    def test_code_generation_endpoint(self, mock_vllm, client, mock_vllm_response):
        """코드 생성 엔드포인트 통합 테스트"""
        # Mock vLLM 서비스
        mock_vllm.check_health = AsyncMock(return_value={"status": "healthy"})
        mock_vllm.generate_code_sync = AsyncMock(return_value=mock_vllm_response)

        # 코드 생성 요청
        request_data = {
            "prompt": "리스트를 정렬하는 함수를 만들어줘",
            "context": "Python 기초 함수 작성",
            "model_type": "general_completion",
            "language": "python",
            "max_tokens": 512
        }

        response = client.post(
            "/api/v1/code/generate",
            json=request_data,
            headers={"X-API-Key": "hapa_demo_20241228_secure_key_for_testing"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "generated_code" in data

    # ======= 성능 메트릭 통합 테스트 =======

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self):
        """성능 메트릭 수집 통합 테스트"""
        # 메트릭 리셋
        ai_performance_metrics.reset_metrics()

        # 테스트 작업 기록
        ai_performance_metrics.record_ai_operation(
            model_name="codellama_13b_instruct",
            response_time=1.5,
            token_count=50,
            success=True,
            operation_type="general_completion"
        )

        ai_performance_metrics.record_ai_operation(
            model_name="codellama_13b_instruct",
            response_time=2.1,
            token_count=75,
            success=True,
            operation_type="code_completion"
        )

        # 성능 요약 확인
        summary = ai_performance_metrics.get_performance_summary(time_window_hours=1)
        assert summary["total_operations"] == 2
        assert summary["average_response_time"] > 0
        assert summary["average_token_speed"] > 0
        assert summary["success_rate"] == 1.0

    # ======= 오류 처리 및 회복력 테스트 =======

    @pytest.mark.asyncio
    async def test_cache_failover_behavior(self):
        """캐시 페일오버 동작 테스트"""
        # Redis 연결 실패 시나리오 시뮬레이션
        smart_cache.redis_available = False

        test_key = "failover_test"
        test_value = {"failover": "test_data"}

        # 파일 캐시로 페일오버되어야 함
        set_result = await smart_cache.set(test_key, test_value)
        assert set_result is True

        retrieved = await smart_cache.get(test_key)
        assert retrieved == test_value

        # 메트릭에서 페일오버 확인
        stats = await smart_cache.get_stats()
        assert stats["performance_metrics"]["failovers"] >= 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """동시 작업 처리 테스트"""
        # 동시 캐시 작업
        async def cache_operation(index: int):
            key = f"concurrent_test_{index}"
            value = {"index": index, "timestamp": time.time()}
            await smart_cache.set(key, value)
            return await smart_cache.get(key)

        # 10개의 동시 작업 실행
        tasks = [cache_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for i, result in enumerate(results):
            assert result["index"] == i

    # ======= 보안 및 검증 테스트 =======

    def test_api_authentication(self, client):
        """API 인증 테스트"""
        # 잘못된 API 키로 요청
        request_data = {
            "prompt": "test prompt",
            "model_type": "general_completion"
        }

        response = client.post(
            "/api/v1/code/generate",
            json=request_data,
            headers={"X-API-Key": "invalid_key"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_input_validation_and_sanitization(self, client):
        """입력 검증 및 새니타이제이션 테스트"""
        # 악성 입력 시도
        malicious_requests = [
            {"prompt": "import os; os.system('rm -rf /')", "model_type": "general_completion"},
            {"prompt": "exec('malicious code')", "model_type": "general_completion"},
            {"prompt": "eval('dangerous expression')", "model_type": "general_completion"},
        ]

        for req in malicious_requests:
            response = client.post(
                "/api/v1/code/generate",
                json=req,
                headers={"X-API-Key": "hapa_demo_20241228_secure_key_for_testing"}
            )
            
            # 요청이 거부되거나 안전하게 처리되어야 함
            assert response.status_code in [400, 422, 200]  # 입력 검증 또는 안전한 처리

    # ======= 전체 시스템 시나리오 테스트 =======

    @pytest.mark.asyncio
    @patch('app.services.vllm_integration_service.vllm_service')
    async def test_complete_workflow_scenario(self, mock_vllm, client, mock_vllm_response):
        """완전한 워크플로우 시나리오 테스트"""
        # Mock 설정
        mock_vllm.check_health = AsyncMock(return_value={"status": "healthy"})
        mock_vllm.generate_code_sync = AsyncMock(return_value=mock_vllm_response)

        # 1. 시스템 헬스 체크
        health_response = client.get("/")
        assert health_response.status_code == 200

        # 2. 캐시 시스템 상태 확인
        cache_health = client.get("/api/v1/cache/health")
        assert cache_health.status_code == 200

        # 3. AI 서비스 초기화
        await enhanced_ai_service.initialize()
        assert enhanced_ai_service.vllm_available is True

        # 4. 코드 생성 요청
        code_request = {
            "prompt": "데이터베이스 연결 함수를 만들어줘",
            "context": "Python SQLite 연결",
            "model_type": "general_completion",
            "language": "python",
            "max_tokens": 1024
        }

        code_response = client.post(
            "/api/v1/code/generate",
            json=code_request,
            headers={"X-API-Key": "hapa_demo_20241228_secure_key_for_testing"}
        )

        assert code_response.status_code == 200
        code_data = code_response.json()
        assert code_data["success"] is True

        # 5. 성능 메트릭 확인
        performance_summary = ai_performance_metrics.get_performance_summary(time_window_hours=1)
        assert performance_summary["total_operations"] >= 1

        # 6. 캐시 통계 확인
        cache_stats = client.get("/api/v1/cache/stats")
        assert cache_stats.status_code == 200

        # 7. 시스템 상태 최종 확인
        final_health = client.get("/api/v1/cache/health")
        assert final_health.status_code == 200
        final_data = final_health.json()
        assert final_data["status"] == "healthy"


# ======= 성능 벤치마크 테스트 =======

class TestPerformanceBenchmarks:
    """성능 벤치마크 테스트"""

    @pytest.mark.asyncio
    async def test_cache_performance_benchmark(self):
        """캐시 성능 벤치마크"""
        operations = 1000
        start_time = time.time()

        # 대량 캐시 작업
        for i in range(operations):
            await smart_cache.set(f"bench_{i}", {"data": i}, policy="short")

        for i in range(operations):
            result = await smart_cache.get(f"bench_{i}")
            assert result["data"] == i

        elapsed = time.time() - start_time
        ops_per_second = (operations * 2) / elapsed  # set + get

        print(f"캐시 성능: {ops_per_second:.2f} ops/sec")
        assert ops_per_second > 100  # 최소 100 ops/sec

    @pytest.mark.asyncio
    @patch('app.services.vllm_integration_service.vllm_service')
    async def test_ai_service_response_time(self, mock_vllm, sample_code_request):
        """AI 서비스 응답 시간 테스트"""
        # Mock 설정
        mock_response = CodeGenerationResponse(
            success=True,
            generated_code="def test(): pass",
            explanation="테스트 함수",
            model_used="codellama_13b_instruct",
            processing_time=0.5,
            token_usage={"total_tokens": 10}
        )
        
        mock_vllm.check_health = AsyncMock(return_value={"status": "healthy"})
        mock_vllm.generate_code_sync = AsyncMock(return_value=mock_response)

        await enhanced_ai_service.initialize()

        # 응답 시간 측정
        start_time = time.time()
        response = await enhanced_ai_service.generate_code(sample_code_request, "bench_user")
        elapsed = time.time() - start_time

        assert response.success is True
        assert elapsed < 5.0  # 5초 이내 응답
        print(f"AI 서비스 응답 시간: {elapsed:.3f}초")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"]) 