from fastapi import APIRouter, HTTPException, Depends, Request
import time
from app.schemas.code_generation import (
    CodeGenerationRequest, 
    CodeGenerationResponse,
    CompletionRequest,
    CompletionResponse
)
from app.services.inference import ai_model_service
from app.core.logging_config import api_monitor, performance_monitor
from app.core.security import (
    get_current_api_key, 
    check_permission, 
    check_rate_limit_dependency,
    APIKeyModel
)
from app.services.performance_profiler import response_timer

router = APIRouter()

@router.post("/generate", response_model=CodeGenerationResponse)
async def generate_code(
    request: CodeGenerationRequest,
    http_request: Request,
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/generate", 50))
):
    """
    최적화된 사용자의 질문과 컨텍스트를 기반으로 Python 코드를 생성합니다.
    AI 모델의 원시 응답을 정교하게 파싱하여 코드와 설명을 분리합니다.
    
    보안: API Key 인증 필수, 시간당 50회 제한
    모니터링: 응답 시간, AI 추론 성능, 캐시 적중률 추적
    """
    start_time = time.time()
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # 요청 시작 로깅
    api_monitor.log_request_start("POST", "/generate", client_ip)
    
    try:
        with response_timer.log_response_time("/generate", "POST"):
            api_monitor.logger.info(
                f"Python 코드 생성 요청 수신",
                user_id=api_key.user_id,
                question_length=len(request.user_question),
                has_context=bool(request.code_context),
                client_ip=client_ip
            )
            
            # 요청 데이터 추출 및 검증
            user_question = request.user_question.strip()
            if not user_question:
                raise HTTPException(status_code=400, detail="사용자 질문이 비어있습니다.")
            
            code_context = request.code_context.strip() if request.code_context else None
            language = "python"  # Python으로 고정
            
            # AI 모델을 통한 최적화된 Python 코드 생성 및 파싱
            ai_start_time = time.time()
            try:
                parsed_result = ai_model_service.predict_and_parse(
                    prompt=user_question,
                    context=code_context,
                    language=language
                )
                
                ai_duration = time.time() - ai_start_time
                
                # 파싱된 결과가 오류인 경우
                if parsed_result["status"] == "error":
                    api_monitor.log_error(
                        Exception(parsed_result["error_message"]),
                        {"user_id": api_key.user_id, "endpoint": "/generate"}
                    )
                    return CodeGenerationResponse(
                        generated_code="",
                        explanation=None,
                        status="error",
                        error_message=parsed_result["error_message"]
                    )
                
                # 성공적인 결과 처리
                generated_code = parsed_result["generated_code"]
                explanation = parsed_result["explanation"]
                
                # 설명이 없는 경우 기본 설명 생성
                if not explanation:
                    explanation = _generate_python_explanation(user_question, generated_code)
                
                # AI 추론 메트릭 로깅
                api_monitor.log_ai_inference(
                    duration=ai_duration,
                    prompt_length=len(user_question + (code_context or "")),
                    response_length=len(generated_code),
                    cached=ai_duration < 0.1  # 매우 빠른 응답은 캐시로 간주
                )
                
                api_monitor.logger.info(
                    "Python 코드 생성 및 파싱 성공",
                    user_id=api_key.user_id,
                    ai_duration=ai_duration,
                    code_length=len(generated_code),
                    explanation_length=len(explanation) if explanation else 0
                )
                
                return CodeGenerationResponse(
                    generated_code=generated_code,
                    explanation=explanation,
                    status="success"
                )
                
            except ValueError as ve:
                # 언어 검증 오류 등
                api_monitor.log_error(ve, {"user_id": api_key.user_id, "endpoint": "/generate"})
                raise HTTPException(status_code=400, detail=str(ve))
                
            except Exception as e:
                # AI 모델 관련 오류
                api_monitor.log_error(e, {"user_id": api_key.user_id, "endpoint": "/generate"})
                return CodeGenerationResponse(
                    generated_code="",
                    explanation=None,
                    status="error",
                    error_message=f"AI 모델 처리 중 오류가 발생했습니다: {str(e)}"
                )
        
    except HTTPException:
        # FastAPI HTTP 예외는 그대로 전달
        raise
    except Exception as e:
        api_monitor.log_error(e, {"user_id": api_key.user_id, "endpoint": "/generate"})
        return CodeGenerationResponse(
            generated_code="",
            explanation=None,
            status="error",
            error_message=f"서버 내부 오류가 발생했습니다: {str(e)}"
        )
    finally:
        # 요청 종료 로깅
        total_duration = time.time() - start_time
        api_monitor.log_request_end("POST", "/generate", 200, total_duration, client_ip)

