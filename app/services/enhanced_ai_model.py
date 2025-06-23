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
    
    async def generate_code_with_safety(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """안전성 검증을 포함한 코드 생성"""
        
        # 1. 입력 안전성 검증
        is_safe, safety_issues = self.safety_validator.validate_input_safety(prompt)
        if not is_safe:
            return {
                "status": "error",
                "error_type": "input_safety",
                "error_message": "입력에서 안전하지 않은 내용이 감지되었습니다.",
                "safety_issues": safety_issues,
                "generated_code": "",
                "explanation": ""
            }
        
        # 2. AI 모델을 통한 코드 생성
        try:
            if self.model_endpoint == "mock":
                generated_code = await self._generate_mock_code(prompt, context, user_preferences)
            else:
                generated_code = await self._call_external_model(prompt, context, user_preferences)
            
            # 3. 생성된 코드 안전성 검증
            code_is_safe, code_issues = self.safety_validator.validate_generated_code_safety(generated_code)
            
            if not code_is_safe:
                logger.warning(f"생성된 코드에서 안전성 문제 감지: {code_issues}")
                # 안전하지 않은 코드는 필터링하여 재생성
                generated_code = await self._generate_safe_fallback_code(prompt)
            
            # 4. 코드 품질 검증
            quality_score = self._evaluate_code_quality(generated_code)
            
            # 5. 설명 생성
            explanation = self._generate_explanation(prompt, generated_code, user_preferences)
            
            return {
                "status": "success",
                "generated_code": generated_code,
                "explanation": explanation,
                "safety_validated": True,
                "quality_score": quality_score,
                "safety_issues": [],
                "metadata": {
                    "model_endpoint": self.model_endpoint,
                    "generation_time": time.time(),
                    "prompt_length": len(prompt),
                    "code_length": len(generated_code)
                }
            }
            
        except Exception as e:
            logger.error(f"코드 생성 중 오류 발생: {e}")
            return {
                "status": "error",
                "error_type": "generation_error",
                "error_message": str(e),
                "generated_code": "",
                "explanation": "",
                "safety_validated": False
            }
    
    async def _call_external_model(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> str:
        """외부 AI 모델 API 호출"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "prompt": prompt,
                    "context": context,
                    "language": "python",
                    "preferences": user_preferences or {}
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.AI_MODEL_API_KEY}"
                }
                
                response = await client.post(
                    self.model_endpoint,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("generated_code", "")
                else:
                    raise Exception(f"AI 모델 API 호출 실패: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"외부 AI 모델 호출 실패: {e}")
            # 외부 모델 실패 시 Mock 모델로 폴백
            return await self._generate_mock_code(prompt, context, user_preferences)
    
    async def _generate_mock_code(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> str:
        """Mock AI 모델 - 안전하고 실용적인 코드 생성"""
        
        prompt_lower = prompt.lower()
        skill_level = user_preferences.get("skill_level", "intermediate") if user_preferences else "intermediate"
        
        # 피보나치 관련 요청
        if any(keyword in prompt_lower for keyword in ["fibonacci", "피보나치"]):
            if skill_level == "beginner":
                return '''def fibonacci(n):
    """피보나치 수열의 n번째 값을 계산합니다."""
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        # 재귀적으로 계산
        return fibonacci(n-1) + fibonacci(n-2)

# 사용 예시
print(fibonacci(10))  # 55'''
            else:
                return '''def fibonacci(n, memo={}):
    """메모이제이션을 사용한 효율적인 피보나치 계산"""
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fibonacci(n-1, memo) + fibonacci(n-2, memo)
    return memo[n]

# 리스트 생성 버전
def fibonacci_sequence(length):
    """피보나치 수열을 리스트로 생성"""
    if length <= 0:
        return []
    elif length == 1:
        return [0]
    elif length == 2:
        return [0, 1]
    
    sequence = [0, 1]
    for i in range(2, length):
        sequence.append(sequence[i-1] + sequence[i-2])
    return sequence'''
        
        # 정렬 관련 요청
        elif any(keyword in prompt_lower for keyword in ["sort", "정렬", "소트"]):
            return '''def quicksort(arr):
    """퀵소트 알고리즘 구현"""
    if len(arr) <= 1:
        return arr
    
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    return quicksort(left) + middle + quicksort(right)

# 사용 예시
numbers = [3, 6, 8, 10, 1, 2, 1]
sorted_numbers = quicksort(numbers)
print(f"정렬 결과: {sorted_numbers}")'''
        
        # 클래스 관련 요청
        elif any(keyword in prompt_lower for keyword in ["class", "클래스", "객체"]):
            return '''class Calculator:
    """간단한 계산기 클래스"""
    
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        """덧셈"""
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
    
    def subtract(self, a, b):
        """뺄셈"""
        result = a - b
        self.history.append(f"{a} - {b} = {result}")
        return result
    
    def multiply(self, a, b):
        """곱셈"""
        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result
    
    def divide(self, a, b):
        """나눗셈"""
        if b == 0:
            raise ValueError("0으로 나눌 수 없습니다")
        result = a / b
        self.history.append(f"{a} / {b} = {result}")
        return result
    
    def get_history(self):
        """계산 히스토리 반환"""
        return self.history

# 사용 예시
calc = Calculator()
print(calc.add(10, 5))  # 15
print(calc.multiply(3, 4))  # 12
print(calc.get_history())'''
        
        # 기본 함수 생성
        else:
            return '''def process_data(data):
    """데이터를 처리하는 함수"""
    if not data:
        return []
    
    # 데이터 정리
    cleaned_data = [item for item in data if item is not None]
    
    # 데이터 변환
    processed_data = [str(item).strip() for item in cleaned_data]
    
    return processed_data

# 사용 예시
sample_data = ["hello", " world ", None, 123, ""]
result = process_data(sample_data)
print(f"처리 결과: {result}")'''
    
    async def _generate_safe_fallback_code(self, prompt: str) -> str:
        """안전한 폴백 코드 생성"""
        return '''# 안전성 검증을 통과하지 못해 기본 코드를 제공합니다.
def safe_function():
    """안전한 기본 함수"""
    message = "안전한 코드가 생성되었습니다."
    print(message)
    return message

# 함수 실행
safe_function()'''
    
    def _evaluate_code_quality(self, code: str) -> float:
        """코드 품질을 평가합니다 (0.0 - 1.0)"""
        score = 0.0
        
        # 기본 점수
        if code.strip():
            score += 0.2
        
        # 독스트링 존재
        if '"""' in code or "'''" in code:
            score += 0.2
        
        # 적절한 함수/클래스 정의
        if 'def ' in code or 'class ' in code:
            score += 0.2
        
        # 주석 존재
        if '#' in code:
            score += 0.1
        
        # 예외 처리
        if 'try:' in code and 'except' in code:
            score += 0.1
        
        # 사용 예시
        if '# 사용 예시' in code or '# 예시' in code:
            score += 0.1
        
        # 변수명 품질 (간단한 검사)
        if not re.search(r'\b[a-z]\b', code):  # 단일 문자 변수가 없음
            score += 0.1
        
        return min(score, 1.0)
    
    def _generate_explanation(
        self, 
        prompt: str, 
        code: str, 
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> str:
        """코드 설명을 생성합니다."""
        
        skill_level = user_preferences.get("skill_level", "intermediate") if user_preferences else "intermediate"
        
        if skill_level == "beginner":
            return f"""
이 코드는 "{prompt}"에 대한 Python 구현입니다.

📝 코드 설명:
• 함수나 클래스를 정의하여 원하는 기능을 구현했습니다
• 각 부분이 어떤 역할을 하는지 주석으로 설명했습니다
• 실제 사용 예시도 포함되어 있어 바로 실행해볼 수 있습니다

🔍 사용 방법:
1. 코드를 Python 파일(.py)에 저장하세요
2. Python 인터프리터나 IDE에서 실행하세요
3. 필요에 따라 변수값을 수정해서 테스트해보세요

💡 학습 포인트:
• Python의 기본 문법을 익힐 수 있습니다
• 함수 정의와 호출 방법을 배울 수 있습니다
• 실용적인 프로그래밍 패턴을 이해할 수 있습니다
"""
        elif skill_level == "advanced" or skill_level == "expert":
            return f"""
고급 Python 구현 - "{prompt}"

🏗️ 아키텍처:
• 최적화된 알고리즘과 데이터 구조 활용
• 성능과 메모리 효율성을 고려한 설계
• 확장 가능하고 재사용 가능한 구조

⚡ 성능 특징:
• 시간 복잡도와 공간 복잡도 최적화
• 메모이제이션 등 성능 향상 기법 적용
• 대용량 데이터 처리 고려

🔧 고급 기능:
• 제네릭 타입 힌트 적용 가능
• 데코레이터 패턴 확장 가능
• 멀티스레딩/비동기 처리 적용 가능

📈 확장 방향:
• 더 복잡한 요구사항에 대응 가능
• 프로덕션 환경에서 안정적 동작
• 테스트 주도 개발(TDD) 적용 권장
"""
        else:  # intermediate
            return f"""
"{prompt}"에 대한 Python 구현

💻 구현 내용:
• 요청하신 기능을 명확하고 효율적으로 구현했습니다
• Python의 표준 라이브러리를 활용하여 안정성을 높였습니다
• 읽기 쉽고 유지보수가 용이한 코드로 작성했습니다

🎯 핵심 기능:
• 입력 데이터 검증 및 예외 처리
• 명확한 함수 분리와 단일 책임 원칙 적용
• 실용적인 사용 예시 제공

🚀 개선 아이디어:
• 더 많은 에러 케이스 처리 추가 가능
• 성능 최적화 (필요시)
• 추가 기능 확장 가능
• 단위 테스트 작성 권장
"""

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