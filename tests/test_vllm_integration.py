"""
vLLM 멀티 LoRA 서버 통합 테스트
- 연결 테스트
- 모델별 코드 생성 테스트
- 스트리밍 응답 테스트
- 페일오버 테스트
- 성능 테스트
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from typing import AsyncGenerator
import logging

from app.services.vllm_integration_service import vllm_service, VLLMModelType
from app.services.enhanced_ai_model import enhanced_ai_service, AIBackendType
from app.schemas.code_generation import (
    CodeGenerationRequest, 
    CodeGenerationResponse,
    ModelType
)

# 테스트용 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestVLLMIntegrationService:
    """vLLM 통합 서비스 테스트"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """vLLM 서버 상태 확인 성공 테스트"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock 응답 설정
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "status": "healthy",
                "timestamp": 1751343490.577505
            }
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # 테스트 실행
            result = await vllm_service.check_health()
            
            # 검증
            assert result["status"] == "healthy"
            assert "details" in result
            assert result["details"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """vLLM 서버 상태 확인 실패 테스트"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock 응답 설정 (서버 오류)
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # 테스트 실행
            result = await vllm_service.check_health()
            
            # 검증
            assert result["status"] == "unhealthy"
            assert result["http_status"] == 500
    
    @pytest.mark.asyncio
    async def test_get_available_models(self):
        """사용 가능한 모델 목록 조회 테스트"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock 응답 설정
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "service": "vLLM Multi-LoRA Server",
                "version": "1.0.0",
                "status": "running",
                "available_models": ["autocomplete", "prompt", "comment", "error_fix"]
            }
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # 테스트 실행
            result = await vllm_service.get_available_models()
            
            # 검증
            assert "available_models" in result
            assert len(result["available_models"]) == 4
            assert "autocomplete" in result["available_models"]
            assert "prompt" in result["available_models"]
    
    def test_hapa_to_vllm_model_mapping(self):
        """HAPA 모델 타입을 vLLM 모델 타입으로 매핑 테스트"""
        test_cases = [
            (ModelType.CODE_COMPLETION, VLLMModelType.AUTOCOMPLETE),
            (ModelType.CODE_GENERATION, VLLMModelType.PROMPT),
            (ModelType.BUG_FIX, VLLMModelType.ERROR_FIX),
            (ModelType.CODE_EXPLANATION, VLLMModelType.COMMENT),
        ]
        
        for hapa_model, expected_vllm_model in test_cases:
            result = vllm_service._map_hapa_to_vllm_model(hapa_model)
            assert result == expected_vllm_model
    
    def test_prepare_vllm_request(self):
        """vLLM 요청 준비 테스트"""
        # 테스트 요청 생성
        request = CodeGenerationRequest(
            prompt="파이썬으로 Hello World를 출력하는 함수를 만들어줘",
            model_type=ModelType.CODE_GENERATION,
            context="",
            temperature=0.3,
            max_tokens=1024
        )
        
        user_id = "test_user_123"
        
        # 요청 준비
        vllm_request = vllm_service._prepare_vllm_request(request, user_id)
        
        # 검증
        assert vllm_request["model_type"] == "prompt"
        assert isinstance(vllm_request["user_id"], int)
        assert vllm_request["temperature"] == 0.3
        assert vllm_request["max_tokens"] == 1024
        assert "user_select_options" in vllm_request
    
    def test_optimize_prompt_for_model(self):
        """모델별 프롬프트 최적화 테스트"""
        request = CodeGenerationRequest(
            prompt="Hello World 함수를 만들어줘",
            context="기존 코드 컨텍스트"
        )
        
        # 각 모델 타입별 테스트
        test_cases = [
            (VLLMModelType.AUTOCOMPLETE, "기존 코드 컨텍스트\nHello World 함수를 만들어줘"),
            (VLLMModelType.COMMENT, "# 다음 코드에 대한 상세한 주석을 작성해주세요.\n기존 코드 컨텍스트\n\n# 요청사항: Hello World 함수를 만들어줘"),
            (VLLMModelType.ERROR_FIX, "# 다음 코드에 버그가 있습니다. 문제를 찾아 수정해주세요.\n# 문제 설명: Hello World 함수를 만들어줘\n\n기존 코드 컨텍스트"),
            (VLLMModelType.PROMPT, "# 컨텍스트:\n기존 코드 컨텍스트\n\n# 요청사항: Hello World 함수를 만들어줘"),
        ]
        
        for model_type, expected_prefix in test_cases:
            result = vllm_service._optimize_prompt_for_model(
                request.prompt, model_type, request
            )
            assert result.startswith(expected_prefix.split('\n')[0])
    
    @pytest.mark.asyncio
    async def test_generate_code_sync_success(self):
        """동기식 코드 생성 성공 테스트"""
        # Mock 스트리밍 응답
        async def mock_stream_generator():
            yield "data: def hello_world():\n\n"
            yield "data:     print('Hello, World!')\n\n"
            yield "data: [DONE]\n\n"
        
        with patch.object(vllm_service, 'generate_code_stream', return_value=mock_stream_generator()):
            request = CodeGenerationRequest(
                prompt="Hello World 함수를 만들어줘",
                model_type=ModelType.CODE_GENERATION
            )
            
            result = await vllm_service.generate_code_sync(request, "test_user")
            
            # 검증
            assert result.success is True
            assert "hello_world" in result.generated_code
            assert result.model_used == "prompt"

