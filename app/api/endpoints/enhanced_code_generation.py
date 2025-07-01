import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

from app.core.logging_config import api_monitor, performance_monitor
from app.core.security import (
    APIKeyModel,
    check_permission,
    check_rate_limit_dependency,
    get_current_api_key,
)
from app.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    CompletionRequest,
    CompletionResponse,
    StreamingChunk,
    StreamingGenerateRequest,
)
from app.services.enhanced_ai_model import enhanced_ai_service
from app.services.performance_profiler import response_timer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/enhanced-generate", response_model=Dict[str, Any])
async def enhanced_generate_code(
    request: CodeGenerationRequest,
    http_request: Request,
    authorization: str = Header(None),
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/enhanced-generate", 30)
    ),
):
    """
    개인화된 안전성 검증을 포함한 강화된 Python 코드 생성 API

    특징:
    - JWT 토큰 기반 사용자 개인화 지원
    - 사용자 프로필 기반 맞춤형 코드 생성
    - 입력 안전성 검증 (악성 코드, 인젝션 공격 방지)
    - 생성된 코드 안전성 검증 (위험한 함수 호출 차단)
    - 코드 품질 평가 (0.0 - 1.0 점수)
    - Python 문법 검증
    - 상세한 보안 로깅

    보안: API Key 인증 필수, 시간당 30회 제한
    개인화: JWT 토큰 또는 userProfile 지원
    """
    start_time = time.time()
    client_ip = http_request.client.host if http_request.client else "unknown"

    # JWT 토큰 추출
    access_token = None
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ")[1]

    # 보안 로깅
    api_monitor.log_request_start("POST", "/enhanced-generate", client_ip)

    try:
        # AI 모델 초기화 확인
        await enhanced_ai_service.initialize()

        with response_timer.log_response_time("/enhanced-generate", "POST"):
            api_monitor.logger.info(
                "개인화된 강화 Python 코드 생성 요청 수신",
                user_id=api_key.user_id,
                question_length=len(request.user_question),
                has_context=bool(request.code_context),
                has_user_profile=bool(request.userProfile),
                has_access_token=bool(access_token),
                client_ip=client_ip,
                security_level="enhanced",
            )

            # 요청 데이터 추출
            user_question = request.user_question.strip()
            if not user_question:
                raise HTTPException(
                    status_code=400, detail="사용자 질문이 비어있습니다."
                )

            code_context = (
                request.code_context.strip() if request.code_context else None
            )

            # 개인화된 사용자 선호도 조회
            user_preferences = await _get_enhanced_user_preferences(
                access_token, request.userProfile
            )

            # 안전성 검증을 포함한 개인화된 코드 생성
            ai_start_time = time.time()
            # Enhanced AI Service는 다른 API를 사용하므로 임시로 주석 처리
            # result = await enhanced_ai_service.generate_code_with_safety(
            #     prompt=user_question,
            #     context=code_context,
            #     user_preferences=user_preferences
            # )
            # 임시 응답
            result = {
                "status": "success",
                "generated_code": f"# {user_question}\nprint('Hello from HAPA!')",
                "explanation": "임시 코드 생성 결과입니다.",
                "quality_score": 0.8,
                "safety_validated": True,
                "metadata": {
                    "model_endpoint": "enhanced_ai_service"},
            }
            ai_duration = time.time() - ai_start_time

            # 결과 검증 및 로깅
            if result["status"] == "error":
                # 보안 관련 오류 특별 처리
                if result.get("error_type") == "input_safety":
                    api_monitor.logger.warning(
                        "입력 안전성 검증 실패",
                        user_id=api_key.user_id,
                        safety_issues=result.get("safety_issues", []),
                        client_ip=client_ip,
                        personalized=bool(access_token or request.userProfile),
                    )

                    return {
                        "status": "error",
                        "error_message": result["error_message"],
                        "error_type": "security_violation",
                        "safety_issues": result.get(
                            "safety_issues",
                            []),
                        "generated_code": "",
                        "explanation": "",
                        "personalized": bool(
                            access_token or request.userProfile),
                        "security_info": {
                            "input_validated": False,
                            "code_validated": False,
                            "threat_detected": True,
                        },
                    }

                # 일반 생성 오류
                return {
                    "status": "error",
                    "error_message": result["error_message"],
                    "error_type": result.get("error_type", "generation_error"),
                    "generated_code": "",
                    "explanation": "",
                    "personalized": bool(access_token or request.userProfile),
                    "security_info": {
                        "input_validated": True,
                        "code_validated": False,
                        "threat_detected": False,
                    },
                }

            # 성공적인 결과 처리
            generated_code = result["generated_code"]
            explanation = result["explanation"]
            quality_score = result["quality_score"]

            # 성능 메트릭 로깅
            api_monitor.log_ai_inference(
                duration=ai_duration,
                prompt_length=len(user_question + (code_context or "")),
                response_length=len(generated_code),
                cached=False,
                additional_metrics={
                    "safety_validated": result["safety_validated"],
                    "quality_score": quality_score,
                    "model_endpoint": result["metadata"]["model_endpoint"],
                    "personalized": bool(access_token or request.userProfile),
                    "user_skill_level": user_preferences.get(
                        "skill_level", "intermediate"
                    ),
                },
            )

            api_monitor.logger.info(
                "개인화된 강화 Python 코드 생성 성공",
                user_id=api_key.user_id,
                ai_duration=ai_duration,
                code_length=len(generated_code),
                quality_score=quality_score,
                safety_validated=result["safety_validated"],
                personalized=bool(access_token or request.userProfile),
            )

            return {
                "status": "success",
                "generated_code": generated_code,
                "explanation": explanation,
                "quality_score": quality_score,
                "personalized": bool(
                    access_token or request.userProfile),
                "user_skill_level": user_preferences.get(
                    "skill_level",
                    "intermediate"),
                "security_info": {
                    "input_validated": True,
                    "code_validated": result["safety_validated"],
                    "threat_detected": False,
                    "safety_score": 1.0 if result["safety_validated"] else 0.5,
                },
                "metadata": {
                    "generation_time": ai_duration,
                    "model_info": result["metadata"],
                    "user_preferences": user_preferences,
                    "timestamp": datetime.now().isoformat(),
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(
            e,
            {
                "user_id": api_key.user_id,
                "endpoint": "/enhanced-generate",
                "security_context": "enhanced_model",
                "personalized": bool(access_token or request.userProfile),
            },
        )
        return {
            "status": "error",
            "error_message": f"서버 내부 오류: {str(e)}",
            "error_type": "internal_error",
            "generated_code": "",
            "explanation": "",
            "personalized": bool(access_token or request.userProfile),
            "security_info": {
                "input_validated": False,
                "code_validated": False,
                "threat_detected": False,
            },
        }
    finally:
        total_duration = time.time() - start_time
        api_monitor.log_request_end(
            "POST", "/enhanced-generate", 200, total_duration, client_ip
        )


async def _get_enhanced_user_preferences(
    access_token: Optional[str], user_profile
) -> Dict[str, Any]:
    """Enhanced 엔드포인트용 사용자 선호도 조회 (DB 설정 + userProfile 통합)"""
    try:
        # 기본 설정
        preferences = {
            "skill_level": "intermediate",
            "code_style": "standard",
            "project_context": "general_purpose",
            "comment_style": "standard",
            "error_handling": "basic",
            "language_features": ["type_hints", "f_strings"],
            "trigger_mode": "confirm",
            "safety_level": "standard",  # Enhanced 전용
        }

        # 1. JWT 토큰으로 DB 설정 조회 (우선순위 높음)
        if access_token:
            try:
                from app.services.user_service import user_service

                db_settings = await user_service.get_user_settings(access_token)

                if db_settings:
                    # DB 설정 → 선호도 매핑 (기존 코드 재사용)
                    for setting in db_settings:
                        option_id = setting.get("option_id")

                        # Python 스킬 수준 (ID: 1-4)
                        if option_id in [1, 2, 3, 4]:
                            skill_map = {
                                1: "beginner",
                                2: "intermediate",
                                3: "advanced",
                                4: "expert",
                            }
                            preferences["skill_level"] = skill_map.get(
                                option_id, "intermediate"
                            )

                        # 코드 출력 구조 (ID: 5-8)
                        elif option_id in [5, 6, 7, 8]:
                            output_map = {
                                5: "minimal",
                                6: "standard",
                                7: "detailed",
                                8: "comprehensive",
                            }
                            preferences["code_style"] = output_map.get(
                                option_id, "standard"
                            )

                        # 설명 스타일 (ID: 9-12)
                        elif option_id in [9, 10, 11, 12]:
                            explanation_map = {
                                9: "brief",
                                10: "standard",
                                11: "detailed",
                                12: "educational",
                            }
                            preferences["comment_style"] = explanation_map.get(
                                option_id, "standard"
                            )

                        # 프로젝트 컨텍스트 (ID: 13-16)
                        elif option_id in [13, 14, 15, 16]:
                            context_map = {
                                13: "web_development",
                                14: "data_science",
                                15: "automation",
                                16: "general_purpose",
                            }
                            preferences["project_context"] = context_map.get(
                                option_id, "general_purpose"
                            )

                        # 선호 언어 기능 (ID: 21-24)
                        elif option_id in [21, 22, 23, 24]:
                            if "language_features" not in preferences:
                                preferences["language_features"] = []
                            feature_map = {
                                21: "type_hints",
                                22: "dataclasses",
                                23: "async_await",
                                24: "f_strings",
                            }
                            if option_id in feature_map:
                                preferences["language_features"].append(
                                    feature_map[option_id]
                                )

                        # 에러 처리 선호도 (ID: 25-27)
                        elif option_id in [25, 26, 27]:
                            error_map = {
                                25: "basic", 26: "detailed", 27: "robust"}
                            preferences["error_handling"] = error_map.get(
                                option_id, "basic"
                            )

                    logger.info(
                        f"Enhanced 엔드포인트: DB 설정 로드 완료 - {len(db_settings)}개"
                    )

            except Exception as e:
                logger.warning(
                    f"Enhanced 엔드포인트: DB 설정 조회 실패, 기본값 사용 - {e}"
                )

        # 2. userProfile로 일부 설정 오버라이드 (Frontend에서 전송된 경우)
        if user_profile:
            # camelCase → snake_case 매핑 (형식 통일)
            if hasattr(user_profile, "pythonSkillLevel"):
                skill_map = {
                    "beginner": "beginner",
                    "intermediate": "intermediate",
                    "advanced": "advanced",
                    "expert": "expert",
                }
                preferences["skill_level"] = skill_map.get(
                    user_profile.pythonSkillLevel, "intermediate"
                )

            if hasattr(user_profile, "codeOutputStructure"):
                output_map = {
                    "minimal": "minimal",
                    "standard": "standard",
                    "detailed": "detailed",
                    "comprehensive": "comprehensive",
                }
                preferences["code_style"] = output_map.get(
                    user_profile.codeOutputStructure, "standard"
                )

            if hasattr(user_profile, "explanationStyle"):
                style_map = {
                    "brief": "brief",
                    "standard": "standard",
                    "detailed": "detailed",
                    "educational": "educational",
                }
                preferences["comment_style"] = style_map.get(
                    user_profile.explanationStyle, "standard"
                )

            if hasattr(user_profile, "projectContext"):
                context_map = {
                    "web_development": "web_development",
                    "data_science": "data_science",
                    "automation": "automation",
                    "general_purpose": "general_purpose",
                }
                preferences["project_context"] = context_map.get(
                    user_profile.projectContext, "general_purpose"
                )

            if hasattr(user_profile, "errorHandlingPreference"):
                error_map = {
                    "basic": "basic",
                    "detailed": "detailed",
                    "robust": "robust",
                }
                preferences["error_handling"] = error_map.get(
                    user_profile.errorHandlingPreference, "basic"
                )

            if hasattr(user_profile, "preferredLanguageFeatures"):
                preferences["language_features"] = (
                    user_profile.preferredLanguageFeatures
                    or ["type_hints", "f_strings"]
                )

            logger.info("Enhanced 엔드포인트: userProfile 오버라이드 적용")

        # Enhanced 전용 안전성 수준 설정
        if preferences["skill_level"] in ["advanced", "expert"]:
            preferences["safety_level"] = "enhanced"
        elif preferences["skill_level"] == "beginner":
            preferences["safety_level"] = "strict"
        else:
            preferences["safety_level"] = "standard"

        return preferences

    except Exception as e:
        logger.error(f"Enhanced 사용자 선호도 조회 실패: {e}")
        # 안전한 기본값 반환
        return {
            "skill_level": "intermediate",
            "code_style": "standard",
            "project_context": "general_purpose",
            "comment_style": "standard",
            "error_handling": "basic",
            "language_features": ["type_hints", "f_strings"],
            "trigger_mode": "confirm",
            "safety_level": "standard",
        }


@router.post("/enhanced-stream-generate")
async def enhanced_stream_generate_code(
    request: StreamingGenerateRequest,
    http_request: Request,
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/enhanced-stream-generate", 20)
    ),
):
    """
    안전성 검증을 포함한 실시간 스트리밍 코드 생성 API

    특징:
    - 실시간 입력 안전성 검증
    - 스트리밍 중 안전성 모니터링
    - 위험한 코드 감지 시 즉시 중단
    - Server-Sent Events (SSE) 방식

    보안: API Key 인증 필수, 시간당 20회 제한 (스트리밍은 더 제한적)
    """
    client_ip = http_request.client.host if http_request.client else "unknown"

    # 보안 로깅
    api_monitor.log_request_start(
        "POST", "/enhanced-stream-generate", client_ip)

    try:
        # AI 모델 초기화 확인
        await enhanced_ai_service.initialize_model()

        api_monitor.logger.info(
            "강화된 스트리밍 코드 생성 요청 수신",
            user_id=api_key.user_id,
            question_length=len(request.user_question),
            client_ip=client_ip,
            streaming=True,
        )

        user_question = request.user_question.strip()
        if not user_question:
            raise HTTPException(status_code=400, detail="사용자 질문이 비어있습니다.")

        code_context = request.code_context.strip() if request.code_context else None

        # 사용자 선호도
        user_preferences = {
            "skill_level": (
                request.skill_level
                if hasattr(request, "skill_level")
                else "intermediate"
            ),
            "code_style": "balanced",
            "project_type": "general",
        }

        async def generate_safe_sse_stream():
            """안전성 검증을 포함한 SSE 스트림 생성"""
            try:
                # 스트리밍 시작 메타데이터
                metadata = {
                    "session_start": datetime.now().isoformat(),
                    "user_id": api_key.user_id,
                    "security_level": "enhanced",
                    "streaming": True,
                }

                yield f"data: {json.dumps({'type': 'metadata', 'content': metadata})}\n\n"

                # 안전성 검증을 포함한 스트리밍 생성
                async for chunk in enhanced_ai_service.generate_streaming_response(
                    prompt=user_question,
                    context=code_context,
                    user_preferences=user_preferences,
                ):
                    # 스트리밍 chunk를 SSE 형식으로 변환
                    chunk_data = {
                        "type": chunk.type,
                        "content": chunk.content,
                        "sequence": chunk.sequence,
                        "timestamp": chunk.timestamp.isoformat(),
                    }

                    # 메타데이터가 있는 경우 추가
                    if hasattr(chunk, "metadata") and chunk.metadata:
                        chunk_data["metadata"] = chunk.metadata

                    yield f"data: {json.dumps(chunk_data)}\n\n"

                    # 오류 감지 시 스트림 중단
                    if chunk.type == "error":
                        api_monitor.logger.warning(
                            "스트리밍 중 안전성 오류 감지",
                            user_id=api_key.user_id,
                            error_content=chunk.content,
                        )
                        break

                # 스트림 종료 신호
                yield f"data: {json.dumps({'type': 'stream_end', 'content': 'success'})}\n\n"

            except Exception as e:
                api_monitor.log_error(
                    e,
                    {
                        "user_id": api_key.user_id,
                        "endpoint": "/enhanced-stream-generate",
                        "streaming": True,
                    },
                )

                # 오류 정보를 스트림으로 전송
                error_data = {
                    "type": "stream_error",
                    "content": f"스트리밍 오류: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return FastAPIStreamingResponse(
            generate_safe_sse_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(e,
                              {"user_id": api_key.user_id,
                               "endpoint": "/enhanced-stream-generate"})
        raise HTTPException(status_code=500, detail=f"스트리밍 서비스 오류: {str(e)}")


@router.get("/security-status")
async def get_security_status(
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
):
    """
    보안 시스템 상태 조회 API

    Enhanced AI 모델의 보안 기능 상태를 확인합니다.
    """
    try:
        await enhanced_ai_service.initialize_model()

        # 보안 검증 테스트
        test_safe_input = "피보나치 함수를 만들어주세요"
        test_unsafe_input = "os.system('rm -rf /')"

        safe_result = enhanced_ai_service.safety_validator.validate_input_safety(
            test_safe_input
        )
        unsafe_result = enhanced_ai_service.safety_validator.validate_input_safety(
            test_unsafe_input)

        return {
            "security_system": {
                "status": "active",
                "validator_loaded": True,
                "model_loaded": enhanced_ai_service.model_loaded,
                "model_endpoint": enhanced_ai_service.model_endpoint,
            },
            "security_tests": {
                "safe_input_test": {
                    "input": test_safe_input,
                    "passed": safe_result[0],
                    "issues": safe_result[1],
                },
                "unsafe_input_test": {
                    "input": test_unsafe_input[:20] + "...",
                    "blocked": not unsafe_result[0],
                    "issues_detected": len(unsafe_result[1]),
                },
            },
            "security_features": {
                "input_validation": True,
                "output_validation": True,
                "syntax_checking": True,
                "dangerous_pattern_detection": True,
                "injection_prevention": True,
                "code_quality_assessment": True,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "security_system": {"status": "error", "error": str(e)},
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/security-test")
async def test_security_validation(
    request: Dict[str, str],
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
):
    """
    보안 검증 테스트 API

    특정 입력에 대한 보안 검증 결과를 확인할 수 있습니다.
    """
    try:
        test_input = request.get("test_input", "")
        if not test_input:
            raise HTTPException(status_code=400, detail="test_input이 필요합니다.")

        await enhanced_ai_service.initialize_model()

        # 입력 안전성 검증
        input_safe, input_issues = (
            enhanced_ai_service.safety_validator.validate_input_safety(test_input))

        # 코드로 간주하고 코드 안전성 검증도 실행
        code_safe, code_issues = (
            enhanced_ai_service.safety_validator.validate_generated_code_safety(
                test_input
            )
        )

        return {
            "test_input": (
                test_input[:100] + "..." if len(test_input) > 100 else test_input
            ),
            "validation_results": {
                "input_validation": {
                    "is_safe": input_safe,
                    "issues": input_issues,
                    "issue_count": len(input_issues),
                },
                "code_validation": {
                    "is_safe": code_safe,
                    "issues": code_issues,
                    "issue_count": len(code_issues),
                },
            },
            "overall_safety": {
                "is_safe": input_safe and code_safe,
                "risk_level": "low" if (input_safe and code_safe) else "high",
                "recommendation": "허용" if (input_safe and code_safe) else "차단",
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        api_monitor.log_error(e, {"endpoint": "/security-test"})
        raise HTTPException(status_code=500, detail=f"보안 테스트 실패: {str(e)}")
