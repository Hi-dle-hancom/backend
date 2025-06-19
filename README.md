# HAPA Backend API Server 🚀

**HAPA Backend**는 Python 개발자를 위한 AI 코딩 어시스턴트의 핵심 API 서버입니다. VSCode 확장 프로그램과 웹 인터페이스에 AI 기반 코드 생성, 자동완성, 피드백 관리 등의 서비스를 제공합니다.

## 📋 목차

- [주요 기능](#-주요-기능)
- [시스템 요구사항](#-시스템-요구사항)
- [빠른 시작](#-빠른-시작)
- [API 엔드포인트](#-api-엔드포인트)
- [환경 설정](#-환경-설정)
- [테스트](#-테스트)
- [배포](#-배포)
- [문제 해결](#-문제-해결)

## 🎯 주요 기능

### 🤖 AI 코드 생성

- **실시간 Python 코드 생성**: 자연어 질문을 Python 코드로 변환
- **스트리밍 응답**: 토큰 단위 실시간 응답으로 향상된 사용자 경험
- **컨텍스트 인식**: 기존 코드 맥락을 이해한 코드 생성

### ⚡ 스마트 자동완성

- **인텔리전트 자동완성**: 코드 컨텍스트 기반 제안
- **다중 제안**: 최대 5개의 완성 옵션 제공
- **실시간 처리**: 빠른 응답 시간 보장

### 🔍 코드 품질 관리

- **실시간 코드 검증**: Python 문법 검사 및 오류 감지
- **피드백 시스템**: 생성된 코드에 대한 사용자 평가 수집
- **히스토리 관리**: 생성 내역 및 세션 추적

### 📊 성능 모니터링

- **실시간 메트릭**: API 응답 시간, 캐시 히트율 추적
- **헬스 체크**: 시스템 상태 모니터링
- **프로메테우스 메트릭**: 운영 환경 모니터링 지원

## 💻 시스템 요구사항

### 최소 요구사항

- **Python**: 3.12 이상
- **RAM**: 최소 2GB (권장 4GB)
- **디스크**: 최소 1GB 여유 공간
- **네트워크**: 인터넷 연결 (AI 모델 API 호출용)

### 권장 요구사항

- **OS**: Ubuntu 20.04+, macOS 12+, Windows 10+
- **Python**: 3.12.x
- **Docker**: 20.10+ (컨테이너 배포 시)
- **PostgreSQL**: 13+ (프로덕션 환경)
- **Redis**: 6+ (프로덕션 캐시)

## 🚀 빠른 시작

### 1. 저장소 클론

```bash
git clone https://github.com/hancom/hapa-backend.git
cd hapa-backend/Backend
```

### 2. Python 가상환경 설정

```bash
# Python 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. 의존성 설치

```bash
# 필수 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 환경 설정

```bash
# 환경 변수 파일 생성
cp .env.example .env

# .env 파일 편집 (필요시)
# 기본 설정으로도 개발 환경에서 실행 가능
```

### 5. 서버 실행

```bash
# 개발 서버 시작
python main.py
```

**✅ 성공!** 서버가 정상적으로 시작되면 다음 URL들에 접근할 수 있습니다:

- **API 서버**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs (Swagger UI)
- **대체 API 문서**: http://localhost:8000/redoc (ReDoc)
- **헬스 체크**: http://localhost:8000/health

## 📡 API 엔드포인트

### 기본 정보

- **Base URL**: `http://localhost:8000`
- **API Version**: `v1`
- **Base Path**: `/api/v1`

### 🤖 코드 생성 API

| 메서드 | 엔드포인트                     | 설명                      | 인증 |
| ------ | ------------------------------ | ------------------------- | ---- |
| `POST` | `/api/v1/code/generate`        | AI 기반 Python 코드 생성  | ✅   |
| `POST` | `/api/v1/code/complete`        | 코드 자동완성 제안        | ✅   |
| `POST` | `/api/v1/code/stream-generate` | 실시간 스트리밍 코드 생성 | ✅   |

### 🔍 코드 검증 API

| 메서드 | 엔드포인트                    | 설명                  | 인증 |
| ------ | ----------------------------- | --------------------- | ---- |
| `POST` | `/api/v1/validation/validate` | Python 코드 문법 검증 | ✅   |

### 💬 피드백 API

| 메서드 | 엔드포인트                    | 설명               | 인증 |
| ------ | ----------------------------- | ------------------ | ---- |
| `POST` | `/api/v1/feedback/submit`     | 사용자 피드백 제출 | ✅   |
| `GET`  | `/api/v1/feedback/statistics` | 피드백 통계 조회   | ✅   |

### 📚 히스토리 API

| 메서드 | 엔드포인트                 | 설명               | 인증 |
| ------ | -------------------------- | ------------------ | ---- |
| `GET`  | `/api/v1/history/sessions` | 세션 목록 조회     | ✅   |
| `POST` | `/api/v1/history/entries`  | 히스토리 항목 추가 | ✅   |
| `GET`  | `/api/v1/history/entries`  | 히스토리 항목 조회 | ✅   |

### 🗄️ 캐시 관리 API (관리자)

| 메서드   | 엔드포인트            | 설명           | 인증 |
| -------- | --------------------- | -------------- | ---- |
| `GET`    | `/api/v1/cache/stats` | 캐시 통계 조회 | ✅   |
| `DELETE` | `/api/v1/cache/clear` | 캐시 초기화    | ✅   |

### 🔧 시스템 API

| 메서드 | 엔드포인트 | 설명                | 인증 |
| ------ | ---------- | ------------------- | ---- |
| `GET`  | `/`        | API 기본 정보       | ❌   |
| `GET`  | `/health`  | 헬스 체크           | ❌   |
| `GET`  | `/stats`   | 성능 통계           | ❌   |
| `GET`  | `/metrics` | 프로메테우스 메트릭 | ❌   |

### 📝 API 사용 예시

#### 코드 생성 요청

```bash
curl -X POST "http://localhost:8000/api/v1/code/generate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: hapa_demo_20241228_secure_key_for_testing" \
  -d '{
    "user_question": "피보나치 수열을 계산하는 함수를 만들어주세요",
    "code_context": "# 수학 관련 함수들",
    "file_path": "/src/math_functions.py"
  }'
```

#### 코드 자동완성 요청

```bash
curl -X POST "http://localhost:8000/api/v1/code/complete" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: hapa_demo_20241228_secure_key_for_testing" \
  -d '{
    "prefix": "def calculate_",
    "file_path": "/src/calculator.py",
    "cursor_position": 14
  }'
```

## 🏗️ 프로젝트 구조

```
Backend/
├── app/                          # 메인 애플리케이션 패키지
│   ├── __init__.py
│   ├── api/                      # API 라우터 및 엔드포인트
│   │   ├── __init__.py
│   │   ├── api.py               # 메인 라우터
│   │   └── endpoints/           # API 엔드포인트 모듈
│   │       ├── __init__.py
│   │       ├── cache.py         # 캐시 관리 API
│   │       ├── code_generation.py # 코드 생성 API
│   │       ├── feedback.py      # 피드백 API
│   │       ├── history.py       # 히스토리 API
│   │       ├── performance.py   # 성능 모니터링 API
│   │       ├── settings.py      # 설정 관리 API
│   │       └── validation.py    # 코드 검증 API
│   ├── core/                    # 핵심 설정 및 유틸리티
│   │   ├── __init__.py
│   │   ├── config.py           # 환경 설정
│   │   ├── logging_config.py   # 로깅 설정
│   │   └── security.py         # 보안 및 인증
│   ├── schemas/                 # Pydantic 데이터 모델
│   │   ├── __init__.py
│   │   ├── code_generation.py  # 코드 생성 스키마
│   │   ├── feedback.py         # 피드백 스키마
│   │   ├── history.py          # 히스토리 스키마
│   │   ├── performance.py      # 성능 스키마
│   │   ├── settings.py         # 설정 스키마
│   │   └── validation.py       # 검증 스키마
│   └── services/               # 비즈니스 로직 서비스
│       ├── __init__.py
│       ├── ai_model.py         # AI 모델 인터페이스
│       ├── cache_service.py    # 캐시 시스템
│       ├── code_generator.py   # 코드 생성 서비스
│       ├── feedback_service.py # 피드백 처리
│       ├── history_service.py  # 히스토리 관리
│       ├── inference.py        # AI 추론 서비스
│       ├── performance_profiler.py # 성능 프로파일링
│       ├── settings_service.py # 설정 관리
│       └── validation_service.py # 코드 검증
├── data/                       # 애플리케이션 데이터 저장소
│   ├── api_keys.json          # API 키 저장 (개발용)
│   ├── cache/                 # 파일 기반 캐시
│   ├── feedback/              # 피드백 데이터
│   ├── history/               # 히스토리 데이터
│   ├── rate_limits.json       # Rate Limit 데이터
│   ├── settings/              # 사용자 설정
│   └── validation/            # 검증 결과
├── docs/                      # 프로젝트 문서
│   ├── api_specification_v1.0.md
│   ├── enhanced_completion_api.md
│   ├── error_response_schema.md
│   ├── performance_optimization_report.md
│   ├── security_enhancement_report.md
│   └── system_architecture_v2.md
├── tests/                     # 테스트 파일
│   ├── __init__.py
│   ├── test_code_generation.py
│   └── test_inference.py
├── main.py                    # 서버 시작점
├── requirements.txt           # Python 의존성
├── Dockerfile                 # Docker 이미지 빌드
├── docker-compose.yml         # Docker Compose 설정
├── .env.example              # 환경변수 예시
├── .gitignore                # Git 무시 파일
└── README.md                 # 이 파일
```

## 🔧 환경 설정

### 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 생성하고 다음 설정들을 참고하여 구성하세요:

```env
# ======================
# 기본 서버 설정
# ======================
DEBUG=true
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000

# ======================
# API 설정
# ======================
API_V1_PREFIX=/api/v1
PROJECT_NAME=HAPA Backend API

# ======================
# AI 모델 설정 (준비중)
# ======================
AI_MODEL_API_KEY=your_openai_api_key_here
AI_MODEL_ENDPOINT=https://api.openai.com/v1/completions
MODEL_NAME=python_coding_assistant
MODEL_VERSION=1.0.0

# ======================
# 보안 설정
# ======================
SECRET_KEY=hapa_secret_key_for_development_only_change_in_production
API_KEY_EXPIRY_DAYS=365

# ======================
# 캐시 및 성능 설정
# ======================
CACHE_TTL=3600
MAX_CACHE_SIZE=1000
REQUEST_TIMEOUT=30
MAX_WORKERS=4

# ======================
# Rate Limiting
# ======================
RATE_LIMIT_ENABLED=true
DEFAULT_RATE_LIMIT=100
RATE_LIMIT_WINDOW_MINUTES=60

# ======================
# 로깅 설정
# ======================
LOG_LEVEL=INFO
LOG_FILE_ROTATION=true
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5

# ======================
# 데이터베이스 (프로덕션용)
# ======================
DATABASE_URL=postgresql://username:password@localhost:5432/hapa_db
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# ======================
# 외부 서비스 설정
# ======================
EXTERNAL_API_TIMEOUT=10
RETRY_ATTEMPTS=3
RETRY_DELAY=1

# ======================
# 모니터링 설정
# ======================
ENABLE_METRICS=true
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30

# ======================
# 개발용 데모 설정
# ======================
ENABLE_DEMO_API_KEY=true
DEMO_USER_ID=demo_user
DEMO_API_KEY=hapa_demo_20241228_secure_key_for_testing
```

### 개발 환경 주요 설정

| 설정                  | 기본값 | 설명                 |
| --------------------- | ------ | -------------------- |
| `DEBUG`               | `true` | 디버그 모드 활성화   |
| `PORT`                | `8000` | 서버 포트            |
| `CACHE_TTL`           | `3600` | 캐시 만료 시간 (초)  |
| `RATE_LIMIT_ENABLED`  | `true` | Rate Limiting 활성화 |
| `ENABLE_DEMO_API_KEY` | `true` | 데모 API Key 사용    |

## 🧪 테스트

### 단위 테스트 실행

```bash
# 모든 테스트 실행
python -m pytest tests/ -v

# 특정 테스트 파일 실행
python -m pytest tests/test_code_generation.py -v

# 커버리지 리포트 포함
python -m pytest tests/ --cov=app --cov-report=html
```

### 통합 테스트 실행

```bash
# 통합 테스트 (실제 서버 시작 필요)
python test_integration.py
```

### API 테스트 (Thunder Client)

```bash
# Thunder Client 테스트 실행 (VS Code 확장 필요)
# thunder-tests/ 디렉토리의 테스트 컬렉션 사용
```

### 헬스 체크

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 성능 메트릭 확인
curl http://localhost:8000/stats

# 프로메테우스 메트릭 확인
curl http://localhost:8000/metrics
```

## 🐳 배포

### Docker 개발 환경

```bash
# Docker 컨테이너 빌드 및 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 컨테이너 중지
docker-compose down
```

### Docker 프로덕션 환경

```bash
# 프로덕션 이미지 빌드
docker build -t hapa-backend:latest .

# 프로덕션 컨테이너 실행
docker run -d \
  --name hapa-backend \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DEBUG=false \
  hapa-backend:latest
```

### 수동 배포

```bash
# 의존성 설치
pip install -r requirements.txt

# 프로덕션 서버 실행
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 🔒 보안

### API 인증

모든 API 엔드포인트는 API Key 인증이 필요합니다:

```bash
# 헤더에 API Key 포함
curl -H "X-API-Key: your_api_key_here" http://localhost:8000/api/v1/...

# 또는 Authorization 헤더 사용
curl -H "Authorization: ApiKey your_api_key_here" http://localhost:8000/api/v1/...
```

### 개발용 데모 API Key

개발 환경에서는 다음 데모 API Key를 사용할 수 있습니다:

```
hapa_demo_20241228_secure_key_for_testing
```

⚠️ **주의**: 프로덕션 환경에서는 반드시 별도의 보안 API Key를 사용하세요.

### Rate Limiting

API는 다음과 같은 Rate Limit이 적용됩니다:

| 엔드포인트         | 제한  | 시간 윈도우 |
| ------------------ | ----- | ----------- |
| `/generate`        | 50회  | 1시간       |
| `/complete`        | 100회 | 1시간       |
| `/stream-generate` | 30회  | 1시간       |
| 기타               | 100회 | 1시간       |

## 📊 모니터링

### 성능 메트릭

서버는 다음 메트릭을 제공합니다:

- **API 응답 시간**: 엔드포인트별 평균/최대 응답 시간
- **요청 처리량**: 초당 요청 수 (RPS)
- **캐시 히트율**: 캐시 효율성 측정
- **에러율**: HTTP 4xx/5xx 에러 비율
- **시스템 리소스**: CPU, 메모리, 디스크 사용률

### 로그 모니터링

로그는 다음 위치에 저장됩니다:

- **개발 환경**: 콘솔 출력
- **프로덕션 환경**: `logs/` 디렉토리
- **로그 레벨**: INFO, WARNING, ERROR
- **로그 로테이션**: 10MB 단위, 5개 파일 백업

## 🛠️ 기술 스택

### 백엔드 프레임워크

- **FastAPI**: 0.104+ (Python 3.12+ 호환)
- **Uvicorn**: ASGI 서버
- **Pydantic**: v2 데이터 검증

### 데이터 저장

- **개발**: 파일 기반 저장소 (JSON)
- **프로덕션**: PostgreSQL 13+
- **캐시**: Redis 6+ (프로덕션), 파일 기반 (개발)

### 모니터링 & 로깅

- **구조화된 로깅**: JSON 형태 로그
- **프로메테우스 메트릭**: `/metrics` 엔드포인트
- **헬스 체크**: `/health` 엔드포인트
- **성능 프로파일링**: 자체 구현

### 보안

- **API Key 인증**: 사용자 정의 구현
- **Rate Limiting**: 메모리 기반 (개발), Redis 기반 (프로덕션)
- **CORS**: 설정 가능한 오리진 허용
- **입력 검증**: Pydantic 스키마

## 🐛 문제 해결

### 자주 발생하는 문제

#### 1. 포트 충돌 (8000번 포트 사용중)

```bash
# 다른 포트로 실행
python main.py --port 8001

# 또는 환경변수 설정
export PORT=8001
python main.py
```

#### 2. 의존성 설치 오류

```bash
# Python 버전 확인
python --version  # 3.12+ 필요

# pip 업그레이드
pip install --upgrade pip

# 가상환경 재생성
rm -rf venv
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 또는
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

#### 3. API Key 인증 오류

```bash
# 데모 API Key 사용
curl -H "X-API-Key: hapa_demo_20241228_secure_key_for_testing" \
     http://localhost:8000/api/v1/code/generate

# API Key 확인
curl http://localhost:8000/health
```

#### 4. 캐시 관련 오류

```bash
# 캐시 디렉토리 권한 확인
ls -la data/cache/

# 캐시 초기화
curl -X DELETE -H "X-API-Key: hapa_demo_20241228_secure_key_for_testing" \
     http://localhost:8000/api/v1/cache/clear
```

#### 5. 로그 파일 권한 오류

```bash
# 로그 디렉토리 생성
mkdir -p logs

# 권한 설정
chmod 755 logs
```

### 디버깅 팁

#### 1. 디버그 모드 활성화

```bash
# .env 파일에서 설정
DEBUG=true
LOG_LEVEL=DEBUG

# 또는 환경변수로 설정
export DEBUG=true
export LOG_LEVEL=DEBUG
python main.py
```

#### 2. 자세한 에러 로그 확인

```bash
# 실시간 로그 모니터링
tail -f logs/hapa_backend.log

# 에러 로그만 필터링
grep ERROR logs/hapa_backend.log
```

#### 3. API 응답 디버깅

```bash
# Verbose 모드로 curl 실행
curl -v -H "X-API-Key: hapa_demo_20241228_secure_key_for_testing" \
     http://localhost:8000/api/v1/code/generate

# JSON 응답 예쁘게 출력
curl -H "X-API-Key: hapa_demo_20241228_secure_key_for_testing" \
     http://localhost:8000/api/v1/code/generate | jq .
```

### 지원 및 문의

- **GitHub Issues**: 버그 리포트 및 기능 요청
- **문서**: `/docs` 디렉토리의 상세 문서 참조
- **API 문서**: http://localhost:8000/docs (Swagger UI)

---

## 📚 관련 문서

- **[API 명세서](docs/api_specification_v1.0.md)**: 상세한 API 문서
- **[시스템 아키텍처](docs/system_architecture_v2.md)**: 시스템 설계 문서
- **[보안 가이드](docs/security_enhancement_report.md)**: 보안 기능 상세
- **[성능 최적화](docs/performance_optimization_report.md)**: 성능 튜닝 가이드
- **[배포 가이드](README_Deploy.md)**: Docker 기반 배포
- **[환경 설정](README_Environment_Setup.md)**: 상세한 환경 설정

---

**버전**: v0.4.0  
**상태**: 프로덕션 준비 완료  
**최종 업데이트**: 2024년 12월 28일
