import pytest
from app.services.inference import AIModelService

class TestAIModelService:
    """AI 모델 서비스 테스트 클래스 (Python 전용)"""
    
    def setup_method(self):
        """각 테스트 전에 실행되는 설정"""
        self.service = AIModelService()
    
    def test_model_initialization(self):
        """모델 초기화 테스트"""
        assert self.service.model_loaded is True
        assert self.service.model is not None
        assert self.service.model["name"] == "python_coding_assistant"
        assert self.service.model["language"] == "python"
    
    def test_model_loading(self):
        """모델 로딩 테스트"""
        # 모델을 다시 로드
        self.service.load_model()
        
        assert self.service.model_loaded is True
        assert "capabilities" in self.service.model
        assert "code_generation" in self.service.model["capabilities"]
        assert "code_completion" in self.service.model["capabilities"]
    
    def test_predict_python_function(self):
        """Python 함수 생성 예측 테스트"""
        prompt = "파이썬 함수를 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "def" in result
    
    def test_predict_python_class(self):
        """Python 클래스 생성 예측 테스트"""
        prompt = "파이썬 클래스를 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "class" in result
        assert "__init__" in result
    
    def test_predict_python_loop(self):
        """Python 반복문 생성 예측 테스트"""
        prompt = "파이썬 반복문을 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "for" in result
    
    def test_predict_python_conditional(self):
        """Python 조건문 생성 예측 테스트"""
        prompt = "파이썬 조건문을 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "if" in result
    
    def test_predict_python_list_operations(self):
        """Python 리스트 조작 코드 생성 예측 테스트"""
        prompt = "파이썬 리스트 조작 방법을 알려줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert ("list" in result.lower() or "리스트" in result)
    
    def test_predict_python_dict_operations(self):
        """Python 딕셔너리 조작 코드 생성 예측 테스트"""
        prompt = "파이썬 딕셔너리 조작 방법을 알려줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "dict" in result.lower() or "dictionary" in result.lower()
    
    def test_predict_python_file_operations(self):
        """Python 파일 조작 코드 생성 예측 테스트"""
        prompt = "파이썬 파일 처리 방법을 알려줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "file" in result.lower()
        assert "open" in result.lower()
    
    def test_predict_python_api_code(self):
        """Python API 코드 생성 예측 테스트"""
        prompt = "파이썬 API 요청 코드를 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "requests" in result.lower() or "api" in result.lower()
    
    def test_predict_with_context(self):
        """컨텍스트가 있는 Python 코드 생성 테스트"""
        prompt = "함수를 추가해줘"
        context = "# 기존 코드\nprint('Hello')"
        
        result = self.service.predict(prompt, context=context, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_predict_default_language(self):
        """기본 언어(Python)로 코드 생성 테스트"""
        prompt = "간단한 함수를 만들어줘"
        
        result = self.service.predict(prompt)  # language 파라미터 생략
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_predict_unsupported_language_error(self):
        """지원하지 않는 언어 사용 시 오류 테스트"""
        prompt = "함수를 만들어줘"
        
        with pytest.raises(ValueError, match="현재 Python 언어만 지원됩니다"):
            self.service.predict(prompt, language="javascript")
    
    def test_predict_model_not_loaded_error(self):
        """모델이 로드되지 않았을 때 오류 테스트"""
        self.service.model_loaded = False
        
        with pytest.raises(Exception, match="AI 모델이 로드되지 않았습니다"):
            self.service.predict("함수를 만들어줘")
    
    def test_complete_python_function_prefix(self):
        """Python 함수 접두사 자동 완성 테스트"""
        prefix = "def hello"
        
        result = self.service.complete_code(prefix, language="python")
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        # 모든 완성 제안이 접두사를 포함하는지 확인
        for suggestion in result:
            assert prefix in suggestion
    
    def test_complete_python_class_prefix(self):
        """Python 클래스 접두사 자동 완성 테스트"""
        prefix = "class Test"
        
        result = self.service.complete_code(prefix, language="python")
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        for suggestion in result:
            assert prefix in suggestion
    
    def test_complete_python_import_prefix(self):
        """Python import 접두사 자동 완성 테스트"""
        prefix = "import "
        
        result = self.service.complete_code(prefix, language="python")
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_complete_python_print_prefix(self):
        """Python print 접두사 자동 완성 테스트"""
        prefix = "print"
        
        result = self.service.complete_code(prefix, language="python")
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_complete_python_for_prefix(self):
        """Python for 접두사 자동 완성 테스트"""
        prefix = "for "
        
        result = self.service.complete_code(prefix, language="python")
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_complete_python_if_prefix(self):
        """Python if 접두사 자동 완성 테스트"""
        prefix = "if "
        
        result = self.service.complete_code(prefix, language="python")
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_complete_python_general_prefix(self):
        """일반적인 Python 접두사 자동 완성 테스트"""
        prefix = "variable"
        
        result = self.service.complete_code(prefix, language="python")
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_complete_with_max_suggestions(self):
        """최대 제안 수 제한 테스트"""
        prefix = "def test"
        max_suggestions = 2
        
        result = self.service.complete_code(prefix, language="python", max_suggestions=max_suggestions)
        
        assert isinstance(result, list)
        assert len(result) <= max_suggestions
    
    def test_complete_default_language(self):
        """기본 언어(Python)로 자동 완성 테스트"""
        prefix = "def hello"
        
        result = self.service.complete_code(prefix)  # language 파라미터 생략
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_complete_unsupported_language_error(self):
        """지원하지 않는 언어로 자동 완성 시 오류 테스트"""
        prefix = "function test"
        
        with pytest.raises(ValueError, match="현재 Python 언어만 지원됩니다"):
            self.service.complete_code(prefix, language="javascript")
    
    def test_complete_model_not_loaded_error(self):
        """모델이 로드되지 않았을 때 자동 완성 오류 테스트"""
        self.service.model_loaded = False
        
        with pytest.raises(Exception, match="AI 모델이 로드되지 않았습니다"):
            self.service.complete_code("def hello")
    
    def test_preprocess_prompt(self):
        """프롬프트 전처리 테스트"""
        prompt = "함수를 만들어줘"
        context = "# 기존 코드"
        
        processed = self.service._preprocess_prompt(prompt, context)
        
        assert isinstance(processed, str)
        assert "Python 코드 생성 요청" in processed
        assert prompt in processed
        assert context in processed
    
    def test_preprocess_prompt_without_context(self):
        """컨텍스트 없는 프롬프트 전처리 테스트"""
        prompt = "함수를 만들어줘"
        
        processed = self.service._preprocess_prompt(prompt, None)
        
        assert isinstance(processed, str)
        assert "Python 코드 생성 요청" in processed
        assert prompt in processed
    
    def test_generate_python_function_method(self):
        """Python 함수 생성 메서드 테스트"""
        result = self.service._generate_python_function()
        
        assert isinstance(result, str)
        assert "def" in result
        assert "fibonacci" in result.lower()
    
    def test_generate_python_class_method(self):
        """Python 클래스 생성 메서드 테스트"""
        result = self.service._generate_python_class()
        
        assert isinstance(result, str)
        assert "class" in result
        assert "__init__" in result
    
    def test_generate_basic_python_code_method(self):
        """기본 Python 코드 생성 메서드 테스트"""
        result = self.service._generate_basic_python_code()
        
        assert isinstance(result, str)
        assert "def main" in result
        assert "__name__" in result
    
    def test_clean_comment_trigger_triple_slash_prompt(self):
        """/// prompt: 형태 주석 트리거 정리 테스트"""
        prompt = "/// prompt: 피보나치 함수를 만들어줘"
        
        result = self.service._clean_comment_trigger(prompt)
        
        assert result == "피보나치 함수를 만들어줘"
    
    def test_clean_comment_trigger_at_gen(self):
        """@gen: 형태 주석 트리거 정리 테스트"""
        prompt = "@gen: Python 클래스를 생성해줘"
        
        result = self.service._clean_comment_trigger(prompt)
        
        assert result == "Python 클래스를 생성해줘"
    
    def test_clean_comment_trigger_hash_prompt(self):
        """# prompt: 형태 주석 트리거 정리 테스트"""
        prompt = "# prompt: 리스트 조작 코드를 작성해줘"
        
        result = self.service._clean_comment_trigger(prompt)
        
        assert result == "리스트 조작 코드를 작성해줘"
    
    def test_clean_comment_trigger_multiline(self):
        """여러 줄 주석 트리거 정리 테스트"""
        prompt = """/// prompt: 
        # 데이터베이스 연결 함수를 만들어줘
        # SQLite를 사용하는 함수"""
        
        result = self.service._clean_comment_trigger(prompt)
        
        assert "데이터베이스 연결 함수를 만들어줘 SQLite를 사용하는 함수" in result
    
    def test_clean_comment_trigger_normal_text(self):
        """일반 텍스트는 그대로 유지 테스트"""
        prompt = "피보나치 함수를 만들어줘"
        
        result = self.service._clean_comment_trigger(prompt)
        
        assert result == "피보나치 함수를 만들어줘"
    
    def test_predict_with_comment_trigger(self):
        """주석 트리거 형태 프롬프트로 코드 생성 테스트"""
        prompt = "/// prompt: Python 함수를 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "def" in result

    def test_predict_and_parse_success(self):
        """predict_and_parse 메서드 성공 케이스 테스트"""
        prompt = "Python 함수를 만들어줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "generated_code" in result
        assert "explanation" in result
        assert result["error_message"] is None
        assert "def" in result["generated_code"]

    def test_predict_and_parse_error_pattern(self):
        """predict_and_parse 메서드 오류 패턴 감지 테스트"""
        prompt = "오류를 발생시켜줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["generated_code"] == ""
        assert result["explanation"] is None
        assert result["error_message"] is not None

    def test_predict_and_parse_markdown_format(self):
        """마크다운 형태 응답 파싱 테스트"""
        prompt = "마크다운 형태로 Python 함수를 만들어줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "def" in result["generated_code"]
        assert result["explanation"] is not None

    def test_predict_and_parse_multiple_blocks(self):
        """여러 코드 블록 처리 테스트"""
        prompt = "멀티블록 형태로 Python 함수를 만들어줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["generated_code"] != ""
        # 가장 긴 코드 블록이 선택되어야 함
        assert "def" in result["generated_code"] or "class" in result["generated_code"]

    def test_extract_code_blocks_markdown(self):
        """마크다운 코드 블록 추출 테스트"""
        text = """
다음은 Python 코드입니다:

```python
def hello():
    print("Hello, World!")
```

위 코드를 사용하세요.
"""
        
        code_blocks = self.service._extract_code_blocks(text)
        
        assert len(code_blocks) == 1
        assert "def hello():" in code_blocks[0]
        assert "print(" in code_blocks[0]

    def test_extract_code_blocks_multiple(self):
        """여러 마크다운 코드 블록 추출 테스트"""
        text = """
첫 번째 방법:
```python
def method1():
    return 1
```

두 번째 방법:
```python
def method2():
    return 2
```
"""
        
        code_blocks = self.service._extract_code_blocks(text)
        
        assert len(code_blocks) == 2
        assert "method1" in code_blocks[0]
        assert "method2" in code_blocks[1]

    def test_extract_code_blocks_no_markdown(self):
        """마크다운이 없는 Python 코드 패턴 추출 테스트"""
        text = """
다음은 Python 코드입니다:

def hello():
    print("Hello")
    return True

if __name__ == "__main__":
    hello()
"""
        
        code_blocks = self.service._extract_code_blocks(text)
        
        assert len(code_blocks) >= 1
        assert any("def hello" in block for block in code_blocks)

    def test_select_best_code_block(self):
        """최적 코드 블록 선택 테스트"""
        code_blocks = [
            "print('short')",
            """def longer_function():
    '''더 긴 함수'''
    x = 1
    y = 2
    return x + y""",
            "x = 1"
        ]
        
        best_block = self.service._select_best_code_block(code_blocks)
        
        # 가장 긴 코드 블록이 선택되어야 함
        assert "longer_function" in best_block
        assert "def" in best_block

    def test_is_valid_python_syntax(self):
        """Python 문법 검증 테스트"""
        # 유효한 Python 코드
        valid_code = """def hello():
    print("Hello")
    return True"""
        
        assert self.service._is_valid_python_syntax(valid_code) == True
        
        # 잘못된 Python 코드
        invalid_code = """def hello(:
    print("Hello"
    return True"""
        
        assert self.service._is_valid_python_syntax(invalid_code) == False

    def test_extract_explanation(self):
        """설명 추출 테스트"""
        raw_response = """
다음은 요청하신 Python 함수입니다:

```python
def hello():
    print("Hello")
```

이 함수는 간단한 인사말을 출력합니다.
사용하기 쉽고 효과적인 함수입니다.
"""
        
        code_blocks = ["def hello():\n    print(\"Hello\")"]
        explanation = self.service._extract_explanation(raw_response, code_blocks)
        
        assert explanation is not None
        assert "함수는" in explanation
        assert "```python" not in explanation  # 마크다운 블록 제거됨

    def test_detect_error_patterns(self):
        """오류 패턴 감지 테스트"""
        # 오류 패턴이 있는 응답
        error_response = "ERROR: 모델 처리 중 오류가 발생했습니다."
        assert self.service._detect_error_patterns(error_response) == True
        
        # 정상 응답
        normal_response = "다음은 Python 함수입니다: def hello(): pass"
        assert self.service._detect_error_patterns(normal_response) == False

    def test_extract_error_message(self):
        """오류 메시지 추출 테스트"""
        error_response = "ERROR: 잘못된 프롬프트입니다."
        
        error_message = self.service._extract_error_message(error_response)
        
        assert error_message == "잘못된 프롬프트입니다."

    def test_generate_simple_explanation(self):
        """간단한 설명 생성 테스트"""
        # 함수 관련 프롬프트
        prompt = "Python 함수를 만들어줘"
        explanation = self.service._generate_simple_explanation(prompt)
        assert "함수" in explanation
        
        # 클래스 관련 프롬프트
        prompt = "Python 클래스를 만들어줘"
        explanation = self.service._generate_simple_explanation(prompt)
        assert "클래스" in explanation 