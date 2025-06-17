# HAPA Backend API Server 🖥️

HAPA 백엔드는 Python 개발자를 위한 AI 코딩 어시스턴트의 핵심 API 서버입니다.

## 🎯 주요 기능

- **코드 생성 API**: AI 모델을 활용한 Python 코드 자동 생성
- **자동완성 API**: 컨텍스트 기반 스마트 코드 자동완성
- **코드 검증 API**: 실시간 문법 검사 및 오류 감지
- **피드백 시스템**: 사용자 피드백 수집 및 분석
- **히스토리 관리**: 생성 내역 및 세션 관리
- **성능 모니터링**: 실시간 성능 지표 추적
- **캐시 시스템**: 응답 속도 최적화

## 🚀 빠른 시작

### 설치 및 실행

```bash
# 환경 설정
cp .env.example .env
# .env 파일에서 필요한 값들 수정

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
python main.py
```

서버는 `http://localhost:8000`에서 실행됩니다.

### Docker 실행

```bash
# 개발 환경
docker-compose up -d

# 프로덕션 환경
docker-compose -f docker-compose.yml up -d
```

## 📡 API 엔드포인트

### 코드 생성

- `POST /api/v1/code-generation/generate` - AI 코드 생성
- `POST /api/v1/code-generation/complete` - 코드 자동완성

### 검증

- `POST /api/v1/validation/validate` - 코드 문법 검증

### 피드백

- `POST /api/v1/feedback/submit` - 피드백 제출
- `GET /api/v1/feedback/statistics` - 피드백 통계

### 히스토리

- `GET /api/v1/history/sessions` - 세션 목록
- `POST /api/v1/history/entries` - 항목 추가

### 캐시 관리 (관리자 전용)

- `GET /api/v1/cache/stats` - 캐시 통계
- `DELETE /api/v1/cache/clear` - 캐시 초기화

### 시스템

- `GET /health` - 헬스 체크
- `GET /` - API 정보

## 🏗️ 아키텍처

```
app/
├── api/                 # REST API 라우터
│   ├── api.py          # 메인 라우터
│   └── endpoints/      # 엔드포인트 모듈
├── core/               # 핵심 설정
│   ├── config.py       # 환경 설정
│   ├── security.py     # 보안 및 인증
│   └── logging_config.py # 로깅 설정
├── schemas/            # Pydantic 모델
├── services/           # 비즈니스 로직
│   ├── ai_model.py     # AI 모델 인터페이스
│   ├── cache_service.py # 캐시 시스템
│   ├── code_generator.py # 코드 생성
│   └── validation_service.py # 검증 서비스
└── data/               # 데이터 저장소
```

## 🔧 환경 설정

### 필수 환경 변수

```env
# 기본 설정
DEBUG=true
HOST=localhost
PORT=8000

# AI 모델 (준비중)
AI_MODEL_API_KEY=your_api_key_here
AI_MODEL_ENDPOINT=https://api.openai.com/v1/completions

# 보안
SECRET_KEY=your_secret_key_here
API_KEY_EXPIRY_DAYS=30

# 성능
CACHE_TTL=3600
MAX_CACHE_SIZE=1000
```

전체 환경 설정은 [환경 설정 가이드](README_Environment_Setup.md)를 참조하세요.

## 🧪 테스트

```bash
# 단위 테스트
python -m pytest tests/ -v

# 통합 테스트
python test_integration.py

# API 테스트 (Thunder Client)
# thunder-tests/ 디렉토리의 테스트 컬렉션 사용
```

## 📊 모니터링

### 헬스 체크

```bash
curl http://localhost:8000/health
```

### 성능 메트릭

- API 응답 시간
- 캐시 히트율
- 에러율
- 활성 세션 수

## 🔒 보안

- **API 키 인증**: 모든 API 요청에 인증 필요
- **Rate Limiting**: 요청 속도 제한
- **입력 검증**: Pydantic 기반 데이터 검증
- **CORS 설정**: 프론트엔드 도메인 허용
- **보안 헤더**: 표준 보안 헤더 적용

## 📚 상세 문서

- [API 명세서](docs/api_specification_v1.0.md) - 전체 API 문서
- [시스템 아키텍처](docs/system_architecture_v2.md) - 설계 문서
- [배포 가이드](README_Deploy.md) - Docker 배포 가이드
- [보안 강화](docs/security_enhancement_report.md) - 보안 기능 상세
- [성능 최적화](docs/performance_optimization_report.md) - 성능 튜닝

## 🛠️ 기술 스택

- **Framework**: FastAPI 0.104+
- **Language**: Python 3.12+
- **Validation**: Pydantic v2
- **Authentication**: API Key 기반
- **Cache**: File-based (개발), Redis (프로덕션)
- **Database**: File-based (개발), PostgreSQL (프로덕션)
- **Monitoring**: Custom metrics + Prometheus
- **Deployment**: Docker + Docker Compose

## 🔄 개발 워크플로우

1. **환경 설정**: `.env` 파일 구성
2. **의존성 설치**: `pip install -r requirements.txt`
3. **개발 서버 실행**: `python main.py`
4. **API 테스트**: Thunder Client 또는 Swagger UI
5. **테스트 실행**: `pytest`
6. **Docker 빌드**: `docker build -t hapa-backend .`

## 📈 성능 최적화

- **캐시 시스템**: LRU 캐시로 응답 속도 향상
- **비동기 처리**: FastAPI 비동기 기능 활용
- **연결 풀링**: 데이터베이스 연결 최적화
- **압축**: 응답 데이터 gzip 압축
- **CDN**: 정적 파일 CDN 배포

## 🐛 문제 해결

### 자주 발생하는 문제

1. **포트 충돌**: 8000번 포트 사용중

   ```bash
   # 다른 포트로 실행
   uvicorn main:app --port 8001
   ```

2. **환경 변수 오류**: `.env` 파일 누락

   ```bash
   cp .env.example .env
   # 필요한 값들 설정
   ```

3. **의존성 오류**: Python 버전 불일치
   ```bash
   python --version  # 3.12+ 확인
   pip install -r requirements.txt
   ```

## 🤝 기여하기

1. Issue 생성 또는 기존 Issue 확인
2. Feature Branch 생성: `git checkout -b feature/new-feature`
3. 코드 작성 및 테스트
4. Pull Request 생성

---

**버전**: v0.4.0  
**상태**: 프로덕션 준비 완료
