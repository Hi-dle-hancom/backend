# HAPA (Hancom AI Python Assistant) - 백엔드 API

HAPA VSCode 확장 프로그램을 위한 Python 전용 AI 코딩 어시스턴트 백엔드 API 서버입니다. 사용자 질문에 기반한 Python 코드 생성 및 자동 완성 기능을 제공하며, 다양한 입력 방식을 지원합니다.

**개발팀**: 하이들 (Hi-dle)

## 📋 프로젝트 개요

이 백엔드 API는 HAPA VSCode 확장 프로그램과 연동하여 사용자가 Python 코드를 쉽게 생성하고 완성할 수 있도록 도와주는 서비스입니다. 현재 4주차까지 개발이 완료되었으며, 모든 핵심 기능이 구현되어 테스트를 통과했습니다.

### ✨ 핵심 기능

- **Python 코드 생성**: 자연어 질문을 기반으로 고품질 Python 코드 생성
- **코드 자동 완성**: 코드 접두사를 기반으로 지능형 완성 제안
- **다양한 입력 방식 지원**: 사이드바 입력, 자동 완성, 주석 트리거 방식
- **표준화된 오류 처리**: 모든 API 응답에 일관된 오류 형식 제공
- **AI 모델 응답 정교한 파싱**: 마크다운, 여러 코드 블록 등 다양한 응답 형식 처리

## 🔍 최신 업데이트 (4주차)

### 1. AI 모델 추론 결과 처리 로직 구체화

- **마크다운 코드 블록 파싱**: AI 모델이 마크다운 형식으로 반환하는 코드 블록 추출
- **최적 코드 블록 선택**: 여러 코드 블록 중 가장 적절한 것을 선택하는 알고리즘
- **Python 문법 검증**: 생성된 코드의 기본 문법 오류 검증
- **설명과 코드 분리**: AI 응답에서 코드와 설명 부분을 정확히 분리

### 2. API 오류 응답 표준화

- **표준 오류 응답 스키마**: 모든 오류에 일관된 형식 적용
- **유효성 검사 오류 처리**: 요청 데이터 검증 실패 시 상세 오류 메시지 제공
- **HTTP 예외 핸들러**: 다양한 HTTP 오류 상황에 대한 일관된 응답
- **일반 예외 처리**: 예상치 못한 서버 오류에 대한 안전한 응답

## 🛠️ 기술 스택

- **언어**: Python 3.12+
- **웹 프레임워크**: FastAPI
- **ASGI 서버**: Uvicorn
- **데이터 검증**: Pydantic v2
- **설정 관리**: pydantic-settings
- **테스트 프레임워크**: pytest

## 📁 프로젝트 구조

```
Backend/
├── app/
│   ├── api/                    # API 라우터 및 엔드포인트
│   │   ├── endpoints/
│   │   │   └── code_generation.py  # 코드 생성/완성 API
│   │   └── api.py              # API 라우터 설정
│   ├── core/                   # 핵심 설정 및 유틸리티
│   │   └── config.py           # 환경 설정 관리
│   ├── schemas/                # 데이터 모델 및 스키마
│   │   └── code_generation.py  # 요청/응답 스키마
│   └── services/               # 비즈니스 로직
│       └── inference.py        # AI 모델 서비스
├── tests/                      # 테스트 코드
│   ├── test_code_generation.py # API 엔드포인트 테스트
│   └── test_inference.py       # AI 서비스 테스트
├── main.py                     # FastAPI 애플리케이션 진입점
├── requirements.txt            # 의존성 관리
└── .env                        # 환경 변수 (개발용)
```

## 🚀 설치 및 실행 방법

### 1. 저장소 클론

```bash
git clone <repository-url>
cd Backend
```

### 2. 가상 환경 설정

