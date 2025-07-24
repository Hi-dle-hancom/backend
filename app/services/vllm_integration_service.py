"""
vLLM 멀티 LoRA 서버 통합 서비스 (적응형 시스템 업그레이드)
- 실시간 스트리밍 응답
- 적응형 청크 버퍼 시스템
- 지능적 Stop Token 감지
- 요청 복잡도별 동적 최적화
"""

import asyncio
import json
import re
import time
import ast
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import aiohttp

from app.core.config import settings

import logging

from app.schemas.code_generation import CodeGenerationRequest, CodeGenerationResponse, ModelType
from .adaptive_chunk_buffer import AdaptiveChunkBuffer, IntelligentStopTokenDetector, create_adaptive_system

logger = logging.getLogger(__name__)


# vLLM 서버 모델 타입 정의
class VLLMModelType:
    """vLLM 서버에서 지원하는 모델 타입"""
    AUTOCOMPLETE = "autocomplete"
    PROMPT = "prompt"
    COMMENT = "comment"
    ERROR_FIX = "error_fix"


# 🛡️ 코드 품질 검증 시스템 - 깨진 코드 방지
class CodeQualityValidator:
    """Python 코드 품질 검증 시스템"""
    
    def __init__(self):
        self.validation_enabled = True
        self.strict_mode = True  # 엄격한 검증 모드
        
    def validate_code_chunk(self, code: str) -> Dict[str, Any]:
        """코드 청크 품질 검증"""
        if not self.validation_enabled or not code.strip():
            return {"valid": True, "issues": [], "confidence": 1.0}
            
        issues = []
        confidence = 1.0
        
        # 🔍 1. 기본 구문 검증
        syntax_issues = self._check_basic_syntax(code)
        if syntax_issues:
            issues.extend(syntax_issues)
            confidence -= 0.3
            
        # 🔍 2. 괄호 균형 검증
        balance_issues = self._check_bracket_balance(code)
        if balance_issues:
            issues.extend(balance_issues)
            confidence -= 0.2
            
        # 🔍 3. 문자열 균형 검증
        quote_issues = self._check_quote_balance(code)
        if quote_issues:
            issues.extend(quote_issues)
            confidence -= 0.2
            
        # 🔍 4. AST 파싱 시도 (완전성 검증)
        ast_issues = self._check_ast_validity(code)
        if ast_issues:
            issues.extend(ast_issues)
            confidence -= 0.3
            
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "confidence": max(0.0, confidence),
            "code_length": len(code),
            "line_count": code.count('\n') + 1
        }
    
    def _check_basic_syntax(self, code: str) -> List[str]:
        """기본 구문 오류 검사"""
        issues = []
        
        # 의심스러운 패턴들
        suspicious_patterns = [
            (r'print\(["\'][^"\']*["\']["\']', "print() 함수의 잘못된 따옴표 패턴"),
            (r'["\'][^"\']*\([^)]*["\']', "함수 호출 내부의 잘못된 따옴표"),
            (r'\([^)]*\([^)]*["\'][^"\']*$', "미완성된 중첩 함수 호출"),
            (r'^[^=]*=[^=]*\([^)]*$', "미완성된 함수 할당"),
        ]
        
        for pattern, issue_desc in suspicious_patterns:
            if re.search(pattern, code):
                issues.append(issue_desc)
                
        return issues
    
    def _check_bracket_balance(self, code: str) -> List[str]:
        """괄호 균형 검사"""
        issues = []
        
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        for char in code:
            if char in brackets:
                stack.append(char)
            elif char in brackets.values():
                if not stack:
                    issues.append("닫는 괄호가 여는 괄호보다 많음")
                    break
                last_open = stack.pop()
                if brackets[last_open] != char:
                    issues.append(f"괄호 타입 불일치: {last_open} vs {char}")
                    
        if stack:
            issues.append(f"닫히지 않은 괄호: {len(stack)}개")
            
        return issues
    
    def _check_quote_balance(self, code: str) -> List[str]:
        """따옴표 균형 검사"""
        issues = []
        
        single_quotes = code.count("'")
        double_quotes = code.count('"')
        
        if single_quotes % 2 != 0:
            issues.append("홀수 개의 단일 따옴표")
        if double_quotes % 2 != 0:
            issues.append("홀수 개의 이중 따옴표")
            
        return issues
    
    def _check_ast_validity(self, code: str) -> List[str]:
        """AST 파싱을 통한 구문 완전성 검사"""
        issues = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"구문 오류: {e.msg}")
        except Exception as e:
            issues.append(f"파싱 오류: {str(e)}")
            
        return issues
    
    async def check_health(self) -> Dict[str, Any]:
        """호환성을 위한 check_health 메서드 (health_check의 확장 버전)"""
        try:
            is_healthy = await self.health_check()
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": time.time(),
                "details": {
                    "connected": self.is_connected,
                    "total_requests": self.total_requests,
                    "success_rate": self.successful_requests / max(self.total_requests, 1) * 100
                }
            }
        except Exception as e:
            logger.error(f"헬스 체크 오류: {e}")
            return {
                "status": "error",
                "timestamp": time.time(),
                "error": str(e)
            }
    
    def suggest_fix(self, code: str, issues: List[str]) -> str:
        """간단한 자동 수정 제안"""
        fixed_code = code
        
        # 간단한 수정들
        for issue in issues:
            if "닫히지 않은 괄호" in issue:
                # 괄호 균형 맞추기
                open_count = fixed_code.count('(')
                close_count = fixed_code.count(')')
                if open_count > close_count:
                    fixed_code += ')' * (open_count - close_count)
                    
            elif "홀수 개의 단일 따옴표" in issue:
                # 마지막에 따옴표 추가
                if fixed_code.count("'") % 2 != 0:
                    fixed_code += "'"
                    
            elif "홀수 개의 이중 따옴표" in issue:
                # 마지막에 따옴표 추가
                if fixed_code.count('"') % 2 != 0:
                    fixed_code += '"'
        
        return fixed_code


