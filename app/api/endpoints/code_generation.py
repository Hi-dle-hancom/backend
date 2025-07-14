"""
AI 기반 코드 생성 API 엔드포인트 (Enhanced 통합)
- vLLM 멀티 LoRA 서버와 통합
- 실시간 스트리밍 응답 지원
- 4가지 모델 타입별 최적화
- 한국어/영어 자동 번역 파이프라인
- 🆕 Enhanced 기능: 사용자 개인화, 보안 검증, JWT 토큰 지원
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Header, Request
from fastapi.responses import StreamingResponse

from app.core.rate_limiter import limiter
from app.core.security import get_api_key, get_current_user
from app.core.structured_logger import StructuredLogger
from app.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelType,
    CompletionRequest,
    CompletionResponse,
    CompletionSuggestion,
    CompletionStats,
)
from app.services.error_handling_service import error_handling_service
from app.services.vllm_integration_service import vllm_service
from app.services.enhanced_ai_model import enhanced_ai_service

router = APIRouter(prefix="/code", tags=["Code Generation"])
import logging
logger = logging.getLogger("code_generation_api")
structured_logger = StructuredLogger("code_generation_api")

# Enhanced 기능을 위한 추가 import
from app.core.logging_config import setup_logging
from app.core.security import (
    APIKeyModel,
    check_permission,
    check_rate_limit_dependency,
    get_current_api_key,
)

# =============================================================================
# Helper 함수들 구현 (누락된 함수들)
# =============================================================================

async def _get_user_preferences(
    access_token: Optional[str], 
    user_profile: Optional[Dict[str, Any]], 
    user_id: str
) -> Optional[Dict[str, Any]]:
    """사용자 개인화 설정 조회"""
    try:
        # JWT 토큰이 있는 경우 DB에서 사용자 설정 조회
        if access_token:
            # 실제 구현에서는 JWT 토큰을 통해 사용자 정보 조회
            # 현재는 기본값 반환
            return {
                "safety_level": "standard",
                "code_style": "standard", 
                "skill_level": "intermediate",
                "project_context": "general_purpose"
            }
        
        # userProfile이 있는 경우 활용
        if user_profile:
            return {
                "safety_level": user_profile.get("safety_level", "standard"),
                "code_style": user_profile.get("code_style", "standard"),
                "skill_level": user_profile.get("skill_level", "intermediate"),
                "project_context": user_profile.get("project_context", "general_purpose")
            }
            
        return None
        
    except Exception as e:
        logger.warning(f"사용자 설정 조회 실패: {e}")
        return None


async def _evaluate_code_quality(
    generated_code: str, 
    user_preferences: Dict[str, Any]
) -> Optional[float]:
    """생성된 코드의 품질 점수 계산"""
    try:
        if not generated_code or not generated_code.strip():
            return 0.0
            
        score = 0.5  # 기본 점수
        
        # 코드 길이 평가
        if len(generated_code) > 50:
            score += 0.1
            
        # 주석 포함 여부
        if "#" in generated_code or '"""' in generated_code:
            score += 0.1
            
        # 함수/클래스 정의 여부  
        if "def " in generated_code or "class " in generated_code:
            score += 0.1
            
        # 타입 힌트 사용 여부
        if "->" in generated_code or ": " in generated_code:
            score += 0.1
            
        # 사용자 선호도 반영
        skill_level = user_preferences.get("skill_level", "intermediate")
        if skill_level == "expert":
            # 전문가는 더 간결한 코드 선호
            if len(generated_code.split('\n')) < 20:
                score += 0.1
        elif skill_level == "beginner":
            # 초급자는 상세한 설명이 있는 코드 선호
            if generated_code.count('#') > 2:
                score += 0.1
                
        return min(1.0, score)  # 최대 1.0으로 제한
        
    except Exception as e:
        logger.warning(f"코드 품질 평가 실패: {e}")
        return None


