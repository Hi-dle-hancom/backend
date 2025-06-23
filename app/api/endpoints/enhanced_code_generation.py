from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
import time
import json
from datetime import datetime
from typing import Dict, Any

from app.schemas.code_generation import (
    CodeGenerationRequest, 
    CodeGenerationResponse,
    CompletionRequest,
    CompletionResponse,
    StreamingGenerateRequest,
    StreamingChunk
)
from app.services.enhanced_ai_model import enhanced_ai_model
from app.core.logging_config import api_monitor, performance_monitor
from app.core.security import (
    get_current_api_key, 
    check_permission, 
    check_rate_limit_dependency,
    APIKeyModel
)
from app.services.performance_profiler import response_timer

router = APIRouter()

@router.post("/enhanced-generate", response_model=Dict[str, Any])
async def enhanced_generate_code(
    request: CodeGenerationRequest,
    http_request: Request,
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/enhanced-generate", 30))
):
    """
    안전성 검증을 포함한 강화된 Python 코드 생성 API
    
    특징:
    - 입력 안전성 검증 (악성 코드, 인젝션 공격 방지)
    - 생성된 코드 안전성 검증 (위험한 함수 호출 차단)
    - 코드 품질 평가 (0.0 - 1.0 점수)
    - Python 문법 검증
    - 상세한 보안 로깅
    
    보안: API Key 인증 필수, 시간당 30회 제한 (더 엄격한 제한)
    """
    start_time = time.time()
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # 보안 로깅
    api_monitor.log_request_start("POST", "/enhanced-generate", client_ip)
    
    try:
        # AI 모델 초기화 확인
        await enhanced_ai_model.initialize_model()
        
        with response_timer.log_response_time("/enhanced-generate", "POST"):
            api_monitor.logger.info(
                "강화된 Python 코드 생성 요청 수신",
                user_id=api_key.user_id,
                question_length=len(request.user_question),
                has_context=bool(request.code_context),
                client_ip=client_ip,
                security_level="enhanced"
            )
            
            # 요청 데이터 추출
            user_question = request.user_question.strip()
            if not user_question:
                raise HTTPException(status_code=400, detail="사용자 질문이 비어있습니다.")
            
            code_context = request.code_context.strip() if request.code_context else None
            
            # 사용자 선호도 (향후 확장)
            user_preferences = {
                "skill_level": "intermediate",
                "code_style": "balanced",
                "project_type": "general"
            }
            
            # 안전성 검증을 포함한 코드 생성
            ai_start_time = time.time()
            result = await enhanced_ai_model.generate_code_with_safety(
                prompt=user_question,
                context=code_context,
                user_preferences=user_preferences
            )
            ai_duration = time.time() - ai_start_time
            
            # 결과 검증 및 로깅
            if result["status"] == "error":
                # 보안 관련 오류 특별 처리
                if result.get("error_type") == "input_safety":
                    api_monitor.logger.warning(
                        "입력 안전성 검증 실패",
                        user_id=api_key.user_id,
                        safety_issues=result.get("safety_issues", []),
                        client_ip=client_ip
                    )
                    
                    return {
                        "status": "error",
                        "error_message": result["error_message"],
                        "error_type": "security_violation",
                        "safety_issues": result.get("safety_issues", []),
                        "generated_code": "",
                        "explanation": "",
                        "security_info": {
                            "input_validated": False,
                            "code_validated": False,
                            "threat_detected": True
                        }
                    }
                
                # 일반 생성 오류
                return {
                    "status": "error",
                    "error_message": result["error_message"],
                    "error_type": result.get("error_type", "generation_error"),
                    "generated_code": "",
                    "explanation": "",
                    "security_info": {
                        "input_validated": True,
                        "code_validated": False,
                        "threat_detected": False
                    }
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
                    "model_endpoint": result["metadata"]["model_endpoint"]
                }
            )
            
            api_monitor.logger.info(
                "강화된 Python 코드 생성 성공",
                user_id=api_key.user_id,
                ai_duration=ai_duration,
                code_length=len(generated_code),
                quality_score=quality_score,
                safety_validated=result["safety_validated"]
            )
            
            return {
                "status": "success",
                "generated_code": generated_code,
                "explanation": explanation,
                "quality_score": quality_score,
                "security_info": {
                    "input_validated": True,
                    "code_validated": result["safety_validated"],
                    "threat_detected": False,
                    "safety_score": 1.0 if result["safety_validated"] else 0.5
                },
                "metadata": {
                    "generation_time": ai_duration,
                    "model_info": result["metadata"],
                    "timestamp": datetime.now().isoformat()
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(e, {
            "user_id": api_key.user_id, 
            "endpoint": "/enhanced-generate",
            "security_context": "enhanced_model"
        })
        return {
            "status": "error",
            "error_message": f"서버 내부 오류: {str(e)}",
            "error_type": "internal_error",
            "generated_code": "",
            "explanation": "",
            "security_info": {
                "input_validated": False,
                "code_validated": False,
                "threat_detected": False
            }
        }
    finally:
        total_duration = time.time() - start_time
        api_monitor.log_request_end("POST", "/enhanced-generate", 200, total_duration, client_ip)

@router.post("/enhanced-stream-generate")
async def enhanced_stream_generate_code(
    request: StreamingGenerateRequest,
    http_request: Request,
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/enhanced-stream-generate", 20))
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
    api_monitor.log_request_start("POST", "/enhanced-stream-generate", client_ip)
    
    try:
        # AI 모델 초기화 확인
        await enhanced_ai_model.initialize_model()
        
        api_monitor.logger.info(
            "강화된 스트리밍 코드 생성 요청 수신",
            user_id=api_key.user_id,
            question_length=len(request.user_question),
            client_ip=client_ip,
            streaming=True
        )
        
        user_question = request.user_question.strip()
        if not user_question:
            raise HTTPException(status_code=400, detail="사용자 질문이 비어있습니다.")
        
        code_context = request.code_context.strip() if request.code_context else None
        
        # 사용자 선호도
        user_preferences = {
            "skill_level": request.skill_level if hasattr(request, 'skill_level') else "intermediate",
            "code_style": "balanced",
            "project_type": "general"
        }
        
        async def generate_safe_sse_stream():
            """안전성 검증을 포함한 SSE 스트림 생성"""
            try:
                # 스트리밍 시작 메타데이터
                metadata = {
                    "session_start": datetime.now().isoformat(),
                    "user_id": api_key.user_id,
                    "security_level": "enhanced",
                    "streaming": True
                }
                
                yield f"data: {json.dumps({'type': 'metadata', 'content': metadata})}\n\n"
                
                # 안전성 검증을 포함한 스트리밍 생성
                async for chunk in enhanced_ai_model.generate_streaming_response(
                    prompt=user_question,
                    context=code_context,
                    user_preferences=user_preferences
                ):
                    # 스트리밍 chunk를 SSE 형식으로 변환
                    chunk_data = {
                        "type": chunk.type,
                        "content": chunk.content,
                        "sequence": chunk.sequence,
                        "timestamp": chunk.timestamp.isoformat()
                    }
                    
                    # 메타데이터가 있는 경우 추가
                    if hasattr(chunk, 'metadata') and chunk.metadata:
                        chunk_data["metadata"] = chunk.metadata
                    
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    # 오류 감지 시 스트림 중단
                    if chunk.type == "error":
                        api_monitor.logger.warning(
                            "스트리밍 중 안전성 오류 감지",
                            user_id=api_key.user_id,
                            error_content=chunk.content
                        )
                        break
                
                # 스트림 종료 신호
                yield f"data: {json.dumps({'type': 'stream_end', 'content': 'success'})}\n\n"
                
            except Exception as e:
                api_monitor.log_error(e, {
                    "user_id": api_key.user_id,
                    "endpoint": "/enhanced-stream-generate",
                    "streaming": True
                })
                
                # 오류 정보를 스트림으로 전송
                error_data = {
                    "type": "stream_error",
                    "content": f"스트리밍 오류: {str(e)}",
                    "timestamp": datetime.now().isoformat()
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
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(e, {
            "user_id": api_key.user_id,
            "endpoint": "/enhanced-stream-generate"
        })
        raise HTTPException(status_code=500, detail=f"스트리밍 서비스 오류: {str(e)}")

@router.get("/security-status")
async def get_security_status(
    api_key: APIKeyModel = Depends(check_permission("code_generation"))
):
    """
    보안 시스템 상태 조회 API
    
    Enhanced AI 모델의 보안 기능 상태를 확인합니다.
    """
    try:
        await enhanced_ai_model.initialize_model()
        
        # 보안 검증 테스트
        test_safe_input = "피보나치 함수를 만들어주세요"
        test_unsafe_input = "os.system('rm -rf /')"
        
        safe_result = enhanced_ai_model.safety_validator.validate_input_safety(test_safe_input)
        unsafe_result = enhanced_ai_model.safety_validator.validate_input_safety(test_unsafe_input)
        
        return {
            "security_system": {
                "status": "active",
                "validator_loaded": True,
                "model_loaded": enhanced_ai_model.model_loaded,
                "model_endpoint": enhanced_ai_model.model_endpoint
            },
            "security_tests": {
                "safe_input_test": {
                    "input": test_safe_input,
                    "passed": safe_result[0],
                    "issues": safe_result[1]
                },
                "unsafe_input_test": {
                    "input": test_unsafe_input[:20] + "...",
                    "blocked": not unsafe_result[0],
                    "issues_detected": len(unsafe_result[1])
                }
            },
            "security_features": {
                "input_validation": True,
                "output_validation": True,
                "syntax_checking": True,
                "dangerous_pattern_detection": True,
                "injection_prevention": True,
                "code_quality_assessment": True
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "security_system": {
                "status": "error",
                "error": str(e)
            },
            "timestamp": datetime.now().isoformat()
        }

@router.post("/security-test")
async def test_security_validation(
    request: Dict[str, str],
    api_key: APIKeyModel = Depends(check_permission("code_generation"))
):
    """
    보안 검증 테스트 API
    
    특정 입력에 대한 보안 검증 결과를 확인할 수 있습니다.
    """
    try:
        test_input = request.get("test_input", "")
        if not test_input:
            raise HTTPException(status_code=400, detail="test_input이 필요합니다.")
        
        await enhanced_ai_model.initialize_model()
        
        # 입력 안전성 검증
        input_safe, input_issues = enhanced_ai_model.safety_validator.validate_input_safety(test_input)
        
        # 코드로 간주하고 코드 안전성 검증도 실행
        code_safe, code_issues = enhanced_ai_model.safety_validator.validate_generated_code_safety(test_input)
        
        return {
            "test_input": test_input[:100] + "..." if len(test_input) > 100 else test_input,
            "validation_results": {
                "input_validation": {
                    "is_safe": input_safe,
                    "issues": input_issues,
                    "issue_count": len(input_issues)
                },
                "code_validation": {
                    "is_safe": code_safe,
                    "issues": code_issues,
                    "issue_count": len(code_issues)
                }
            },
            "overall_safety": {
                "is_safe": input_safe and code_safe,
                "risk_level": "low" if (input_safe and code_safe) else "high",
                "recommendation": "허용" if (input_safe and code_safe) else "차단"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        api_monitor.log_error(e, {"endpoint": "/security-test"})
        raise HTTPException(status_code=500, detail=f"보안 테스트 실패: {str(e)}") 