# 전역 검증기 인스턴스
code_validator = CodeQualityValidator()


# 🎯 응답 분리 시스템 - 설명과 코드 구분
class ResponseParser:
    """AI 응답을 설명과 코드로 분리하는 파서"""
    
    def __init__(self):
        self.code_patterns = [
            r'```python\s*(.*?)\s*```',  # Python 코드 블록
            r'```\s*(.*?)\s*```',        # 일반 코드 블록
            r'def\s+\w+.*?(?=\n\n|\Z)',  # 함수 정의
            r'class\s+\w+.*?(?=\n\n|\Z)', # 클래스 정의
            r'print\s*\([^)]*\)',        # print 문
            r'^\s*[a-zA-Z_]\w*\s*=.*',   # 변수 할당
        ]
        
        self.explanation_markers = [
            '이 코드는', '설명:', '다음과 같이', '작동 방식:',
            '주요 기능:', '사용법:', '예시:', '참고:',
            'This code', 'Explanation:', 'How it works:',
            'Usage:', 'Example:', 'Note:'
        ]
    
    def parse_response(self, raw_response: str) -> Dict[str, str]:
        """응답을 설명과 코드로 분리"""
        if not raw_response or not raw_response.strip():
            return {"explanation": "", "code": ""}
        
        # 1. 코드 블록 탐지 및 추출
        code_blocks = self._extract_code_blocks(raw_response)
        
        # 2. 설명 부분 추출
        explanation_text = self._extract_explanation(raw_response, code_blocks)
        
        # 3. 최종 정리
        final_code = self._merge_code_blocks(code_blocks)
        final_explanation = self._clean_explanation(explanation_text)
        
        return {
            "explanation": final_explanation,
            "code": final_code,
            "metadata": {
                "code_blocks_found": len(code_blocks),
                "has_explanation": bool(final_explanation),
                "parsing_confidence": self._calculate_confidence(final_explanation, final_code)
            }
        }
    
    def _extract_code_blocks(self, text: str) -> List[str]:
        """코드 블록들을 추출"""
        code_blocks = []
        
        # 1. 마크다운 코드 블록 추출
        for pattern in [r'```python\s*(.*?)\s*```', r'```\s*(.*?)\s*```']:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            code_blocks.extend([match.strip() for match in matches if match.strip()])
        
        # 2. 코드 블록이 없으면 인라인 코드 패턴 찾기
        if not code_blocks:
            for pattern in self.code_patterns[2:]:  # 함수, 클래스, print 등
                matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
                code_blocks.extend([match.strip() for match in matches if match.strip()])
        
        # 3. 중복 제거 및 정리
        unique_blocks = []
        for block in code_blocks:
            if block and block not in unique_blocks:
                # 최소 길이 확인 (너무 짧은 것 제외)
                if len(block) >= 3:
                    unique_blocks.append(block)
        
        return unique_blocks
    
    def _extract_explanation(self, text: str, code_blocks: List[str]) -> str:
        """설명 부분을 추출"""
        # 코드 블록 제거
        explanation_text = text
        
        # 마크다운 코드 블록 제거
        for pattern in [r'```python.*?```', r'```.*?```']:
            explanation_text = re.sub(pattern, '', explanation_text, flags=re.DOTALL | re.IGNORECASE)
        
        # 인라인 코드 제거
        for block in code_blocks:
            explanation_text = explanation_text.replace(block, '')
        
        # 설명 마커 기반 추출
        lines = explanation_text.split('\n')
        explanation_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 명확한 설명 패턴 확인
            is_explanation = any(marker in line for marker in self.explanation_markers)
            
            # 코드가 아닌 일반 텍스트인지 확인
            is_not_code = not any(pattern in line for pattern in ['def ', 'class ', 'import ', 'print(', '='])
            
            if is_explanation or (is_not_code and len(line) > 10):
                explanation_lines.append(line)
        
        return '\n'.join(explanation_lines)
    
    def _merge_code_blocks(self, code_blocks: List[str]) -> str:
        """코드 블록들을 병합"""
        if not code_blocks:
            return ""
        
        # 중복 제거
        unique_blocks = []
        for block in code_blocks:
            if block not in unique_blocks:
                unique_blocks.append(block)
        
        # 블록이 하나면 그대로 반환
        if len(unique_blocks) == 1:
            return unique_blocks[0]
        
        # 여러 블록이 있으면 적절히 병합
        return '\n\n'.join(unique_blocks)
    
    def _clean_explanation(self, explanation: str) -> str:
        """설명 텍스트 정리"""
        if not explanation:
            return ""
        
        # 불필요한 마커 제거
        explanation = re.sub(r'^[#*\-=]+\s*', '', explanation, flags=re.MULTILINE)
        
        # 연속된 공백 정리
        explanation = re.sub(r'\n\s*\n\s*\n', '\n\n', explanation)
        
        # 앞뒤 공백 제거
        explanation = explanation.strip()
        
        return explanation
    
    def _calculate_confidence(self, explanation: str, code: str) -> float:
        """파싱 신뢰도 계산"""
        confidence = 0.5  # 기본값
        
        # 코드가 있으면 +0.3
        if code and len(code) > 10:
            confidence += 0.3
        
        # 설명이 있으면 +0.2
        if explanation and len(explanation) > 20:
            confidence += 0.2
        
        # 명확한 구분이 있으면 추가 점수
        if explanation and code:
            if any(marker in explanation for marker in self.explanation_markers):
                confidence += 0.1
        
        return min(1.0, confidence)