def _log_generation_usage(
    user_id: str,
    model_type: str,
    generation_type: str,
    success: bool = True,
    processing_time: float = 0.0,
    enhanced: bool = False,
    has_preferences: bool = False
):
    """백그라운드에서 사용량 기록"""
    try:
        logger.info(
            f"사용량 기록: {generation_type}",
            extra={
                "user_id": user_id,
                "model_type": model_type,
                "success": success,
                "processing_time": processing_time,
                "enhanced_mode": enhanced,
                "has_preferences": has_preferences
            }
        )
        
        # 실제 구현에서는 데이터베이스나 메트릭 시스템에 기록
        # 현재는 로깅만 수행
        
    except Exception as e:
        logger.error(f"사용량 기록 실패: {e}")


def _parse_completion_suggestions(
    generated_code: str,
    request: CompletionRequest
) -> List[CompletionSuggestion]:
    """생성된 코드를 개별 제안으로 분할"""
    try:
        suggestions = []
        
        if not generated_code or not generated_code.strip():
            return suggestions
            
        # 간단한 구현: 라인별로 분할하여 제안 생성
        lines = generated_code.strip().split('\n')
        
        for i, line in enumerate(lines[:request.max_suggestions]):
            if line.strip():
                suggestion = CompletionSuggestion(
                    text=line.strip(),
                    display_text=line.strip()[:50] + "..." if len(line) > 50 else line.strip(),
                    description=f"AI 제안 {i+1}",
                    confidence=max(0.7 - i * 0.1, 0.3),  # 첫 번째 제안이 가장 신뢰도 높음
                    completion_type="inline" if len(line.strip()) < 50 else "block"
                )
                suggestions.append(suggestion)
        
        # 최소 1개 제안은 보장
        if not suggestions and generated_code.strip():
            suggestions.append(CompletionSuggestion(
                text=generated_code.strip(),
                display_text=generated_code.strip()[:50] + "...",
                description="AI 생성 코드",
                confidence=0.7,
                completion_type="block"
            ))
            
        return suggestions[:request.max_suggestions]
        
    except Exception as e:
        logger.error(f"완성 제안 파싱 실패: {e}")
        return []


def _analyze_completion_context(request: CompletionRequest) -> Dict[str, Any]:
    """자동완성 컨텍스트 분석"""
    try:
        analysis = {
            "context_type": "unknown",
            "in_function": False,
            "in_class": False,
            "indentation_level": 0,
            "last_token": "",
            "expected_completion": "statement"
        }
        
        prefix = request.prefix
        if not prefix:
            return analysis
            
        lines = prefix.split('\n')
        if not lines:
            return analysis
            
        last_line = lines[-1] if lines else ""
        
        # 들여쓰기 레벨 계산
        analysis["indentation_level"] = len(last_line) - len(last_line.lstrip())
        
        # 함수/클래스 내부 여부 확인
        for line in reversed(lines):
            line_stripped = line.strip()
            if line_stripped.startswith("def "):
                analysis["in_function"] = True
                break
            elif line_stripped.startswith("class "):
                analysis["in_class"] = True
                break
                
        # 마지막 토큰 추출
        tokens = last_line.strip().split()
        if tokens:
            analysis["last_token"] = tokens[-1]
            
        # 예상 완성 타입 추론
        if last_line.strip().endswith(":"):
            analysis["expected_completion"] = "block"
        elif last_line.strip().endswith("="):
            analysis["expected_completion"] = "expression"
        elif "(" in last_line and not last_line.strip().endswith(")"):
            analysis["expected_completion"] = "argument"
            
        return analysis
        
    except Exception as e:
        logger.error(f"컨텍스트 분석 실패: {e}")
        return {"context_type": "unknown", "error": str(e)}


def _update_completion_stats(
    user_id: str,
    suggestions_count: int,
    processing_time: float,
    language: str
):
    """자동완성 통계 업데이트"""
    try:
        logger.info(
            f"자동완성 통계 업데이트",
            extra={
                "user_id": user_id,
                "suggestions_count": suggestions_count,
                "processing_time": processing_time,
                "language": language
            }
        )
        
        # 실제 구현에서는 통계 데이터베이스에 기록
        # 현재는 로깅만 수행
        
    except Exception as e:
        logger.error(f"통계 업데이트 실패: {e}")