```bash
# 가상 환경 생성
python -m venv venv

# 가상 환경 활성화 (Windows)
venv\Scripts\activate

# 가상 환경 활성화 (macOS/Linux)
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 추가:

```
DEBUG=true
LOG_LEVEL=info
MODEL_NAME=python_coding_assistant
MODEL_VERSION=1.0.0
```

### 5. 서버 실행

```bash
uvicorn main:app --reload
```

서버가 실행되면 다음 URL에서 접근 가능합니다:

- API 서버: http://localhost:8000
- API 문서: http://localhost:8000/docs

## 📚 API 엔드포인트

### 🔐 인증 (Authentication)

#### API Key 기반 인증 방식

HAPA 백엔드 API는 **API Key 기반 인증 시스템**을 채택하여 보안과 사용량 관리를 제공합니다.

##### 인증 방식 개요

- **API Key란?**: 각 사용자에게 발급되는 고유한 문자열로, 사용자 식별 및 권한 부여를 위한 수단입니다.
- **전송 방식**: 모든 API 요청 시 HTTP 헤더에 API Key를 포함해야 합니다.
- **헤더 형식**: `X-API-Key: YOUR_API_KEY` 또는 `Authorization: ApiKey YOUR_API_KEY`

##### 인증 처리 절차

1. **요청 수신**: 클라이언트로부터 API 요청 수신
2. **헤더 추출**: 요청 헤더에서 API Key 추출
3. **유효성 검증**: 추출된 API Key가 유효한지 데이터베이스에서 확인
4. **권한 확인**: API Key에 연결된 사용자의 권한 및 사용량 제한 확인
5. **요청 처리**: 인증 성공 시 요청 처리, 실패 시 오류 응답 반환

##### 인증 실패 시 응답

- **401 Unauthorized**: API Key가 제공되지 않았거나 유효하지 않은 경우
- **403 Forbidden**: 유효한 API Key이지만 해당 리소스에 대한 접근 권한이 없는 경우
- **429 Too Many Requests**: API 사용량 제한에 도달한 경우

```json
{
  "detail": "Invalid API Key",
  "status_code": 401,
  "timestamp": "2024-12-28T10:30:00Z"
}
```

#### 인증 적용 엔드포인트

다음 엔드포인트들은 **API Key 인증이 필수**입니다:

- `POST /api/v1/code/generate` - 코드 생성 API
- `POST /api/v1/code/complete` - 코드 자동 완성 API
- `POST /api/v1/feedback/submit` - 피드백 제출 API
- `GET /api/v1/history/*` - 히스토리 관련 모든 API

다음 엔드포인트는 **인증이 불필요**합니다:

- `GET /` - 서버 상태 확인
- `GET /health` - 헬스 체크
- `GET /docs` - API 문서

#### 🔑 API KEY 관리 방안

##### 1. API Key 생성 (Generation)

###### 생성 시점

- **사용자 등록 시**: VSCode Extension 최초 설치 및 활성화 시 자동 생성
- **사용자 요청 시**: 기존 Key 분실 또는 재생성 필요 시
- **관리자 발급**: 엔터프라이즈 사용자 대상 수동 발급

###### 생성 방식

- **UUID4 기반**: 32자리 고유 식별자 생성 (`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`)
- **접두사 포함**: HAPA 서비스 식별을 위한 접두사 (`hapa_` + UUID)
- **예시**: `hapa_a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d`

```python
import uuid
import secrets

def generate_api_key() -> str:
    """보안성이 강화된 API Key 생성"""
    random_part = secrets.token_hex(16)  # 32자리 랜덤 문자열
    return f"hapa_{random_part}"
```

##### 2. API Key 저장 (Storage)

###### 저장 위치

- **프로덕션**: PostgreSQL 데이터베이스의 `api_keys` 테이블
- **개발 환경**: SQLite 데이터베이스 또는 JSON 파일

###### 저장 방식

- **해시화 저장**: 원본 Key는 SHA-256으로 해시화하여 저장
- **메타데이터 포함**: 생성일, 만료일, 사용량, 권한 레벨 등 함께 저장
- **백업**: 정기적인 데이터베이스 백업으로 Key 손실 방지

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    usage_count INTEGER DEFAULT 0,
    rate_limit INTEGER DEFAULT 1000
);
```

##### 3. API Key 배포 (Distribution)

###### VSCode Extension 사용자

- **자동 등록**: Extension 최초 실행 시 백엔드 API 호출하여 자동 Key 발급
- **로컬 저장**: VSCode의 Global State 또는 Secret Storage에 안전하게 저장
- **자동 갱신**: Key 만료 시 자동으로 새 Key 요청 및 갱신

###### 웹 포털 사용자 (향후 구현)

- **대시보드 제공**: 사용자 전용 웹 포털에서 API Key 확인 및 관리
- **이메일 발송**: 보안을 위해 Key의 일부만 이메일로 발송
- **QR 코드**: 모바일 환경에서 쉬운 Key 입력을 위한 QR 코드 제공

##### 4. 사용자 관리 (User Management)

###### Key 재생성

- **사용자 요청**: 웹 포털 또는 Extension에서 Key 재생성 요청
- **보안 절차**: 기존 Key 즉시 무효화 후 새 Key 발급
- **알림 시스템**: Key 변경 시 사용자에게 알림 전송

###### 사용량 모니터링

- **실시간 추적**: API 호출 횟수, 시간대별 사용 패턴 분석
- **제한 관리**: 사용자별 일일/월별 API 호출 제한 설정
- **알림**: 사용량 임계점 도달 시 사용자에게 알림

```python
class APIKeyManager:
    async def track_usage(self, api_key: str, endpoint: str):
        """API 사용량 추적 및 제한 확인"""
        key_info = await self.get_key_info(api_key)
        key_info.usage_count += 1

        if key_info.usage_count > key_info.rate_limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

##### 5. API Key 폐기 (Revocation)

###### 자동 폐기

- **만료일 도달**: 설정된 만료일에 자동으로 Key 비활성화
- **비활성 사용자**: 90일 이상 미사용 시 자동 폐기
- **보안 위반**: 비정상적인 사용 패턴 감지 시 자동 차단

###### 수동 폐기

- **사용자 요청**: 사용자가 직접 Key 삭제 요청
- **관리자 조치**: 서비스 남용 또는 정책 위반 시 관리자가 강제 폐기
- **일괄 폐기**: 보안 사고 발생 시 모든 Key 일괄 무효화

###### 폐기 절차

1. **즉시 비활성화**: 데이터베이스에서 `is_active = FALSE` 설정
2. **캐시 무효화**: Redis 등 캐시 시스템에서 Key 정보 삭제
3. **로그 기록**: 폐기 사유 및 시점 상세 로그 기록
4. **사용자 알림**: Key 폐기 사실을 사용자에게 알림

##### 6. 보안 고려사항

###### 클라이언트 보안

- **안전한 저장**: VSCode Extension에서 OS의 보안 저장소 활용
- **HTTPS 필수**: 모든 API 통신은 HTTPS로만 허용
- **Key 노출 방지**: 로그, 오류 메시지에 API Key 노출 금지

###### 서버 보안

- **해시화 저장**: 원본 API Key는 절대 평문으로 저장하지 않음
- **접근 제어**: 데이터베이스 접근 권한 최소화
- **감사 로그**: 모든 인증 시도 및 실패 기록

```python
# 보안 강화 예시
class SecurityManager:
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """API Key를 SHA-256으로 해시화"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def verify_api_key(api_key: str, stored_hash: str) -> bool:
        """API Key 검증"""
        return hashlib.sha256(api_key.encode()).hexdigest() == stored_hash
```

### 1. 코드 생성 API

**엔드포인트**: `POST /api/v1/code/generate`

Python 코드를 생성하는 엔드포인트입니다. 자연어 질문을 기반으로 코드를 생성하며, 주석 트리거 방식도 지원합니다.

**요청 형식**:

```json
{
  "user_question": "피보나치 수열을 계산하는 함수를 만들어줘",
  "code_context": "# 선택적 코드 컨텍스트",
  "language": "python",
  "file_path": "/path/to/file.py"
}
```

**응답 형식**:

```json
{
  "generated_code": "def fibonacci(n):\n    ...",
  "explanation": "피보나치 수열을 계산하는 재귀 함수입니다...",
  "status": "success",
  "error_message": null
}
```

### 2. 코드 자동 완성 API

**엔드포인트**: `POST /api/v1/code/complete`

Python 코드 자동 완성 제안을 제공하는 엔드포인트입니다.

**요청 형식**:

```json
{
  "prefix": "def calc",
  "language": "python",
  "cursor_position": 8,
  "file_path": "/path/to/file.py"
}
```

**응답 형식**:

```json
{
  "completions": ["def calculate(x, y):", "def calculate_average(numbers):"],
  "status": "success",
  "error_message": null
}
```

## 🧪 테스트

프로젝트는 총 **80개의 테스트 케이스**로 철저하게 검증되었습니다.

### 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 특정 테스트 파일 실행
pytest tests/test_inference.py

# 상세 출력과 함께 실행
pytest -v
```

### 테스트 범위

- **API 엔드포인트 테스트**: 31개

  - 코드 생성 API 테스트
  - 코드 자동 완성 API 테스트
  - 오류 처리 테스트

- **AI 서비스 테스트**: 49개
  - 모델 로딩 및 초기화 테스트
  - 코드 생성 기능 테스트
  - 주석 트리거 처리 테스트
  - 마크다운 코드 블록 파싱 테스트
  - 여러 코드 블록 처리 테스트
  - Python 문법 검증 테스트

## 🔄 주요 기능 구현 상세

### AI 모델 응답 파싱 로직

AI 모델이 반환하는 다양한 형태의 응답을 처리하기 위한 정교한 파싱 로직이 구현되어 있습니다:

1. **마크다운 코드 블록 추출**: `python ... ` 형식의 코드 블록 인식 및 추출
2. **최적 코드 블록 선택**: 여러 코드 블록 중 가장 적합한 것을 선택하는 알고리즘
3. **Python 문법 검증**: AST 파싱을 통한 기본 문법 오류 검증
4. **설명과 코드 분리**: 코드 블록을 제외한 텍스트를 설명으로 추출

### 주석 트리거 처리

다양한 형태의 주석 트리거를 인식하고 처리하는 기능이 구현되어 있습니다:

- **트리플 슬래시**: `/// prompt: 코드 생성 요청`
- **@gen 태그**: `@gen: 코드 생성 요청`
- **해시 주석**: `# prompt: 코드 생성 요청`
- **더블 슬래시**: `// prompt: 코드 생성 요청`
- **여러 줄 주석**: 여러 줄에 걸친 주석 자동 파싱

### 표준화된 오류 처리

모든 API 응답에 일관된 오류 형식을 제공하는 시스템이 구현되어 있습니다:

- **ValidationErrorResponse**: 요청 데이터 검증 실패 시 사용
- **ErrorResponse**: 일반적인 오류 상황에 사용
- **HTTP 예외 핸들러**: 다양한 HTTP 오류 상황에 대한 일관된 응답

## 🔮 향후 계획

### 1. 실제 AI 모델 연동

- 현재는 더미 모델을 사용하고 있으며, 향후 실제 AI 모델(OpenAI, HuggingFace 등)과 연동할 예정입니다.

### 2. 성능 최적화

- 응답 속도 개선 및 캐싱 시스템 구현을 통한 성능 향상을 계획하고 있습니다.

### 3. 지원 언어 확장

- 현재는 Python만 지원하고 있으며, 향후 JavaScript, TypeScript 등 추가 언어 지원을 검토 중입니다.

## 📝 개발자 참고 사항

### 코드 스타일 및 품질

- 프로젝트는 PEP 8 스타일 가이드를 따릅니다.
- 모든 새로운 기능에 대한 테스트 작성이 권장됩니다.

### 기여 방법

1. 이슈 생성 또는 기존 이슈 확인
2. 기능 브랜치 생성
3. 코드 작성 및 테스트
4. Pull Request 제출

## 📞 문의 및 지원

프로젝트에 대한 질문이나 제안사항이 있으시면 이슈를 생성해 주세요.

---

**현재 상태**: 4주차 개발 완료, 모든 핵심 기능 구현 및 테스트 통과 (80개 테스트 케이스)
