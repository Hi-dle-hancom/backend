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
from app.core.structured_logger import StructuredLogger
from app.schemas.code_generation import CodeGenerationRequest, CodeGenerationResponse
from .adaptive_chunk_buffer import AdaptiveChunkBuffer, IntelligentStopTokenDetector, create_adaptive_system

logger = StructuredLogger("vllm_integration")


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
        self.base_url = "http://localhost:8000"
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
            self.session = aiohttp.ClientSession(timeout=timeout)
        
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
            # 개인화된 프롬프트 생성 (code_generation.py에서 정의한 함수 사용)
            from app.api.endpoints.code_generation import build_personalized_prompt
            personalized_prompt = build_personalized_prompt(base_prompt, user_preferences)
            
            logger.info(f"개인화된 프롬프트 적용됨: skill_level={user_preferences.get('skill_level', 'unknown')}")
            return personalized_prompt
            else:
            logger.debug("개인화 정보 없음, 기본 프롬프트 사용")
            return base_prompt

    def _prepare_vllm_payload(self, request: CodeGenerationRequest, complexity, user_preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        
        payload = {
            "model": "CodeLlama-7b-Python-hf",
            "prompt": enhanced_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1,
            "stream": True,
            "stop": ["[DONE]"]
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
        """적응형 스트리밍 코드 생성 (개인화 정보 반영)"""
        
        start_time = time.time()
        self.total_requests += 1
        accumulated_content = ""  # 전체 응답 누적
        
        try:
            # 적응형 버퍼 설정
            complexity = self.adaptive_buffer.configure_for_request(
                request.prompt, 
                request.context
            )
            
            # 개인화된 요청 준비
            payload = self._prepare_vllm_payload(request, complexity, user_preferences)
            
            personalization_info = f"(개인화: {bool(user_preferences)})" if user_preferences else "(기본 모드)"
            logger.info(f"구조화된 스트리밍 요청 시작 {personalization_info} (복잡도: {complexity.value})")
            
            if not self.is_connected:
                await self.connect()

            async with self.session.post(
                f"{self.base_url}/v1/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    raise aiohttp.ClientError(f"vLLM API 오류 {response.status}: {error_text}")

                async for line in response.content:
                    line_text = line.decode('utf-8').strip()

                    if not line_text or not line_text.startswith('data: '):
                            continue

                    if line_text == 'data: [DONE]':
                        # 최종 응답 분리 및 전송
                        if accumulated_content.strip():
                            parsed_response = response_parser.parse_response(accumulated_content)
                            
                            # 설명 청크 전송
                            if parsed_response["explanation"]:
                                yield {
                                    "type": "explanation",
                                    "content": parsed_response["explanation"],
                                    "is_complete": False,
                                    "metadata": {
                                        "chunk_type": "explanation",
                                        "complexity": complexity.value,
                                        "personalized": bool(user_preferences)
                                    }
                                }
                            
                            # 코드 청크 전송
                            if parsed_response["code"]:
                                yield {
                                    "type": "code",
                                    "content": parsed_response["code"],
                                    "is_complete": False,
                                    "metadata": {
                                        "chunk_type": "code",
                                        "complexity": complexity.value,
                                        "parsing_confidence": parsed_response["metadata"]["parsing_confidence"],
                                        "personalized": bool(user_preferences),
                                        "user_preferences": user_preferences if user_preferences else {}
                                    }
                                }
                            
                            # 완료 신호
                            yield {
                                "type": "done",
                                "content": "",
                                "is_complete": True,
                                "metadata": {
                                    **self.adaptive_buffer.get_metrics(),
                                    **parsed_response["metadata"],
                                    "personalized": bool(user_preferences),
                                    "personalization_applied": user_preferences if user_preferences else None
                                }
                            }
                        break
                    
                    # JSON 파싱 및 처리 (기존 로직 유지)
                    try:
                        json_data = json.loads(line_text[6:])  # 'data: ' 제거
                        
                        if 'choices' in json_data and json_data['choices']:
                            choice = json_data['choices'][0]
                            
                            if 'delta' in choice and 'content' in choice['delta']:
                                content = choice['delta']['content']
                                accumulated_content += content  # 전체 응답에 누적
                                
                                # 적응형 버퍼에 추가
                                ready_chunks = self.adaptive_buffer.add_chunk(content)
                                
                                # 실시간 청크 전송 (개인화 메타데이터 포함)
                                for chunk in ready_chunks:
                                    if chunk.strip():
                                        # Stop token 감지
                                        should_stop, reason = self.stop_detector.should_stop(
                                            chunk, 
                                            {'request_type': complexity.value}
                                        )
                                        
                                        if should_stop:
                                            logger.info(f"Stop token 감지: {reason}")
                                            # 조기 종료 시에도 응답 분리 적용
                                            if accumulated_content.strip():
                                                parsed_response = response_parser.parse_response(accumulated_content)
                                                
                                                if parsed_response["explanation"]:
                                                    yield {
                                                        "type": "explanation",
                                                        "content": parsed_response["explanation"],
                                                        "is_complete": True,
                                                        "stop_reason": reason,
                                                        "personalized": bool(user_preferences)
                                                    }
                                                
                                                if parsed_response["code"]:
                                                    yield {
                                                        "type": "code",
                                                        "content": parsed_response["code"],
                                                        "is_complete": True,
                                                        "stop_reason": reason,
                                                        "personalized": bool(user_preferences)
                                                    }
                                            return
                                        
                                        # 일반 실시간 청크 전송 (개인화 메타데이터 포함)
                                        yield {
                                            "type": "token",
                                            "content": chunk,
                                            "is_complete": False,
                                            "metadata": {
                                                "complexity": complexity.value,
                                                "chunk_size": len(chunk),
                                                "is_preview": True,
                                                "personalized": bool(user_preferences)
                                            }
                                        }
                                        
                                        # 콜백 호출
                                        if chunk_callback:
                                            await chunk_callback(chunk)
                                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 파싱 오류: {e}, 라인: {line_text}")
                        continue
                    except Exception as e:
                        logger.error(f"청크 처리 오류: {e}")
                        continue

            # 성공 통계 업데이트
            self.successful_requests += 1
            response_time = time.time() - start_time
            self._update_metrics(response_time, True)
            
            personalization_msg = f" (개인화 적용: {user_preferences.get('skill_level', 'unknown')})" if user_preferences else ""
            logger.info(f"구조화된 스트리밍 완료{personalization_msg} (응답시간: {response_time:.2f}초)")

        except Exception as e:
            self.failed_requests += 1
            response_time = time.time() - start_time
            self._update_metrics(response_time, False)
            
            logger.error(f"구조화된 스트리밍 생성 오류: {e}")
            
            yield {
                "type": "error",
                "content": f"코드 생성 중 오류가 발생했습니다: {str(e)}",
                "is_complete": True,
                "error": str(e),
                "personalized": bool(user_preferences)
            }

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

    async def health_check(self) -> bool:
        """헬스 체크"""
        try:
            if not self.session:
                await self.connect()
            
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"헬스 체크 실패: {e}")
            return False

# 호환성을 위한 별칭
ChunkBuffer = AdaptiveChunkBuffer 