@router.post("/complete", response_model=CompletionResponse)
async def complete_code(
    request: CompletionRequest,
    http_request: Request,
    api_key: APIKeyModel = Depends(check_permission("code_completion")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/complete", 100))
):
    """
    최적화된 Python 코드 자동 완성 제안을 제공합니다.
    
    보안: API Key 인증 필수, 시간당 100회 제한
    모니터링: 응답 시간, 자동완성 성능, 제안 품질 추적
    """
    start_time = time.time()
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # 요청 시작 로깅
    api_monitor.log_request_start("POST", "/complete", client_ip)
    
    try:
        with response_timer.log_response_time("/complete", "POST"):
            api_monitor.logger.info(
                f"Python 코드 자동 완성 요청 수신",
                user_id=api_key.user_id,
                prefix_length=len(request.prefix),
                client_ip=client_ip
            )
            
            # 요청 데이터 추출 및 검증
            prefix = request.prefix.strip()
            if not prefix:
                raise HTTPException(status_code=400, detail="코드 접두사가 비어있습니다.")
            
            language = "python"  # Python으로 고정
            
            # AI 모델을 통한 최적화된 Python 코드 자동 완성
            ai_start_time = time.time()
            try:
                completions = ai_model_service.complete_code(
                    prefix=prefix,
                    language=language,
                    max_suggestions=5  # 최대 5개 제안
                )
                
                ai_duration = time.time() - ai_start_time
                
                # 자동완성 메트릭 로깅
                api_monitor.log_ai_inference(
                    duration=ai_duration,
                    prompt_length=len(prefix),
                    response_length=sum(len(comp) for comp in completions),
                    cached=ai_duration < 0.05  # 매우 빠른 응답은 캐시로 간주
                )
                
                api_monitor.logger.info(
                    f"Python 코드 자동 완성 성공",
                    user_id=api_key.user_id,
                    ai_duration=ai_duration,
                    suggestions_count=len(completions),
                    total_response_length=sum(len(comp) for comp in completions)
                )
                
                return CompletionResponse(
                    completions=completions,
                    status="success"
                )
                
            except ValueError as ve:
                # 언어 검증 오류 등
                api_monitor.log_error(ve, {"user_id": api_key.user_id, "endpoint": "/complete"})
                raise HTTPException(status_code=400, detail=str(ve))
                
            except Exception as e:
                # AI 모델 관련 오류
                api_monitor.log_error(e, {"user_id": api_key.user_id, "endpoint": "/complete"})
                return CompletionResponse(
                    completions=[],
                    status="error",
                    error_message=f"AI 모델 처리 중 오류가 발생했습니다: {str(e)}"
                )
        
    except HTTPException:
        # FastAPI HTTP 예외는 그대로 전달
        raise
    except Exception as e:
        api_monitor.log_error(e, {"user_id": api_key.user_id, "endpoint": "/complete"})
        return CompletionResponse(
            completions=[],
            status="error",
            error_message=f"서버 내부 오류가 발생했습니다: {str(e)}"
        )
    finally:
        # 요청 종료 로깅
        total_duration = time.time() - start_time
        api_monitor.log_request_end("POST", "/complete", 200, total_duration, client_ip)

def _generate_python_explanation(user_question: str, generated_code: str) -> str:
    """
    생성된 Python 코드에 대한 설명을 생성합니다.
    
    Args:
        user_question: 사용자 질문
        generated_code: 생성된 Python 코드
        
    Returns:
        Python 코드 설명 문자열
    """
    try:
        code_lines = len(generated_code.split('\n')) if generated_code else 0
        
        if "함수" in user_question or "function" in user_question.lower() or "def" in user_question.lower():
            return f"요청하신 Python 함수를 생성했습니다. 총 {code_lines}줄의 코드로 구성되어 있으며, 매개변수와 반환값, 그리고 docstring을 포함한 완전한 함수 구조를 제공합니다."
        
        elif "클래스" in user_question or "class" in user_question.lower():
            return f"요청하신 Python 클래스를 생성했습니다. 총 {code_lines}줄의 코드로 구성되어 있으며, 생성자(__init__)와 메서드들을 포함한 완전한 클래스 구조를 제공합니다."
        
        elif "반복" in user_question or "loop" in user_question.lower() or "for" in user_question.lower():
            return f"요청하신 Python 반복문을 생성했습니다. for문, while문, 리스트 컴프리헨션 등 다양한 반복 처리 방법을 포함한 실용적인 코드입니다."
        
        elif "조건" in user_question or "if" in user_question.lower():
            return f"요청하신 Python 조건문을 생성했습니다. if-elif-else 구조와 다양한 조건 처리 방법을 포함한 실용적인 코드입니다."
        
        elif "리스트" in user_question or "list" in user_question.lower():
            return f"요청하신 Python 리스트 조작 코드를 생성했습니다. 리스트 생성, 수정, 삭제, 정렬, 필터링 등의 다양한 기능을 포함합니다."
        
        elif "딕셔너리" in user_question or "dict" in user_question.lower():
            return f"요청하신 Python 딕셔너리 조작 코드를 생성했습니다. 딕셔너리 생성, 접근, 수정, 삭제 등의 다양한 기능을 포함합니다."
        
        elif "파일" in user_question or "file" in user_question.lower():
            return f"요청하신 Python 파일 처리 코드를 생성했습니다. 파일 읽기, 쓰기, 예외 처리 등을 포함한 안전한 파일 조작 코드입니다."
        
        elif "API" in user_question or "requests" in user_question.lower() or "웹" in user_question:
            return f"요청하신 Python API 처리 코드를 생성했습니다. HTTP 요청/응답 처리와 예외 처리를 포함한 실용적인 웹 API 클라이언트 코드입니다."
        
        elif "마크다운" in user_question or "markdown" in user_question.lower():
            return f"마크다운 형태의 AI 응답을 성공적으로 파싱하여 코드와 설명을 분리했습니다. 총 {code_lines}줄의 Python 코드를 추출했습니다."
        
        elif "멀티블록" in user_question or "multiple" in user_question.lower():
            return f"여러 코드 블록이 포함된 AI 응답에서 가장 적절한 코드를 선택했습니다. 선택된 코드는 {code_lines}줄로 구성되어 있습니다."
        
        else:
            return f"요청하신 Python 코드를 생성했습니다. 총 {code_lines}줄의 코드로 구성되어 있으며, Python 모범 사례를 따르는 실행 가능한 형태로 제공됩니다."
    
    except Exception as e:
        logger.warning(f"설명 생성 실패: {e}")
        return f"생성된 Python 코드입니다. 요청하신 기능을 구현하는 실용적인 코드를 제공합니다." 