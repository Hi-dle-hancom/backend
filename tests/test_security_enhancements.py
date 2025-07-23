"""
보안 강화 모듈 테스트
즉시 적용 가능한 보안 테스트들
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import re

from app.core.security_improvements import (
    SecurityEnhancements,
    validate_input,
    generate_api_key,
    check_rate_limit,
    get_security_headers,
    security_enhancer
)


class TestSecurityEnhancements:
    """보안 강화 기능 테스트"""
    
    def setup_method(self):
        """각 테스트 전 초기화"""
        self.security = SecurityEnhancements()
    
    def test_input_validation_success(self):
        """안전한 입력 검증 테스트"""
        safe_inputs = [
            "def hello(): return 'world'",
            "파이썬 함수를 만들어주세요",
            "print('Hello, World!')",
            "import pandas as pd",
            "# 주석입니다",
        ]
        
        for input_data in safe_inputs:
            assert self.security.validate_input_security(input_data) is True
    
    def test_input_validation_xss_detection(self):
        """XSS 공격 패턴 감지 테스트"""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "<script src='evil.js'></script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(HTTPException) as exc_info:
                self.security.validate_input_security(malicious_input)
            assert exc_info.value.status_code == 400
            assert "허용되지 않는 패턴" in str(exc_info.value.detail)
    
    def test_input_validation_sql_injection_detection(self):
        """SQL Injection 공격 감지 테스트"""
        sql_injection_patterns = [
            "'; DROP TABLE users; --",
            "UNION SELECT * FROM passwords",
            "1' OR '1'='1",
            "admin'--",
            "1; DROP TABLE orders",
        ]
        
        for sql_pattern in sql_injection_patterns:
            with pytest.raises(HTTPException) as exc_info:
                self.security.validate_input_security(sql_pattern)
            assert exc_info.value.status_code == 400
    
    def test_input_validation_code_injection_detection(self):
        """코드 실행 공격 감지 테스트"""
        code_injection_patterns = [
            "exec('malicious code')",
            "eval(user_input)",
            "__import__('os').system('rm -rf /')",
            "compile(malicious_code, '<string>', 'exec')",
        ]
        
        for code_pattern in code_injection_patterns:
            with pytest.raises(HTTPException) as exc_info:
                self.security.validate_input_security(code_pattern)
            assert exc_info.value.status_code == 400
    
    def test_input_validation_size_limit(self):
        """입력 크기 제한 테스트"""
        # 50KB 초과 데이터
        large_input = "A" * 50001
        
        with pytest.raises(HTTPException) as exc_info:
            self.security.validate_input_security(large_input)
        assert exc_info.value.status_code == 413
        assert "너무 큽니다" in str(exc_info.value.detail)
    
    def test_api_key_generation(self):
        """API 키 생성 테스트"""
        api_key = self.security.generate_secure_api_key()
        
        # 형식 검증
        assert api_key.startswith("hapa_")
        assert len(api_key) > 50  # 충분한 길이
        
        # 패턴 검증
        pattern = r'^hapa_\d{8}_[a-f0-9]{16}_[a-f0-9]{32}$'
        assert re.match(pattern, api_key) is not None
        
        # 고유성 검증 (여러 번 생성해서 다른지 확인)
        api_key2 = self.security.generate_secure_api_key()
        assert api_key != api_key2
    
    def test_api_key_validation_success(self):
        """유효한 API 키 검증 테스트"""
        valid_key = self.security.generate_secure_api_key()
        assert self.security.validate_api_key_format(valid_key) is True
    
    def test_api_key_validation_failure(self):
        """잘못된 API 키 검증 테스트"""
        invalid_keys = [
            "",  # 빈 문자열
            "short_key",  # 너무 짧음
            "wrong_prefix_20241228_abc123_def456",  # 잘못된 접두사
            "hapa_invalid_format",  # 잘못된 형식
            "hapa_20241228",  # 불완전한 키
        ]
        
        for invalid_key in invalid_keys:
            assert self.security.validate_api_key_format(invalid_key) is False
    
    def test_rate_limiting_normal_usage(self):
        """정상적인 Rate Limiting 테스트"""
        identifier = "test_user_1"
        
        # 정상 범위 내 요청 (10회)
        for i in range(10):
            assert self.security.advanced_rate_limiting(identifier, max_requests=50) is True
    
    def test_rate_limiting_exceeded(self):
        """Rate Limiting 초과 테스트"""
        identifier = "test_user_2"
        max_requests = 5
        
        # 한도까지 요청
        for i in range(max_requests):
            self.security.advanced_rate_limiting(identifier, max_requests=max_requests)
        
        # 한도 초과 시 예외 발생
        with pytest.raises(HTTPException) as exc_info:
            self.security.advanced_rate_limiting(identifier, max_requests=max_requests)
        assert exc_info.value.status_code == 429
        assert "요청 한도 초과" in str(exc_info.value.detail)
    
    def test_ip_blocking_mechanism(self):
        """IP 차단 메커니즘 테스트"""
        identifier = "test_user_3"
        max_requests = 5
        
        # 극도로 많은 요청으로 IP 차단 유도
        self.security.rate_limit_tracker[identifier] = [
            datetime.now() for _ in range(max_requests * 3)
        ]
        
        with pytest.raises(HTTPException):
            self.security.advanced_rate_limiting(identifier, max_requests=max_requests)
        
        # IP가 차단 목록에 추가되었는지 확인
        assert identifier in self.security.blocked_ips
    
    def test_code_sanitization(self):
        """코드 입력 정제 테스트"""
        dangerous_code = """
