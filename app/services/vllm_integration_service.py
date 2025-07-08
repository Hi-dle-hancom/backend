"""
vLLM 멀티 LoRA 서버 통합 서비스
- 4가지 모델 타입별 코드 생성
- 실시간 스트리밍 응답 처리
- 한국어/영어 자동 번역 파이프라인 지원
- 사용자 선택 옵션 최적화
"""

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, Literal, Optional

import aiohttp

from app.core.config import settings
from app.core.structured_logger import StructuredLogger
from app.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelType,
)

logger = StructuredLogger("vllm_integration")


class VLLMModelType(str, Enum):
    """vLLM 서버에서 지원하는 모델 타입"""

    AUTOCOMPLETE = "autocomplete"  # 코드 자동완성 (번역 없음)
    PROMPT = "prompt"  # 일반 코드 생성 (전체 번역)
    COMMENT = "comment"  # 주석/docstring 생성 (주석만 번역)
    ERROR_FIX = "error_fix"  # 버그 수정 (전체 번역)


class VLLMIntegrationService:
    """vLLM 멀티 LoRA 서버와의 통합 서비스"""

    def __init__(self):
        self.vllm_base_url = settings.VLLM_SERVER_URL
        self.timeout = aiohttp.ClientTimeout(total=settings.VLLM_TIMEOUT_SECONDS)
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp 세션 생성 및 재사용"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            )
        return self.session

    async def check_health(self) -> Dict[str, Any]:
        """vLLM 서버 상태 확인"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.vllm_base_url}/health") as response:
                if response.status == 200:
                    result = await response.json()
                    logger.log_system_event(
                        "vLLM 서버 상태 확인", "success", {"server_status": result}
                    )
                    return {"status": "healthy", "details": result}
                else:
                    logger.log_system_event(
                        "vLLM 서버 상태 확인",
                        "failed",
                        {"http_status": response.status},
                    )
                    return {
                        "status": "unhealthy",
                        "http_status": response.status}
        except Exception as e:
            logger.log_error(e, "vLLM 서버 연결")
            return {"status": "error", "error": str(e)}

    async def get_available_models(self) -> Dict[str, Any]:
        """사용 가능한 모델 목록 조회"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.vllm_base_url}/") as response:
                if response.status == 200:
                    result = await response.json()
                    logger.log_system_event(
                        "vLLM 모델 목록 조회",
                        "success",
                        {"models": result.get("available_models", [])},
                    )
                    return result
                else:
                    logger.log_system_event(
                        "vLLM 모델 목록 조회",
                        "failed",
                        {"http_status": response.status},
                    )
                    return {"available_models": []}
        except Exception as e:
            logger.log_error(e, "vLLM 모델 목록 조회")
            return {"available_models": []}

    def _map_hapa_to_vllm_model(self, hapa_model: ModelType) -> VLLMModelType:
        """HAPA 모델 타입을 vLLM 모델 타입으로 매핑"""
        mapping = {
            ModelType.CODE_COMPLETION: VLLMModelType.AUTOCOMPLETE,
            ModelType.CODE_GENERATION: VLLMModelType.PROMPT,
            ModelType.CODE_EXPLANATION: VLLMModelType.COMMENT,
            ModelType.CODE_REVIEW: VLLMModelType.COMMENT,
            ModelType.BUG_FIX: VLLMModelType.ERROR_FIX,
            ModelType.CODE_OPTIMIZATION: VLLMModelType.PROMPT,
            ModelType.UNIT_TEST_GENERATION: VLLMModelType.PROMPT,
            ModelType.DOCUMENTATION: VLLMModelType.COMMENT,
        }
        return mapping.get(hapa_model, VLLMModelType.PROMPT)

    def _prepare_vllm_request(
        self, request: CodeGenerationRequest, user_id: str
    ) -> Dict[str, Any]:
        """HAPA 요청을 vLLM 요청 형식으로 변환"""
        vllm_model = self._map_hapa_to_vllm_model(request.model_type)

        # 모델별 프롬프트 최적화
        optimized_prompt = self._optimize_prompt_for_model(
            request.prompt, vllm_model, request
        )

        # 사용자 선택 옵션 매핑
        user_select_options = self._map_user_options(request)

        # user_id를 숫자로 변환 (해시 사용)
        try:
            numeric_user_id = abs(hash(user_id)) % 1000000  # 1-1000000 범위
        except BaseException:
            numeric_user_id = 12345  # 기본값

        vllm_request = {
            "user_id": numeric_user_id,
            "model_type": vllm_model.value,
            "prompt": optimized_prompt,
            "user_select_options": user_select_options,
            "temperature": float(getattr(request, "temperature", 0.3)),
            "top_p": float(getattr(request, "top_p", 0.95)),
            "max_tokens": int(getattr(request, "max_tokens", 1024)),
        }

        logger.log_system_event(
            f"vLLM 요청 준비",
            "success",
            {
                "user_id": user_id,
                "numeric_user_id": numeric_user_id,
                "model_type": vllm_model.value,
                "prompt_length": len(optimized_prompt),
                "temperature": vllm_request["temperature"],
            },
        )

        return vllm_request

    def _optimize_prompt_for_model(
            self,
            prompt: str,
            model_type: VLLMModelType,
            request: CodeGenerationRequest) -> str:
        """모델 타입별 프롬프트 최적화"""

        if model_type == VLLMModelType.AUTOCOMPLETE:
            # 자동완성: 영어 코드 컨텍스트로 변환
            if request.context:
                return f"{request.context}\n{prompt}"
            return prompt

        elif model_type == VLLMModelType.COMMENT:
            # 주석 생성: 코드와 주석 요청을 분리하여 최적화
            if request.context:
                return f"# 다음 코드에 대한 상세한 주석을 작성해주세요.\n{
                    request.context}\n\n# 요청사항: {prompt}"
            return f"# {prompt}"

        elif model_type == VLLMModelType.ERROR_FIX:
            # 버그 수정: 문제 상황과 코드를 명확히 구분하고 단계별 접근
            if request.context:
                return f"""# 파이썬 코드 오류 수정 요청

## 문제 상황:
{prompt}

## 오류가 있는 코드:
{request.context}

## 요구사항:
1. 위 코드의 문법 오류나 논리적 오류를 찾아주세요
2. 수정된 코드를 제공해주세요
3. 수정한 부분에 대한 간단한 설명을 주석으로 추가해주세요

## 수정된 코드:"""
            return f"""# 파이썬 코드 오류 수정

## 문제:
{prompt}

## 해결 방법:
1. 문제를 분석하고 올바른 파이썬 코드로 수정
2. 문법 오류 및 논리적 오류 수정
3. 간단하고 명확한 코드 작성

## 수정된 코드:"""

        else:  # PROMPT (기본)
            # 일반 코드 생성: 요구사항을 명확히 표현
            context_prefix = (
                f"# 컨텍스트:\n{request.context}\n\n" if request.context else ""
            )
            return f"{context_prefix}# 요청사항: {prompt}"

    def _map_user_options(
            self, request: CodeGenerationRequest) -> Dict[str, Any]:
        """HAPA 사용자 옵션을 vLLM 형식으로 매핑"""
        options = {}

        # 프로그래밍 기술 수준 매핑
        if hasattr(request, "programming_level"):
            level_mapping = {
                "beginner": "beginner",
                "intermediate": "intermediate",
                "advanced": "advanced",
                "expert": "advanced",
            }
            options["python_skill_level"] = level_mapping.get(
                request.programming_level, "intermediate"
            )
        else:
            options["python_skill_level"] = "intermediate"

        # 설명 스타일 매핑
        if hasattr(request, "explanation_detail"):
            detail_mapping = {
                "minimal": "brief",
                "standard": "standard",
                "detailed": "detailed",
                "comprehensive": "detailed",
            }
            options["explanation_style"] = detail_mapping.get(
                request.explanation_detail, "standard"
            )
        else:
            options["explanation_style"] = "standard"

        # 추가 옵션들
        if hasattr(request, "include_comments"):
            options["include_comments"] = request.include_comments

        if hasattr(request, "code_style"):
            options["code_style"] = request.code_style

        return options

    async def generate_code_stream(
        self, request: CodeGenerationRequest, user_id: str
    ) -> AsyncGenerator[str, None]:
        """vLLM 서버로부터 스트리밍 코드 생성"""

        vllm_request = self._prepare_vllm_request(request, user_id)

        try:
            session = await self._get_session()

            async with session.post(
                f"{self.vllm_base_url}/generate/stream", json=vllm_request
            ) as response:

                if response.status != 200:
                    error_msg = f"vLLM 서버 오류: HTTP {response.status}"
                    logger.log_system_event(
                        "vLLM 서버 오류",
                        "failed",
                        {"user_id": user_id, "status": response.status},
                    )
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    return

                logger.log_system_event(
                    "vLLM 스트리밍 시작",
                    "started",
                    {"user_id": user_id, "model": vllm_request["model_type"]},
                )

                async for line in response.content:
                    try:
                        line_text = line.decode("utf-8").strip()

                        if not line_text:
                            continue

                        # Server-Sent Events 형식 처리
                        if line_text.startswith("data: "):
                            data_content = line_text[6:]  # 'data: ' 제거

                            # 스트림 종료 신호 감지
                            if data_content == "[DONE]":
                                logger.log_system_event(
                                    "vLLM 스트리밍", "completed", {
                                        "user_id": user_id})
                                yield f"data: [DONE]\n\n"
                                break

                            # 데이터 전달
                            yield f"data: {data_content}\n\n"

                    except Exception as e:
                        logger.log_error(e, f"스트림 라인 처리 - user_id: {user_id}")
                        continue

        except asyncio.TimeoutError:
            error_msg = "vLLM 서버 응답 시간 초과"
            logger.log_system_event("vLLM 응답", "timeout", {"user_id": user_id})
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

        except Exception as e:
            error_msg = f"vLLM 서버 연결 오류: {str(e)}"
            logger.log_error(e, f"vLLM 서버 연결 - user_id: {user_id}")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    async def generate_code_sync(
        self, request: CodeGenerationRequest, user_id: str
    ) -> CodeGenerationResponse:
        """동기식 코드 생성 (스트리밍 응답을 모두 수집)"""

        generated_content = []
        error_occurred = False
        error_message = ""

        async for chunk in self.generate_code_stream(request, user_id):
            try:
                if chunk.startswith("data: "):
                    data_content = chunk[6:].strip()

                    if data_content == "[DONE]":
                        break

                    # JSON 파싱 시도
                    try:
                        data = json.loads(data_content)
                        if "error" in data:
                            error_occurred = True
                            error_message = data["error"]
                            break
                        elif "text" in data:
                            generated_content.append(data["text"])
                        elif isinstance(data, str):
                            generated_content.append(data)
                    except json.JSONDecodeError:
                        # JSON이 아닌 경우 직접 텍스트로 처리
                        generated_content.append(data_content)

            except Exception as e:
                logger.log_error(e, f"동기식 응답 처리 - user_id: {user_id}")
                error_occurred = True
                error_message = str(e)
                break

        if error_occurred:
            return CodeGenerationResponse(
                success=False,
                generated_code="",
                error_message=error_message,
                model_used=self._map_hapa_to_vllm_model(
                    request.model_type).value,
                processing_time=0,
                token_usage={
                    "total_tokens": 0},
            )

        final_code = "".join(generated_content)

        return CodeGenerationResponse(
            success=True,
            generated_code=final_code,
            model_used=self._map_hapa_to_vllm_model(request.model_type).value,
            processing_time=0,  # 실제 처리 시간 계산 필요
            token_usage={"total_tokens": len(final_code.split())},  # 근사치
        )

    async def close(self):
        """세션 정리"""
        if self.session and not self.session.closed:
            await self.session.close()

    def __del__(self):
        """소멸자에서 세션 정리"""
        if hasattr(
                self,
                "session") and self.session and not self.session.closed:
            # 이벤트 루프가 실행 중인 경우에만 정리
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.session.close())
            except RuntimeError:
                pass


# 전역 서비스 인스턴스
vllm_service = VLLMIntegrationService()
