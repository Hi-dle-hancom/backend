"""
AI 모델 서비스 - Enhanced AI 모델 서비스 연동
vLLM 멀티 LoRA 서버와 기존 AI 모델의 통합 인터페이스
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.core.config import settings
from app.core.structured_logger import StructuredLogger

from ..schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelType,
    StreamingChunk,
)

logger = StructuredLogger("ai_model")


class AIModelManager:
    """AI 모델 로딩과 관리를 담당하는 클래스"""
    
    def __init__(self):
        self.model_loaded = False
        self.model = None
        self._load_time = None
    
    def lazy_load_model(self):
        """필요할 때만 모델을 로드합니다."""
        if not self.model_loaded:
            self._load_model()
    
    def _load_model(self):
        """실제 모델 로딩 로직"""
        try:
            logger.info("Python 코드 생성 AI 모델 로딩 시작...")
            start_time = time.time()
            
            # 실제 모델 로딩 로직이 들어갈 자리
            self.model = {
                "name": settings.MODEL_NAME,
                "version": settings.MODEL_VERSION,
                "language": "python",
                "status": "loaded",
                "load_time": start_time,
                "capabilities": {
                    "code_generation": True,
                    "code_completion": True,
                    "code_explanation": True,
                    "error_detection": True,
                },
            }
            
            self._load_time = time.time() - start_time
            self.model_loaded = True
            
            logger.info(f"AI 모델 로딩 완료 (소요시간: {self._load_time:.2f}초)")
            
        except Exception as e:
            logger.error(f"AI 모델 로딩 실패: {e}")
            self.model_loaded = False
            raise Exception(f"AI 모델 로딩에 실패했습니다: {e}")
    
    def is_loaded(self) -> bool:
        """모델이 로드되었는지 확인"""
        return self.model_loaded
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        if not self.model_loaded:
            return {"status": "not_loaded"}
        
        return {
            "status": "loaded",
            "load_time": self._load_time,
            "model_info": self.model,
        }

    async def generate_streaming_response(
        self, prompt: str, context: Optional[str] = None
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        스트리밍 방식으로 AI 응답 생성
        실제 AI 모델에서는 토큰 단위로 생성되는 응답을 yield
        """
        session_id = str(uuid.uuid4())
        sequence = 0
        
        # 시뮬레이션된 AI 응답 생성
        sample_responses = [
            "# 요청하신 기능을 구현해보겠습니다.\n\n",
            "def ",
            "fibonacci",
            "(n):",
            "\n    ",
            '"""',
            "피보나치 수열의 n번째 값을 계산합니다",
            '"""\n    ',
            "if n <= 0:",
            "\n        ",
            "return 0",
            "\n    ",
            "elif n == 1:",
            "\n        ",
            "return 1",
            "\n    ",
            "else:",
            "\n        ",
            "return fibonacci(n-1) + fibonacci(n-2)",
            "\n\n# 사용 예시\n",
            "print(fibonacci(10))",
        ]
        
        # 초기 메타데이터 전송
        yield StreamingChunk(
            type="start",
            content=f"코드 생성을 시작합니다... (세션: {session_id[:8]})",
            sequence=sequence,
            timestamp=datetime.now(),
        )
        sequence += 1
        
        # 토큰별 스트리밍 시뮬레이션
        for token in sample_responses:
            # 실제 AI 모델 응답 대기 시뮬레이션
            await asyncio.sleep(0.05)  # 50ms 지연으로 타이핑 효과
            
            # 코드 블록 감지
            chunk_type = (
                "code"
                if any(
                    keyword in token.lower()
                    for keyword in ["def ", "class ", "import ", "from "]
                )
                else "token"
            )
            
            yield StreamingChunk(
                type=chunk_type,
                content=token,
                sequence=sequence,
                timestamp=datetime.now(),
            )
            sequence += 1
        
        # 설명 부분 스트리밍
        explanation_parts = [
            "\n\n이 함수는 ",
            "재귀적으로 ",
            "피보나치 수열을 ",
            "계산합니다. ",
            "더 효율적인 ",
            "동적 프로그래밍 ",
            "방식으로도 ",
            "구현할 수 있습니다.",
        ]
        
        for part in explanation_parts:
            await asyncio.sleep(0.08)  # 설명 부분은 조금 더 빠르게
            
            yield StreamingChunk(
                type="explanation",
                content=part,
                sequence=sequence,
                timestamp=datetime.now(),
            )
            sequence += 1
        
        # 완료 신호
        yield StreamingChunk(
            type="done", content="", sequence=sequence, timestamp=datetime.now()
        )


