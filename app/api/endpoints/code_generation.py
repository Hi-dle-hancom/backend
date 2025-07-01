"""
AI 기반 코드 생성 API 엔드포인트
- vLLM 멀티 LoRA 서버와 통합
- 실시간 스트리밍 응답 지원
- 4가지 모델 타입별 최적화
- 한국어/영어 자동 번역 파이프라인
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.rate_limiter import limiter
from app.core.security import get_api_key, get_current_user
from app.core.structured_logger import StructuredLogger
from app.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelType,
)
from app.services.error_handling_service import error_handling_service
from app.services.vllm_integration_service import vllm_service

router = APIRouter(prefix="/code", tags=["Code Generation"])
logger = StructuredLogger("code_generation_api")


@router.get("/models", summary="사용 가능한 AI 모델 목록")
@limiter.limit("30/minute")
async def get_available_models(api_key: str = Depends(get_api_key)):
    """
    vLLM 서버에서 사용 가능한 AI 모델들의 목록을 조회합니다.

    **지원하는 모델 타입:**
    - `autocomplete`: 코드 자동완성 (번역 없음, 영어 입력 권장)
    - `prompt`: 일반 코드 생성 (전체 번역)
    - `comment`: 주석/docstring 생성 (주석만 번역)
    - `error_fix`: 버그 수정 (전체 번역)
    """
    try:
        # vLLM 서버 상태 확인
        health_status = await vllm_service.check_health()
        if health_status["status"] != "healthy":
            logger.warning(
                "vLLM 서버 상태 불안정", extra={"health_status": health_status}
            )

        # 사용 가능한 모델 조회
        models_info = await vllm_service.get_available_models()

        # HAPA 모델 타입과 매핑 정보 추가
        hapa_model_mapping = {
            "autocomplete": {
                "hapa_types": ["CODE_COMPLETION"],
                "description": "코드 자동완성 (영어 입력 권장)",
                "translation": "없음",
            },
            "prompt": {
                "hapa_types": [
                    "CODE_GENERATION",
                    "CODE_OPTIMIZATION",
                    "UNIT_TEST_GENERATION",
                ],
                "description": "일반 코드 생성",
                "translation": "전체 번역",
            },
            "comment": {
                "hapa_types": [
                    "CODE_EXPLANATION",
                    "CODE_REVIEW",
                    "DOCUMENTATION"],
                "description": "주석/문서 생성",
                "translation": "주석만 번역",
            },
            "error_fix": {
                "hapa_types": ["BUG_FIX"],
                "description": "버그 수정",
                "translation": "전체 번역",
            },
        }

        result = {
            "vllm_server_status": health_status["status"],
            "available_models": models_info.get("available_models", []),
            "model_mapping": hapa_model_mapping,
            "server_info": models_info,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"모델 목록 조회 성공: {len(result['available_models'])}개")
        return result

    except Exception as e:
        logger.error(f"모델 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail="모델 목록을 조회하는 중 오류가 발생했습니다"
        )


@router.post("/generate/stream", summary="실시간 스트리밍 코드 생성")
@limiter.limit("20/minute")
async def generate_code_stream(
    request: CodeGenerationRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    vLLM 서버를 통해 실시간 스트리밍으로 코드를 생성합니다.

    **지원 기능:**
    - 🔄 **실시간 스트리밍**: Server-Sent Events 형식으로 점진적 응답
    - 🌐 **자동 번역**: 모델별 한국어→영어 번역 전략
    - 🎯 **모델 최적화**: 요청 타입에 따른 프롬프트 최적화
    - 📊 **상세 로깅**: 요청 추적 및 성능 모니터링

    **응답 형식:**
    - Content-Type: `text/event-stream`
    - 각 데이터 청크: `data: <json_data>\\n\\n`
    - 스트림 종료: `data: [DONE]\\n\\n`
    """

    user_id = current_user.get("user_id", "anonymous")

    try:
        # 요청 로깅
        logger.info(
            f"스트리밍 코드 생성 요청",
            extra={
                "user_id": user_id,
                "model_type": request.model_type.value,
                "prompt_length": len(request.prompt),
                "has_context": bool(request.context),
            },
        )

        # vLLM 서버 상태 확인
        health_status = await vllm_service.check_health()
        if health_status["status"] != "healthy":
            raise HTTPException(
                status_code=503,
                detail=f"vLLM 서버가 사용 불가능합니다: {
                    health_status.get(
                        'error',
                        'Unknown error')}",
            )

        # 스트리밍 응답 생성
        async def stream_generator():
            try:
                async for chunk in vllm_service.generate_code_stream(request, user_id):
                    yield chunk

            except Exception as e:
                error_msg = f"스트리밍 중 오류 발생: {str(e)}"
                logger.error(error_msg, extra={"user_id": user_id})

                # 오류를 스트림으로 전송
                error_data = json.dumps({"error": error_msg})
                yield f"data: {error_data}\n\n"
                yield f"data: [DONE]\n\n"

        # 백그라운드 태스크로 사용량 기록
        background_tasks.add_task(
            _log_generation_usage,
            user_id,
            request.model_type.value,
            "streaming")

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스트리밍 코드 생성 실패: {e}", extra={"user_id": user_id})
        raise HTTPException(
            status_code=500, detail="코드 생성 중 예상치 못한 오류가 발생했습니다"
        )