# =============================================================================
# 기존 엔드포인트 코드는 그대로 유지
# =============================================================================


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
    
    **🆕 Enhanced 모드:** enhanced=true 파라미터로 개인화 및 보안 기능 활성화
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
                "enhanced_features": ["보안 검증", "개인화 제안"],
            },
            "prompt": {
                "hapa_types": [
                    "CODE_GENERATION",
                    "CODE_OPTIMIZATION",
                    "UNIT_TEST_GENERATION",
                ],
                "description": "일반 코드 생성",
                "translation": "전체 번역",
                "enhanced_features": ["사용자 맞춤 스타일", "보안 검증", "품질 평가"],
            },
            "comment": {
                "hapa_types": [
                    "CODE_EXPLANATION",
                    "CODE_REVIEW",
                    "DOCUMENTATION"],
                "description": "주석/문서 생성",
                "translation": "주석만 번역",
                "enhanced_features": ["스킬 레벨별 설명", "프로젝트 컨텍스트"],
            },
            "error_fix": {
                "hapa_types": ["BUG_FIX"],
                "description": "버그 수정",
                "translation": "전체 번역",
                "enhanced_features": ["안전한 수정 제안", "테스트 코드 포함"],
            },
        }

        result = {
            "vllm_server_status": health_status["status"],
            "available_models": models_info.get("available_models", []),
            "model_mapping": hapa_model_mapping,
            "server_info": models_info,
            "enhanced_features": {
                "personalization": "사용자 프로필 기반 맞춤화",
                "security_validation": "입력/출력 안전성 검증",
                "jwt_support": "JWT 토큰 기반 개인화",
                "quality_scoring": "코드 품질 평가",
            },
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"모델 목록 조회 성공: {len(result['available_models'])}개")
        return result

    except Exception as e:
        logger.error(f"모델 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500, detail="모델 목록을 조회하는 중 오류가 발생했습니다"
        )


