"""
HAPA 보안 헤더 미들웨어
Content Security Policy, HSTS, X-Frame-Options 등 보안 헤더 설정
"""

from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import secrets
import time


class SecurityHeadersMiddleware:
    """보안 헤더 미들웨어"""
    
    def __init__(self, app, enable_csp: bool = True, enable_hsts: bool = True):
        self.app = app
        self.enable_csp = enable_csp
        self.enable_hsts = enable_hsts
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        request = Request(scope, receive)
        
        # 응답 처리를 위한 wrapper
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                
                # 보안 헤더 추가
                security_headers = self._get_security_headers(request)
                for key, value in security_headers.items():
                    headers[key.encode()] = value.encode()
                
                message["headers"] = list(headers.items())
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
    
    def _get_security_headers(self, request: Request) -> dict:
        """보안 헤더 생성"""
        headers = {}
        
        # Content Security Policy
        if self.enable_csp:
            nonce = secrets.token_urlsafe(16)
            csp_policy = self._build_csp_policy(nonce)
            headers["Content-Security-Policy"] = csp_policy
            headers["X-Content-Security-Policy"] = csp_policy  # Legacy support
            
        # HTTP Strict Transport Security
        if self.enable_hsts:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # X-Frame-Options (clickjacking 방지)
        headers["X-Frame-Options"] = "DENY"
        
        # X-Content-Type-Options (MIME 스니핑 방지)
        headers["X-Content-Type-Options"] = "nosniff"
        
        # X-XSS-Protection (XSS 필터링)
        headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer Policy
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (구 Feature Policy)
        headers["Permissions-Policy"] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "accelerometer=(), "
            "gyroscope=()"
        )
        
        # Cross-Origin 정책
        headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        headers["Cross-Origin-Opener-Policy"] = "same-origin"
        headers["Cross-Origin-Resource-Policy"] = "same-origin"
        
        # 캐시 제어
        if request.url.path.startswith("/api/"):
            headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            headers["Pragma"] = "no-cache"
            headers["Expires"] = "0"
        
        # 서버 정보 숨기기
        headers["Server"] = "HAPA"
        
        return headers
    
    def _build_csp_policy(self, nonce: str) -> str:
        """Content Security Policy 빌드"""
        policies = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' vscode-webview:",
            "style-src 'self' 'unsafe-inline' vscode-webview:",
            "img-src 'self' data: blob: vscode-webview:",
            "font-src 'self' data: vscode-webview:",
            "connect-src 'self' ws: wss: vscode-webview:",
            "media-src 'self' vscode-webview:",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "upgrade-insecure-requests"
        ]
        
        return "; ".join(policies)


class RateLimitMiddleware:
    """Rate Limiting 미들웨어"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # {ip: [timestamp, ...]}
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        request = Request(scope, receive)
        client_ip = self._get_client_ip(request)
        
        # Rate limit 검사
        if not self._is_allowed(client_ip):
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": 60
                }
            )
            await response(scope, receive, send)
            return
        
        # 요청 기록
        self._record_request(client_ip)
        
        await self.app(scope, receive, send)
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        # X-Forwarded-For 헤더 확인 (프록시 환경)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 직접 연결 IP
        return request.client.host if request.client else "unknown"
    
    def _is_allowed(self, client_ip: str) -> bool:
        """Rate limit 허용 여부 확인"""
        current_time = time.time()
        minute_ago = current_time - 60
        
        # 해당 IP의 요청 기록 정리 (1분 이전 제거)
        if client_ip in self.requests:
            self.requests[client_ip] = [
                timestamp for timestamp in self.requests[client_ip]
                if timestamp > minute_ago
            ]
        
        # 요청 횟수 확인
        request_count = len(self.requests.get(client_ip, []))
        return request_count < self.requests_per_minute
    
    def _record_request(self, client_ip: str):
        """요청 기록"""
        current_time = time.time()
        
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        self.requests[client_ip].append(current_time)


class RequestLoggingMiddleware:
    """요청 로깅 미들웨어"""
    
    def __init__(self, app, log_body: bool = False):
        self.app = app
        self.log_body = log_body
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        request = Request(scope, receive)
        start_time = time.time()
        
        # 요청 로깅
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # 민감한 정보 제외하고 로깅
        safe_headers = {
            k: "***REDACTED***" if k.lower() in ["authorization", "cookie", "x-api-key"] else v
            for k, v in request.headers.items()
        }
        
        print(f"[REQUEST] {request.method} {request.url} from {client_ip}")
        print(f"[HEADERS] {safe_headers}")
        print(f"[USER-AGENT] {user_agent}")
        
        # 응답 처리
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.time() - start_time
                status_code = message["status"]
                print(f"[RESPONSE] {status_code} in {process_time:.3f}s")
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


def add_security_middleware(app, config=None):
    """보안 미들웨어 추가 함수"""
    if config is None:
        config = {}
    
    # Rate Limiting
    requests_per_minute = config.get("rate_limit_requests", 60)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=requests_per_minute)
    
    # Security Headers
    enable_csp = config.get("enable_csp", True)
    enable_hsts = config.get("enable_hsts", True)
    app.add_middleware(SecurityHeadersMiddleware, enable_csp=enable_csp, enable_hsts=enable_hsts)
    
    # Request Logging (개발 환경에서만)
    if config.get("environment") == "development":
        app.add_middleware(RequestLoggingMiddleware, log_body=False)
    
    return app