@router.post(
    "/generate", response_model=CodeGenerationResponse, summary="동기식 코드 생성"
)
@limiter.limit("15/minute")
async def generate_code(
    request: CodeGenerationRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    vLLM 서버를 통해 동기식으로 코드를 생성합니다.

    **특징:**
    - 완전한 응답을 한 번에 반환
    - 모든 스트리밍 데이터를 수집하여 종합
    - 상세한 메타데이터 포함
    - 오류 처리 및 복구 지원
    """

    user_id = current_user.get("user_id", "anonymous")
    start_time = datetime.now()

    try:
        # 요청 로깅
        logger.info(
            f"동기식 코드 생성 요청",
            extra={
                "user_id": user_id,
                "model_type": request.model_type.value,
                "prompt_length": len(request.prompt),
            },
        )

        # vLLM 서버 상태 확인
        health_status = await vllm_service.check_health()
        if health_status["status"] != "healthy":
            return CodeGenerationResponse(
                success=False,
                generated_code="",
                error_message=f"vLLM 서버 사용 불가: {
                    health_status.get(
                        'error',
                        'Unknown error')}",
                model_used="N/A",
                processing_time=0,
                token_usage={
                    "total_tokens": 0},
            )

        # 코드 생성 실행
        response = await vllm_service.generate_code_sync(request, user_id)

        # 처리 시간 계산
        processing_time = (datetime.now() - start_time).total_seconds()
        response.processing_time = processing_time

        # 성공 로깅
        if response.success:
            logger.info(
                f"코드 생성 성공",
                extra={
                    "user_id": user_id,
                    "model_used": response.model_used,
                    "processing_time": processing_time,
                    "output_length": len(response.generated_code),
                },
            )
        else:
            logger.warning(
                f"코드 생성 실패",
                extra={
                    "user_id": user_id,
                    "error": response.error_message,
                    "processing_time": processing_time,
                },
            )

        # 백그라운드 태스크로 사용량 기록
        background_tasks.add_task(
            _log_generation_usage,
            user_id,
            request.model_type.value,
            "sync",
            response.success,
            processing_time,
        )

        return response

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        error_msg = f"동기식 코드 생성 실패: {str(e)}"

        logger.error(
            error_msg,
            extra={
                "user_id": user_id,
                "processing_time": processing_time,
                "exception": str(e),
            },
        )

        # 오류 응답 반환
        return CodeGenerationResponse(
            success=False,
            generated_code="",
            error_message="코드 생성 중 예상치 못한 오류가 발생했습니다",
            model_used="N/A",
            processing_time=processing_time,
            token_usage={"total_tokens": 0},
        )


@router.get("/health", summary="vLLM 서버 상태 확인")
async def check_vllm_health(api_key: str = Depends(get_api_key)):
    """
    vLLM 멀티 LoRA 서버의 상태를 확인합니다.

    **반환 정보:**
    - 서버 상태 (healthy/unhealthy/error)
    - 응답 시간
    - 사용 가능한 모델 목록
    - 서버 세부 정보
    """
    try:
        health_status = await vllm_service.check_health()
        models_info = await vllm_service.get_available_models()

        return {
            "vllm_server": health_status,
            "available_models": models_info.get("available_models", []),
            "server_details": models_info,
            "timestamp": datetime.now().isoformat(),
            "integration_status": "active",
        }

    except Exception as e:
        logger.error(f"vLLM 상태 확인 실패: {e}")
        return {
            "vllm_server": {"status": "error", "error": str(e)},
            "available_models": [],
            "server_details": {},
            "timestamp": datetime.now().isoformat(),
            "integration_status": "error",
        }


@router.post("/test", summary="vLLM 연동 테스트")
@limiter.limit("5/minute")
async def test_vllm_integration(
    model_type: ModelType = Query(
        ModelType.CODE_GENERATION, description="테스트할 모델 타입"
    ),
    api_key: str = Depends(get_api_key),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    vLLM 서버와의 연동을 테스트합니다.

    **테스트 내용:**
    - 간단한 코드 생성 요청
    - 응답 시간 측정
    - 오류 처리 검증
    """

    user_id = current_user.get("user_id", "test_user")

    # 테스트 요청 생성
    test_request = CodeGenerationRequest(
        prompt="파이썬으로 Hello World를 출력하는 간단한 함수를 만들어주세요.",
        model_type=model_type,
        context="",
        max_tokens=100,
        temperature=0.3,
    )

    try:
        start_time = datetime.now()

        # 동기식 생성 테스트
        response = await vllm_service.generate_code_sync(test_request, user_id)

        processing_time = (datetime.now() - start_time).total_seconds()

        test_result = {
            "test_status": "success" if response.success else "failed",
            "response_time_seconds": processing_time,
            "model_used": response.model_used,
            "output_length": len(
                response.generated_code) if response.success else 0,
            "error_message": response.error_message if not response.success else None,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"vLLM 연동 테스트 완료", extra=test_result)
        return test_result

    except Exception as e:
        error_result = {
            "test_status": "error",
            "error_message": str(e),
            "timestamp": datetime.now().isoformat(),
        }

        logger.error(f"vLLM 연동 테스트 실패: {e}")
        return error_result


# === 내부 도우미 함수 ===


async def _log_generation_usage(
    user_id: str,
    model_type: str,
    request_type: str,
    success: bool = True,
    processing_time: float = 0,
):
    """코드 생성 사용량 로깅 (백그라운드 태스크)"""
    try:
        usage_data = {
            "user_id": user_id,
            "model_type": model_type,
            "request_type": request_type,
            "success": success,
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("코드 생성 사용량 기록", extra=usage_data)

        # 추후 분석용 데이터베이스 저장 로직 추가 가능

    except Exception as e:
        logger.error(f"사용량 로깅 실패: {e}")
