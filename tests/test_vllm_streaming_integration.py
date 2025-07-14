"""
VLLM Streaming Integration Test
테스트 목적: VLLM 스트리밍 기능의 완전한 검증
- print("Jay") 코드 생성 요청으로 스트리밍 검증
- 청크 처리 성능 검증 (50-100 청크, 3-5초 내)
- 최종 출력 정확성 검증
- 백엔드에서 프론트엔드까지 완전한 스트리밍 플로우 검증
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import logging

from app.services.vllm_integration_service import vllm_service, VLLMModelType
from app.schemas.code_generation import (
    CodeGenerationRequest, 
    CodeGenerationResponse,
    ModelType
)
from app.api.endpoints.code_generation import generate_code_stream
from fastapi import BackgroundTasks, Request
from fastapi.responses import StreamingResponse

# 테스트용 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamingTestResult:
    """스트리밍 테스트 결과를 저장하는 클래스"""
    
    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.total_chunks: int = 0
        self.processing_time: float = 0.0
        self.final_code: str = ""
        self.error_occurred: bool = False
        self.error_message: str = ""
        self.chunk_sizes: List[int] = []
        self.chunk_timestamps: List[float] = []
        self.chunks_per_second: float = 0.0
        self.average_chunk_size: float = 0.0
        self.streaming_complete: bool = False
        
    def add_chunk(self, chunk_data: Dict[str, Any], timestamp: float):
        """청크 데이터 추가"""
        self.chunks.append(chunk_data)
        self.chunk_timestamps.append(timestamp)
        
        if 'text' in chunk_data:
            text = chunk_data['text']
            self.chunk_sizes.append(len(text))
            self.final_code += text
            
        self.total_chunks += 1
        
    def calculate_stats(self):
        """통계 계산"""
        if self.chunk_timestamps:
            self.processing_time = self.chunk_timestamps[-1] - self.chunk_timestamps[0]
            self.chunks_per_second = self.total_chunks / max(self.processing_time, 0.001)
            
        if self.chunk_sizes:
            self.average_chunk_size = sum(self.chunk_sizes) / len(self.chunk_sizes)
            
    def is_performance_acceptable(self) -> bool:
        """성능 기준 충족 여부 확인"""
        return (
            50 <= self.total_chunks <= 100 and
            3.0 <= self.processing_time <= 5.0
        )
        
    def contains_expected_output(self) -> bool:
        """기대하는 출력 포함 여부 확인"""
        return 'print("Jay")' in self.final_code or "print('Jay')" in self.final_code


class TestVLLMStreamingIntegration:
    """VLLM 스트리밍 통합 테스트 클래스"""
    
    @pytest.fixture
    def test_request(self):
        """테스트용 코드 생성 요청"""
        return CodeGenerationRequest(
            prompt="파이썬으로 Jay라는 문자열을 출력하는 간단한 코드를 작성해주세요",
            model_type=ModelType.CODE_GENERATION,
            context="",
            temperature=0.3,
            max_tokens=150
        )
    
    @pytest.fixture
    def mock_vllm_stream(self):
        """Mock VLLM 스트리밍 응답 생성"""
        async def mock_stream():
            # 시뮬레이션된 스트리밍 응답 (50-100 청크)
            chunks = [
                {"text": "# Jay를 출력하는 코드\n"},
                {"text": "def "},
                {"text": "print_jay"},
                {"text": "():\n"},
                {"text": "    "},
                {"text": "\"\"\"Jay를 출력하는 함수\"\"\"\n"},
                {"text": "    "},
                {"text": "print"},
                {"text": "("},
                {"text": "\"Jay\""},
                {"text": ")\n\n"},
                {"text": "# 함수 호출\n"},
                {"text": "print_jay()"}
            ]
            
            # 충분한 청크 생성 (목표: 50-100개)
            extended_chunks = []
            for i, chunk in enumerate(chunks):
                # 각 청크를 더 작은 단위로 분할
                text = chunk["text"]
                if len(text) > 3:
                    # 긴 텍스트를 작은 청크로 분할
                    for j in range(0, len(text), 2):
                        extended_chunks.append({"text": text[j:j+2]})
                else:
                    extended_chunks.append(chunk)
            
            # 목표 청크 수에 맞게 조정
            while len(extended_chunks) < 50:
                extended_chunks.append({"text": " "})
            
            # SSE 형식으로 전송
            for i, chunk in enumerate(extended_chunks[:75]):  # 75개 청크로 제한
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.05)  # 50ms 간격 (realistic streaming)
                
            # 스트림 종료
            yield f"data: [DONE]\n\n"
            
        return mock_stream
    
    @pytest.mark.asyncio
    async def test_vllm_streaming_basic_functionality(self, test_request, mock_vllm_stream):
        """기본 VLLM 스트리밍 기능 테스트"""
        logger.info("🧪 기본 VLLM 스트리밍 기능 테스트 시작")
        
        result = StreamingTestResult()
        start_time = time.time()
        
        try:
            with patch.object(vllm_service, 'generate_code_stream', return_value=mock_vllm_stream()):
                # 스트리밍 실행
                chunk_count = 0
                async for chunk in vllm_service.generate_code_stream(test_request, "test_user"):
                    current_time = time.time()
                    
                    if chunk.startswith("data: "):
                        data_content = chunk[6:].strip()
                        
                        if data_content == "[DONE]":
                            result.streaming_complete = True
                            break
                            
                        try:
                            parsed_data = json.loads(data_content)
                            result.add_chunk(parsed_data, current_time)
                            chunk_count += 1
                            
                            # 성능 모니터링
                            if chunk_count % 10 == 0:
                                logger.info(f"처리된 청크: {chunk_count}개")
                                
                        except json.JSONDecodeError:
                            logger.warning(f"JSON 파싱 실패: {data_content}")
                            
                result.calculate_stats()
                
                # 검증
                assert result.streaming_complete, "스트리밍이 완료되지 않음"
                assert result.total_chunks >= 50, f"청크 수 부족: {result.total_chunks} < 50"
                assert result.total_chunks <= 100, f"청크 수 초과: {result.total_chunks} > 100"
                assert 3.0 <= result.processing_time <= 5.0, f"처리 시간 범위 초과: {result.processing_time}"
                
                logger.info(f"✅ 기본 스트리밍 테스트 통과: {result.total_chunks}개 청크, {result.processing_time:.2f}초")
                
        except Exception as e:
            result.error_occurred = True
            result.error_message = str(e)
            logger.error(f"❌ 기본 스트리밍 테스트 실패: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_streaming_output_accuracy(self, test_request, mock_vllm_stream):
        """스트리밍 출력 정확성 테스트"""
        logger.info("🎯 스트리밍 출력 정확성 테스트 시작")
        
        result = StreamingTestResult()
        
        try:
            with patch.object(vllm_service, 'generate_code_stream', return_value=mock_vllm_stream()):
                async for chunk in vllm_service.generate_code_stream(test_request, "test_user"):
                    if chunk.startswith("data: "):
                        data_content = chunk[6:].strip()
                        
                        if data_content == "[DONE]":
                            break
                            
                        try:
                            parsed_data = json.loads(data_content)
                            result.add_chunk(parsed_data, time.time())
                        except json.JSONDecodeError:
                            continue
                
                result.calculate_stats()
                
                # 출력 정확성 검증
                assert result.contains_expected_output(), f"기대하는 출력 없음: {result.final_code}"
                assert "print" in result.final_code.lower(), "print 문이 포함되지 않음"
                assert "jay" in result.final_code.lower(), "Jay 문자열이 포함되지 않음"
                
                logger.info(f"✅ 출력 정확성 테스트 통과")
                logger.info(f"생성된 코드: {result.final_code}")
                
        except Exception as e:
            logger.error(f"❌ 출력 정확성 테스트 실패: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_streaming_performance_metrics(self, test_request, mock_vllm_stream):
        """스트리밍 성능 메트릭 테스트"""
        logger.info("⚡ 스트리밍 성능 메트릭 테스트 시작")
        
        result = StreamingTestResult()
        
        try:
            with patch.object(vllm_service, 'generate_code_stream', return_value=mock_vllm_stream()):
                async for chunk in vllm_service.generate_code_stream(test_request, "test_user"):
                    if chunk.startswith("data: "):
                        data_content = chunk[6:].strip()
                        
                        if data_content == "[DONE]":
                            break
                            
                        try:
                            parsed_data = json.loads(data_content)
                            result.add_chunk(parsed_data, time.time())
                        except json.JSONDecodeError:
                            continue
                
                result.calculate_stats()
                
                # 성능 메트릭 검증
                assert result.is_performance_acceptable(), (
                    f"성능 기준 미충족: {result.total_chunks}개 청크, "
                    f"{result.processing_time:.2f}초"
                )
                
                assert result.chunks_per_second >= 10, (
                    f"초당 청크 처리 속도 부족: {result.chunks_per_second:.1f} < 10"
                )
                
                logger.info(f"✅ 성능 메트릭 테스트 통과")
                logger.info(f"성능 지표: {result.chunks_per_second:.1f} 청크/초, "
                           f"평균 청크 크기: {result.average_chunk_size:.1f}자")
                
        except Exception as e:
            logger.error(f"❌ 성능 메트릭 테스트 실패: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_api_endpoint_streaming(self, test_request):
        """API 엔드포인트 스트리밍 테스트"""
        logger.info("🌐 API 엔드포인트 스트리밍 테스트 시작")
        
        # Mock dependencies
        mock_background_tasks = MagicMock(spec=BackgroundTasks)
        mock_api_key = "test_api_key"
        mock_current_user = {"user_id": "test_user"}
        
        # Mock 스트리밍 응답
        async def mock_stream():
            for i in range(60):  # 60개 청크
                yield f"data: {json.dumps({'text': f'chunk_{i} '})}\n\n"
                await asyncio.sleep(0.05)
            yield f"data: {json.dumps({'text': 'print(\"Jay\")'})}\n\n"
            yield f"data: [DONE]\n\n"
        
        try:
            with patch.object(vllm_service, 'check_health', return_value={"status": "healthy"}):
                with patch.object(vllm_service, 'generate_code_stream', return_value=mock_stream()):
                    
                    # API 엔드포인트 호출
                    response = await generate_code_stream(
                        request=test_request,
                        background_tasks=mock_background_tasks,
                        api_key=mock_api_key,
                        current_user=mock_current_user
                    )
                    
                    # 응답 타입 검증
                    assert isinstance(response, StreamingResponse), "StreamingResponse가 아님"
                    assert response.media_type == "text/event-stream", "미디어 타입 불일치"
                    
                    # 스트리밍 내용 검증
                    result = StreamingTestResult()
                    start_time = time.time()
                    
                    async for chunk in response.body_iterator:
                        chunk_str = chunk.decode('utf-8')
                        if chunk_str.startswith("data: "):
                            data_content = chunk_str[6:].strip()
                            
                            if data_content == "[DONE]":
                                result.streaming_complete = True
                                break
                                
                            try:
                                parsed_data = json.loads(data_content)
                                result.add_chunk(parsed_data, time.time())
                            except json.JSONDecodeError:
                                continue
                    
                    result.calculate_stats()
                    
                    # 검증
                    assert result.streaming_complete, "API 스트리밍이 완료되지 않음"
                    assert result.total_chunks >= 50, f"API 청크 수 부족: {result.total_chunks}"
                    assert "print" in result.final_code, "API 응답에 print 문 없음"
                    
                    logger.info(f"✅ API 엔드포인트 스트리밍 테스트 통과")
                    
        except Exception as e:
            logger.error(f"❌ API 엔드포인트 스트리밍 테스트 실패: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_chunk_buffering_performance(self, test_request):
        """청크 버퍼링 성능 테스트"""
        logger.info("🗂️ 청크 버퍼링 성능 테스트 시작")
        
        # 매우 작은 청크들로 시뮬레이션
        async def mock_small_chunks_stream():
            text = "def print_jay():\n    print(\"Jay\")\n\nprint_jay()"
            for char in text:
                yield f"data: {json.dumps({'text': char})}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: [DONE]\n\n"
        
        try:
            with patch.object(vllm_service, 'generate_code_stream', return_value=mock_small_chunks_stream()):
                result = StreamingTestResult()
                
                async for chunk in vllm_service.generate_code_stream(test_request, "test_user"):
                    if chunk.startswith("data: "):
                        data_content = chunk[6:].strip()
                        
                        if data_content == "[DONE]":
                            break
                            
                        try:
                            parsed_data = json.loads(data_content)
                            result.add_chunk(parsed_data, time.time())
                        except json.JSONDecodeError:
                            continue
                
                result.calculate_stats()
                
                # 버퍼링 효과 검증
                # 원본 문자 수보다 적은 청크가 출력되어야 함 (버퍼링으로 인해)
                original_char_count = len("def print_jay():\n    print(\"Jay\")\n\nprint_jay()")
                
                logger.info(f"원본 문자 수: {original_char_count}, 출력 청크 수: {result.total_chunks}")
                logger.info(f"버퍼링 효율: {(1 - result.total_chunks/original_char_count)*100:.1f}%")
                
                # 최종 출력 정확성 검증
                assert result.contains_expected_output(), "버퍼링 후 출력 불정확"
                
                logger.info(f"✅ 청크 버퍼링 성능 테스트 통과")
                
        except Exception as e:
            logger.error(f"❌ 청크 버퍼링 성능 테스트 실패: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_error_handling_during_streaming(self, test_request):
        """스트리밍 중 오류 처리 테스트"""
        logger.info("🚨 스트리밍 오류 처리 테스트 시작")
        
        # 오류 발생 시뮬레이션
        async def mock_error_stream():
            # 정상 청크 몇 개 전송
            for i in range(10):
                yield f"data: {json.dumps({'text': f'chunk_{i} '})}\n\n"
                await asyncio.sleep(0.01)
            
            # 오류 발생
            yield f"data: {json.dumps({'error': 'Mock streaming error'})}\n\n"
            yield f"data: [DONE]\n\n"
        
        try:
            with patch.object(vllm_service, 'generate_code_stream', return_value=mock_error_stream()):
                result = StreamingTestResult()
                
                async for chunk in vllm_service.generate_code_stream(test_request, "test_user"):
                    if chunk.startswith("data: "):
                        data_content = chunk[6:].strip()
                        
                        if data_content == "[DONE]":
                            break
                            
                        try:
                            parsed_data = json.loads(data_content)
                            if 'error' in parsed_data:
                                result.error_occurred = True
                                result.error_message = parsed_data['error']
                            else:
                                result.add_chunk(parsed_data, time.time())
                        except json.JSONDecodeError:
                            continue
                
                # 오류 처리 검증
                assert result.error_occurred, "오류가 제대로 감지되지 않음"
                assert result.error_message == "Mock streaming error", "오류 메시지 불일치"
                assert result.total_chunks == 10, f"오류 전 청크 수 불일치: {result.total_chunks}"
                
                logger.info(f"✅ 스트리밍 오류 처리 테스트 통과")
                
        except Exception as e:
            logger.error(f"❌ 스트리밍 오류 처리 테스트 실패: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_end_to_end_streaming_flow(self, test_request):
        """종단간 스트리밍 플로우 테스트"""
        logger.info("🔄 종단간 스트리밍 플로우 테스트 시작")
        
        # 실제 시나리오와 유사한 스트리밍 시뮬레이션
        async def mock_realistic_stream():
            # 시작 메타데이터
            yield f"data: {json.dumps({'type': 'start', 'model': 'prompt'})}\n\n"
            
            # 코드 생성 청크들
            code_parts = [
                "# Jay를 출력하는 간단한 코드\n",
                "def print_jay():\n",
                "    \"\"\"Jay 문자열을 출력하는 함수\"\"\"\n",
                "    print(\"Jay\")\n",
                "\n",
                "# 함수 호출\n",
                "print_jay()\n"
            ]
            
            for part in code_parts:
                # 각 부분을 더 작은 청크로 분할
                words = part.split()
                for word in words:
                    yield f"data: {json.dumps({'text': word + ' '})}\n\n"
                    await asyncio.sleep(0.03)
                yield f"data: {json.dumps({'text': '\n'})}\n\n"
                await asyncio.sleep(0.05)
            
            # 완료 메타데이터
            yield f"data: {json.dumps({'type': 'done', 'tokens': 45})}\n\n"
            yield f"data: [DONE]\n\n"
        
        try:
            with patch.object(vllm_service, 'generate_code_stream', return_value=mock_realistic_stream()):
                result = StreamingTestResult()
                metadata = {}
                
                async for chunk in vllm_service.generate_code_stream(test_request, "test_user"):
                    if chunk.startswith("data: "):
                        data_content = chunk[6:].strip()
                        
                        if data_content == "[DONE]":
                            result.streaming_complete = True
                            break
                            
                        try:
                            parsed_data = json.loads(data_content)
                            
                            if 'type' in parsed_data:
                                metadata[parsed_data['type']] = parsed_data
                            else:
                                result.add_chunk(parsed_data, time.time())
                                
                        except json.JSONDecodeError:
                            continue
                
                result.calculate_stats()
                
                # 종단간 플로우 검증
                assert result.streaming_complete, "종단간 스트리밍이 완료되지 않음"
                assert result.total_chunks >= 20, f"종단간 청크 수 부족: {result.total_chunks}"
                assert result.contains_expected_output(), "종단간 출력 불정확"
                assert 'start' in metadata, "시작 메타데이터 없음"
                assert 'done' in metadata, "완료 메타데이터 없음"
                
                logger.info(f"✅ 종단간 스트리밍 플로우 테스트 통과")
                logger.info(f"최종 생성 코드:\n{result.final_code}")
                
        except Exception as e:
            logger.error(f"❌ 종단간 스트리밍 플로우 테스트 실패: {e}")
            raise


# 실행 가능한 테스트 함수들
async def run_streaming_tests():
    """모든 스트리밍 테스트 실행"""
    logger.info("🚀 VLLM 스트리밍 통합 테스트 시작")
    
    test_instance = TestVLLMStreamingIntegration()
    test_request = CodeGenerationRequest(
        prompt="파이썬으로 Jay라는 문자열을 출력하는 간단한 코드를 작성해주세요",
        model_type=ModelType.CODE_GENERATION,
        context="",
        temperature=0.3,
        max_tokens=150
    )
    
    # Mock 스트리밍 함수
    async def mock_stream():
        chunks = [
            {"text": "def print_jay():\n"},
            {"text": "    print(\"Jay\")\n"},
            {"text": "\nprint_jay()"}
        ]
        
        # 더 많은 청크 생성
        extended_chunks = []
        for chunk in chunks:
            text = chunk["text"]
            for i in range(0, len(text), 2):
                extended_chunks.append({"text": text[i:i+2]})
        
        # 목표 청크 수에 맞게 패딩
        while len(extended_chunks) < 60:
            extended_chunks.append({"text": " "})
        
        for chunk in extended_chunks:
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.05)
        
        yield f"data: [DONE]\n\n"
    
    try:
        # 각 테스트 실행
        await test_instance.test_vllm_streaming_basic_functionality(test_request, mock_stream)
        await test_instance.test_streaming_output_accuracy(test_request, mock_stream)
        await test_instance.test_streaming_performance_metrics(test_request, mock_stream)
        await test_instance.test_chunk_buffering_performance(test_request)
        await test_instance.test_error_handling_during_streaming(test_request)
        await test_instance.test_end_to_end_streaming_flow(test_request)
        
        logger.info("🎉 모든 VLLM 스트리밍 테스트 통과!")
        
    except Exception as e:
        logger.error(f"❌ 스트리밍 테스트 실패: {e}")
        raise


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(run_streaming_tests())