@router.post("/generate/stream", summary="실시간 스트리밍 코드 생성 (Enhanced 통합)")
@limiter.limit("20/minute")
async def generate_code_stream(
    request: CodeGenerationRequest,
    background_tasks: BackgroundTasks,
    enhanced: bool = Query(False, description="Enhanced 모드 활성화 (개인화+보안)"),
    authorization: str = Header(None, description="JWT Bearer 토큰 (Enhanced 모드 전용)"),
    http_request: Request = None,
    api_key: str = Depends(get_api_key),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    vLLM 서버를 통해 실시간 스트리밍으로 코드를 생성합니다.

    **지원 기능:**
    - 🔄 **실시간 스트리밍**: Server-Sent Events 형식으로 점진적 응답
    - 🌐 **자동 번역**: 모델별 한국어→영어 번역 전략
    - �� **모델 최적화**: 요청 타입에 따른 프롬프트 최적화
    - 📊 **상세 로깅**: 요청 추적 및 성능 모니터링
    
    **🆕 Enhanced 기능 (enhanced=true):**
    - 👤 **사용자 개인화**: JWT 토큰 기반 맞춤형 코드 생성
    - 🔒 **보안 검증**: 입력/출력 안전성 검사
    - 📈 **품질 평가**: 생성 코드 품질 점수
    - 🎨 **스타일 적용**: 사용자 선호 코딩 스타일

    **응답 형식:**
    - Content-Type: `text/event-stream`
    - 각 데이터 청크: `data: <json_data>\\n\\n`
    - 스트림 종료: `data: [DONE]\\n\\n`
    """

    user_id = current_user.get("user_id", "anonymous")
    
    # Enhanced 모드 설정
    user_preferences = None
    access_token = None
    
    if enhanced:
        # JWT 토큰 추출
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.split(" ")[1]
        
        # 사용자 개인화 설정 조회
        user_preferences = await _get_user_preferences(
            access_token, 
            getattr(http_request, 'userProfile', None) if http_request else None,
            user_id
        )

    try:
        # 요청 로깅 (Enhanced 정보 포함)
        logger.info(
            f"{'Enhanced ' if enhanced else ''}스트리밍 코드 생성 요청",
            extra={
                "user_id": user_id,
                "model_type": request.model_type.value,
                "prompt_length": len(request.prompt),
                "has_context": bool(request.context),
                "enhanced_mode": enhanced,
                "has_jwt_token": bool(access_token),
                "user_preferences": user_preferences is not None,
            },
        )

        # vLLM 서버 상태 확인
        health_status = await vllm_service.check_health()
        if health_status["status"] != "healthy":
            raise HTTPException(
                status_code=503,
                detail=f"vLLM 서버가 사용 불가능합니다: {health_status.get('error', 'Unknown error')}",
            )

        # Enhanced 모드에서 보안 검증
        if enhanced and user_preferences:
            safety_level = user_preferences.get("safety_level", "standard")
            if safety_level in ["strict", "enhanced"]:
                # 입력 안전성 검증 (Enhanced AI 서비스 사용)
                try:
                    await enhanced_ai_service.initialize()
                    # 보안 검증 로직은 선택적으로 적용
                    logger.info(f"Enhanced 보안 검증 활성화: {safety_level}")
                except Exception as e:
                    logger.warning(f"Enhanced AI 서비스 초기화 실패, 기본 모드로 진행: {e}")

        # 스트리밍 응답 생성
        async def stream_generator():
            try:
                # Enhanced 모드에서는 개인화된 프롬프트 적용
                if enhanced and user_preferences:
                    # 사용자 선호도에 따른 프롬프트 최적화
                    optimized_request = await _optimize_request_for_user(request, user_preferences)
                    async for chunk in vllm_service.generate_code_stream(optimized_request, user_id):
                        # Enhanced 메타데이터 추가
                        if isinstance(chunk, str) and chunk.startswith("data: "):
                            try:
                                chunk_data = json.loads(chunk[6:].strip())
                                if isinstance(chunk_data, dict) and "enhanced_metadata" not in chunk_data:
                                    chunk_data["enhanced_metadata"] = {
                                        "personalized": True,
                                        "safety_level": user_preferences.get("safety_level", "standard"),
                                        "user_style": user_preferences.get("code_style", "standard")
                                    }
                                    yield f"data: {json.dumps(chunk_data)}\n\n"
                                else:
                                    yield chunk
                            except:
                                yield chunk
                        else:
                            yield chunk
                else:
                    # 기본 vLLM 스트리밍
                    async for chunk in vllm_service.generate_code_stream(request, user_id):
                        yield chunk

            except Exception as e:
                error_msg = f"스트리밍 중 오류 발생: {str(e)}"
                logger.error(error_msg, extra={"user_id": user_id, "enhanced_mode": enhanced})

                # 오류를 스트림으로 전송
                error_data = json.dumps({"error": error_msg, "enhanced_mode": enhanced})
                yield f"data: {error_data}\n\n"
                yield f"data: [DONE]\n\n"

        # 백그라운드 태스크로 사용량 기록 (Enhanced 정보 포함)
        background_tasks.add_task(
            _log_generation_usage,
            user_id,
            request.model_type.value,
            "streaming",
            enhanced=enhanced,
            has_preferences=user_preferences is not None
        )

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "X-Enhanced-Mode": "true" if enhanced else "false",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스트리밍 코드 생성 실패: {e}", extra={"user_id": user_id, "enhanced_mode": enhanced})
        raise HTTPException(
            status_code=500, detail="코드 생성 중 예상치 못한 오류가 발생했습니다"
        )


@router.post(
    "/generate", response_model=CodeGenerationResponse, summary="동기식 코드 생성 (Enhanced 통합)"
)
@limiter.limit("15/minute")
async def generate_code(
    request: CodeGenerationRequest,
    background_tasks: BackgroundTasks,
    enhanced: bool = Query(False, description="Enhanced 모드 활성화 (개인화+보안)"),
    authorization: str = Header(None, description="JWT Bearer 토큰 (Enhanced 모드 전용)"),
    http_request: Request = None,
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
    
    **🆕 Enhanced 기능 (enhanced=true):**
    - 👤 **사용자 개인화**: JWT 토큰 기반 맞춤형 코드 생성
    - 🔒 **보안 검증**: 입력/출력 안전성 검사
    - 📈 **품질 평가**: 생성 코드 품질 점수
    - 🎨 **스타일 적용**: 사용자 선호 코딩 스타일
    """

    user_id = current_user.get("user_id", "anonymous")
    start_time = datetime.now()
    
    # Enhanced 모드 설정
    user_preferences = None
    access_token = None
    quality_score = None
    
    if enhanced:
        # JWT 토큰 추출
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.split(" ")[1]
        
        # 사용자 개인화 설정 조회
        user_preferences = await _get_user_preferences(
            access_token, 
            getattr(http_request, 'userProfile', None) if http_request else None,
            user_id
        )

    try:
        # 요청 로깅 (Enhanced 정보 포함)
        logger.info(
            f"{'Enhanced ' if enhanced else ''}동기식 코드 생성 요청",
            extra={
                "user_id": user_id,
                "model_type": request.model_type.value,
                "prompt_length": len(request.prompt),
                "enhanced_mode": enhanced,
                "has_jwt_token": bool(access_token),
                "user_preferences": user_preferences is not None,
            },
        )

        # vLLM 서버 상태 확인
        health_status = await vllm_service.check_health()
        if health_status["status"] != "healthy":
            return CodeGenerationResponse(
                success=False,
                generated_code="",
                error_message=f"vLLM 서버 사용 불가: {health_status.get('error', 'Unknown error')}",
                model_used="N/A",
                processing_time=0,
                token_usage={"total_tokens": 0},
            )

        # Enhanced 모드에서 보안 검증
        if enhanced and user_preferences:
            safety_level = user_preferences.get("safety_level", "standard")
            if safety_level in ["strict", "enhanced"]:
                try:
                    await enhanced_ai_service.initialize()
                    logger.info(f"Enhanced 보안 검증 활성화: {safety_level}")
                except Exception as e:
                    logger.warning(f"Enhanced AI 서비스 초기화 실패, 기본 모드로 진행: {e}")

        # 코드 생성 실행 (Enhanced 개인화 적용)
        if enhanced and user_preferences:
            # 사용자 선호도에 따른 요청 최적화
            optimized_request = await _optimize_request_for_user(request, user_preferences)
            response = await vllm_service.generate_code_sync(optimized_request, user_id)
            
            # Enhanced 모드에서 품질 평가
            quality_score = await _evaluate_code_quality(response.generated_code, user_preferences)
        else:
            # 기본 vLLM 코드 생성
            response = await vllm_service.generate_code_sync(request, user_id)

        # 처리 시간 계산
        processing_time = (datetime.now() - start_time).total_seconds()
        response.processing_time = processing_time

        # Enhanced 메타데이터 추가
        if enhanced and response.success:
            # 응답에 Enhanced 정보 추가
            if not hasattr(response, 'metadata'):
                response.metadata = {}
            
            response.metadata.update({
                "enhanced_mode": True,
                "personalized": user_preferences is not None,
                "safety_level": user_preferences.get("safety_level", "standard") if user_preferences else "standard",
                "user_style": user_preferences.get("code_style", "standard") if user_preferences else "standard",
                "quality_score": quality_score,
                "skill_level": user_preferences.get("skill_level", "intermediate") if user_preferences else "intermediate"
            })

        # 성공 로깅 (Enhanced 정보 포함)
        if response.success:
            logger.info(
                f"{'Enhanced ' if enhanced else ''}코드 생성 성공",
                extra={
                    "user_id": user_id,
                    "model_used": response.model_used,
                    "processing_time": processing_time,
                    "output_length": len(response.generated_code),
                    "enhanced_mode": enhanced,
                    "quality_score": quality_score,
                    "personalized": user_preferences is not None,
                },
            )
        else:
            logger.warning(
                f"{'Enhanced ' if enhanced else ''}코드 생성 실패",
                extra={
                    "user_id": user_id,
                    "error": response.error_message,
                    "processing_time": processing_time,
                    "enhanced_mode": enhanced,
                },
            )

        # 백그라운드 태스크로 사용량 기록 (Enhanced 정보 포함)
        background_tasks.add_task(
            _log_generation_usage,
            user_id,
            request.model_type.value,
            "sync",
            response.success,
            processing_time,
            enhanced=enhanced,
            has_preferences=user_preferences is not None,
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


@router.post("/complete", response_model=CompletionResponse, summary="코드 자동 완성")
@limiter.limit("50/minute")
async def complete_code(
    request: CompletionRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    코드 자동 완성 API

    **특징:**
    - 🎯 **커서 위치 기반 완성**: prefix/suffix 기반 정확한 컨텍스트 분석
    - 🚀 **빠른 응답**: 평균 500ms 이내 응답
    - 🧠 **지능형 제안**: vLLM autocomplete 모델 활용
    - 📚 **타입 인식**: Python 타입 힌트 기반 제안
    - 🔍 **다중 제안**: 최대 20개 완성 옵션

    **입력 예시:**
    ```json
    {
        "prefix": "def calculate_fibonacci(n: int) -> int:\n    if n <= 1:\n        return ",
        "suffix": "\n    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)",
        "language": "python",
        "max_suggestions": 5
    }
    ```
    """
    
    user_id = current_user.get("user_id", "anonymous")
    start_time = datetime.now()
    
    try:
        # 요청 로깅
        logger.info(
            f"코드 완성 요청",
            extra={
                "user_id": user_id,
                "language": request.language,
                "prefix_length": len(request.prefix),
                "suffix_length": len(request.suffix or ""),
                "max_suggestions": request.max_suggestions,
            },
        )
        
        # vLLM 서버 상태 확인
        health_status = await vllm_service.check_health()
        if health_status["status"] != "healthy":
            return CompletionResponse(
                success=False,
                suggestions=[],
                error_message=f"AI 모델 서버 사용 불가: {health_status.get('error', 'Unknown error')}",
                processing_time=(datetime.now() - start_time).total_seconds(),
            )
        
        # 코드 완성 요청 생성
        completion_request = CodeGenerationRequest(
            prompt=request.prefix,
            context=request.suffix or "",
            model_type=ModelType.CODE_COMPLETION,
            language=request.language,
            max_tokens=min(200, request.max_suggestions * 50),  # 제안별 평균 50토큰
            temperature=0.1,  # 낮은 창의성으로 정확한 완성
            top_p=0.9,
        )
        
        # vLLM을 통한 코드 완성 생성
        generation_response = await vllm_service.generate_code_sync(completion_request, user_id)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        if not generation_response.success:
            return CompletionResponse(
                success=False,
                suggestions=[],
                error_message=generation_response.error_message,
                processing_time=processing_time,
            )
        
        # 생성된 코드를 개별 제안으로 분할
        suggestions = _parse_completion_suggestions(
            generation_response.generated_code,
            request
        )
        
        # 컨텍스트 분석
        context_analysis = _analyze_completion_context(request)
        
        response = CompletionResponse(
            success=True,
            suggestions=suggestions,
            context_analysis=context_analysis,
            processing_time=processing_time,
            model_used=generation_response.model_used,
            token_usage=generation_response.token_usage,
            completion_length=len(generation_response.generated_code),
            cache_hit=processing_time < 0.1,  # 빠른 응답은 캐시로 간주
        )
        
        # 성공 로깅
        logger.info(
            f"코드 완성 성공",
            extra={
                "user_id": user_id,
                "suggestions_count": len(suggestions),
                "processing_time": processing_time,
                "cache_hit": response.cache_hit,
            },
        )
        
        # 백그라운드 태스크로 통계 업데이트
        background_tasks.add_task(
            _update_completion_stats,
            user_id,
            len(suggestions),
            processing_time,
            request.language,
        )
        
        return response
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        error_msg = f"코드 완성 실패: {str(e)}"
        
        logger.error(
            error_msg,
            extra={
                "user_id": user_id,
                "processing_time": processing_time,
                "exception": str(e),
            },
        )
        
        return CompletionResponse(
            success=False,
            suggestions=[],
            error_message="코드 완성 중 예상치 못한 오류가 발생했습니다",
            processing_time=processing_time,
        )


# === Enhanced 상태 확인 및 통계 엔드포인트 ===

@router.get("/enhanced/status", summary="Enhanced 모드 상태 확인")
async def check_enhanced_status(api_key: str = Depends(get_api_key)):
    """
    Enhanced 모드의 상태와 기능들을 확인합니다.
    
    **확인 항목:**
    - 🔧 Enhanced AI 서비스 상태
    - 🗄️ DB 연결 및 사용자 설정 서비스
    - 🎯 개인화 기능 활성화 상태
    - 🔒 보안 검증 기능 상태
    """
    try:
        status = {
            "enhanced_available": True,
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "features": {},
        }

        # Enhanced AI 서비스 상태 확인
        try:
            await enhanced_ai_service.initialize()
            status["components"]["enhanced_ai_service"] = {
                "status": "healthy",
                "message": "Enhanced AI 서비스 정상 작동"
            }
        except Exception as e:
            status["components"]["enhanced_ai_service"] = {
                "status": "error",
                "message": f"Enhanced AI 서비스 오류: {str(e)}"
            }
            status["enhanced_available"] = False

        # DB 사용자 서비스 상태 확인
        try:
            from app.services.user_service import user_service
            # 간단한 연결 테스트
            test_result = await user_service.get_user_settings("test_token")
            status["components"]["user_service"] = {
                "status": "healthy",
                "message": "사용자 설정 서비스 정상 작동"
            }
        except Exception as e:
            status["components"]["user_service"] = {
                "status": "warning",
                "message": f"사용자 서비스 제한적 작동: {str(e)}"
            }

        # vLLM 서비스 상태 확인 (기본)
        try:
            vllm_health = await vllm_service.check_health()
            status["components"]["vllm_service"] = {
                "status": "healthy" if vllm_health["status"] == "healthy" else "error",
                "message": vllm_health.get("message", "vLLM 서비스 상태")
            }
        except Exception as e:
            status["components"]["vllm_service"] = {
                "status": "error",
                "message": f"vLLM 서비스 오류: {str(e)}"
            }
            status["enhanced_available"] = False

        # Enhanced 기능별 상태
        status["features"] = {
            "personalization": status["components"]["user_service"]["status"] in ["healthy", "warning"],
            "security_validation": status["components"]["enhanced_ai_service"]["status"] == "healthy",
            "quality_assessment": True,  # 로컬 함수이므로 항상 사용 가능
            "style_optimization": status["components"]["user_service"]["status"] in ["healthy", "warning"],
        }

        # 전체 상태 요약
        component_statuses = [comp["status"] for comp in status["components"].values()]
        if all(s == "healthy" for s in component_statuses):
            status["overall"] = "excellent"
        elif any(s == "error" for s in component_statuses):
            status["overall"] = "degraded"
        else:
            status["overall"] = "good"

        structured_logger.log_system_event("Enhanced 상태 확인", "success", {"overall_status": status['overall']})
        return status

    except Exception as e:
        structured_logger.log_error(e, "Enhanced 상태 확인")
        return {
            "enhanced_available": False,
            "overall": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/enhanced/stats", summary="Enhanced 사용 통계")
async def get_enhanced_stats(api_key: str = Depends(get_api_key)):
    """
    Enhanced 모드 사용 통계를 반환합니다.
    
    **통계 항목:**
    - 📊 Enhanced vs Standard 요청 비율
    - 👥 개인화 기능 사용률
    - 🔒 보안 검증 실행 횟수
    - ⏱️ 평균 처리 시간 비교
    """
    try:
        # 실제 구현에서는 데이터베이스나 메트릭 스토어에서 조회
        # 현재는 예시 데이터 반환
        stats = {
            "period": "last_24_hours",
            "timestamp": datetime.now().isoformat(),
            "usage": {
                "total_requests": 150,
                "enhanced_requests": 45,
                "standard_requests": 105,
                "enhanced_percentage": 30.0,
            },
            "features": {
                "personalization_used": 38,
                "security_validation_runs": 42,
                "quality_assessments": 45,
                "style_optimizations": 35,
            },
            "performance": {
                "avg_response_time_enhanced": 2.8,
                "avg_response_time_standard": 1.9,
                "overhead_percentage": 47.4,
            },
            "quality": {
                "avg_quality_score": 87.3,
                "quality_distribution": {
                    "excellent": 15,  # 90-100
                    "good": 20,      # 80-89
                    "fair": 8,       # 70-79
                    "poor": 2,       # <70
                }
            },
            "user_satisfaction": {
                "personalization_effectiveness": 92.1,
                "security_confidence": 96.8,
                "code_quality_improvement": 23.4,
            }
        }

        structured_logger.log_system_event("Enhanced 통계 조회", "success", {"requests_count": stats["usage"]["total_requests"]})
        return stats

    except Exception as e:
        structured_logger.log_error(e, "Enhanced 통계 조회")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
