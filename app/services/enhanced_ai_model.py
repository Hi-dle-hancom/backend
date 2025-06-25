import logging
import time
import uuid
import asyncio
import re
import ast
import subprocess
import tempfile
import os
from typing import Optional, Dict, Any, AsyncGenerator, List, Tuple
from functools import lru_cache
from datetime import datetime
import httpx
from app.core.config import settings
from app.schemas.code_generation import StreamingChunk
from app.core.settings_mapper import get_default_user_preferences

logger = logging.getLogger(__name__)

class SafetyValidator:
    """코드 안전성 검증을 담당하는 클래스"""
    
    # 위험한 키워드 패턴
    DANGEROUS_PATTERNS = [
        r'os\.system\s*\(',
        r'subprocess\.',
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__\s*\(',
        r'open\s*\(.+[\'\"](w|a|r\+)',
        r'file\s*\(.+[\'\"](w|a|r\+)',
        r'input\s*\(',
        r'raw_input\s*\(',
        r'compile\s*\(',
        r'globals\s*\(',
        r'locals\s*\(',
        r'vars\s*\(',
        r'dir\s*\(',
        r'getattr\s*\(',
        r'setattr\s*\(',
        r'delattr\s*\(',
        r'hasattr\s*\(',
        r'isinstance\s*\(',
        r'issubclass\s*\(',
        r'__.*__',  # 매직 메소드
        r'import\s+os',
        r'import\s+sys',
        r'import\s+subprocess',
        r'from\s+os\s+import',
        r'from\s+sys\s+import',
        r'from\s+subprocess\s+import',
    ]
    
    # 허용되는 안전한 키워드
    SAFE_KEYWORDS = [
        'def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 
        'finally', 'with', 'return', 'yield', 'pass', 'break', 'continue',
        'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple',
        'range', 'enumerate', 'zip', 'map', 'filter', 'sum', 'max', 'min',
        'sorted', 'reversed', 'any', 'all'
    ]
    
    def validate_input_safety(self, user_input: str) -> Tuple[bool, List[str]]:
        """사용자 입력의 안전성을 검증합니다."""
        issues = []
        
        # 입력 길이 검증
        if len(user_input) > 10000:
            issues.append("입력이 너무 깁니다 (최대 10,000자)")
        
        # 악성 패턴 검출
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                issues.append(f"위험한 패턴 감지: {pattern}")
        
        # SQL 인젝션 패턴 검출
        sql_patterns = [
            r'DROP\s+TABLE',
            r'DELETE\s+FROM',
            r'INSERT\s+INTO',
            r'UPDATE\s+.*SET',
            r'UNION\s+SELECT',
            r';\s*--',
            r'\/\*.*\*\/'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                issues.append(f"SQL 인젝션 패턴 감지: {pattern}")
        
        # 스크립트 인젝션 검출
        script_patterns = [
            r'<script.*?>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*='
        ]
        
        for pattern in script_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                issues.append(f"스크립트 인젝션 패턴 감지: {pattern}")
        
        return len(issues) == 0, issues
    
    def validate_generated_code_safety(self, code: str) -> Tuple[bool, List[str]]:
        """생성된 코드의 안전성을 검증합니다."""
        issues = []
        
        # 기본 안전성 검증
        is_safe, basic_issues = self.validate_input_safety(code)
        issues.extend(basic_issues)
        
        # Python 문법 검증
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Python 문법 오류: {str(e)}")
        except Exception as e:
            issues.append(f"코드 파싱 오류: {str(e)}")
        
        # 보안 취약점 검증
        security_issues = self._check_security_vulnerabilities(code)
        issues.extend(security_issues)
        
        return len(issues) == 0, issues
    
    def _check_security_vulnerabilities(self, code: str) -> List[str]:
        """보안 취약점을 검사합니다."""
        vulnerabilities = []
        
        # 파일 시스템 접근 검사
        if re.search(r'open\s*\(.*[\'\"]/.*[\'\"]\s*,\s*[\'\"](w|a)', code):
            vulnerabilities.append("파일 시스템에 쓰기 접근 시도")
        
        # 네트워크 요청 검사
        network_patterns = [
            r'urllib\.request',
            r'requests\.',
            r'socket\.',
            r'http\.client',
            r'ftplib\.',
            r'smtplib\.'
        ]
        
        for pattern in network_patterns:
            if re.search(pattern, code):
                vulnerabilities.append(f"네트워크 접근 감지: {pattern}")
        
        # 시스템 명령 실행 검사
        if re.search(r'os\.system|subprocess|popen', code):
            vulnerabilities.append("시스템 명령 실행 감지")
        
        return vulnerabilities

class EnhancedAIModelManager:
    """강화된 AI 모델 관리자 - 실제 모델 호출 및 안전성 검증 포함"""
    
    def __init__(self):
        self.model_loaded = False
        self.model_endpoint = None
        self.safety_validator = SafetyValidator()
        self._load_time = None
        self._model_info = None
    
    async def initialize_model(self):
        """AI 모델을 초기화합니다."""
        if self.model_loaded:
            return
        
        try:
            logger.info("Enhanced AI 모델 초기화 시작...")
            start_time = time.time()
            
            # 실제 AI 모델 엔드포인트 설정
            if settings.AI_MODEL_ENDPOINT:
                self.model_endpoint = settings.AI_MODEL_ENDPOINT
            else:
                # 개발 환경에서는 Mock 모델 사용
                self.model_endpoint = "mock"
                logger.warning("AI 모델 엔드포인트가 설정되지 않아 Mock 모델을 사용합니다.")
            
            self._model_info = {
                "name": settings.MODEL_NAME,
                "version": settings.MODEL_VERSION,
                "endpoint": self.model_endpoint,
                "language": "python",
                "status": "loaded",
                "features": {
                    "code_generation": True,
                    "code_completion": True,
                    "safety_validation": True,
                    "syntax_checking": True,
                    "streaming_response": True
                }
            }
            
            self._load_time = time.time() - start_time
            self.model_loaded = True
            
            logger.info(f"Enhanced AI 모델 초기화 완료 (소요시간: {self._load_time:.2f}초)")
            
        except Exception as e:
            logger.error(f"AI 모델 초기화 실패: {e}")
            raise Exception(f"AI 모델 초기화 실패: {e}")
    
    async def generate_code_with_safety(self, prompt: str, context: Optional[str] = None, user_preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """개인화된 안전성 검증을 포함한 Python 코드 생성"""
        
        # 개인화 설정 적용
        if user_preferences is None:
            user_preferences = get_default_user_preferences()
        
        try:
            logger.info(f"개인화된 Enhanced 코드 생성 시작: skill_level={user_preferences.get('skill_level')}, context={user_preferences.get('project_context')}")
            
            # 1. 입력 안전성 검증
            safety_result = await self._validate_input_safety(prompt, context)
            if not safety_result["is_safe"]:
                return {
                    "status": "error",
                    "error_message": "입력이 안전하지 않습니다. 악성 코드나 위험한 요청이 감지되었습니다.",
                    "error_type": "input_safety",
                    "safety_issues": safety_result["issues"],
                    "generated_code": "",
                    "explanation": "",
                    "safety_validated": False
                }
            
            # 2. 개인화된 코드 생성
            generation_result = await self._generate_personalized_code_with_ai(prompt, context, user_preferences)
            
            if generation_result["status"] != "success":
                return generation_result
            
            generated_code = generation_result["generated_code"]
            explanation = generation_result["explanation"]
            
            # 3. 생성된 코드 안전성 검증
            code_safety_result = await self._validate_code_safety(generated_code, user_preferences)
            
            # 4. 코드 품질 평가 (개인화 반영)
            quality_score = await self._evaluate_code_quality(generated_code, prompt, user_preferences)
            
            # 5. 개인화된 설명 생성
            personalized_explanation = self._enhance_explanation_with_personalization(explanation, user_preferences)
            
            return {
                "status": "success",
                "generated_code": generated_code,
                "explanation": personalized_explanation,
                "quality_score": quality_score,
                "safety_validated": code_safety_result["is_safe"],
                "metadata": {
                    "model_endpoint": self.model_endpoint,
                    "safety_level": user_preferences.get('safety_level', 'standard'),
                    "personalization": {
                        "skill_level": user_preferences.get('skill_level'),
                        "project_context": user_preferences.get('project_context'),
                        "code_style": user_preferences.get('code_style'),
                        "language_features": user_preferences.get('language_features', [])
                    },
                    "safety_checks": {
                        "input_safety": safety_result["is_safe"],
                        "code_safety": code_safety_result["is_safe"],
                        "detected_issues": code_safety_result.get("issues", [])
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Enhanced 개인화 코드 생성 실패: {e}")
            return {
                "status": "error",
                "error_message": f"코드 생성 중 오류가 발생했습니다: {str(e)}",
                "error_type": "generation_error",
                "generated_code": "",
                "explanation": "",
                "safety_validated": False
            }

    async def _generate_personalized_code_with_ai(self, prompt: str, context: Optional[str], user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 선호도를 반영한 AI 코드 생성"""
        try:
            # 개인화된 시스템 프롬프트 생성
            system_prompt = self._build_personalized_system_prompt(user_preferences)
            
            # 개인화된 사용자 프롬프트 생성
            user_prompt = self._build_personalized_user_prompt(prompt, context, user_preferences)
            
            # AI 모델 호출
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
                top_p=0.9
            )
            
            content = response.choices[0].message.content
            
            # 코드와 설명 분리
            if "```python" in content:
                parts = content.split("```python")
                if len(parts) > 1:
                    code_part = parts[1].split("```")[0].strip()
                    explanation_part = content.replace(f"```python\n{code_part}\n```", "").strip()
                else:
                    code_part = content
                    explanation_part = "생성된 Python 코드입니다."
            else:
                code_part = content
                explanation_part = "생성된 Python 코드입니다."
            
            return {
                "status": "success",
                "generated_code": code_part,
                "explanation": explanation_part
            }
            
        except Exception as e:
            logger.error(f"AI 개인화 코드 생성 실패: {e}")
            return {
                "status": "error",
                "error_message": f"AI 코드 생성 실패: {str(e)}",
                "error_type": "ai_generation_error"
            }

    def _build_personalized_system_prompt(self, user_preferences: Dict[str, Any]) -> str:
        """사용자 선호도를 반영한 시스템 프롬프트 생성"""
        skill_level = user_preferences.get('skill_level', 'intermediate')
        code_style = user_preferences.get('code_style', 'standard')
        project_context = user_preferences.get('project_context', 'general_purpose')
        comment_style = user_preferences.get('comment_style', 'standard')
        error_handling = user_preferences.get('error_handling', 'basic')
        language_features = user_preferences.get('language_features', [])
        safety_level = user_preferences.get('safety_level', 'standard')
        
        base_prompt = """당신은 안전하고 고품질의 Python 코드를 생성하는 전문 AI 어시스턴트입니다."""
        
        # 스킬 수준별 프롬프트 조정
        if skill_level == 'beginner':
            skill_prompt = """
사용자는 Python 초급자입니다:
- 매우 상세한 주석과 단계별 설명을 포함하세요
- 기본적이고 이해하기 쉬운 문법을 사용하세요
- 복잡한 개념은 간단히 설명하세요
- 학습에 도움이 되는 설명을 추가하세요"""
        elif skill_level == 'advanced':
            skill_prompt = """
사용자는 Python 고급자입니다:
- 효율적이고 최적화된 코드를 작성하세요
- 고급 Python 기능과 패턴을 활용하세요
- 성능과 메모리 효율성을 고려하세요
- 간결하지만 명확한 주석을 포함하세요"""
        elif skill_level == 'expert':
            skill_prompt = """
사용자는 Python 전문가입니다:
- 최신 Python 기능과 모범 사례를 적용하세요
- 아키텍처 설계와 확장성을 고려하세요
- 고성능 및 메모리 최적화된 솔루션을 제공하세요
- 필요시 고급 디자인 패턴을 활용하세요"""
        else:
            skill_prompt = """
사용자는 Python 중급자입니다:
- 실용적이고 읽기 쉬운 코드를 작성하세요
- 적절한 수준의 주석을 포함하세요
- 좋은 프로그래밍 관행을 따르세요"""
        
        # 프로젝트 컨텍스트별 프롬프트
        if project_context == 'web_development':
            context_prompt = """
웹 개발 컨텍스트에 맞는 코드를 생성하세요:
- FastAPI, Flask 등 웹 프레임워크 활용
- REST API, HTTP 처리, JSON 응답 등 고려
- 보안, 인증, 데이터 검증 포함
- 웹 개발 모범 사례 적용"""
        elif project_context == 'data_science':
            context_prompt = """
데이터 사이언스 컨텍스트에 맞는 코드를 생성하세요:
- pandas, numpy, matplotlib, seaborn 등 활용
- 데이터 처리, 분석, 시각화 포함
- 머신러닝 라이브러리(scikit-learn) 활용
- 데이터 과학 워크플로우 고려"""
        elif project_context == 'automation':
            context_prompt = """
자동화 컨텍스트에 맞는 코드를 생성하세요:
- 파일 처리, 스케줄링, 시스템 작업 등
- 오류 처리와 로깅 강화
- 안정성과 신뢰성 우선
- 반복 작업 자동화에 특화"""
        else:
            context_prompt = """일반적인 Python 프로그래밍 컨텍스트로 코드를 생성하세요."""
        
        # 언어 기능 선호도
        feature_prompts = []
        if 'type_hints' in language_features:
            feature_prompts.append("- 타입 힌트를 적극적으로 사용하세요")
        if 'f_strings' in language_features:
            feature_prompts.append("- f-string을 사용한 문자열 포맷팅을 선호하세요")
        if 'dataclasses' in language_features:
            feature_prompts.append("- 적절한 경우 dataclass를 활용하세요")
        if 'async_await' in language_features:
            feature_prompts.append("- 비동기 프로그래밍이 필요한 경우 async/await를 사용하세요")
        
        feature_prompt = "\n".join(feature_prompts) if feature_prompts else ""
        
        # 에러 처리 수준
        if error_handling == 'robust':
            error_prompt = """
강화된 에러 처리를 포함하세요:
- 모든 예외 상황을 고려한 comprehensive try-catch
- 상세한 에러 로깅과 메시지
- 복구 메커니즘과 fallback 로직
- 사용자 친화적인 에러 메시지"""
        elif error_handling == 'detailed':
            error_prompt = """
상세한 에러 처리를 포함하세요:
- 주요 예외 상황에 대한 try-catch
- 적절한 에러 메시지와 로깅
- 기본적인 복구 로직"""
        else:
            error_prompt = """기본적인 에러 처리를 포함하세요."""
        
        # 안전성 수준
        if safety_level == 'strict':
            safety_prompt = """
매우 엄격한 안전성 기준을 적용하세요:
- 모든 입력 검증과 sanitization
- SQL injection, XSS 등 보안 취약점 방지
- 최소 권한 원칙 적용
- 보안 모범 사례 철저히 준수"""
        elif safety_level == 'enhanced':
            safety_prompt = """
강화된 안전성 기준을 적용하세요:
- 입력 검증과 데이터 타입 확인
- 일반적인 보안 취약점 방지
- 안전한 코딩 관행 적용"""
        else:
            safety_prompt = """기본적인 안전성 기준을 적용하세요."""
        
        return f"""{base_prompt}

{skill_prompt}

{context_prompt}

{feature_prompt}

{error_prompt}

{safety_prompt}

안전하고 실행 가능한 Python 코드만 생성하세요. 악성 코드나 시스템에 해를 끼칠 수 있는 코드는 절대 생성하지 마세요."""

    def _build_personalized_user_prompt(self, prompt: str, context: Optional[str], user_preferences: Dict[str, Any]) -> str:
        """개인화된 사용자 프롬프트 생성"""
        code_style = user_preferences.get('code_style', 'standard')
        comment_style = user_preferences.get('comment_style', 'standard')
        
        base_prompt = f"다음 요청에 대한 Python 코드를 생성해주세요:\n\n{prompt}"
        
        if context:
            base_prompt += f"\n\n컨텍스트:\n{context}"
        
        style_instructions = []
        
        if code_style == 'minimal':
            style_instructions.append("- 최소한의 코드로 핵심 기능만 구현")
        elif code_style == 'detailed':
            style_instructions.append("- 상세한 구현과 추가 기능 포함")
        elif code_style == 'comprehensive':
            style_instructions.append("- 포괄적이고 완전한 솔루션 제공")
        
        if comment_style == 'brief':
            style_instructions.append("- 간단한 주석만 포함")
        elif comment_style == 'detailed':
            style_instructions.append("- 상세한 주석과 설명 포함")
        elif comment_style == 'educational':
            style_instructions.append("- 학습용 상세 설명과 주석 포함")
        
        if style_instructions:
            base_prompt += f"\n\n요구사항:\n" + "\n".join(style_instructions)
        
        return base_prompt

    async def _validate_code_safety(self, code: str, user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """개인화된 코드 안전성 검증"""
        try:
            safety_level = user_preferences.get('safety_level', 'standard')
            skill_level = user_preferences.get('skill_level', 'intermediate')
            
            # 기본 위험 패턴
            dangerous_patterns = [
                r'os\.system\s*\(',
                r'subprocess\.',
                r'eval\s*\(',
                r'exec\s*\(',
                r'__import__\s*\(',
                r'open\s*\(\s*["\'][^"\']*["\']\s*,\s*["\']w',
                r'shutil\.rmtree',
                r'os\.remove',
                r'socket\.',
                r'urllib\.request\.',
                r'requests\.'
            ]
            
            # 안전성 수준별 추가 패턴
            if safety_level == 'strict':
                dangerous_patterns.extend([
                    r'pickle\.',
                    r'marshal\.',
                    r'compile\s*\(',
                    r'globals\s*\(',
                    r'locals\s*\(',
                    r'vars\s*\(',
                    r'dir\s*\(',
                    r'getattr\s*\(',
                    r'setattr\s*\(',
                    r'delattr\s*\(',
                ])
            
            # 초급자는 더 엄격한 검증
            if skill_level == 'beginner':
                dangerous_patterns.extend([
                    r'lambda\s+',
                    r'yield\s+',
                    r'with\s+open\s*\(',
                ])
            
            issues = []
            for pattern in dangerous_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    issues.append(f"잠재적 위험 패턴 감지: {pattern}")
            
            is_safe = len(issues) == 0
            
            return {
                "is_safe": is_safe,
                "issues": issues,
                "safety_level": safety_level,
                "validation_details": {
                    "patterns_checked": len(dangerous_patterns),
                    "issues_found": len(issues)
                }
            }
            
        except Exception as e:
            logger.error(f"코드 안전성 검증 실패: {e}")
            return {
                "is_safe": False,
                "issues": ["안전성 검증 중 오류 발생"],
                "safety_level": "unknown"
            }

    async def _evaluate_code_quality(self, code: str, prompt: str, user_preferences: Dict[str, Any]) -> float:
        """개인화된 코드 품질 평가"""
        try:
            skill_level = user_preferences.get('skill_level', 'intermediate')
            language_features = user_preferences.get('language_features', [])
            
            quality_score = 0.0
            
            # 기본 품질 지표
            if len(code.strip()) > 10:
                quality_score += 0.2
            
            if 'def ' in code or 'class ' in code:
                quality_score += 0.2
            
            if '#' in code:  # 주석 포함
                quality_score += 0.15
            
            # Python 문법 검증
            try:
                ast.parse(code)
                quality_score += 0.25
            except SyntaxError:
                quality_score -= 0.3
            
            # 언어 기능 선호도 반영
            if 'type_hints' in language_features and ':' in code and '->' in code:
                quality_score += 0.1
            
            if 'f_strings' in language_features and 'f"' in code:
                quality_score += 0.05
            
            if 'dataclasses' in language_features and '@dataclass' in code:
                quality_score += 0.05
            
            # 스킬 수준별 추가 평가
            if skill_level == 'expert':
                # 고급 패턴 확인
                if any(pattern in code for pattern in ['with ', 'yield ', 'async def', 'await ']):
                    quality_score += 0.1
            elif skill_level == 'beginner':
                # 초급자용 명확성 확인
                if code.count('\n') >= 5:  # 충분한 설명
                    quality_score += 0.05
            
            return max(0.0, min(1.0, quality_score))
            
        except Exception as e:
            logger.error(f"코드 품질 평가 실패: {e}")
            return 0.5

    def _enhance_explanation_with_personalization(self, explanation: str, user_preferences: Dict[str, Any]) -> str:
        """개인화된 설명 강화"""
        try:
            skill_level = user_preferences.get('skill_level', 'intermediate')
            comment_style = user_preferences.get('comment_style', 'standard')
            project_context = user_preferences.get('project_context', 'general_purpose')
            
            enhanced_explanation = explanation
            
            # 스킬 수준별 설명 조정
            if skill_level == 'beginner':
                enhanced_explanation += "\n\n[초급자용 추가 설명]\n"
                enhanced_explanation += "- 이 코드는 단계별로 실행됩니다\n"
                enhanced_explanation += "- 각 함수의 역할과 매개변수를 확인해보세요\n"
                enhanced_explanation += "- 궁금한 부분이 있으면 Python 공식 문서를 참조하세요"
            
            elif skill_level == 'expert':
                enhanced_explanation += "\n\n[전문가용 추가 정보]\n"
                enhanced_explanation += "- 성능 최적화 고려사항을 검토해보세요\n"
                enhanced_explanation += "- 확장성과 유지보수성을 고려한 구조입니다\n"
                enhanced_explanation += "- 필요시 추가적인 디자인 패턴 적용을 고려하세요"
            
            # 프로젝트 컨텍스트별 추가 정보
            if project_context == 'web_development':
                enhanced_explanation += "\n\n[웹 개발 관련 팁]\n"
                enhanced_explanation += "- 보안과 인증을 고려하세요\n"
                enhanced_explanation += "- RESTful API 설계 원칙을 따르세요"
            
            elif project_context == 'data_science':
                enhanced_explanation += "\n\n[데이터 사이언스 팁]\n"
                enhanced_explanation += "- 데이터 검증과 전처리를 확인하세요\n"
                enhanced_explanation += "- 결과 시각화를 고려해보세요"
            
            return enhanced_explanation
            
        except Exception as e:
            logger.error(f"설명 개인화 실패: {e}")
            return explanation

    async def generate_streaming_response(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StreamingChunk, None]:
        """안전성 검증을 포함한 스트리밍 응답 생성"""
        
        session_id = str(uuid.uuid4())
        sequence = 0
        
        # 입력 안전성 검증
        is_safe, safety_issues = self.safety_validator.validate_input_safety(prompt)
        if not is_safe:
            yield StreamingChunk(
                type="error",
                content=f"입력 안전성 검증 실패: {', '.join(safety_issues)}",
                sequence=sequence,
                timestamp=datetime.now()
            )
            return
        
        # 시작 신호
        yield StreamingChunk(
            type="start",
            content=f"안전성 검증 완료. 코드 생성을 시작합니다... (세션: {session_id[:8]})",
            sequence=sequence,
            timestamp=datetime.now()
        )
        sequence += 1
        
        # 코드 생성
        generated_code = await self._generate_mock_code(prompt, context, user_preferences)
        
        # 생성된 코드 안전성 재검증
        code_is_safe, code_issues = self.safety_validator.validate_generated_code_safety(generated_code)
        if not code_is_safe:
            generated_code = await self._generate_safe_fallback_code(prompt)
        
        # 코드를 토큰 단위로 스트리밍
        lines = generated_code.split('\n')
        for line in lines:
            await asyncio.sleep(0.03)  # 스트리밍 효과
            
            chunk_type = "code" if line.strip() else "newline"
            if line.strip().startswith('#'):
                chunk_type = "comment"
            elif line.strip().startswith('def ') or line.strip().startswith('class '):
                chunk_type = "definition"
            
            yield StreamingChunk(
                type=chunk_type,
                content=line + '\n',
                sequence=sequence,
                timestamp=datetime.now()
            )
            sequence += 1
        
        # 설명 부분 스트리밍
        explanation = self._generate_explanation(prompt, generated_code, user_preferences)
        explanation_lines = explanation.split('\n')
        
        for line in explanation_lines:
            if line.strip():
                await asyncio.sleep(0.05)
                yield StreamingChunk(
                    type="explanation",
                    content=line + '\n',
                    sequence=sequence,
                    timestamp=datetime.now()
                )
                sequence += 1
        
        # 완료 신호
        yield StreamingChunk(
            type="done",
            content="",
            sequence=sequence,
            timestamp=datetime.now(),
            metadata={
                "safety_validated": code_is_safe,
                "quality_score": self._evaluate_code_quality(generated_code),
                "session_id": session_id
            }
        )

# 글로벌 인스턴스
enhanced_ai_model = EnhancedAIModelManager() 