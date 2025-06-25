from fastapi import APIRouter, HTTPException, Depends, Request, Header
import time
from app.schemas.code_generation import (
    CodeGenerationRequest, 
    CodeGenerationResponse,
    CompletionRequest,
    CompletionResponse,
    StreamingGenerateRequest,
    StreamingChunk
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
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
import json
from datetime import datetime
from typing import Optional, Dict, Any

router = APIRouter()

@router.post("/generate", response_model=CodeGenerationResponse)
async def generate_code(
    request: CodeGenerationRequest,
    http_request: Request,
    authorization: str = Header(None),
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/generate", 50))
):
    """
    개인화된 사용자의 질문과 컨텍스트를 기반으로 Python 코드를 생성합니다.
    AI 모델의 원시 응답을 정교하게 파싱하여 코드와 설명을 분리합니다.
    
    **개인화 지원**: JWT 토큰 또는 API Key 기반 사용자 설정 적용
    **보안**: API Key 인증 필수, 시간당 50회 제한
    **모니터링**: 응답 시간, AI 추론 성능, 캐시 적중률 추적
    """
    start_time = time.time()
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # 요청 시작 로깅
    api_monitor.log_request_start("POST", "/generate", client_ip)
    
    try:
        with response_timer.log_response_time("/generate", "POST"):
            # JWT 토큰 추출 (있는 경우)
            access_token = None
            if authorization and authorization.startswith("Bearer "):
                access_token = authorization.split(" ")[1]
            
            api_monitor.logger.info(
                f"개인화된 Python 코드 생성 요청 수신",
                user_id=api_key.user_id,
                question_length=len(request.user_question),
                has_context=bool(request.code_context),
                has_user_profile=bool(request.userProfile),
                has_jwt_token=bool(access_token),
                client_ip=client_ip
            )
            
            # 요청 데이터 추출 및 검증
            user_question = request.user_question.strip()
            if not user_question:
                raise HTTPException(status_code=400, detail="사용자 질문이 비어있습니다.")
            
            code_context = request.code_context.strip() if request.code_context else None
            language = "python"  # Python으로 고정
            
            # AI 모델을 통한 개인화된 Python 코드 생성 및 파싱
            ai_start_time = time.time()
            try:
                parsed_result = await ai_model_service.predict_and_parse(
                    prompt=user_question,
                    context=code_context,
                    language=language,
                    access_token=access_token,  # JWT 토큰 전달
                    user_profile=request.userProfile  # 사용자 프로필 전달
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
                
                # 설명이 없는 경우 사용자 프로필 기반 기본 설명 생성
                if not explanation:
                    explanation = _generate_personalized_explanation(
                        user_question, 
                        generated_code, 
                        request.userProfile
                    )
                
                # AI 추론 메트릭 로깅
                api_monitor.log_ai_inference(
                    duration=ai_duration,
                    prompt_length=len(user_question + (code_context or "")),
                    response_length=len(generated_code),
                    cached=ai_duration < 0.1,  # 매우 빠른 응답은 캐시로 간주
                    additional_metrics={
                        "personalized": bool(access_token or request.userProfile),
                        "user_skill_level": request.userProfile.pythonSkillLevel if request.userProfile else None
                    }
                )
                
                api_monitor.logger.info(
                    "개인화된 Python 코드 생성 및 파싱 성공",
                    user_id=api_key.user_id,
                    ai_duration=ai_duration,
                    code_length=len(generated_code),
                    explanation_length=len(explanation) if explanation else 0,
                    personalized=bool(access_token or request.userProfile)
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

@router.post("/stream-generate")
async def stream_generate_code(
    request: StreamingGenerateRequest,
    http_request: Request,
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/stream-generate", 30))
):
    """
    실시간 스트리밍 방식으로 코드 생성
    Server-Sent Events(SSE) 형태로 응답
    """
    try:
        logger.info(f"스트리밍 코드 생성 요청 - 사용자: {api_key.user_id}")
        
        async def generate_sse_stream():
            """SSE 형태의 스트리밍 응답 생성"""
            try:
                # AI 모델을 통한 스트리밍 응답 생성
                async for chunk in ai_model_manager.generate_streaming_response(
                    prompt=request.user_question,
                    context=request.code_context
                ):
                    # SSE 형태로 데이터 포맷팅
                    chunk_data = {
                        "type": chunk.type,
                        "content": chunk.content,
                        "sequence": chunk.sequence,
                        "timestamp": chunk.timestamp.isoformat()
                    }
                    
                    # SSE 형식: data: {json}\n\n
                    sse_data = f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                    yield sse_data.encode('utf-8')
                    
                    # 완료 시 연결 종료
                    if chunk.type == "done":
                        break
                        
            except Exception as e:
                logger.error(f"스트리밍 중 오류 발생: {str(e)}")
                error_chunk = {
                    "type": "error",
                    "content": f"스트리밍 중 오류가 발생했습니다: {str(e)}",
                    "sequence": -1,
                    "timestamp": datetime.now().isoformat()
                }
                yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n".encode('utf-8')
        
        # SSE 응답 헤더 설정
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
        
        return FastAPIStreamingResponse(
            generate_sse_stream(),
            media_type="text/event-stream",
            headers=headers
        )
        
    except Exception as e:
        logger.error(f"스트리밍 엔드포인트 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"스트리밍 서비스 오류: {str(e)}"
        )

def _generate_personalized_explanation(
    user_question: str, 
    generated_code: str, 
    user_profile=None
) -> str:
    """사용자 프로필 기반 개인화된 설명 생성"""
    if not user_profile:
        return _generate_python_explanation(user_question, generated_code)
    
    skill_level = getattr(user_profile, 'pythonSkillLevel', 'intermediate')
    explanation_style = getattr(user_profile, 'explanationStyle', 'standard')
    project_context = getattr(user_profile, 'projectContext', 'general_purpose')
    
    # 스킬 수준별 설명 조절
    if skill_level == "beginner":
        if explanation_style == "educational":
            return f"""
🔰 **초급자를 위한 상세 설명**

**질문**: {user_question}

**📝 코드 단계별 해설**:
이 Python 코드는 다음과 같이 동작합니다:

1. **함수 정의**: `def`를 사용해 재사용 가능한 함수를 만듭니다
2. **매개변수**: 함수에 필요한 입력값을 받습니다  
3. **로직 처리**: 요청하신 기능을 단계별로 수행합니다
4. **반환값**: `return`으로 결과를 돌려줍니다

**💡 활용 팁**:
- 이 코드를 복사해서 Python 파일에 붙여넣으세요
- 함수를 호출할 때 적절한 값을 전달하세요
- 궁금한 부분이 있으면 `print()`로 중간 결과를 확인해보세요

**🚀 다음 단계**: 
이 기본 패턴을 이해하신 후 더 복잡한 기능에 도전해보세요!
"""
        else:
            return f"""
이 코드는 "{user_question}"에 대한 Python 구현입니다.

📖 **코드 설명**:
• 기본적인 Python 문법을 사용했습니다
• 각 단계가 명확하도록 주석을 추가했습니다  
• 바로 실행해볼 수 있는 예시를 포함했습니다

💡 **사용법**: 코드를 복사한 후 Python 환경에서 실행해보세요.
"""
    
    elif skill_level == "advanced" or skill_level == "expert":
        if explanation_style == "brief":
            return f"""
**구현**: {user_question}

**주요 특징**:
• 최적화된 알고리즘 사용
• 에러 핸들링 포함
• 확장 가능한 구조 설계

**복잡도**: {_analyze_complexity(generated_code)}
"""
        else:
            return f"""
**고급 구현 분석**

**설계 원칙**:
• 성능 최적화 고려
• 메모리 효율성
• 확장성과 유지보수성

**기술적 세부사항**:
• 사용된 패턴: {_identify_patterns(generated_code)}
• 복잡도: {_analyze_complexity(generated_code)}
• 개선 가능점: {_suggest_improvements(generated_code)}

**{project_context} 프로젝트에서의 활용**:
이 구현은 {_get_context_usage(project_context)} 분야에서 효과적으로 사용할 수 있습니다.
"""
    
    else:  # intermediate
        return f"""
**구현 설명**: {user_question}

**핵심 로직**:
{_extract_key_logic(generated_code)}

**사용 방법**:
제공된 함수를 호출하여 원하는 작업을 수행할 수 있습니다.

**확장 아이디어**:
• 추가 매개변수로 기능 확장
• 에러 처리 강화
• 성능 최적화 적용
"""

def _analyze_complexity(code: str) -> str:
    """코드 복잡도 분석"""
    lines = code.count('\n')
    if lines < 10:
        return "단순 (O(1) ~ O(n))"
    elif lines < 30:
        return "중간 (O(n) ~ O(n log n))"
    else:
        return "복잡 (O(n²) 이상)"

def _identify_patterns(code: str) -> str:
    """사용된 디자인 패턴 식별"""
    patterns = []
    if "class" in code:
        patterns.append("객체지향")
    if "yield" in code:
        patterns.append("제너레이터")
    if "async" in code:
        patterns.append("비동기")
    if "@" in code:
        patterns.append("데코레이터")
    
    return ", ".join(patterns) if patterns else "함수형 프로그래밍"

def _suggest_improvements(code: str) -> str:
    """개선 제안"""
    suggestions = []
    if "try:" not in code:
        suggestions.append("예외 처리 추가")
    if "typing" not in code and "def " in code:
        suggestions.append("타입 힌트 적용") 
    if "docstring" not in code.lower() and '"""' not in code:
        suggestions.append("독스트링 추가")
    
    return ", ".join(suggestions) if suggestions else "현재 구현이 적절합니다"

def _get_context_usage(project_context: str) -> str:
    """프로젝트 컨텍스트별 활용 설명"""
    context_map = {
        "web_development": "웹 애플리케이션 개발",
        "data_science": "데이터 분석 및 머신러닝",
        "automation": "업무 자동화 스크립팅",
        "general_purpose": "범용 프로그래밍"
    }
    return context_map.get(project_context, "소프트웨어 개발")

def _extract_key_logic(code: str) -> str:
    """핵심 로직 추출"""
    lines = code.strip().split('\n')
    logic_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
    
    if len(logic_lines) <= 3:
        return "\n".join(f"• {line}" for line in logic_lines)
    else:
        return f"• {logic_lines[0]}\n• {logic_lines[1]}\n• ... (총 {len(logic_lines)}줄의 로직)"

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

async def _get_user_preferences(access_token: Optional[str], user_profile) -> Dict[str, Any]:
    """사용자 선호도 조회 (중앙화된 매핑 시스템 사용)"""
    from app.core.settings_mapper import map_db_to_preferences, map_profile_to_preferences, get_default_user_preferences
    
    try:
        # 1. 기본 설정으로 시작
        preferences = get_default_user_preferences()
        
        # 2. JWT 토큰으로 DB 설정 조회 (우선순위 높음)
        if access_token:
            try:
                from app.services.user_service import user_service
                db_settings = await user_service.get_user_settings(access_token)
                
                if db_settings:
                    # 중앙화된 매핑 시스템 사용
                    preferences = map_db_to_preferences(db_settings)
                    logger.info(f"DB 설정 로드 완료 - {len(db_settings)}개")
            
            except Exception as e:
                logger.warning(f"DB 설정 조회 실패, 기본값 사용 - {e}")
        
        # 3. userProfile로 일부 설정 오버라이드 (Frontend에서 전송된 경우)
        if user_profile:
            # 중앙화된 매핑 시스템 사용 (camelCase → snake_case + 검증)
            preferences = map_profile_to_preferences(user_profile, preferences)
            logger.info("userProfile 오버라이드 적용")
        
        return preferences
        
    except Exception as e:
        logger.error(f"사용자 선호도 조회 실패: {e}")
        # 안전한 기본값 반환
        return get_default_user_preferences() 