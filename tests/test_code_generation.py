import pytest
from fastapi.testclient import TestClient
from main import app

class TestCodeGeneration:
    """코드 생성 엔드포인트 테스트 클래스"""
    
    def setup_method(self):
        """각 테스트 전에 실행되는 설정"""
        self.client = TestClient(app)
        # 테스트용 API Key 설정 (security.py에서 허용됨)
        self.headers = {
            "X-API-Key": "test_api_key_for_testing",
            "Content-Type": "application/json"
        }
    
    def test_root_endpoint(self):
        """루트 엔드포인트 테스트"""
        response = self.client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()
    
    def test_generate_python_function_success(self):
        """Python 함수 생성 성공 테스트"""
        data = {
            "user_question": "파이썬 함수를 만들어줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=data, headers=self.headers)
        assert response.status_code == 200
        
        response_data = response.json()
        assert "generated_code" in response_data
        assert "status" in response_data
        assert response_data["status"] == "success"
        assert len(response_data["generated_code"]) > 0
        assert "def" in response_data["generated_code"]
        # AI 모델이 생성한 함수가 유효한 Python 함수인지 확인
        assert ":" in response_data["generated_code"]  # 함수 정의 구문
        assert "explanation" in response_data
        # error_message가 None이거나 없는지 확인
        assert response_data.get("error_message") is None
    
    def test_generate_python_class_success(self):
        """Python 클래스 생성 성공 테스트"""
        request_data = {
            "user_question": "Python 클래스를 만들어줘",
            "code_context": "# 기존 코드\nprint('hello')",
            "language": "python",
            "file_path": "/path/to/test.py"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "generated_code" in response_data
        assert len(response_data["generated_code"]) > 0
        assert "class" in response_data["generated_code"]
        assert "__init__" in response_data["generated_code"]
    
    def test_generate_python_loop(self):
        """Python 반복문 생성 테스트"""
        request_data = {
            "user_question": "Python 반복문을 만들어줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "for" in response_data["generated_code"]
    
    def test_generate_python_list_operations(self):
        """Python 리스트 조작 코드 생성 테스트"""
        request_data = {
            "user_question": "Python 리스트 조작 방법을 알려줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert ("list" in response_data["generated_code"].lower() or 
                "리스트" in response_data["generated_code"])
    
    def test_generate_python_with_default_language(self):
        """언어 필드 없이 Python 코드 생성 테스트 (기본값 적용)"""
        request_data = {
            "user_question": "함수를 만들어줘"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "def" in response_data["generated_code"]
    
    def test_generate_code_empty_question(self):
        """빈 질문으로 코드 생성 테스트 (실패 케이스)"""
        request_data = {
            "user_question": "",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # Pydantic 유효성 검사에 의해 422 오류 발생
        assert response.status_code == 422
    
    def test_generate_code_missing_question(self):
        """질문 필드 누락 테스트 (실패 케이스)"""
        request_data = {
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # 필수 필드 누락으로 422 오류 발생
        assert response.status_code == 422
    
    def test_generate_code_long_question(self):
        """너무 긴 질문 테스트 (실패 케이스)"""
        request_data = {
            "user_question": "x" * 10001,  # 최대 길이(10000) 초과
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # 길이 제한 초과로 422 오류 발생
        assert response.status_code == 422
    
    def test_generate_code_unsupported_language(self):
        """지원하지 않는 언어 테스트 (실패 케이스)"""
        request_data = {
            "user_question": "함수를 만들어줘",
            "language": "javascript"  # Python 이외의 언어
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # 지원하지 않는 언어로 422 오류 발생
        assert response.status_code == 422

    def test_generate_code_with_comment_trigger_triple_slash(self):
        """/// prompt: 형태 주석 트리거로 코드 생성 테스트"""
        request_data = {
            "user_question": "/// prompt: 파이썬 함수를 만들어줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "def" in response_data["generated_code"]
    
    def test_generate_code_with_comment_trigger_at_gen(self):
        """@gen: 형태 주석 트리거로 코드 생성 테스트"""
        request_data = {
            "user_question": "@gen: Python 반복문을 작성해줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "for" in response_data["generated_code"]
    
    def test_generate_code_with_comment_trigger_hash_prompt(self):
        """# prompt: 형태 주석 트리거로 코드 생성 테스트"""
        request_data = {
            "user_question": "# prompt: Python 클래스를 생성해줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "class" in response_data["generated_code"]
        assert "__init__" in response_data["generated_code"]

    def test_generate_code_with_markdown_parsing(self):
        """마크다운 형태 응답 파싱 테스트"""
        request_data = {
            "user_question": "마크다운 형태로 Python 함수를 만들어줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "def" in response_data["generated_code"]
        assert response_data["explanation"] is not None
        assert "마크다운" in response_data["explanation"]

    def test_generate_code_with_multiple_blocks(self):
        """여러 코드 블록 처리 테스트"""
        request_data = {
            "user_question": "멀티블록 형태로 Python 함수를 만들어줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert response_data["generated_code"] != ""
        assert response_data["explanation"] is not None
        assert "멀티블록" in response_data["explanation"]

    def test_generate_code_with_error_pattern(self):
        """AI 모델 오류 패턴 처리 테스트"""
        request_data = {
            "user_question": "오류를 발생시켜줘",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "error"
        assert response_data["generated_code"] == ""
        assert response_data["explanation"] is None
        assert response_data["error_message"] is not None

    def test_generate_code_validation_error(self):
        """유효성 검사 오류 표준 응답 테스트"""
        request_data = {
            "user_question": "",  # 빈 질문 (유효성 검사 실패)
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 422
        response_data = response.json()
        
        # 표준 오류 응답 형식 확인
        assert response_data["status"] == "error"
        assert "error_message" in response_data
        assert "error_code" in response_data
        assert response_data["error_code"] == "VALIDATION_ERROR"
        assert "error_details" in response_data

    def test_generate_code_invalid_language(self):
        """지원하지 않는 언어 오류 처리 테스트"""
        request_data = {
            "user_question": "함수를 만들어줘",
            "language": "javascript"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        assert response.status_code == 422
        response_data = response.json()
        
        assert response_data["status"] == "error"
        assert "Python 언어만 지원" in response_data["error_message"]

    def test_generate_code_empty_question_http_error(self):
        """빈 질문으로 인한 HTTP 오류 테스트"""
        request_data = {
            "user_question": "   ",  # 공백만 있는 질문
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # 400 오류나 성공적인 처리 (공백 제거 후 빈 문자열)
        if response.status_code == 400:
            response_data = response.json()
            assert response_data["status"] == "error"
            assert "error_message" in response_data
        else:
            # 유효성 검사에서 처리되는 경우
            assert response.status_code == 422

class TestCodeCompletion:
    """Python 코드 자동 완성 API 테스트 클래스"""
    
    def test_complete_python_function_success(self):
        """Python 함수 자동 완성 성공 테스트"""
        request_data = {
            "prefix": "def hello",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert "completions" in response_data
        assert isinstance(response_data["completions"], list)
        assert len(response_data["completions"]) > 0
        assert response_data["error_message"] is None
        
        # 모든 완성 제안이 prefix를 포함하는지 확인
        for completion in response_data["completions"]:
            assert "def hello" in completion
    
    def test_complete_python_class_success(self):
        """Python 클래스 자동 완성 성공 테스트"""
        request_data = {
            "prefix": "class Test",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert len(response_data["completions"]) > 0
    
    def test_complete_python_import_success(self):
        """Python import 자동 완성 성공 테스트"""
        request_data = {
            "prefix": "import ",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert len(response_data["completions"]) > 0
    
    def test_complete_code_with_cursor_position(self):
        """커서 위치가 있는 Python 코드 자동 완성 테스트"""
        request_data = {
            "prefix": "print",
            "language": "python",
            "cursor_position": 5,
            "file_path": "/test/file.py"
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert len(response_data["completions"]) > 0
    
    def test_complete_code_with_default_language(self):
        """언어 필드 없이 Python 코드 자동 완성 테스트 (기본값 적용)"""
        request_data = {
            "prefix": "def test"
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["status"] == "success"
        assert len(response_data["completions"]) > 0
    
    def test_complete_code_empty_prefix(self):
        """빈 접두사로 코드 자동 완성 테스트 (실패 케이스)"""
        request_data = {
            "prefix": "",
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        # Pydantic 유효성 검사에 의해 422 오류 발생
        assert response.status_code == 422
    
    def test_complete_code_unsupported_language(self):
        """지원하지 않는 언어로 자동 완성 테스트 (실패 케이스)"""
        request_data = {
            "prefix": "function test",
            "language": "javascript"  # Python 이외의 언어
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        # 지원하지 않는 언어로 422 오류 발생
        assert response.status_code == 422
    
    def test_complete_code_negative_cursor_position(self):
        """음수 커서 위치 테스트 (실패 케이스)"""
        request_data = {
            "prefix": "def hello",
            "language": "python",
            "cursor_position": -1
        }
        
        response = self.client.post("/api/v1/code/complete", json=request_data, headers=self.headers)
        
        # 음수 값으로 422 오류 발생
        assert response.status_code == 422

class TestValidation:
    """데이터 유효성 검사 테스트 클래스"""
    
    def test_invalid_file_path_characters(self):
        """유효하지 않은 파일 경로 문자 테스트"""
        request_data = {
            "user_question": "Python 함수를 만들어줘",
            "language": "python",
            "file_path": "/invalid<path>with|special*chars?"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # 유효하지 않은 파일 경로 문자로 422 오류 발생
        assert response.status_code == 422
    
    def test_python_file_extension_allowed(self):
        """.py 확장자 파일 경로 테스트"""
        request_data = {
            "user_question": "Python 함수를 만들어줘",
            "language": "python",
            "file_path": "/path/to/script.py"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # .py 확장자는 허용되므로 성공해야 함
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
    
    def test_non_python_file_extension_allowed(self):
        """Python 이외 확장자도 허용되는지 테스트"""
        request_data = {
            "user_question": "Python 함수를 만들어줘",
            "language": "python",
            "file_path": "/path/to/script.txt"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # Python 이외 확장자도 허용하므로 성공해야 함
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
    
    def test_very_long_code_context(self):
        """매우 긴 코드 컨텍스트 테스트"""
        request_data = {
            "user_question": "Python 함수를 만들어줘",
            "code_context": "x" * 50001,  # 최대 길이(50000) 초과
            "language": "python"
        }
        
        response = self.client.post("/api/v1/code/generate", json=request_data, headers=self.headers)
        
        # 길이 제한 초과로 422 오류 발생
        assert response.status_code == 422 