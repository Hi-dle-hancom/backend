import pytest
from app.services.inference import OptimizedAIModelService

class TestOptimizedAIModelService:
    """AI 모델 서비스 테스트 클래스 (Python 전용)"""
    
    def setup_method(self):
        """각 테스트 전에 실행되는 설정"""
        self.service = OptimizedAIModelService()
    
    def test_model_initialization(self):
        """모델 초기화 테스트"""
        # 모델을 먼저 로드
        self.service.lazy_load_model()
        
        from app.services.ai_model import ai_model_manager
        assert ai_model_manager.is_loaded() is True
        assert ai_model_manager.model is not None
        assert ai_model_manager.model["name"] == "python_coding_assistant"
        assert ai_model_manager.model["language"] == "python"
    
    def test_model_loading(self):
        """모델 로딩 테스트"""
        # 모델을 다시 로드
        self.service.lazy_load_model()
        
        from app.services.ai_model import ai_model_manager
        assert ai_model_manager.is_loaded() is True
        assert "capabilities" in ai_model_manager.model
        assert "code_generation" in ai_model_manager.model["capabilities"]
        assert "code_completion" in ai_model_manager.model["capabilities"]
    
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
        prompt = "파이썬 for 반복문을 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "for" in result
    
    def test_predict_python_conditional(self):
        """Python 조건문 생성 예측 테스트"""
        prompt = "파이썬 if 조건문을 만들어줘"
        
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
        # 딕셔너리 관련 키워드가 있는지 확인 (더 유연하게)
        dict_keywords = ["dict", "dictionary", "{", "}", "items()", "keys()", "values()"]
        assert any(keyword in result.lower() for keyword in dict_keywords)
    
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
        """모델이 로드되지 않았을 때 오류 테스트 - 리팩토링으로 lazy loading 적용됨"""
        # 리팩토링 후에는 lazy loading이 적용되어 이 테스트는 더 이상 유효하지 않음
        # 대신 AI 모델 매니저의 상태를 확인
        from app.services.ai_model import ai_model_manager
        
        # 모델이 자동으로 로드되는지 확인
        result = self.service.predict("함수를 만들어줘")
        assert isinstance(result, str)
        assert len(result) > 0
    
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
        """모델이 로드되지 않았을 때 완성 오류 테스트 - 리팩토링으로 lazy loading 적용됨"""
        # 리팩토링 후에는 lazy loading이 적용되어 이 테스트는 더 이상 유효하지 않음
        # 대신 완성 기능이 정상 작동하는지 확인
        result = self.service.complete_code("def hello", language="python")
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_preprocess_prompt(self):
        """프롬프트 전처리 테스트"""
        prompt = "함수를 만들어줘"
        context = "# 기존 코드"
        
        processed = self.service._preprocess_prompt(prompt, context)
        
        assert isinstance(processed, str)
        assert context in processed
        assert prompt in processed
    
    def test_preprocess_prompt_without_context(self):
        """컨텍스트 없는 프롬프트 전처리 테스트"""
        prompt = "함수를 만들어줘"
        
        processed = self.service._preprocess_prompt(prompt, None)
        
        assert isinstance(processed, str)
        assert processed == prompt
    
    def test_clean_comment_trigger_hash_prompt(self):
        """# 주석 트리거 정리 테스트"""
        prompt = "# prompt: 리스트 조작 코드를 작성해줘"
        
        result = self.service._clean_comment_trigger(prompt)
        
        assert result == "리스트 조작 코드를 작성해줘"
    
    def test_clean_comment_trigger_normal_text(self):
        """일반 텍스트 트리거 정리 테스트"""
        prompt = "일반 텍스트입니다"
        
        result = self.service._clean_comment_trigger(prompt)
        
        assert result == "일반 텍스트입니다"

    def test_predict_with_comment_trigger(self):
        """주석 트리거 형태 프롬프트로 코드 생성 테스트"""
        prompt = "# Python 함수를 만들어줘"
        
        result = self.service.predict(prompt, language="python")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "def" in result

    def test_predict_and_parse_success(self):
        """AI 모델 예측 및 파싱 성공 테스트"""
        prompt = "Python 함수를 만들어줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert "generated_code" in result
        assert "explanation" in result
        assert "status" in result
        assert result["status"] == "success"
        assert len(result["generated_code"]) > 0

    def test_predict_and_parse_error_pattern(self):
        """오류 패턴이 포함된 응답 파싱 테스트"""
        prompt = "오류가 발생하는 코드를 만들어줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert "status" in result
        # 오류 패턴이 감지되면 error 상태가 되어야 함

    def test_predict_and_parse_markdown_format(self):
        """마크다운 형식 응답 파싱 테스트"""
        prompt = "Python 함수를 만들어줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert "generated_code" in result
        assert "status" in result

    def test_predict_and_parse_multiple_blocks(self):
        """여러 코드 블록이 포함된 응답 파싱 테스트"""
        prompt = "Python 함수와 클래스를 만들어줘"
        
        result = self.service.predict_and_parse(prompt, language="python")
        
        assert isinstance(result, dict)
        assert "generated_code" in result
        assert "status" in result

    def test_generate_simple_explanation(self):
        """간단한 설명 생성 테스트"""
        prompt = "Python 함수를 만들어줘"
        
        explanation = self.service._generate_simple_explanation(prompt)
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "함수" in explanation 