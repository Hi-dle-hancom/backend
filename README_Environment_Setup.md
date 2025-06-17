# HAPA 환경변수 설정 가이드

## 개요

HAPA (Hancom AI Python Assistant) 프로젝트의 환경변수 설정 방법을 안내합니다.

## 환경별 설정 파일

### 1. 개발 환경 (`.env`)

- 로컬 개발 및 테스트용
- 모든 디버깅 기능 활성화
- 데모 API Key 자동 생성

### 2. 운영 환경 (`.env.production`)

- 프로덕션 배포용
- 보안 강화 설정
- 성능 최적화

## 주요 환경변수 설명

### 🔧 애플리케이션 기본 설정

```bash
PROJECT_NAME="HAPA (Hancom AI Python Assistant) API"
ENVIRONMENT=development  # development | staging | production
DEBUG=true              # 개발: true, 운영: false
```

### 🌐 서버 설정

```bash
HOST=0.0.0.0           # 바인드할 호스트
PORT=8000              # 서버 포트
CORS_ORIGINS=["*"]     # 허용할 CORS Origins
```

### 🤖 AI 모델 설정

```bash
MODEL_NAME=python_coding_assistant
MODEL_VERSION=1.0.0
AI_MODEL_API_KEY=your_ai_model_api_key_here
AI_MODEL_ENDPOINT=https://api.example.com/v1/generate
```

### 🔐 보안 설정

```bash
SECRET_KEY=your_secret_key_here        # JWT 등 암호화용 키
API_KEY_EXPIRY_DAYS=365               # API Key 만료 일수
ENABLE_SECURITY_HEADERS=true          # 보안 헤더 활성화
ENABLE_CSRF_PROTECTION=false          # CSRF 보호 (API는 일반적으로 false)
```

### 📊 로깅 설정

```bash
LOG_LEVEL=INFO                        # DEBUG | INFO | WARNING | ERROR
LOG_FILE_ROTATION=true               # 로그 파일 순환
LOG_MAX_SIZE=10MB                    # 로그 파일 최대 크기
LOG_BACKUP_COUNT=5                   # 백업 로그 파일 수
```

### ⚡ 성능 및 캐시 설정

```bash
CACHE_TTL=3600                       # 캐시 생존 시간 (초)
MAX_CACHE_SIZE=1000                  # 최대 캐시 크기
REQUEST_TIMEOUT=30                   # 요청 타임아웃 (초)
MAX_WORKERS=4                        # 최대 워커 수
```

### 🚦 Rate Limiting 설정

```bash
RATE_LIMIT_ENABLED=true              # Rate Limiting 활성화
DEFAULT_RATE_LIMIT=100               # 기본 요청 제한 (시간당)
RATE_LIMIT_WINDOW_MINUTES=60         # Rate Limiting 윈도우 (분)
```

## 환경별 설정 가이드

### 개발 환경 설정

1. **`.env` 파일 복사 및 수정**:

```bash
cd Backend
cp .env.example .env
```

2. **개발용 설정 적용**:

```bash
# 개발 환경 확인
ENVIRONMENT=development
DEBUG=true
ENABLE_DEMO_API_KEY=true

# 느슨한 보안 설정
CORS_ORIGINS=["*"]
RATE_LIMIT_ENABLED=false
```

### 운영 환경 설정

1. **`.env.production` 파일 설정**:

```bash
# 운영 환경 설정
ENVIRONMENT=production
DEBUG=false
ENABLE_DEMO_API_KEY=false

# 엄격한 보안 설정
SECRET_KEY=${생성된_보안_키}
CORS_ORIGINS=["https://your-domain.com"]
RATE_LIMIT_ENABLED=true
DEFAULT_RATE_LIMIT=50
```

2. **필수 환경변수 설정**:

```bash
# 시스템 환경변수로 설정
export SECRET_KEY="매우_복잡하고_안전한_키_64자_이상"
export AI_MODEL_API_KEY="실제_AI_모델_API_키"
export DATABASE_URL="postgresql://user:pass@localhost/hapa"
```

## 보안 체크리스트

### ⚠️ 운영 환경 필수 변경사항

1. **SECRET_KEY 변경**:

```bash
# 개발용 키 사용 금지!
# SECRET_KEY=hapa_secret_key_for_development_only_change_in_production

# 안전한 키 생성 방법:
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

2. **CORS 설정 제한**:

```bash
# 모든 Origin 허용 금지!
# CORS_ORIGINS=["*"]

# 특정 도메인만 허용:
CORS_ORIGINS=["https://your-domain.com", "https://api.your-domain.com"]
```

3. **데모 기능 비활성화**:

```bash
ENABLE_DEMO_API_KEY=false
DEBUG=false
```

## 환경변수 우선순위

1. **시스템 환경변수** (최우선)
2. **`.env` 파일**
3. **기본값** (코드에 정의된 값)

## 설정 확인 방법

### 1. 설정 값 확인

```bash
cd Backend
python -c "
from app.core.config import settings
print(f'Environment: {settings.ENVIRONMENT}')
print(f'Debug Mode: {settings.DEBUG}')
print(f'Secret Key: {settings.SECRET_KEY[:10]}...')
"
```

### 2. 서버 시작 시 로그 확인

```bash
# 개발 환경
INFO:app.core.config:🔧 개발 환경 모드로 실행 중입니다.

# 운영 환경
WARNING:app.core.config:⚠️  운영 환경 모드로 실행 중입니다.
```

## 문제 해결

### 일반적인 문제

1. **환경변수 로드 실패**:

```bash
# .env 파일 존재 확인
ls -la .env

# 파일 권한 확인
chmod 644 .env
```

2. **SECRET_KEY 경고**:

```bash
# 운영 환경에서 개발용 키 사용 시 발생
ERROR:app.core.config:🚨 운영 환경에서 개발용 SECRET_KEY를 사용하고 있습니다!
```

3. **포트 충돌**:

```bash
# 다른 포트 사용
PORT=8001
```

## 배포 시 주의사항

### Docker 사용 시

```dockerfile
# 환경변수 파일 복사
COPY .env.production /app/.env

# 또는 빌드 시 환경변수 전달
ARG SECRET_KEY
ENV SECRET_KEY=${SECRET_KEY}
```

### 클라우드 배포 시

- 환경변수를 별도 보안 저장소에 저장
- `.env` 파일을 소스 코드에 포함하지 않음
- 민감한 정보는 시스템 환경변수로만 설정

## 추가 참고사항

- 모든 환경변수는 `app/core/config.py`에서 관리됩니다
- 새로운 환경변수 추가 시 해당 파일도 업데이트 필요
- 환경변수 변경 후 서버 재시작 필요