class AIModelService:
    """
    AI 모델 서비스 - Enhanced AI 서비스 래퍼
    기존 코드와의 호환성을 위한 레거시 인터페이스
    """

    def __init__(self):
        self.service_name = "AIModelService"
        self._enhanced_service = None

    async def _get_enhanced_service(self):
        """Enhanced AI 서비스 지연 로딩"""
        if self._enhanced_service is None:
            from app.services.enhanced_ai_model import enhanced_ai_service

            self._enhanced_service = enhanced_ai_service

            # 초기화되지 않은 경우 초기화
            if not hasattr(self._enhanced_service, "vllm_available"):
                await self._enhanced_service.initialize()

        return self._enhanced_service

    async def predict_and_parse(
        self,
        prompt: str,
        context: Optional[str] = None,
        language: str = "python",
        access_token: Optional[str] = None,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        레거시 인터페이스: AI 모델 예측 및 파싱
        Enhanced AI 서비스로 라우팅
        """
        start_time = time.time()

        try:
            logger.log_system_event(
                "레거시 AI 예측 요청",
                "started",
                {
                    "prompt_length": len(prompt),
                    "has_context": bool(context),
                    "language": language,
                },
            )

            # Enhanced AI 서비스 가져오기
            enhanced_service = await self._get_enhanced_service()

            # 레거시 요청을 새로운 형식으로 변환
            request = CodeGenerationRequest(
                prompt=prompt,
                context=context or "",
                model_type=ModelType.CODE_GENERATION,  # 기본값
                language=language,
                programming_level="intermediate",  # 기본값
                explanation_detail="standard",  # 기본값
            )

            # 사용자 ID 추출 (access_token 또는 기본값)
            user_id = "legacy_user"
            if access_token:
                # 실제 구현에서는 JWT 토큰에서 user_id 추출
                user_id = f"token_user_{hash(access_token) % 10000}"

            # Enhanced AI 서비스로 코드 생성
            response = await enhanced_service.generate_code(
                request=request, user_id=user_id, preferred_backend=None  # 자동 선택
            )

            processing_time = time.time() - start_time

            # 레거시 형식으로 응답 변환
            if response.success:
                result = {
                    "status": "success",
                    "generated_code": response.generated_code,
                    "explanation": response.explanation or "",
                    "model_used": response.model_used,
                    "processing_time": processing_time,
                    "backend_type": "enhanced",  # 구분용
                }

                logger.log_ai_generation(
                    model_name=response.model_used,
                    prompt_length=len(prompt),
                    response_length=len(response.generated_code),
                    generation_time_ms=processing_time * 1000,
                    user_id=user_id,
                )

            else:
                result = {
                    "status": "error",
                    "error_message": response.error_message,
                    "generated_code": "",
                    "explanation": "",
                    "processing_time": processing_time,
                }

                logger.log_system_event(
                    "레거시 AI 예측",
                    "failed",
                    {
                        "error": response.error_message,
                        "processing_time": processing_time,
                    },
                )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"AI 모델 예측 실패: {str(e)}"

            logger.log_error(e, "레거시 AI 예측")

            return {
                "status": "error",
                "error_message": error_msg,
                "generated_code": "",
                "explanation": "",
                "processing_time": processing_time,
            }

    async def complete_code(
        self, prefix: str, language: str = "python", max_suggestions: int = 5
    ) -> List[str]:
        """
        레거시 인터페이스: 코드 자동완성
        Enhanced AI 서비스로 라우팅
        """
        try:
            logger.log_system_event(
                "레거시 코드 완성 요청",
                "started",
                {
                    "prefix_length": len(prefix),
                    "language": language,
                    "max_suggestions": max_suggestions,
                },
            )

            # Enhanced AI 서비스 가져오기
            enhanced_service = await self._get_enhanced_service()

            # 자동완성 요청 생성
            request = CodeGenerationRequest(
                prompt=prefix,
                context="",
                model_type=ModelType.CODE_COMPLETION,
                language=language,
                max_tokens=64,  # 자동완성은 짧게
            )

            # 코드 생성
            response = await enhanced_service.generate_code(
                request=request, user_id="completion_user", preferred_backend=None
            )

            if response.success:
                # 단일 응답을 여러 제안으로 분할 (간단한 구현)
                code = response.generated_code.strip()
                suggestions = [code] if code else []

                # 필요시 추가 제안 생성 (실제로는 더 정교한 로직 필요)
                while len(suggestions) < max_suggestions and len(
                        suggestions) < 3:
                    suggestions.append(code)  # 임시로 같은 내용 반복

                logger.log_system_event(
                    "레거시 코드 완성",
                    "success",
                    {"suggestions_count": len(suggestions)},
                )

                return suggestions[:max_suggestions]
            else:
                logger.log_system_event(
                    "레거시 코드 완성", "failed", {"error": response.error_message}
                )
                return []

        except Exception as e:
            logger.log_error(e, "레거시 코드 완성")
            return []

    async def get_model_info(self) -> Dict[str, Any]:
        """Enhanced AI 서비스의 모델 정보 조회"""
        try:
            enhanced_service = await self._get_enhanced_service()
            backend_status = await enhanced_service.get_backend_status()

            return {
                "service": "Enhanced AI Model Service",
                "backends": backend_status["backends"],
                "current_backend": backend_status["current_backend"],
                "last_health_check": backend_status["last_health_check"],
                "legacy_compatibility": True,
            }

        except Exception as e:
            logger.log_error(e, "모델 정보 조회")
            return {
                "service": "AI Model Service (Legacy)",
                "status": "error",
                "error": str(e),
            }

    async def switch_backend(self, backend_type: str) -> bool:
        """백엔드 전환 (Enhanced AI 서비스에 위임)"""
        try:
            enhanced_service = await self._get_enhanced_service()

            from app.services.enhanced_ai_model import AIBackendType

            backend_map = {
                "vllm": AIBackendType.VLLM,
                "legacy": AIBackendType.LEGACY,
                "auto": AIBackendType.AUTO,
            }

            if backend_type.lower() not in backend_map:
                logger.log_system_event(
                    "백엔드 전환", "failed", {
                        "requested_backend": backend_type, "reason": "unknown_backend"}, )
                return False

            result = await enhanced_service.switch_backend(
                backend_map[backend_type.lower()]
            )

            logger.log_system_event(
                "백엔드 전환",
                "success" if result else "failed",
                {"requested_backend": backend_type, "result": result},
            )

            return result

        except Exception as e:
            logger.log_error(e, f"백엔드 전환 - {backend_type}")
            return False


# 전역 서비스 인스턴스 (기존 코드 호환성)
ai_model_service = AIModelService()

# 싱글톤 인스턴스
ai_model_manager = AIModelManager() 