import os
exec('print("hello")')
eval('1+1')
os.system('ls')
subprocess.call(['echo', 'test'])
"""
        
        sanitized = self.security.sanitize_code_input(dangerous_code)
        
        # 위험한 함수들이 주석 처리되었는지 확인
        assert "# BLOCKED: exec(" in sanitized
        assert "# BLOCKED: eval(" in sanitized
        assert "os.system" in sanitized  # os.system은 패턴이 다르므로 별도 처리 필요
        
    def test_session_id_generation(self):
        """세션 ID 생성 테스트"""
        session_id = self.security.generate_secure_session_id()
        
        # 형식 검증
        assert session_id.startswith("sess_")
        assert len(session_id) > 80  # 충분한 길이
        
        # 고유성 검증
        session_id2 = self.security.generate_secure_session_id()
        assert session_id != session_id2
    
    def test_file_upload_validation_success(self):
        """안전한 파일 업로드 검증 테스트"""
        safe_files = [
            ("test.py", b"print('hello')"),
            ("readme.txt", b"This is a readme file"),
            ("config.json", b'{"key": "value"}'),
            ("data.yml", b"key: value"),
        ]
        
        for filename, content in safe_files:
            assert self.security.validate_file_upload_security(filename, content) is True
    
    def test_file_upload_validation_extension_blocked(self):
        """위험한 파일 확장자 차단 테스트"""
        dangerous_files = [
            ("virus.exe", b"executable content"),
            ("script.sh", b"#!/bin/bash\necho hello"),
            ("page.html", b"<html><body>content</body></html>"),
            ("app.js", b"console.log('hello')"),
        ]
        
        for filename, content in dangerous_files:
            with pytest.raises(HTTPException) as exc_info:
                self.security.validate_file_upload_security(filename, content)
            assert exc_info.value.status_code == 400
            assert "허용되지 않는 파일 형식" in str(exc_info.value.detail)
    
    def test_file_upload_validation_size_limit(self):
        """파일 크기 제한 테스트"""
        large_content = b"A" * (11 * 1024 * 1024)  # 11MB
        
        with pytest.raises(HTTPException) as exc_info:
            self.security.validate_file_upload_security("large.txt", large_content)
        assert exc_info.value.status_code == 413
        assert "파일 크기가 너무 큽니다" in str(exc_info.value.detail)
    
    def test_file_upload_validation_malicious_content(self):
        """악성 파일 내용 감지 테스트"""
        malicious_content = b"<script>alert('xss')</script>"
        
        with pytest.raises(HTTPException) as exc_info:
            self.security.validate_file_upload_security("test.txt", malicious_content)
        assert exc_info.value.status_code == 400
        assert "의심스러운 패턴" in str(exc_info.value.detail)
    
    def test_security_headers_generation(self):
        """보안 헤더 생성 테스트"""
        headers = self.security.create_security_headers()
        
        # 필수 보안 헤더들 확인
        required_headers = [
            "Strict-Transport-Security",
            "X-Content-Type-Options", 
            "X-XSS-Protection",
            "X-Frame-Options",
            "Content-Security-Policy",
        ]
        
        for header in required_headers:
            assert header in headers
            assert headers[header]  # 빈 값이 아닌지 확인
        
        # 특정 헤더 값 검증
        assert "max-age=" in headers["Strict-Transport-Security"]
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"


class TestSecurityIntegration:
    """보안 기능 통합 테스트"""
    
    def test_convenience_functions(self):
        """편의 함수들 테스트"""
        # validate_input 함수
        assert validate_input("safe input") is True
        
        with pytest.raises(HTTPException):
            validate_input("<script>alert('xss')</script>")
        
        # generate_api_key 함수
        api_key = generate_api_key()
        assert api_key.startswith("hapa_")
        
        # get_security_headers 함수
        headers = get_security_headers()
        assert "X-Content-Type-Options" in headers
    
    def test_rate_limiting_convenience_function(self):
        """Rate Limiting 편의 함수 테스트"""
        identifier = "test_convenience"
        
        # 정상 요청
        assert check_rate_limit(identifier, max_requests=10) is True
        
        # 여러 번 요청 후 한도 초과
        for _ in range(10):
            check_rate_limit(identifier, max_requests=10)
        
        with pytest.raises(HTTPException):
            check_rate_limit(identifier, max_requests=10)
    
    def test_multiple_identifiers_isolation(self):
        """여러 식별자 간 격리 테스트"""
        # 서로 다른 식별자는 독립적으로 처리되어야 함
        user1 = "user1"
        user2 = "user2"
        
        # user1이 한도 초과
        for _ in range(5):
            check_rate_limit(user1, max_requests=5)
        
        with pytest.raises(HTTPException):
            check_rate_limit(user1, max_requests=5)
        
        # user2는 여전히 정상 작동해야 함
        assert check_rate_limit(user2, max_requests=5) is True


class TestSecurityPerformance:
    """보안 기능 성능 테스트"""
    
    def test_input_validation_performance(self):
        """입력 검증 성능 테스트"""
        import time
        
        large_safe_input = "safe_text " * 1000  # 반복되는 안전한 텍스트
        
        start_time = time.time()
        for _ in range(100):
            validate_input(large_safe_input)
        end_time = time.time()
        
        # 100회 검증이 1초 이내에 완료되어야 함
        assert (end_time - start_time) < 1.0
    
    def test_api_key_generation_performance(self):
        """API 키 생성 성능 테스트"""
        import time
        
        start_time = time.time()
        keys = [generate_api_key() for _ in range(100)]
        end_time = time.time()
        
        # 100개 키 생성이 1초 이내에 완료되어야 함
        assert (end_time - start_time) < 1.0
        
        # 모든 키가 고유한지 확인
        assert len(set(keys)) == 100 