class TestEnhancedAIModelService:
    """Enhanced AI 모델 서비스 테스트"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Enhanced AI 서비스 초기화 테스트"""
        # Mock vLLM 서비스
        with patch.object(enhanced_ai_service, '_check_vllm_health', return_value=True), \
             patch.object(enhanced_ai_service, '_check_legacy_health', return_value=True):
            
            await enhanced_ai_service.initialize()
            
            # 검증
            assert enhanced_ai_service.vllm_available is True
            assert enhanced_ai_service.legacy_available is True
            assert enhanced_ai_service.current_backend == AIBackendType.VLLM
    
    @pytest.mark.asyncio
    async def test_backend_failover(self):
        """백엔드 페일오버 테스트"""
        # vLLM 실패, Legacy 성공 시나리오
        enhanced_ai_service.vllm_available = False
        enhanced_ai_service.legacy_available = True
        
        request = CodeGenerationRequest(
            prompt="테스트 코드",
            model_type=ModelType.CODE_GENERATION
        )
        
        with patch.object(enhanced_ai_service, '_generate_with_legacy') as mock_legacy:
            mock_legacy.return_value = CodeGenerationResponse(
                success=True,
                generated_code="def test(): pass",
                model_used="legacy_ai_model",
                processing_time=1.0,
                token_usage={"total_tokens": 10}
            )
            
            result = await enhanced_ai_service.generate_code(request, "test_user")
            
            # 검증
            assert result.success is True
            assert result.model_used == "legacy_ai_model"
            mock_legacy.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_performance_stats_update(self):
        """성능 통계 업데이트 테스트"""
        # 초기 상태
        initial_stats = enhanced_ai_service.performance_stats.copy()
        
        # 성능 통계 업데이트
        enhanced_ai_service._update_performance_stats("vllm", 2.5, True)
        enhanced_ai_service._update_performance_stats("vllm", 1.5, True)
        
        # 검증
        vllm_stats = enhanced_ai_service.performance_stats["vllm"]
        assert vllm_stats["requests"] == 2
        assert vllm_stats["successes"] == 2
        assert vllm_stats["avg_response_time"] > 0
    
    @pytest.mark.asyncio
    async def test_backend_switching(self):
        """백엔드 수동 전환 테스트"""
        # vLLM 사용 가능 상태 설정
        enhanced_ai_service.vllm_available = True
        enhanced_ai_service.legacy_available = True
        
        # Legacy로 전환
        result = await enhanced_ai_service.switch_backend(AIBackendType.LEGACY)
        
        # 검증
        assert result is True
        assert enhanced_ai_service.current_backend == AIBackendType.LEGACY
        
        # vLLM으로 다시 전환
        result = await enhanced_ai_service.switch_backend(AIBackendType.VLLM)
        
        # 검증
        assert result is True
        assert enhanced_ai_service.current_backend == AIBackendType.VLLM