# 전역 파서 인스턴스
response_parser = ResponseParser()


class VLLMIntegrationService:
    """적응형 vLLM 통합 서비스"""

    def __init__(self):
        """서비스 초기화"""
        self.base_url = settings.VLLM_SERVER_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_connected = False
        self.connection_retries = 0
        self.max_retries = 3
        
        # 적응형 시스템 초기화
        self.adaptive_buffer, self.stop_detector = create_adaptive_system()
        
        # 성능 메트릭
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.avg_response_time = 0.0
        
        # 모델 타입 매핑 (완전한 매핑)
        self.model_mapping = {
            ModelType.CODE_GENERATION: VLLMModelType.PROMPT,
            ModelType.CODE_COMPLETION: VLLMModelType.AUTOCOMPLETE,
            ModelType.CODE_EXPLANATION: VLLMModelType.COMMENT,
            ModelType.CODE_REVIEW: VLLMModelType.COMMENT,
            ModelType.BUG_FIX: VLLMModelType.ERROR_FIX,
            ModelType.CODE_OPTIMIZATION: VLLMModelType.PROMPT,
            ModelType.UNIT_TEST_GENERATION: VLLMModelType.PROMPT,
            ModelType.DOCUMENTATION: VLLMModelType.COMMENT,
        }
        
        logger.info("vLLM 통합 서비스 초기화 (적응형 모드)")

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.disconnect()

    async def connect(self):
        """vLLM 서버 연결"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(
                ssl=False,  # SSL 완전 비활성화
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
        
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": "HAPA-Backend/1.0",
                    "Accept": "text/event-stream, application/json",
                    "Cache-Control": "no-cache"
                },
                # Transfer-Encoding 오류 방지를 위한 설정
                auto_decompress=True,
                read_bufsize=8192  # 버퍼 크기 설정
            )
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    self.is_connected = True
                    self.connection_retries = 0
                    logger.info("vLLM 서버 연결 성공")
                else:
                    raise aiohttp.ClientError(f"Health check failed: {response.status}")
        except Exception as e:
            self.is_connected = False
            self.connection_retries += 1
            logger.error(f"vLLM 서버 연결 실패 (시도 {self.connection_retries}/{self.max_retries}): {e}")
            
            if self.connection_retries < self.max_retries:
                await asyncio.sleep(2 ** self.connection_retries)  # 지수 백오프
                await self.connect()
            else:
                raise ConnectionError("vLLM 서버 연결 최대 재시도 횟수 초과")

    async def disconnect(self):
        """연결 종료"""
        if self.session:
            await self.session.close()
            self.session = None
        self.is_connected = False
        logger.info("vLLM 서버 연결 종료")

    def _build_enhanced_prompt(self, request: CodeGenerationRequest, user_preferences: Optional[Dict[str, Any]] = None) -> str:
        """향상된 프롬프트 구성 (개인화 정보 반영)"""
        
        # 기본 시스템 프롬프트
        system_prompt = """당신은 고품질 Python 코드를 생성하는 AI 코딩 어시스턴트입니다.
