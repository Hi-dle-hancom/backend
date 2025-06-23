# 🖥️ HAPA Backend API Server

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-0.24+-purple.svg)](https://www.uvicorn.org/)

> **HAPA의 핵심 AI 코드 생성 백엔드 서버**  
> FastAPI 기반 고성능 RESTful API 서비스

## 🎯 **서버 개요**

HAPA Backend는 AI 기반 코드 생성, 분석, 자동완성을 담당하는 **핵심 마이크로서비스**입니다. 스트리밍 응답, 스마트 캐싱, 성능 모니터링을 통해 최적화된 개발자 경험을 제공합니다.

### ✨ **주요 기능**

- 🤖 **AI 코드 생성**: 사용자 질문을 Python 코드로 변환
- ⚡ **실시간 자동완성**: 컨텍스트 기반 코드 완성 제안
- 🌊 **스트리밍 응답**: 토큰 단위 실시간 응답 스트리밍
- 📊 **개인화 설정**: 스킬 레벨별 맞춤 코드 생성
- 🔒 **보안 강화**: API 키 인증 및 Rate Limiting
- 📈 **성능 모니터링**: Prometheus 메트릭 수집
- 💾 **스마트 캐싱**: Redis 기반 응답 캐시

## 🏗️ **아키텍처**

```
Backend/
├── 📁 app/                    # 메인 애플리케이션
│   ├── 📁 api/               # API 엔드포인트
│   │   ├── api.py            # 메인 라우터
│   │   └── endpoints/        # 개별 엔드포인트
│   │       ├── code_generation.py      # 코드 생성 API
│   │       ├── enhanced_code_generation.py  # 강화된 코드 생성
│   │       ├── validation.py # 입력 검증 API
│   │       ├── feedback.py   # 피드백 수집 API
│   │       ├── history.py    # 히스토리 관리 API
│   │       ├── cache.py      # 캐시 관리 API
│   │       ├── metrics.py    # 메트릭 API
│   │       └── users.py      # 사용자 프로필 API
│   ├── 📁 core/              # 핵심 설정
│   │   ├── config.py         # 환경 설정
│   │   ├── security.py       # 보안 설정
│   │   └── logging_config.py # 로깅 설정
│   ├── 📁 services/          # 비즈니스 로직
│   │   ├── ai_model.py       # AI 모델 인터페이스
│   │   ├── enhanced_ai_model.py  # 강화된 AI 모델
│   │   ├── code_generator.py # 코드 생성 서비스
│   │   ├── cache_service.py  # 캐시 서비스
│   │   ├── validation_service.py  # 검증 서비스
│   │   ├── feedback_service.py    # 피드백 서비스
│   │   ├── history_service.py     # 히스토리 서비스
│   │   ├── performance_profiler.py # 성능 프로파일링
│   │   ├── response_parser.py     # 응답 파싱
│   │   └── environment_validator.py # 환경 변수 검증
│   └── 📁 schemas/           # 데이터 모델
│       ├── code_generation.py    # 코드 생성 스키마
│       ├── validation.py     # 검증 스키마
│       ├── feedback.py       # 피드백 스키마
│       └── users.py          # 사용자 스키마
├── 📁 data/                  # 데이터 저장소
│   ├── cache/               # 파일 기반 캐시
│   ├── feedback/            # 사용자 피드백
│   ├── history/             # 대화 히스토리
│   └── settings/            # 사용자 설정
├── 📁 tests/                # 테스트 코드
├── main.py                  # 애플리케이션 진입점
├── requirements.txt         # Python 의존성
└── Dockerfile              # Docker 설정
```

## 🚀 **빠른 시작**

### 로컬 개발 환경

```bash
# 1. 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경 변수 설정
cp .env.development .env
# .env 파일에서 필요한 값들 수정

# 4. 개발 서버 시작
python main.py
```

### Docker 실행

```bash
# 1. Docker 이미지 빌드
docker build -t hapa-backend .

# 2. 컨테이너 실행
docker run -p 8000:8000 \
  -e SECRET_KEY="your-secret-key" \
  -e AI_MODEL_API_KEY="your-api-key" \
  hapa-backend
```

### 서버 확인

```bash
# 헬스 체크
curl http://localhost:8000/health

# API 문서 확인
open http://localhost:8000/docs
```

## 🔧 **환경 설정**

### 필수 환경 변수

```bash
# 기본 설정
ENVIRONMENT=development          # development/production
DEBUG=true                      # 디버그 모드
HOST=0.0.0.0                   # 서버 호스트
PORT=8000                      # 서버 포트

# 보안 설정
SECRET_KEY=your-32-char-secret-key     # JWT 시크릿 키 (32자 이상)
API_KEY_EXPIRY_DAYS=90         # API 키 만료 기간

# AI 모델 설정
AI_MODEL_API_KEY=your-ai-api-key       # AI 모델 API 키
AI_MODEL_ENDPOINT=https://api.openai.com/v1/completions

# 데이터베이스 설정
DATABASE_URL=sqlite:///./data/hapa.db  # 개발용 SQLite
# DATABASE_URL=postgresql://user:pass@host:5432/db  # 운영용

# 성능 설정
CACHE_TTL=1800                 # 캐시 유효시간 (초)
MAX_CACHE_SIZE=1000           # 최대 캐시 항목 수
REQUEST_TIMEOUT=30            # 요청 타임아웃 (초)
MAX_WORKERS=4                 # 최대 워커 수

# Rate Limiting
RATE_LIMIT_ENABLED=true       # Rate Limiting 활성화
DEFAULT_RATE_LIMIT=100        # 기본 요청 한도
RATE_LIMIT_WINDOW_MINUTES=60  # 제한 윈도우 (분)
```

### 운영 환경 추가 설정

```bash
# 운영 환경 전용
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=["https://your-domain.com"]

# SSL 설정
SSL_ENABLED=true
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem

# 모니터링
ENABLE_METRICS=true
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=60
```

## 📡 **API 엔드포인트**

### 🤖 **코드 생성 API**

#### **기본 코드 생성**

```http
POST /api/v1/generate-code
Content-Type: application/json
X-API-Key: your-api-key

{
  "user_question": "리스트에서 중복 제거하는 함수 만들어줘",
  "code_context": "데이터 처리 스크립트",
  "language": "python",
  "user_profile": {
    "pythonSkillLevel": "intermediate",
    "codeOutputStructure": "standard",
    "explanationStyle": "detailed"
  }
}
```

**응답:**

```json
{
  "generated_code": "def remove_duplicates(lst):\n    return list(set(lst))",
  "explanation": "set()을 사용하여 중복을 제거하고 다시 리스트로 변환합니다.",
  "status": "success"
}
```

#### **스트리밍 코드 생성**

```http
POST /api/v1/generate-code-streaming
Content-Type: application/json
X-API-Key: your-api-key

{
  "user_question": "Flask 웹 애플리케이션 만들어줘",
  "language": "python"
}
```

**스트리밍 응답:**

```
data: {"type": "start", "content": "", "sequence": 0}
data: {"type": "code", "content": "from flask import Flask\n", "sequence": 1}
data: {"type": "code", "content": "app = Flask(__name__)\n", "sequence": 2}
data: {"type": "done", "content": "", "sequence": 3}
```

### ⚡ **자동완성 API**

```http
POST /api/v1/complete-code
Content-Type: application/json
X-API-Key: your-api-key

{
  "prefix": "def fibonacci(",
  "language": "python",
  "cursor_position": 13,
  "context": "수학 함수 라이브러리"
}
```

**응답:**

```json
{
  "completions": [
    {
      "code": "n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
      "label": "피보나치 순열 (재귀)",
      "confidence": 0.95,
      "category": "function",
      "complexity": "simple"
    }
  ],
  "status": "success"
}
```

### 🔍 **검증 및 분석 API**

#### **코드 검증**

```http
POST /api/v1/validate-code
Content-Type: application/json
X-API-Key: your-api-key

{
  "code": "def hello():\n    print('Hello World')",
  "language": "python",
  "validation_type": "syntax"
}
```

#### **코드 분석**

```http
POST /api/v1/analyze-code
Content-Type: application/json
X-API-Key: your-api-key

{
  "code": "def process_data(data): return [x*2 for x in data]",
  "analysis_type": "performance"
}
```

### 📊 **피드백 및 히스토리 API**

#### **피드백 제출**

```http
POST /api/v1/submit-feedback
Content-Type: application/json
X-API-Key: your-api-key

{
  "type": "positive",
  "comment": "생성된 코드가 정확하고 효율적입니다",
  "code_snippet": "def remove_duplicates(lst): return list(set(lst))",
  "user_question": "중복 제거 함수"
}
```

#### **히스토리 조회**

```http
GET /api/v1/user/history?limit=10
X-API-Key: your-api-key
```

### 🔧 **시스템 API**

#### **헬스 체크**

```http
GET /health
```

**응답:**

```json
{
  "status": "healthy",
  "version": "0.4.0",
  "timestamp": "2024-12-28T10:00:00Z",
  "system_info": {
    "cpu_usage": 15.2,
    "memory_usage": 45.8,
    "disk_usage": 23.1
  },
  "environment_validation": {
    "status": "healthy",
    "issues": {
      "critical": 0,
      "errors": 0,
      "warnings": 1
    }
  }
}
```

#### **메트릭 조회**

```http
GET /metrics
```

## 🔒 **보안**

### API 키 인증

```python
# API 키 생성 (개발용)
from app.core.security import create_demo_api_key

demo_key = create_demo_api_key()
print(f"Demo API Key: {demo_key['api_key']}")
```

### Rate Limiting

- **기본 제한**: 100 요청/시간
- **코드 생성**: 50 요청/시간
- **스트리밍**: 10 동시 연결
- **IP별 제한**: 1000 요청/일

### 보안 헤더

```python
# 운영 환경에서 자동 적용
ENABLE_SECURITY_HEADERS=true
ENABLE_CSRF_PROTECTION=true
```

## 📊 **모니터링**

### Prometheus 메트릭

```bash
# 메트릭 확인
curl http://localhost:8000/metrics

# 주요 메트릭
- hapa_requests_total: 총 요청 수
- hapa_request_duration_seconds: 요청 처리 시간
- hapa_cache_hits_total: 캐시 히트 수
- hapa_ai_model_requests_total: AI 모델 요청 수
```

### 로깅

```python
# 로그 레벨별 설정
LOG_LEVEL=DEBUG    # 개발: DEBUG, 운영: WARNING
LOG_FILE_ROTATION=true
LOG_MAX_SIZE=50MB
```

### 성능 통계

```http
GET /stats
```

## 🧪 **테스트**

### 단위 테스트

```bash
# 전체 테스트 실행
python -m pytest tests/ -v

# 커버리지 포함
python -m pytest tests/ --cov=app --cov-report=html

# 특정 모듈 테스트
python -m pytest tests/test_code_generation.py -v
```

### 통합 테스트

```bash
# 통합 테스트 실행
python test_integration.py

# API 테스트
python -m pytest tests/test_api.py -v
```

### 성능 테스트

```bash
# AI 모델 보안 테스트
python test_ai_model_security.py

# 부하 테스트 (개발 도구)
# locust -f tests/locustfile.py --host=http://localhost:8000
```

## 🚀 **배포**

### Docker 배포

```yaml
# docker-compose.yml
version: "3.8"
services:
  backend:
    build: ./Backend
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - SECRET_KEY=${SECRET_KEY}
      - AI_MODEL_API_KEY=${AI_MODEL_API_KEY}
    volumes:
      - ./data:/app/data
```

### 프로덕션 배포

```bash
# 1. 환경 변수 검증
python -c "from app.services.environment_validator import validate_environment_on_startup; validate_environment_on_startup()"

# 2. 운영 서버 시작
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 3. 모니터링 확인
curl http://localhost:8000/health
curl http://localhost:9090/metrics
```

## 🐛 **트러블슈팅**

### 자주 발생하는 문제

#### 1. 환경 변수 오류

```bash
# 환경 변수 검증
python -c "from app.services.environment_validator import environment_validator; results = environment_validator.validate_all(); print(results)"
```

#### 2. AI 모델 연결 실패

```bash
# API 키 확인
curl -H "Authorization: Bearer $AI_MODEL_API_KEY" https://api.openai.com/v1/models
```

#### 3. 메모리 사용량 증가

```python
# 캐시 정리
import requests
requests.delete("http://localhost:8000/api/v1/cache/clear")
```

#### 4. 포트 충돌

```bash
# 포트 사용 확인
lsof -i :8000
kill -9 <PID>
```

### 로그 분석

```bash
# 에러 로그 확인
grep "ERROR" logs/app.log | tail -20

# 성능 이슈 확인
grep "SLOW" logs/app.log | tail -10
```

## 📚 **추가 문서**

- [📋 **API 명세서**](../docs/backend/api_specification_v1.0.md)
- [🔧 **환경 설정 가이드**](../docs/backend/README_Environment_Setup.md)
- [🚀 **배포 가이드**](../docs/backend/README_Deploy.md)
- [📊 **성능 최적화**](../docs/backend/performance_optimization_report.md)
- [🔒 **보안 가이드**](../docs/backend/security_enhancement_report.md)

## 🤝 **기여하기**

1. **포크** 후 feature 브랜치 생성
2. **코드 수정** 및 테스트 작성
3. **Lint 검사** 통과 확인
4. **Pull Request** 생성

### 코드 스타일

```bash
# 코드 포맷팅
black app/
isort app/

# 린트 검사
flake8 app/
mypy app/
```

---

**개발팀**: 한컴AI Backend Team  
**버전**: v0.4.0  
**문의**: backend-dev@hancom.com