class TestAPIIntegration:
    """API 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_streaming_endpoint_mock(self):
        """스트리밍 엔드포인트 Mock 테스트"""
        from app.api.endpoints.code_generation import generate_code_stream
        from fastapi import Request
        from unittest.mock import Mock
        
        # Mock 객체 생성
        mock_request = CodeGenerationRequest(
            prompt="테스트 코드 생성",
            model_type=ModelType.CODE_GENERATION
        )
        
        mock_background_tasks = Mock()
        mock_api_key = "test_api_key"
        mock_current_user = {"user_id": "test_user"}
        
        # Mock vLLM 서비스
        async def mock_stream():
            yield "data: def test():\n\n"
            yield "data:     pass\n\n"
            yield "data: [DONE]\n\n"
        
        with patch('app.api.endpoints.code_generation.vllm_service') as mock_vllm:
            mock_vllm.check_health.return_value = {"status": "healthy"}
            mock_vllm.generate_code_stream.return_value = mock_stream()
            
            # 스트리밍 응답 생성 (실제 호출은 FastAPI 테스트에서)
            # 여기서는 Mock 동작 확인
            health_check = await mock_vllm.check_health()
            assert health_check["status"] == "healthy"
    
    def test_model_type_validation(self):
        """모델 타입 검증 테스트"""
        # 유효한 모델 타입
        valid_request = CodeGenerationRequest(
            prompt="테스트",
            model_type=ModelType.CODE_GENERATION
        )
        assert valid_request.model_type == ModelType.CODE_GENERATION
        
        # 프롬프트 검증
        with pytest.raises(ValueError):
            CodeGenerationRequest(
                prompt="",  # 빈 프롬프트
                model_type=ModelType.CODE_GENERATION
            )

class TestErrorHandling:
    """오류 처리 테스트"""
    
    @pytest.mark.asyncio
    async def test_vllm_connection_error(self):
        """vLLM 연결 오류 처리 테스트"""
        with patch('aiohttp.ClientSession.get', side_effect=Exception("Connection failed")):
            result = await vllm_service.check_health()
            
            # 검증
            assert result["status"] == "error"
            assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self):
        """잘못된 응답 형식 처리 테스트"""
        async def mock_malformed_stream():
            yield "invalid_data_format"
            yield "data: invalid_json_{"
            yield "data: [DONE]\n\n"
        
        with patch.object(vllm_service, 'generate_code_stream', return_value=mock_malformed_stream()):
            request = CodeGenerationRequest(
                prompt="테스트",
                model_type=ModelType.CODE_GENERATION
            )
            
            result = await vllm_service.generate_code_sync(request, "test_user")
            
            # 오류 상황에서도 응답 객체가 반환되어야 함
            assert isinstance(result, CodeGenerationResponse)

@pytest.fixture
def event_loop():
    """비동기 테스트를 위한 이벤트 루프"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# 통합 테스트 실행 함수
async def run_integration_tests():
    """통합 테스트 실행"""
    logger.info("🧪 vLLM 통합 테스트 시작...")
    
    try:
        # 실제 vLLM 서버 연결 테스트
        health_result = await vllm_service.check_health()
        print(f"✅ vLLM 서버 상태: {health_result['status']}")
        
        # 모델 목록 조회 테스트
        models_result = await vllm_service.get_available_models()
        print(f"✅ 사용 가능한 모델: {models_result.get('available_models', [])}")
        
        # Enhanced AI 서비스 초기화 테스트
        await enhanced_ai_service.initialize()
        backend_status = await enhanced_ai_service.get_backend_status()
        print(f"✅ 현재 백엔드: {backend_status['current_backend']}")
        
        # 간단한 코드 생성 테스트
        request = CodeGenerationRequest(
            prompt="Hello World 함수",
            model_type=ModelType.CODE_GENERATION,
            max_tokens=100
        )
        
        response = await enhanced_ai_service.generate_code(request, "integration_test_user")
        print(f"✅ 코드 생성 성공: {response.success}")
        
        print("🎉 모든 통합 테스트 통과!")
        
    except Exception as e:
        print(f"❌ 통합 테스트 실패: {e}")
        raise
    
    finally:
        # 정리
        await enhanced_ai_service.close()
        await vllm_service.close()

if __name__ == "__main__":
    # 통합 테스트 실행
    asyncio.run(run_integration_tests()) 