다음 규칙을 따라 코드를 생성해주세요:
1. 완전하고 실행 가능한 코드를 작성
2. 적절한 주석과 문서화 포함
3. 파이썬 최선의 관례(best practices) 준수
4. 간결하고 읽기 쉬운 코드 작성"""

        # 컨텍스트가 있는 경우 추가
        context_section = ""
        if request.context and request.context.strip():
            context_section = f"\n\n기존 코드 컨텍스트:\n```python\n{request.context}\n```"

        # 기본 프롬프트 조합
        base_prompt = f"""{system_prompt}

사용자 요청: {request.prompt}{context_section}

Python 코드:
```python"""

        # 사용자 개인화 정보가 있는 경우 적용
        if user_preferences:
            try:
                # 런타임에만 import
                from app.api.endpoints.code_generation import build_personalized_prompt
                personalized_prompt = build_personalized_prompt(base_prompt, user_preferences)
                logger.info(f"개인화된 프롬프트 적용됨: skill_level={user_preferences.get('skill_level', 'unknown')}")
                return personalized_prompt
            except ImportError as e:
                logger.warning(f"개인화 모듈 import 실패, 기본 프롬프트 사용: {e}")
                return base_prompt
        else:
            return base_prompt

    def _map_hapa_to_vllm_model(self, model_type: ModelType):
        """하파 모델 타입을 vLLM 모델 타입으로 매핑"""
        mapped = self.model_mapping.get(model_type, VLLMModelType.PROMPT)
        logger.debug(f"모델 타입 매핑: {model_type.value} -> {mapped}")
        return mapped

    def _prepare_vllm_payload(self, request: CodeGenerationRequest, complexity, user_id: str, user_preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """vLLM 요청 페이로드 준비 (개인화 정보 반영)"""
        
        # 사용자 선호도에 따른 파라미터 조정
        base_temperature = 0.3
        base_max_tokens = 400
        base_top_p = 0.8
        
        if user_preferences:
            skill_level = user_preferences.get("skill_level", "intermediate")
            code_style = user_preferences.get("code_style", "standard")
            safety_level = user_preferences.get("safety_level", "standard")
            
            # 스킬 레벨에 따른 토큰 수 조정
            if skill_level == "beginner":
                base_max_tokens = int(base_max_tokens * 1.5)  # 더 상세한 설명
            elif skill_level == "expert":
                base_max_tokens = int(base_max_tokens * 0.8)  # 간결한 코드
            
            # 코드 스타일에 따른 temperature 조정
            if code_style == "concise":
                base_temperature = max(base_temperature * 0.8, 0.1)
            elif code_style == "detailed":
                base_temperature = min(base_temperature * 1.2, 0.4)
            
            # 안전성 레벨에 따른 top_p 조정
            if safety_level == "enhanced":
                base_top_p = max(base_top_p * 0.9, 0.7)
            elif safety_level == "minimal":
                base_top_p = min(base_top_p * 1.1, 0.95)
        
        # 복잡도별 추가 파라미터 조정
        if complexity.value == 'simple':
            temperature = base_temperature
            max_tokens = base_max_tokens
            top_p = base_top_p
        elif complexity.value == 'medium':
            temperature = min(base_temperature * 1.3, 0.5)
            max_tokens = int(base_max_tokens * 1.5)
            top_p = min(base_top_p * 1.1, 0.9)
        else:  # complex
            temperature = min(base_temperature * 1.6, 0.7)
            max_tokens = int(base_max_tokens * 2.0)
            top_p = min(base_top_p * 1.2, 0.95)
        
        # 개인화된 프롬프트 구성
        enhanced_prompt = self._build_enhanced_prompt(request, user_preferences)
        
        # vLLM 서버 스키마에 맞게 수정
        mapped_model = self._map_hapa_to_vllm_model(request.model_type)
        payload = {
            "user_id": hash(str(user_id or "anonymous")) % 1000000,
            "prompt": enhanced_prompt,
            "model_type": mapped_model,
            "user_select_options": user_preferences or {},
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p
        }
        
        if user_preferences:
            logger.info(f"개인화된 vLLM 페이로드 준비 완료: skill={user_preferences.get('skill_level')}, style={user_preferences.get('code_style')}, complexity={complexity.value}")
        else:
            logger.debug(f"기본 vLLM 페이로드 준비 완료 (복잡도: {complexity.value})")
        
        return payload

    async def generate_code_streaming(
        self,
        request: CodeGenerationRequest,
        user_id: str,
        user_preferences: Optional[Dict[str, Any]] = None,
        chunk_callback: Optional[callable] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """간소화된 스트리밍 코드 생성"""
        
        logger.info(f"스트리밍 요청 시작: {request.prompt[:50]}...")
        
        start_time = time.time()
        
        try:
            # vLLM 서버 스키마에 맞춘 요청 준비
            mapped_model = self.model_mapping.get(request.model_type, request.model_type)
            payload = {
                "user_id": hash(user_id) % 1000000,  # user_id를 정수로 변환
                "prompt": request.prompt,
                "model_type": str(mapped_model),  # VLLMModelType은 이미 문자열 상수
                "user_select_options": user_preferences or {},  # 필수 필드
                "max_tokens": request.max_tokens or 512,
                "temperature": request.temperature or 0.7,
                "top_p": request.top_p or 0.9
            }
            
            logger.info(f"vLLM 서버 요청 페이로드: {json.dumps(payload, ensure_ascii=False)[:200]}...")
            
            if not self.is_connected:
                logger.info("vLLM 서버 연결 시도...")
                await self.connect()
            else:
                logger.info("vLLM 서버 이미 연결됨")

            # Transfer-Encoding 오류 방지를 위한 강화된 설정
            timeout = aiohttp.ClientTimeout(
                total=300,      # 전체 타임아웃
                connect=30,     # 연결 타임아웃
                sock_read=60    # 소켓 읽기 타임아웃
            )
            
            async with self.session.post(
                f"{self.base_url}/generate/stream",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                },
                timeout=timeout,
                chunked=True  # aiohttp가 자동으로 Transfer-Encoding 헤더 설정
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"vLLM API 오류: {response.status} - {error_text}")
                    yield {
                        "type": "error",
                        "content": f"API 오류: {response.status}",
                        "is_complete": True
                    }
                    return

                logger.info(f"vLLM 서버 응답 시작, 상태: {response.status}")
                logger.info(f"Content-Length: {response.headers.get('Content-Length', 'N/A')}, Transfer-Encoding: {response.headers.get('Transfer-Encoding', 'N/A')}")
                
                # 안전한 청크 읽기를 위한 개선된 방식
                try:
                    async for chunk in response.content.iter_chunked(8192):  # 8KB 청크로 읽기
                        if not chunk:
                            logger.debug("빈 청크 수신")
                            continue
                            
                        try:
                            chunk_text = chunk.decode('utf-8')
                            lines = chunk_text.split('\n')
                            
                            for line in lines:
                                line_text = line.strip()
                                if line_text and line_text != 'data: ':
                                    logger.debug(f"수신된 라인: '{line_text[:100]}...'")
                                    result = await self._process_stream_line(line_text)
                                    if result:
                                        yield result
                                        if result.get('type') == 'done':
                                            return
                                    
                        except UnicodeDecodeError as e:
                            logger.warning(f"Unicode 디코딩 오류: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"청크 처리 오류: {e}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Transfer-Encoding 오류 발생: {e}")
                    yield {
                        "type": "error",
                        "content": f"Transfer-Encoding 오류: {str(e)}",
                        "is_complete": True
                    }
                    return

                # 완료 신호 전송
                logger.info("스트리밍 완료")
                yield {
                    "type": "done",
                    "content": "",
                    "is_complete": True
                }
                
        except Exception as e:
            logger.error(f"스트리밍 오류: {e}")
            yield {
                "type": "error",
                "content": f"오류: {str(e)}",
                "is_complete": True
            }

    async def _process_stream_line(self, line_text: str):
        """스트림 라인을 처리하는 내부 메서드"""
        if not line_text:
            logger.debug("빈 라인 건너뛰기")
            return None
            
        if not line_text.startswith('data: '):
            logger.debug(f"data: 로 시작하지 않는 라인 건너뛰기: '{line_text[:50]}...'")
            return None

        # 완료 신호 처리
        if line_text == 'data: [DONE]':
            logger.info("스트림 완료: [DONE]")
            return {"type": "done", "content": "", "is_complete": True}
            
        # JSON 데이터 처리
        try:
            data_part = line_text[6:]  # 'data: ' 제거
            logger.debug(f"JSON 파싱 시도: '{data_part[:100]}...'")
            parsed_data = json.loads(data_part)
            logger.debug(f"파싱된 데이터: {parsed_data}")
            
            if parsed_data.get('type') == 'done':
                logger.info("스트림 완료: JSON done")
                return {"type": "done", "content": "", "is_complete": True}
            
            # 텍스트 데이터 전송
            if 'text' in parsed_data and parsed_data['text']:
                content = parsed_data['text']
                logger.info(f"토큰 전송: '{content[:50]}...'")
                return {
                    "type": "token",
                    "content": content,
                    "is_complete": False
                }
            else:
                logger.debug(f"text 필드 없거나 비어있음: {parsed_data}")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 파싱 오류: {e}")
            return None

    async def generate_code_sync(
        self,
        request: CodeGenerationRequest,
        user_id: str,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> CodeGenerationResponse:
        """동기식 코드 생성 (개인화 정보 반영)"""
        
        start_time = time.time()
        accumulated_content = ""
        
        try:
            # 스트리밍으로 데이터 수집
            async for chunk in self.generate_code_streaming(request, user_id, user_preferences):
                if chunk.get("type") == "token":
                    accumulated_content += chunk.get("content", "")
                elif chunk.get("type") == "done":
                        break
                elif chunk.get("type") == "error":
                    return CodeGenerationResponse(
                        success=False,
                        generated_code="",
                        error_message=chunk.get("content", "알 수 없는 오류"),
                        model_used="vllm",
                        processing_time=time.time() - start_time,
                        token_usage={"total_tokens": 0},
                    )
            
            # 응답 분리
            parsed_response = response_parser.parse_response(accumulated_content)
            
            # 성공 응답 구성
            response = CodeGenerationResponse(
                success=True,
                generated_code=parsed_response["code"],
                explanation=parsed_response["explanation"],
                model_used="vllm",
                processing_time=time.time() - start_time,
                token_usage={"total_tokens": len(accumulated_content.split())},
                confidence_score=parsed_response["metadata"]["parsing_confidence"]
            )
            
            # 개인화 메타데이터 추가
            if user_preferences:
                if not hasattr(response, 'metadata'):
                    response.metadata = {}
                response.metadata.update({
                    "personalized": True,
                    "user_preferences": user_preferences,
                    "skill_level": user_preferences.get("skill_level", "unknown"),
                    "code_style": user_preferences.get("code_style", "unknown")
                })
            
            return response
            
        except Exception as e:
            logger.error(f"동기식 코드 생성 실패: {e}")
            return CodeGenerationResponse(
                success=False,
                generated_code="",
                error_message=f"코드 생성 실패: {str(e)}",
                model_used="vllm",
                processing_time=time.time() - start_time,
                token_usage={"total_tokens": 0},
            )

    def _update_metrics(self, response_time: float, success: bool):
        """성능 메트릭 업데이트"""
        # 이동 평균으로 응답 시간 업데이트
        alpha = 0.1
        self.avg_response_time = (
            self.avg_response_time * (1 - alpha) + response_time * alpha
        )

    def get_service_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        success_rate = (
            self.successful_requests / max(self.total_requests, 1) * 100
        )
        
        return {
            "connected": self.is_connected,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(success_rate, 2),
            "avg_response_time": round(self.avg_response_time, 2),
            "adaptive_system": {
                "buffer_metrics": self.adaptive_buffer.get_metrics(),
                "current_complexity": self.adaptive_buffer.current_complexity.value if self.adaptive_buffer.current_complexity else None,
            }
        }
    
    async def check_health(self) -> Dict[str, Any]:
        """
        호환성을 위한 check_health 메서드
        기존 health_check() 메서드를 확장하여 더 상세한 정보 제공
        """
        try:
            # 기존 health_check() 메서드 호출
            is_healthy = await self.health_check()
            
            # 상세한 상태 정보 구성
            status_info = {
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": time.time(),
                "details": {
                    "connected": self.is_connected,
                    "base_url": self.base_url,
                    "total_requests": self.total_requests,
                    "successful_requests": self.successful_requests,
                    "failed_requests": self.failed_requests,
                    "connection_retries": self.connection_retries,
                    "max_retries": self.max_retries
                },
                "performance": {
                    "success_rate": (
                        self.successful_requests / max(self.total_requests, 1) * 100
                    ),
                    "avg_response_time": self.avg_response_time
                }
            }
            
            if is_healthy:
                logger.debug("vLLM 서버 상태 확인 완료: 정상")
            else:
                logger.warning("vLLM 서버 상태 확인 완료: 비정상")
                
            return status_info
            
        except Exception as e:
            logger.error(f"vLLM 헬스 체크 오류: {e}")
            return {
                "status": "error",
                "timestamp": time.time(),
                "error": str(e),
                "details": {
                    "connected": False,
                    "base_url": self.base_url,
                    "connection_retries": self.connection_retries
                }
            }

    async def health_check(self) -> bool:
        """헬스 체크"""
        try:
            logger.info(f"🔍 vLLM 헬스 체크 시작: {self.base_url}")
            
            if not self.session:
                logger.info("세션이 없어서 새로 연결합니다")
                await self.connect()
            
            health_url = f"{self.base_url}/health"
            logger.info(f"🔍 요청 URL: {health_url}")
            
            async with self.session.get(health_url) as response:
                status = response.status
                logger.info(f"🔍 vLLM 헬스 체크 응답: {status}")
                
                if status == 200:
                    response_text = await response.text()
                    logger.info(f"✅ vLLM 서버 정상: {response_text}")
                    return True
                else:
                    logger.warning(f"❌ vLLM 서버 응답 오류: {status}")
                    return False
                    
        except aiohttp.ClientConnectorError as e:
            logger.error(f"❌ vLLM 서버 연결 실패 (ClientConnectorError): {e}")
            logger.error(f"❌ 시도한 URL: {self.base_url}/health")
            return False
        except asyncio.TimeoutError as e:
            logger.error(f"❌ vLLM 서버 연결 타임아웃: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ vLLM 헬스 체크 실패: {type(e).__name__}: {e}")
            return False

# 호환성을 위한 별칭
ChunkBuffer = AdaptiveChunkBuffer 

# 전역 서비스 인스턴스
vllm_service = VLLMIntegrationService()