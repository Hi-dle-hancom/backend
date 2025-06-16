# HAPA (Hancom AI Python Assistant) API 명세서 v1.0

**작성일**: 2024년 12월 28일  
**버전**: v1.0  
**Base URL**: `http://localhost:8000`  
**API 프리픽스**: `/api/v1`

---

## 📋 **1. 개요**

### **서비스 정보**

- **서비스명**: HAPA (Hancom AI Python Assistant)
- **목적**: VSCode Extension을 위한 AI 기반 Python 코딩 어시스턴트
- **지원 언어**: Python (전용)
- **인증 방식**: API Key 기반 인증

### **API 설계 원칙**

- RESTful API 아키텍처
- JSON 기반 요청/응답
- 표준 HTTP 상태 코드 사용
- 일관된 오류 응답 형식

---

## 📋 **2. 인증 시스템**

### **API Key 인증**

**헤더 방식 1** (권장):

```http
X-API-Key: hapa_1234567890abcdef1234567890abcdef
```

**헤더 방식 2**:

```http
Authorization: ApiKey hapa_1234567890abcdef1234567890abcdef
```

### **권한 체계**

- `code_generation`: 코드 생성 권한
- `code_completion`: 자동 완성 권한
- `feedback`: 피드백 제출 권한
- `history`: 히스토리 조회 권한

### **Rate Limiting**

- `/generate`: 시간당 50회
- `/complete`: 시간당 100회
- `/feedback`: 시간당 20회

---

## 📋 **3. 핵심 API 엔드포인트**

### **3.1 코드 생성 API**

#### **POST /api/v1/code/generate**

Python 코드를 생성합니다.

**요청 헤더**:

```http
Content-Type: application/json
X-API-Key: {your_api_key}
```

**요청 본문**:

```json
{
  "user_question": "피보나치 수열을 계산하는 함수를 만들어주세요",
  "code_context": "# 수학 관련 함수들\n",
  "language": "python",
  "file_path": "/src/math_functions.py"
}
```

**요청 스키마**:

```python
class CodeGenerationRequest(BaseModel):
    user_question: str = Field(..., min_length=1, max_length=10000)
    code_context: Optional[str] = Field(None, max_length=50000)
    language: Optional[str] = Field("python")
    file_path: Optional[str] = Field(None, max_length=1000)
```

**성공 응답** (200):

```json
{
  "generated_code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
  "explanation": "피보나치 수열을 재귀적으로 계산하는 함수입니다.",
  "status": "success",
  "error_message": null
}
```

**오류 응답**:

- **401 Unauthorized**: API Key 필요
- **403 Forbidden**: 권한 부족
- **422 Validation Error**: 요청 데이터 검증 실패
- **429 Too Many Requests**: Rate Limit 초과

---

### **3.2 코드 자동 완성 API**

#### **POST /api/v1/code/complete**

Python 코드 자동 완성 제안을 제공합니다.

**요청 본문**:

```json
{
  "prefix": "def calculate_",
  "language": "python",
  "cursor_position": 14,
  "file_path": "/src/calculator.py"
}
```

**요청 스키마**:

```python
class CompletionRequest(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=5000)
    language: str = Field("python")
    cursor_position: Optional[int] = Field(None, ge=0)
    file_path: Optional[str] = Field(None, max_length=1000)
```

**성공 응답** (200):

```json
{
  "completions": [
    "def calculate_average(numbers):",
    "def calculate_sum(values):",
    "def calculate_max(data):"
  ],
  "status": "success",
  "error_message": null
}
```

---

### **3.3 피드백 제출 API**

#### **POST /api/v1/feedback/submit**

사용자 피드백을 제출합니다.

**요청 본문**:

```json
{
  "session_id": "session_123",
  "feedback_type": "positive",
  "rating": 5,
  "comment": "생성된 코드가 매우 유용했습니다",
  "generated_code": "def hello_world():\n    print('Hello, World!')",
  "user_question": "Hello World 함수를 만들어주세요"
}
```

**성공 응답** (200):

```json
{
  "feedback_id": "feedback_abc123",
  "status": "success",
  "message": "피드백이 성공적으로 제출되었습니다."
}
```

---

### **3.4 히스토리 조회 API**

#### **GET /api/v1/history/sessions**

사용자의 세션 히스토리를 조회합니다.

**쿼리 파라미터**:

- `limit`: 조회할 세션 수 (기본값: 20)
- `offset`: 시작 위치 (기본값: 0)

**성공 응답** (200):

```json
{
  "sessions": [
    {
      "session_id": "session_123",
      "created_at": "2024-12-28T10:30:00Z",
      "questions_count": 5,
      "last_activity": "2024-12-28T11:00:00Z"
    }
  ],
  "total_count": 1,
  "has_more": false
}
```

---

## 📋 **4. 시스템 API 엔드포인트**

### **4.1 헬스 체크**

#### **GET /health**

서버 상태를 확인합니다. (인증 불필요)

**성공 응답** (200):

