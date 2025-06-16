import logging
import re
from typing import Optional, Dict, Any, List, Tuple
import time
import asyncio
from functools import lru_cache
from app.core.config import settings
from app.services.performance_profiler import profiler, response_timer

# 로깅 설정
logger = logging.getLogger(__name__)

class OptimizedAIModelService:
    """최적화된 Python 코드 생성을 위한 AI 모델 서비스 클래스"""
    
    def __init__(self):
        """AI 모델 서비스 초기화"""
        self.model_loaded = False
        self.model = None
        self._model_cache = {}
        self._response_cache = {}
        self.lazy_load_model()
    
    def lazy_load_model(self):
        """Lazy Loading 방식의 AI 모델 로드 (첫 요청 시에만 로드)"""
        if not self.model_loaded:
            with profiler.profile_function("model_loading"):
                self._load_model_internal()
    
    def _load_model_internal(self):
        """내부 AI 모델 로딩 로직 (최적화됨)"""
        try:
            logger.info("Python 코드 생성 AI 모델 로딩 시작...")
            
            # 실제 AI 모델 로딩 로직이 들어갈 자리
            # 예: self.model = load_pretrained_model(settings.MODEL_NAME)
            # 현재는 더미 모델 설정 (최적화된 버전)
            self.model = {
                "name": settings.MODEL_NAME,
                "version": settings.MODEL_VERSION,
                "language": "python",
                "status": "loaded",
                "load_time": time.time(),
                "capabilities": {
                    "code_generation": True,
                    "code_completion": True,
                    "code_explanation": True,
                    "error_detection": True,
                    "caching": True,
                    "async_processing": True
                }
            }
            
            self.model_loaded = True
            logger.info("Python 코드 생성 AI 모델 로딩 완료 (최적화됨)")
            
        except Exception as e:
            logger.error(f"AI 모델 로딩 실패: {e}")
            self.model_loaded = False
            raise Exception(f"AI 모델 로딩에 실패했습니다: {e}")

    @lru_cache(maxsize=128)
    def get_cached_response(self, prompt_hash: str, context_hash: str = "") -> Optional[str]:
        """LRU 캐시를 사용한 응답 캐싱"""
        cache_key = f"{prompt_hash}_{context_hash}"
        return self._response_cache.get(cache_key)
    
    def set_cached_response(self, prompt_hash: str, response: str, context_hash: str = ""):
        """응답을 캐시에 저장"""
        cache_key = f"{prompt_hash}_{context_hash}"
        self._response_cache[cache_key] = response
        
        # 캐시 크기 제한 (메모리 최적화)
        if len(self._response_cache) > 100:
            # 가장 오래된 항목 제거
            oldest_key = next(iter(self._response_cache))
            del self._response_cache[oldest_key]

    def predict(self, prompt: str, context: Optional[str] = None, language: str = "python") -> str:
        """
        최적화된 AI 모델을 사용하여 Python 코드를 생성합니다.
        
        Args:
            prompt: 사용자 질문 또는 요청
            context: 코드 컨텍스트
            language: 프로그래밍 언어 (python 고정)
            
        Returns:
            생성된 Python 코드 문자열
        """
        # Lazy loading 확인
        if not self.model_loaded:
            self.lazy_load_model()
        
        # 언어 검증
        if language and language.lower() != "python":
            raise ValueError("현재 Python 언어만 지원됩니다.")
        
        with profiler.profile_function("ai_prediction"):
            try:
                # 캐시 키 생성
                prompt_hash = str(hash(prompt))
                context_hash = str(hash(context or ""))
                
                # 캐시에서 먼저 확인
                cached_result = self.get_cached_response(prompt_hash, context_hash)
                if cached_result:
                    logger.info("캐시된 응답 반환")
                    return cached_result
                
                # 프롬프트 전처리
                processed_prompt = self._preprocess_prompt(prompt, context)
                
                # Python 코드 추론 로직 (최적화된 더미 모델)
                generated_code = self._generate_python_code_optimized(processed_prompt)
                
                # 결과 캐싱
                self.set_cached_response(prompt_hash, generated_code, context_hash)
                
                logger.info(f"Python 코드 생성 완료 (최적화됨) - 길이: {len(generated_code)}")
                return generated_code
                
            except Exception as e:
                logger.error(f"Python 코드 생성 실패: {e}")
                raise Exception(f"Python 코드 생성 중 오류가 발생했습니다: {e}")
    
    async def predict_async(self, prompt: str, context: Optional[str] = None, language: str = "python") -> str:
        """
        비동기 Python 코드 생성 (성능 최적화)
        """
        return await asyncio.to_thread(self.predict, prompt, context, language)

    def predict_and_parse(self, prompt: str, context: Optional[str] = None, language: str = "python") -> Dict[str, Any]:
        """
        AI 모델을 사용하여 Python 코드를 생성하고 결과를 파싱합니다.
        
        Args:
            prompt: 사용자 질문 또는 요청
            context: 코드 컨텍스트
            language: 프로그래밍 언어 (python 고정)
            
        Returns:
            파싱된 결과 딕셔너리 {generated_code, explanation, status, error_message}
        """
        try:
            # 1. AI 모델로부터 원시 응답 생성
            raw_response = self._generate_raw_model_response(prompt, context, language)
            
            # 2. 원시 응답에서 오류 패턴 감지
            if self._detect_error_patterns(raw_response):
                return {
                    "generated_code": "",
                    "explanation": None,
                    "status": "error",
                    "error_message": self._extract_error_message(raw_response)
                }
            
            # 3. 원시 응답에서 코드와 설명 분리
            parsed_result = self._parse_model_response(raw_response)
            
            # 4. 성공적인 결과 반환
            return {
                "generated_code": parsed_result["code"],
                "explanation": parsed_result["explanation"],
                "status": "success",
                "error_message": None
            }
            
        except Exception as e:
            logger.error(f"AI 모델 추론 및 파싱 실패: {e}")
            return {
                "generated_code": "",
                "explanation": None,
                "status": "error",
                "error_message": f"AI 모델 처리 중 오류가 발생했습니다: {str(e)}"
            }

    def _generate_raw_model_response(self, prompt: str, context: Optional[str], language: str) -> str:
        """
        실제 AI 모델의 원시 응답을 시뮬레이션합니다.
        실제 모델은 마크다운 형태나 혼합된 형태의 응답을 반환할 수 있습니다.
        """
        # 프롬프트 전처리
        processed_prompt = self._preprocess_prompt(prompt, context)
        
        # 다양한 형태의 더미 응답 시뮬레이션
        if "오류" in prompt or "error" in prompt.lower():
            # 오류 시뮬레이션
            return "ERROR: 모델 처리 중 오류가 발생했습니다. 잘못된 프롬프트입니다."
        
        elif "마크다운" in prompt or "markdown" in prompt.lower():
            # 마크다운 형태 응답 시뮬레이션
            code = self._generate_python_code(processed_prompt)
            return f"""
마크다운 형태로 요청하신 Python 코드를 생성했습니다:

```python
{code}
```

마크다운 코드 블록을 사용하여 {self._generate_simple_explanation(prompt)}를 구현합니다.
마크다운 형식으로 깔끔하게 표현된 여러 줄 구성의 상세한 설명입니다.
"""
        
        elif "멀티블록" in prompt or "multiple" in prompt.lower():
            # 여러 코드 블록 응답 시뮬레이션
            code1 = self._generate_python_function()
            code2 = self._generate_python_class()
            return f"""
멀티블록 형태로 요청하신 내용에 대해 두 가지 접근 방법을 제시합니다:

첫 번째 방법 - 함수 기반:
```python
{code1}
```

두 번째 방법 - 클래스 기반:
```python
{code2}
```

멀티블록 구조를 활용하여 두 방법 모두 동일한 기능을 제공하지만, 클래스 기반이 더 확장성이 좋습니다.
"""
        
        else:
            # 일반적인 코드만 포함된 응답
            code = self._generate_python_code(processed_prompt)
            explanation = self._generate_simple_explanation(prompt)
            
            # 때로는 설명과 코드가 섞인 형태
            return f"{explanation}\n\n{code}\n\n위 코드를 사용하여 원하는 기능을 구현할 수 있습니다."

    def _parse_model_response(self, raw_response: str) -> Dict[str, str]:
        """
        AI 모델의 원시 응답에서 코드와 설명을 분리합니다.
        
        Args:
            raw_response: AI 모델의 원시 응답 텍스트
            
        Returns:
            {"code": "...", "explanation": "..."}
        """
        # 1. 마크다운 코드 블록 추출
        code_blocks = self._extract_code_blocks(raw_response)
        
        # 2. 가장 적절한 코드 블록 선택
        selected_code = self._select_best_code_block(code_blocks)
        
        # 3. 설명 부분 추출 (코드 블록 제외한 나머지)
        explanation = self._extract_explanation(raw_response, code_blocks)
        
        return {
            "code": selected_code,
            "explanation": explanation
        }

    def _extract_code_blocks(self, text: str) -> List[str]:
        """
        텍스트에서 마크다운 코드 블록을 추출합니다.
        """
        code_blocks = []
        
        # 1. 특정 언어가 명시된 코드 블록 먼저 추출
        language_patterns = [
            r'```python\s*\n(.*?)```',  # ```python
            r'```py\s*\n(.*?)```',      # ```py
        ]
        
        for pattern in language_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            code_blocks.extend([match.strip() for match in matches])
        
        # 2. 언어가 명시된 블록이 있으면 그것만 사용
        if code_blocks:
            return code_blocks
        
        # 3. 일반적인 코드 블록 추출 (언어 미명시)
        general_pattern = r'```\s*\n(.*?)```'
        matches = re.findall(general_pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            stripped = match.strip()
            # 실제 코드처럼 보이는지 확인 (단순 텍스트 제외)
            if (len(stripped) > 5 and 
                (re.search(r'[(){}[\];]', stripped) or  # 프로그래밍 문법 기호
                 re.search(r'^(def |class |import |from |if |for |while |return |print)', stripped, re.MULTILINE))):
                code_blocks.append(stripped)
        
        # 4. 마크다운 블록이 없는 경우만 Python 코드 패턴으로 추출 시도
        if not code_blocks:
            code_blocks = self._extract_python_code_patterns(text)
        
        return code_blocks

    def _extract_python_code_patterns(self, text: str) -> List[str]:
        """
        마크다운 블록이 없는 경우 Python 코드 패턴을 직접 추출합니다.
        """
        lines = text.split('\n')
        code_blocks = []
        
        # 전체 텍스트에서 Python 코드 같은 부분을 추출
        # def, class, import 등으로 시작하는 라인을 찾아 코드 블록 구성
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Python 코드 시작 패턴 감지
            if re.match(r'^(def |class |import |from |if __name__|@|async def)', line):
                current_block = [lines[i]]
                i += 1
                
                # 해당 함수/클래스의 끝까지 수집
                while i < len(lines):
                    next_line = lines[i]
                    
                    # 빈 줄이거나 들여쓰기가 있는 줄이면 계속
                    if (next_line.strip() == '' or 
                        next_line.startswith(' ') or 
                        next_line.startswith('\t') or
                        next_line.strip().startswith('#')):
                        current_block.append(next_line)
                        i += 1
                    else:
                        # 들여쓰기가 없는 새로운 라인이면 현재 블록 종료
                        break
                
                if current_block:
                    code_blocks.append('\n'.join(current_block).strip())
            else:
                i += 1
        
        # 코드 블록이 없으면 전체 텍스트에서 Python 코드 라인만 추출
        if not code_blocks:
            python_lines = []
            for line in lines:
                stripped = line.strip()
                # Python 코드 같은 패턴 감지
                if (stripped and 
                    (re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*=', stripped) or  # 변수 할당
                     re.match(r'^(def|class|import|from|if|for|while|try|with|return|print)', stripped) or
                     re.match(r'^\s+(.*)', line))):  # 들여쓰기된 라인
                    python_lines.append(line)
            
            if python_lines:
                code_blocks.append('\n'.join(python_lines).strip())
        
        return code_blocks

    def _select_best_code_block(self, code_blocks: List[str]) -> str:
        """
        여러 코드 블록 중 가장 적절한 것을 선택합니다.
        현재는 가장 긴 코드 블록을 선택하는 단순한 로직을 사용합니다.
        """
        if not code_blocks:
            return ""
        
        # 1. 가장 긴 코드 블록 선택 (일반적으로 더 완전한 구현)
        best_block = max(code_blocks, key=len)
        
        # 2. 기본적인 Python 문법 검증
        if self._is_valid_python_syntax(best_block):
            return best_block
        
        # 3. 문법이 잘못된 경우 다른 블록 시도
        for block in sorted(code_blocks, key=len, reverse=True):
            if self._is_valid_python_syntax(block):
                return block
        
        # 4. 모든 블록이 문법 오류인 경우 가장 긴 것 반환
        return best_block

    def _is_valid_python_syntax(self, code: str) -> bool:
        """
        Python 코드의 기본적인 문법 검증을 수행합니다.
        """
        try:
            import ast
            ast.parse(code)
            return True
        except SyntaxError:
            return False
        except Exception:
            # 기타 예외는 유효한 것으로 간주 (import 오류 등)
            return True

    def _extract_explanation(self, raw_response: str, code_blocks: List[str]) -> str:
        """
        원시 응답에서 설명 부분을 추출합니다 (코드 블록 제외).
        """
        explanation = raw_response
        
        # 1. 마크다운 코드 블록 제거
        explanation = re.sub(r'```python.*?```', '', explanation, flags=re.DOTALL | re.IGNORECASE)
        explanation = re.sub(r'```py.*?```', '', explanation, flags=re.DOTALL | re.IGNORECASE)
        explanation = re.sub(r'```.*?```', '', explanation, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. 순수 코드 라인들 제거
        for code_block in code_blocks:
            explanation = explanation.replace(code_block, '')
        
        # 3. 설명 텍스트 정리
        explanation = re.sub(r'\n\s*\n\s*\n', '\n\n', explanation)  # 연속된 빈 줄 정리
        explanation = explanation.strip()
        
        # 4. 의미 있는 설명인지 확인
        if len(explanation) < 10 or not explanation:
            return None
        
        return explanation

    def _detect_error_patterns(self, raw_response: str) -> bool:
        """
        AI 모델 응답에서 오류 패턴을 감지합니다.
        """
        error_patterns = [
            r'^ERROR:',
            r'^오류:',
            r'모델 처리 중 오류',
            r'잘못된 프롬프트',
            r'처리할 수 없습니다',
            r'이해할 수 없습니다',
            r'지원하지 않는',
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, raw_response, re.IGNORECASE | re.MULTILINE):
                return True
        
        return False

    def _extract_error_message(self, raw_response: str) -> str:
        """
        오류 응답에서 오류 메시지를 추출합니다.
        """
        # ERROR: 다음의 내용 추출
        error_match = re.search(r'ERROR:\s*(.+)', raw_response, re.IGNORECASE)
        if error_match:
            return error_match.group(1).strip()
        
        # 오류: 다음의 내용 추출  
        error_match = re.search(r'오류:\s*(.+)', raw_response, re.IGNORECASE)
        if error_match:
            return error_match.group(1).strip()
        
        # 기본 오류 메시지
        return "AI 모델에서 처리할 수 없는 요청입니다."

    def _generate_simple_explanation(self, prompt: str) -> str:
        """
        프롬프트를 기반으로 간단한 설명을 생성합니다.
        """
        if "함수" in prompt or "function" in prompt.lower():
            return "요청하신 Python 함수를 생성했습니다."
        elif "클래스" in prompt or "class" in prompt.lower():
            return "요청하신 Python 클래스를 구현했습니다."
        elif "리스트" in prompt or "list" in prompt.lower():
            return "리스트 조작을 위한 Python 코드입니다."
        elif "딕셔너리" in prompt or "dict" in prompt.lower():
            return "딕셔너리 처리를 위한 Python 코드입니다."
        else:
            return "요청하신 Python 코드를 생성했습니다."
    
    def _preprocess_prompt(self, prompt: str, context: Optional[str]) -> str:
        """Python 코드 생성을 위한 프롬프트를 전처리합니다."""
        # 주석 트리거 형태의 프롬프트 정리
        cleaned_prompt = self._clean_comment_trigger(prompt)
        
        processed = f"Python 코드 생성 요청: {cleaned_prompt}"
        
        if context:
            processed += f"\n\n기존 Python 코드 컨텍스트:\n{context}"
        
        processed += "\n\n생성할 Python 코드:"
        
        return processed
    
    def _clean_comment_trigger(self, prompt: str) -> str:
        """주석 트리거 형태의 프롬프트를 정리합니다."""
        import re
        
        # 주석 트리거 패턴 제거
        # /// prompt: 텍스트 -> 텍스트
        # @gen: 텍스트 -> 텍스트  
        # # prompt: 텍스트 -> 텍스트
        patterns = [
            r'^///\s*prompt:\s*',  # /// prompt:
            r'^@gen:\s*',          # @gen:
            r'^#\s*prompt:\s*',    # # prompt:
            r'^//\s*prompt:\s*',   # // prompt: (다른 언어 호환)
        ]
        
        cleaned = prompt.strip()
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
        
        # 여러 줄 주석에서 각 줄의 주석 기호 제거
        lines = cleaned.split('\n')
        cleaned_lines = []
        for line in lines:
            # 각 줄에서 주석 기호 제거
            line = re.sub(r'^\s*#\s*', '', line)  # # 제거
            line = re.sub(r'^\s*//\s*', '', line)  # // 제거
            line = re.sub(r'^\s*///\s*', '', line)  # /// 제거
            if line.strip():  # 빈 줄이 아닌 경우만 추가
                cleaned_lines.append(line.strip())
        
        result = ' '.join(cleaned_lines).strip()
        
        # 결과가 비어있으면 원본 반환
        return result if result else prompt.strip()
    
    def _generate_python_code_optimized(self, prompt: str) -> str:
        """최적화된 Python 코드 생성 로직"""
        with profiler.profile_function("code_generation"):
            return self._generate_python_code(prompt)
    
    def _generate_python_code(self, prompt: str) -> str:
        """더미 Python 코드 생성 로직"""
        
        # 프롬프트 키워드 기반 더미 응답 생성
        if "함수" in prompt or "function" in prompt.lower() or "def" in prompt.lower():
            return self._generate_python_function()
        
        elif "클래스" in prompt or "class" in prompt.lower():
            return self._generate_python_class()
        
        elif "반복" in prompt or "loop" in prompt.lower() or "for" in prompt.lower():
            return self._generate_python_loop()
        
        elif "조건" in prompt or "if" in prompt.lower() or "조건문" in prompt:
            return self._generate_python_conditional()
        
        elif "리스트" in prompt or "list" in prompt.lower():
            return self._generate_python_list_operations()
        
        elif "딕셔너리" in prompt or "dict" in prompt.lower():
            return self._generate_python_dict_operations()
        
        elif "파일" in prompt or "file" in prompt.lower():
            return self._generate_python_file_operations()
        
        elif "API" in prompt or "requests" in prompt.lower() or "웹" in prompt:
            return self._generate_python_api_code()
        
        else:
            # 기본 더미 응답
            return self._generate_basic_python_code()
    
    def _generate_python_function(self) -> str:
        """Python 함수 더미 생성"""
        return '''def calculate_fibonacci(n):
    """
    피보나치 수열의 n번째 값을 계산합니다.
    
    Args:
        n (int): 계산할 피보나치 수열의 위치
    
    Returns:
        int: n번째 피보나치 수
    """
    if n <= 1:
        return n
    else:
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# 사용 예시
result = calculate_fibonacci(10)
print(f"10번째 피보나치 수: {result}")'''
    
    def _generate_python_class(self) -> str:
        """Python 클래스 더미 생성"""
        return '''class DataProcessor:
    """데이터 처리를 위한 클래스입니다."""
    
    def __init__(self, data_source: str):
        """
        DataProcessor 초기화
        
        Args:
            data_source (str): 데이터 소스 경로
        """
        self.data_source = data_source
        self.data = []
        self.processed_data = []
    
    def load_data(self) -> bool:
        """데이터를 로드합니다."""
        try:
            # 데이터 로딩 로직
            print(f"데이터 로딩 중: {self.data_source}")
            # 실제 구현에서는 파일 읽기 등의 작업 수행
            self.data = [1, 2, 3, 4, 5]  # 예시 데이터
            return True
        except Exception as e:
            print(f"데이터 로딩 실패: {e}")
            return False
    
    def process_data(self) -> list:
        """데이터를 처리합니다."""
        if not self.data:
            raise ValueError("처리할 데이터가 없습니다. 먼저 load_data()를 호출하세요.")
        
        self.processed_data = [x * 2 for x in self.data]
        return self.processed_data
    
    def get_summary(self) -> dict:
        """데이터 요약 정보를 반환합니다."""
        return {
            "원본_데이터_수": len(self.data),
            "처리된_데이터_수": len(self.processed_data),
            "평균값": sum(self.processed_data) / len(self.processed_data) if self.processed_data else 0
        }'''
    
    def _generate_python_loop(self) -> str:
        """Python 반복문 더미 생성"""
        return '''# 다양한 Python 반복문 예시

# 1. 기본 for 반복문
numbers = [1, 2, 3, 4, 5]
for num in numbers:
    print(f"숫자: {num}")

# 2. range를 사용한 반복문
for i in range(10):
    print(f"인덱스: {i}")

# 3. enumerate를 사용한 반복문
fruits = ['사과', '바나나', '오렌지']
for index, fruit in enumerate(fruits):
    print(f"{index}: {fruit}")

# 4. 딕셔너리 반복문
person = {'이름': '홍길동', '나이': 30, '직업': '개발자'}
for key, value in person.items():
    print(f"{key}: {value}")

# 5. while 반복문
count = 0
while count < 5:
    print(f"카운트: {count}")
    count += 1

# 6. 리스트 컴프리헨션
squared_numbers = [x**2 for x in range(1, 6)]
print(f"제곱수: {squared_numbers}")'''
    
    def _generate_python_conditional(self) -> str:
        """Python 조건문 더미 생성"""
        return '''# Python 조건문 예시

def check_grade(score):
    """점수에 따른 등급을 반환합니다."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"

# 사용 예시
student_score = 85
grade = check_grade(student_score)
print(f"점수 {student_score}점의 등급: {grade}")

# 복합 조건문 예시
age = 25
has_license = True

if age >= 18 and has_license:
    print("운전 가능")
elif age >= 18 and not has_license:
    print("면허증이 필요합니다")
else:
    print("나이가 부족합니다")

# 삼항 연산자 (조건부 표현식)
result = "성인" if age >= 18 else "미성년자"
print(f"분류: {result}")'''
    
    def _generate_python_list_operations(self) -> str:
        """Python 리스트 조작 더미 생성"""
        return '''# Python 리스트 조작 예시

# 리스트 생성
fruits = ['사과', '바나나', '오렌지']
numbers = [1, 2, 3, 4, 5]

# 리스트 요소 추가
fruits.append('포도')
fruits.insert(1, '딸기')
print(f"과일 리스트: {fruits}")

# 리스트 요소 제거
fruits.remove('바나나')  # 값으로 제거
removed_fruit = fruits.pop()  # 마지막 요소 제거 및 반환
print(f"제거된 과일: {removed_fruit}")
print(f"남은 과일: {fruits}")

# 리스트 슬라이싱
first_three = numbers[:3]
last_two = numbers[-2:]
middle = numbers[1:4]
print(f"처음 3개: {first_three}")
print(f"마지막 2개: {last_two}")
print(f"중간 요소들: {middle}")

# 리스트 정렬
mixed_numbers = [3, 1, 4, 1, 5, 9, 2, 6]
sorted_asc = sorted(mixed_numbers)  # 오름차순
sorted_desc = sorted(mixed_numbers, reverse=True)  # 내림차순
print(f"오름차순 정렬: {sorted_asc}")
print(f"내림차순 정렬: {sorted_desc}")

# 리스트 필터링 및 변환
even_numbers = [x for x in numbers if x % 2 == 0]
squared_numbers = [x**2 for x in numbers]
print(f"짝수만: {even_numbers}")
print(f"제곱수: {squared_numbers}")'''
    
    def _generate_python_dict_operations(self) -> str:
        """Python 딕셔너리 조작 더미 생성"""
        return '''# Python 딕셔너리 조작 예시

# 딕셔너리 생성
person = {
    '이름': '홍길동',
    '나이': 30,
    '직업': '개발자',
    '취미': ['독서', '영화감상', '코딩']
}

# 딕셔너리 요소 접근 및 수정
print(f"이름: {person['이름']}")
print(f"나이: {person.get('나이', '정보 없음')}")

person['나이'] = 31  # 값 수정
person['거주지'] = '서울'  # 새 키-값 추가
print(f"수정된 정보: {person}")

# 딕셔너리 요소 제거
del person['취미']  # 키로 삭제
removed_value = person.pop('거주지', '기본값')  # 안전한 삭제
print(f"제거된 값: {removed_value}")

# 딕셔너리 순회
for key in person:
    print(f"{key}: {person[key]}")

# 키, 값, 항목 접근
print(f"모든 키: {list(person.keys())}")
print(f"모든 값: {list(person.values())}")
print(f"모든 항목: {list(person.items())}")

# 딕셔너리 병합 (Python 3.9+)
additional_info = {'학력': '대학교 졸업', '경력': '5년'}
merged_person = person | additional_info
print(f"병합된 정보: {merged_person}")

# 딕셔너리 컴프리헨션
squared_dict = {x: x**2 for x in range(1, 6)}
print(f"제곱수 딕셔너리: {squared_dict}")'''
    
    def _generate_python_file_operations(self) -> str:
        """Python 파일 조작 더미 생성"""
        return '''# Python 파일 조작 예시
import os
from pathlib import Path

def read_text_file(file_path):
    """텍스트 파일을 읽어서 내용을 반환합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {file_path}")
        return None
    except Exception as e:
        print(f"파일 읽기 오류: {e}")
        return None

def write_text_file(file_path, content):
    """텍스트 파일에 내용을 씁니다."""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"파일 저장 완료: {file_path}")
        return True
    except Exception as e:
        print(f"파일 쓰기 오류: {e}")
        return False

def append_to_file(file_path, content):
    """파일에 내용을 추가합니다."""
    try:
        with open(file_path, 'a', encoding='utf-8') as file:
            file.write(content)
        return True
    except Exception as e:
        print(f"파일 추가 오류: {e}")
        return False

# 파일 및 디렉토리 정보 확인
def check_file_info(path):
    """파일 또는 디렉토리 정보를 확인합니다."""
    path_obj = Path(path)
    
    if path_obj.exists():
        print(f"경로 존재: {path}")
        print(f"파일 여부: {path_obj.is_file()}")
        print(f"디렉토리 여부: {path_obj.is_dir()}")
        
        if path_obj.is_file():
            print(f"파일 크기: {path_obj.stat().st_size} bytes")
            print(f"확장자: {path_obj.suffix}")
    else:
        print(f"경로가 존재하지 않습니다: {path}")

# 사용 예시
sample_content = """이것은 샘플 텍스트 파일입니다.
여러 줄의 내용을 포함하고 있습니다.
Python에서 파일을 다루는 예시입니다."""

write_text_file('sample.txt', sample_content)
read_content = read_text_file('sample.txt')
print(f"읽은 내용:\\n{read_content}")'''
    
    def _generate_python_api_code(self) -> str:
        """Python API 관련 더미 코드 생성"""
        return '''# Python API 요청 예시
import requests
import json
from typing import Optional, Dict, Any

class APIClient:
    """간단한 API 클라이언트 클래스"""
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        API 클라이언트 초기화
        
        Args:
            base_url (str): API의 기본 URL
            timeout (int): 요청 타임아웃 (초)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 요청을 보냅니다."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"GET 요청 실패: {e}")
            return {"error": str(e)}
    
    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST 요청을 보냅니다."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"POST 요청 실패: {e}")
            return {"error": str(e)}

# 사용 예시
def fetch_user_data(user_id: int):
    """사용자 데이터를 가져오는 함수"""
    api_client = APIClient('https://jsonplaceholder.typicode.com')
    
    # 사용자 정보 가져오기
    user_data = api_client.get(f'/users/{user_id}')
    
    if 'error' not in user_data:
        print(f"사용자 이름: {user_data.get('name')}")
        print(f"이메일: {user_data.get('email')}")
        return user_data
    else:
        print("사용자 데이터를 가져올 수 없습니다.")
        return None

# 실행 예시
user = fetch_user_data(1)
if user:
    print(f"가져온 사용자 데이터: {json.dumps(user, indent=2, ensure_ascii=False)}")'''
    
    def _generate_basic_python_code(self) -> str:
        """기본 Python 코드 더미 생성"""
        return '''# 기본 Python 코드 예시

def main():
    """메인 함수"""
    print("안녕하세요! Python 코딩 어시스턴트입니다.")
    
    # 변수 선언 및 사용
    message = "AI가 생성한 Python 코드입니다."
    numbers = [1, 2, 3, 4, 5]
    
    # 리스트 처리
    total = sum(numbers)
    average = total / len(numbers)
    
    print(f"메시지: {message}")
    print(f"숫자 리스트: {numbers}")
    print(f"합계: {total}")
    print(f"평균: {average:.2f}")
    
    # 간단한 계산
    result = calculate_square(5)
    print(f"5의 제곱: {result}")

def calculate_square(number):
    """숫자의 제곱을 계산합니다."""
    return number ** 2

# 스크립트가 직접 실행될 때만 main 함수 호출
if __name__ == "__main__":
    main()'''

    def complete_code(self, prefix: str, language: str = "python", max_suggestions: int = 3) -> list[str]:
        """
        Python 코드 자동 완성 제안을 생성합니다.
        
        Args:
            prefix: 완성할 코드 접두사
            language: 프로그래밍 언어 (python 고정)
            max_suggestions: 최대 제안 개수
            
        Returns:
            Python 코드 완성 제안 리스트
        """
        if not self.model_loaded:
            raise Exception("AI 모델이 로드되지 않았습니다.")
        
        # 언어 검증
        if language and language.lower() != "python":
            raise ValueError("현재 Python 언어만 지원됩니다.")
        
        try:
            # Python 자동 완성 로직
            completions = self._generate_python_completions(prefix, max_suggestions)
            
            logger.info(f"Python 코드 자동 완성 완료 - 제안 수: {len(completions)}")
            return completions
            
        except Exception as e:
            logger.error(f"Python 코드 자동 완성 실패: {e}")
            raise Exception(f"Python 코드 자동 완성 중 오류가 발생했습니다: {e}")

    def _generate_python_completions(self, prefix: str, max_suggestions: int) -> list[str]:
        """Python 자동 완성 더미 로직"""
        suggestions = []
        
        if prefix.startswith("def "):
            suggestions = [
                f"{prefix}():",
                f"{prefix}(self):",
                f"{prefix}(self, *args, **kwargs):",
                f"{prefix}(param1, param2=None):",
            ]
        elif prefix.startswith("class "):
            suggestions = [
                f"{prefix}:",
                f"{prefix}():",
                f"{prefix}(object):",
                f"{prefix}(Exception):",
            ]
        elif prefix.startswith("import "):
            suggestions = [
                f"{prefix}os",
                f"{prefix}sys",
                f"{prefix}json",
                f"{prefix}requests",
            ]
        elif prefix.startswith("from "):
            suggestions = [
                f"{prefix}typing import List, Dict, Optional",
                f"{prefix}datetime import datetime",
                f"{prefix}pathlib import Path",
            ]
        elif prefix.startswith("print"):
            suggestions = [
                f"{prefix}('Hello, World!')",
                f"{prefix}(f'값: {{variable}}')",
                f"{prefix}('디버그:', variable)",
                f"{prefix}(*args, sep=', ')",
            ]
        elif prefix.startswith("for "):
            suggestions = [
                f"{prefix}i in range(10):",
                f"{prefix}item in items:",
                f"{prefix}key, value in dictionary.items():",
            ]
        elif prefix.startswith("if "):
            suggestions = [
                f"{prefix}condition:",
                f"{prefix}variable is not None:",
                f"{prefix}len(items) > 0:",
            ]
        else:
            # 일반적인 Python 코드 제안
            suggestions = [
                f"{prefix}.append()",
                f"{prefix}.strip()",
                f"{prefix}_variable = None",
                f"{prefix}_function()",
            ]
        
        # 최대 제안 개수로 제한
        return suggestions[:max_suggestions]

# 하위 호환성을 위한 별칭
AIModelService = OptimizedAIModelService

# 전역 인스턴스 생성
ai_model_service = AIModelService() 