# HAPA 백엔드 표준 오류 응답 스키마 정의서

**작성일**: 2024년 12월 28일  
**버전**: v1.0  
**목적**: 일관된 오류 응답 형식 정의

---

## 📋 **1. 기본 오류 응답 스키마**

### **ErrorResponse 모델**

```python
class ErrorResponse(BaseModel):
    """표준 오류 응답 모델"""
    status: str = Field("error", description="응답 상태 (항상 error)")
    error_message: str = Field(..., description="오류 메시지")
    error_code: Optional[str] = Field(None, description="오류 코드 (선택사항)")
    error_details: Optional[Dict[str, Any]] = Field(None, description="상세 오류 정보 (선택사항)")
```

**응답 예시**:

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

---

## 📋 **2. 유효성 검사 오류 응답 스키마**

### **ValidationErrorResponse 모델**

```python
class ValidationErrorResponse(ErrorResponse):
    """유효성 검사 오류 응답 모델"""
    error_code: str = Field("VALIDATION_ERROR", description="유효성 검사 오류 코드")
    error_details: Dict[str, List[str]] = Field(..., description="필드별 유효성 검사 오류 목록")
```

**응답 예시**:

```json
{
  "status": "error",
  "error_message": "요청 데이터 유효성 검사에 실패했습니다: Input should be a valid string",
  "error_code": "VALIDATION_ERROR",
  "error_details": {
    "user_question": ["field required"],
    "language": ["현재 Python 언어만 지원됩니다."]
  }
}
```

---

## 📋 **3. HTTP 상태 코드별 오류 코드 매핑**

| HTTP 상태 코드 | 오류 코드             | 설명                 |
| -------------- | --------------------- | -------------------- |
| 400            | BAD_REQUEST           | 잘못된 요청          |
| 401            | UNAUTHORIZED          | 인증 실패            |
| 403            | FORBIDDEN             | 권한 부족            |
| 404            | NOT_FOUND             | 리소스 찾을 수 없음  |
| 405            | METHOD_NOT_ALLOWED    | 허용되지 않은 메서드 |
| 409            | CONFLICT              | 충돌 발생            |
| 422            | VALIDATION_ERROR      | 유효성 검사 실패     |
| 429            | TOO_MANY_REQUESTS     | 요청 제한 초과       |
| 500            | INTERNAL_SERVER_ERROR | 내부 서버 오류       |
| 502            | BAD_GATEWAY           | 게이트웨이 오류      |
| 503            | SERVICE_UNAVAILABLE   | 서비스 사용 불가     |

---

## 📋 **4. 프로덕션 vs 개발 환경 오류 정보**

### **개발 환경** (DEBUG=True)

- 상세한 예외 정보 포함
- 스택 트레이스 노출
- 내부 구현 정보 제공

### **프로덕션 환경** (DEBUG=False)

- 일반적인 오류 메시지만 제공
- 민감한 정보 숨김
- 사용자 친화적 메시지

---

## 📋 **5. 오류 응답 검증 규칙**

### **필수 필드**

- `status`: 항상 "error"
- `error_message`: 사용자에게 표시될 오류 메시지

### **선택 필드**

- `error_code`: 클라이언트 측 오류 처리용
- `error_details`: 상세 디버깅 정보

### **검증 로직**

```python
@field_validator('status')
@classmethod
def validate_status(cls, v):
    """상태 값은 항상 error여야 합니다."""
    return "error"
```