```json
{
  "status": "healthy",
  "message": "HAPA 백엔드 API is healthy",
  "version": "0.4.0",
  "timestamp": "2024-12-28T10:30:00Z",
  "system_info": {
    "cpu_percent": 25.5,
    "memory_percent": 45.2,
    "disk_percent": 60.1
  },
  "performance_metrics": {
    "requests_per_minute": 120,
    "average_response_time": 0.25,
    "error_rate": 0.01
  }
}
```

### **4.2 성능 통계**

#### **GET /stats**

성능 통계 정보를 반환합니다.

**성공 응답** (200):

```json
{
  "performance": {
    "status": "healthy",
    "system": {
      "cpu_percent": 25.5,
      "memory_percent": 45.2
    },
    "application": {
      "requests_per_minute": 120,
      "average_response_time": 0.25
    }
  },
  "response_times": {
    "total_requests": 1000,
    "average_response_time": 0.25,
    "min_response_time": 0.05,
    "max_response_time": 2.1
  }
}
```

### **4.3 Prometheus 메트릭**

#### **GET /metrics**

Prometheus 형식의 메트릭을 반환합니다.

**응답 타입**: `text/plain`

**응답 예시**:

```
# HELP api_requests_total Total API requests
# TYPE api_requests_total counter
api_requests_total{method="POST",endpoint="/generate",status="200"} 1000

# HELP api_request_duration_seconds API request duration
# TYPE api_request_duration_seconds histogram
api_request_duration_seconds_bucket{le="0.1"} 500
```

---

## 📋 **5. 코드 검증 API**

### **5.1 단일 코드 검증**

#### **POST /api/v1/validation/validate**

Python 코드의 구문, 스타일, 실행 가능성을 검증합니다.

**요청 본문**:

```json
{
  "code": "def hello():\n    print('Hello, World!')",
  "language": "python",
  "file_name": "test.py",
  "check_execution": true,
  "check_style": false
}
```

**성공 응답** (200):

```json
{
  "validation_id": "val_abc123",
  "status": "valid",
  "is_valid": true,
  "is_executable": true,
  "issues": [],
  "total_issues": 0,
  "error_count": 0,
  "warning_count": 0,
  "lines_of_code": 2,
  "functions_count": 1,
  "classes_count": 0,
  "validation_time": 0.025
}
```

### **5.2 배치 코드 검증**

#### **POST /api/v1/validation/validate/batch**

여러 코드 스니펫을 한 번에 검증합니다.

**요청 본문**:

```json
{
  "code_snippets": [
    {
      "code": "def hello():\n    print('Hello')",
      "language": "python"
    },
    {
      "code": "def world():\n    print('World')",
      "language": "python"
    }
  ],
  "common_language": "python",
  "session_id": "session_123"
}
```

---

## 📋 **6. 오류 응답 형식**

### **표준 오류 응답**

```json
{
  "status": "error",
  "error_message": "유효하지 않은 API Key입니다.",
  "error_code": "UNAUTHORIZED",
  "error_details": {
    "request_path": "/api/v1/generate",
    "timestamp": "2024-12-28T10:30:00Z"
  }
}
```

### **유효성 검사 오류**

```json
{
  "status": "error",
  "error_message": "요청 데이터 유효성 검사에 실패했습니다",
  "error_code": "VALIDATION_ERROR",
  "error_details": {
    "user_question": ["field required"],
    "language": ["현재 Python 언어만 지원됩니다."]
  }
}
```

---

## 📋 **7. SDK 및 클라이언트 예시**

### **JavaScript/TypeScript (VSCode Extension)**

```typescript
class HAPAClient {
  private apiKey: string;
  private baseUrl: string;

  constructor(apiKey: string, baseUrl = "http://localhost:8000") {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
  }

  async generateCode(
    question: string,
    context?: string
  ): Promise<CodeGenerationResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/code/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
      },
      body: JSON.stringify({
        user_question: question,
        code_context: context,
        language: "python",
      }),
    });

    return response.json();
  }
}
```

### **Python 클라이언트**

```python
import requests

class HAPAClient:
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }

    def generate_code(self, question: str, context: str = None) -> dict:
        url = f"{self.base_url}/api/v1/code/generate"
        data = {
            "user_question": question,
            "code_context": context,
            "language": "python"
        }

        response = requests.post(url, json=data, headers=self.headers)
        return response.json()
```

---

## 📋 **8. 개발 및 테스트**

### **로컬 개발 서버 실행**

```bash
# 백엔드 서버 시작
cd Backend
python -m uvicorn main:app --reload --port 8000

# API 문서 확인
open http://localhost:8000/docs
```

### **데모 API Key**

개발 환경에서는 서버 시작 시 자동으로 생성되는 데모 API Key를 사용할 수 있습니다.

```bash
# 서버 로그에서 데모 키 확인
# 또는 /stats 엔드포인트에서 확인
```

### **curl 테스트 예시**

```bash
# 코드 생성 테스트
curl -X POST http://localhost:8000/api/v1/code/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "user_question": "Hello World 함수를 만들어주세요",
    "language": "python"
  }'
```
