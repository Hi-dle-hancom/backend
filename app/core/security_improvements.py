"""
HAPA 보안 강화 모듈
즉시 적용 가능한 보안 개선사항들
"""

import hashlib
import hmac
import secrets
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import ipaddress
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

class SecurityEnhancements:
    """보안 강화 클래스"""
    
    def __init__(self):
        self.blocked_ips: set = set()
        self.rate_limit_tracker: Dict[str, List[datetime]] = {}
        self.suspicious_patterns = [
            r'<script.*?>.*?</script>',  # XSS 패턴
            r'union.*select.*from',      # SQL Injection 패턴
            r'drop\s+table',             # SQL 위험 구문
            r'exec\s*\(',                # 코드 실행 패턴
            r'eval\s*\(',                # 코드 평가 패턴
        ]
    
    def validate_input_security(self, input_data: str, field_name: str = "input") -> bool:
        """입력 데이터 보안 검증"""
        if not input_data:
            return True
            
        # 길이 제한 검증
        if len(input_data) > 50000:  # 50KB 제한
            raise HTTPException(
                status_code=413,
                detail=f"{field_name}: 입력 데이터가 너무 큽니다 (최대 50KB)"
            )
        
        # 악성 패턴 검사
        for pattern in self.suspicious_patterns:
            if re.search(pattern, input_data.lower()):
                logger.warning(f"의심스러운 패턴 감지: {field_name}")
                raise HTTPException(
                    status_code=400,
                    detail=f"{field_name}: 허용되지 않는 패턴이 감지되었습니다"
                )
        
        return True
    
    def generate_secure_api_key(self, prefix: str = "hapa_") -> str:
        """보안 강화된 API 키 생성"""
        # 32바이트 랜덤 데이터 생성
        random_bytes = secrets.token_bytes(32)
        
        # 타임스탬프 추가 (키 생성 시점 추적)
        timestamp = datetime.now().strftime("%Y%m%d")
        
        # HMAC-SHA256으로 서명
        signature = hmac.new(
            b"HAPA_API_KEY_SECRET_2024",
            random_bytes + timestamp.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        # 최종 API 키 조합
        api_key = f"{prefix}{timestamp}_{signature}_{secrets.token_hex(16)}"
        
        return api_key
    
    def validate_api_key_format(self, api_key: str) -> bool:
        """API 키 형식 검증"""
        if not api_key:
            return False
            
        # 최소 길이 검증
        if len(api_key) < 32:
            return False
            
        # 접두사 검증
        if not api_key.startswith("hapa_"):
            return False
            
        # 패턴 검증 (영숫자와 언더스코어만 허용)
        if not re.match(r'^hapa_\d{8}_[a-f0-9]{16}_[a-f0-9]{32}$', api_key):
            return False
            
        return True
    
    def check_ip_security(self, ip_address: str) -> bool:
        """IP 보안 검증"""
        # 차단된 IP 확인
        if ip_address in self.blocked_ips:
            raise HTTPException(
                status_code=403,
                detail="차단된 IP 주소입니다"
            )
        
        # 사설 IP 대역 확인 (개발환경에서만 허용)
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            if ip_obj.is_private:
                return True  # 개발환경에서는 허용
        except ValueError:
            return False
        
        return True
    
    def advanced_rate_limiting(self, identifier: str, max_requests: int = 100, window_minutes: int = 60) -> bool:
        """고급 Rate Limiting"""
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # 해당 식별자의 요청 기록 초기화
        if identifier not in self.rate_limit_tracker:
            self.rate_limit_tracker[identifier] = []
        
        # 윈도우 시간 이전 요청들 제거
        self.rate_limit_tracker[identifier] = [
            req_time for req_time in self.rate_limit_tracker[identifier]
            if req_time > window_start
        ]
        
        # 현재 요청 수 확인
        current_requests = len(self.rate_limit_tracker[identifier])
        
        if current_requests >= max_requests:
            # IP 차단 (심각한 경우)
            if current_requests > max_requests * 2:
                self.blocked_ips.add(identifier)
                logger.warning(f"IP 차단: {identifier} (과도한 요청)")
            
            raise HTTPException(
                status_code=429,
                detail=f"요청 한도 초과: {window_minutes}분 내 최대 {max_requests}회"
            )
        
        # 현재 요청 기록
        self.rate_limit_tracker[identifier].append(now)
        return True
    
    def sanitize_code_input(self, code: str) -> str:
        """코드 입력 정제"""
        if not code:
            return code
        
        # 위험한 함수 호출 패턴 제거
        dangerous_functions = [
            'exec', 'eval', 'compile', '__import__',
            'open', 'file', 'input', 'raw_input',
            'os.system', 'subprocess.call', 'subprocess.run'
        ]
        
        # 주석으로 위험한 함수들 표시
        for func in dangerous_functions:
            pattern = rf'\b{re.escape(func)}\s*\('
            if re.search(pattern, code):
                logger.warning(f"위험한 함수 사용 감지: {func}")
                # 실행하지 않고 주석 처리
                code = re.sub(pattern, f'# BLOCKED: {func}(', code)
        
        return code
    
    def generate_secure_session_id(self) -> str:
        """보안 강화된 세션 ID 생성"""
        # 48바이트 랜덤 데이터 + 타임스탬프
        random_part = secrets.token_bytes(48)
        timestamp = datetime.now().timestamp()
        
        # HMAC 서명
        signature = hmac.new(
            b"HAPA_SESSION_SECRET_2024",
            random_part + str(timestamp).encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"sess_{secrets.token_hex(32)}_{signature[:16]}"
    
    def validate_file_upload_security(self, filename: str, content: bytes) -> bool:
        """파일 업로드 보안 검증"""
        # 허용된 확장자만 허용
        allowed_extensions = {'.py', '.txt', '.md', '.json', '.yml', '.yaml'}
        file_ext = '.' + filename.split('.')[-1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"허용되지 않는 파일 형식: {file_ext}"
            )
        
        # 파일 크기 제한 (10MB)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="파일 크기가 너무 큽니다 (최대 10MB)"
            )
        
        # 악성 코드 패턴 검사
        content_str = content.decode('utf-8', errors='ignore')
        for pattern in self.suspicious_patterns:
            if re.search(pattern, content_str.lower()):
                raise HTTPException(
                    status_code=400,
                    detail="파일에서 의심스러운 패턴이 감지되었습니다"
                )
        
        return True
    
    def create_security_headers(self) -> Dict[str, str]:
        """보안 헤더 생성"""
        return {
            # HSTS (HTTP Strict Transport Security)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # 콘텐츠 타입 스니핑 방지
            "X-Content-Type-Options": "nosniff",
            
            # XSS 보호
            "X-XSS-Protection": "1; mode=block",
            
            # 클릭재킹 방지
            "X-Frame-Options": "DENY",
            
            # 리퍼러 정책
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # 권한 정책
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            
            # CSP (Content Security Policy)
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
            
            # 서버 정보 숨김
            "Server": "HAPA/1.0",
        }

# 글로벌 인스턴스
security_enhancer = SecurityEnhancements()

# 편의 함수들
def validate_input(data: str, field_name: str = "input") -> bool:
    """입력 데이터 검증 편의 함수"""
    return security_enhancer.validate_input_security(data, field_name)

def generate_api_key() -> str:
    """API 키 생성 편의 함수"""
    return security_enhancer.generate_secure_api_key()

def check_rate_limit(identifier: str, max_requests: int = 100) -> bool:
    """Rate Limiting 편의 함수"""
    return security_enhancer.advanced_rate_limiting(identifier, max_requests)

def get_security_headers() -> Dict[str, str]:
    """보안 헤더 편의 함수"""
    return security_enhancer.create_security_headers() 