# HAPA 백엔드 Docker 이미지 - vLLM 멀티 LoRA 서버 통합
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# vLLM 통합을 위한 추가 의존성
RUN pip install --no-cache-dir \
    aiohttp \
    asyncio-mqtt \
    httpx[http2]

# 애플리케이션 코드 복사
COPY . .

# 로그 및 데이터 디렉토리 생성
RUN mkdir -p logs data/cache data/feedback data/history data/validation data/settings

# 환경변수 설정 (기본값)
ENV ENVIRONMENT=production
ENV DEBUG=false
ENV HOST=0.0.0.0
ENV PORT=8000

# 로깅 최적화 설정 (운영환경)
ENV LOG_LEVEL=WARNING
ENV ENABLE_DEBUG_LOGS=false
ENV ENABLE_PERFORMANCE_LOGS=true
ENV ENABLE_REQUEST_RESPONSE_LOGS=false
ENV LOG_CHUNK_DETAILS=false

# vLLM 서버 설정 (기본값)
ENV VLLM_SERVER_URL=http://3.13.240.111:8002
ENV VLLM_TIMEOUT_SECONDS=300
ENV VLLM_MAX_RETRIES=3
ENV VLLM_HEALTH_CHECK_INTERVAL=60

# vLLM 모델 기본 설정
ENV VLLM_DEFAULT_TEMPERATURE=0.3
ENV VLLM_DEFAULT_TOP_P=0.95
ENV VLLM_DEFAULT_MAX_TOKENS=1024

# vLLM 성능 설정
ENV VLLM_CONNECTION_POOL_SIZE=10
ENV VLLM_ENABLE_RETRY=true
ENV VLLM_RETRY_DELAY=1.0

# 운영용 설정 (로깅 최적화)
ENV VLLM_DEBUG_MODE=false
ENV VLLM_LOG_REQUESTS=false
ENV VLLM_ENABLE_MONITORING=true

# AI 모델 설정
ENV MODEL_NAME=python_coding_assistant
ENV MODEL_VERSION=1.0.0

# 보안 설정
ENV ENABLE_SECURITY_HEADERS=true
ENV ENABLE_CSRF_PROTECTION=true

# 성능 설정
ENV MAX_WORKERS=4
ENV REQUEST_TIMEOUT=60
ENV CACHE_TTL=3600

# Rate Limiting
ENV RATE_LIMIT_ENABLED=true
ENV DEFAULT_RATE_LIMIT=50
ENV RATE_LIMIT_WINDOW_MINUTES=60

# 헬스체크 설정
ENV HEALTH_CHECK_INTERVAL=30

# 포트 노출
EXPOSE 8000

# 헬스체크 명령
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 비루트 사용자 생성 및 전환 (보안)
RUN groupadd -r hapa && useradd -r -g hapa hapa
RUN chown -R hapa:hapa /app

# 프로덕션 사용자로 전환
USER hapa

# 애플리케이션 시작
CMD ["python", "main.py"] 