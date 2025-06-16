# HAPA 시스템 아키텍처 v2.0 및 컴포넌트 간 통신 정의

**작성일**: 2024년 12월 28일  
**버전**: v2.0  
**목적**: 전체 시스템 아키텍처 및 컴포넌트 간 통신 구조 정의

---

## 📋 **1. 전체 시스템 아키텍처 다이어그램**

### **1.1 High-Level 아키텍처**

```mermaid
graph TB
    subgraph "사용자 환경"
        VSCode[VSCode Editor]
        VSExt[HAPA VSCode Extension]
        Browser[웹 브라우저]
    end

    subgraph "프론트엔드 레이어"
        LP[Landing Page<br/>React + TypeScript]
        WebView[Extension WebView<br/>HTML + CSS + JS]
    end

    subgraph "백엔드 레이어"
        API[FastAPI Server<br/>Python 3.12+]
        Auth[인증 시스템<br/>API Key Manager]
        RateLimit[Rate Limiter<br/>Redis-like Storage]
    end

    subgraph "AI 서비스 레이어"
        AIModel[AI Code Generator<br/>Python 전용]
        Cache[Response Cache<br/>LRU Cache]
        Profiler[Performance Profiler]
    end

    subgraph "데이터 레이어"
        FileStore[파일 저장소<br/>JSON Files]
        Logs[로그 시스템<br/>Structured Logging]
        Metrics[메트릭 수집<br/>Prometheus]
    end

    subgraph "모니터링 레이어"
        Grafana[Grafana Dashboard]
        AlertManager[Alert Manager]
    end

    %% 연결 관계
    VSCode --> VSExt
    VSExt --> WebView
    Browser --> LP

    VSExt --> API
    LP --> API

    API --> Auth
    API --> RateLimit
    API --> AIModel

    AIModel --> Cache
    AIModel --> Profiler

    Auth --> FileStore
    RateLimit --> FileStore
    API --> Logs
    API --> Metrics

    Metrics --> Grafana
    Metrics --> AlertManager

    %% 스타일링
    classDef frontend fill:#e1f5fe
    classDef backend fill:#f3e5f5
    classDef ai fill:#e8f5e8
    classDef data fill:#fff3e0
    classDef monitoring fill:#fce4ec

    class VSCode,VSExt,Browser,LP,WebView frontend
    class API,Auth,RateLimit backend
    class AIModel,Cache,Profiler ai
    class FileStore,Logs,Metrics data
    class Grafana,AlertManager monitoring
```

### **1.2 상세 컴포넌트 구조**

```mermaid
graph TD
    subgraph "VSCode Extension"
        ExtMain[Extension Main<br/>TypeScript]
        ExtUI[Sidebar Panel<br/>WebView]
        ExtCmd[Command Palette<br/>Commands]
        ExtCtx[Context Menu<br/>Right-click]
    end

    subgraph "Backend API"
        Router[API Router<br/>FastAPI]
        CodeGen[Code Generation<br/>Service]
        CodeComp[Code Completion<br/>Service]
        Feedback[Feedback<br/>Service]
        Validation[Code Validation<br/>Service]
    end

    subgraph "Security Layer"
        APIKey[API Key Auth]
        RBAC[Role-Based Access]
        CORS[CORS Handler]
        RateL[Rate Limiting]
    end

    subgraph "AI Engine"
        ModelMgr[Model Manager<br/>Lazy Loading]
        Inference[Inference Engine<br/>Python Generator]
        CacheL[Cache Layer<br/>LRU + Hash]
    end

    ExtMain --> ExtUI
    ExtMain --> ExtCmd
    ExtMain --> ExtCtx

    ExtUI --> Router
    ExtCmd --> Router
    ExtCtx --> Router

    Router --> APIKey
    APIKey --> RBAC
    RBAC --> CORS
    CORS --> RateL

    Router --> CodeGen
    Router --> CodeComp
    Router --> Feedback
    Router --> Validation

    CodeGen --> ModelMgr
    CodeComp --> ModelMgr
    Validation --> ModelMgr

    ModelMgr --> Inference
    Inference --> CacheL
```

---

## 📋 **2. 컴포넌트 간 통신 정의**

### **2.1 VSCode Extension ↔ Backend API 통신**

#### **통신 프로토콜**

- **프로토콜**: HTTP/HTTPS REST API
- **데이터 형식**: JSON
- **인증**: API Key (X-API-Key 헤더)
- **포트**: 8000 (기본값)

#### **통신 플로우**

```mermaid
sequenceDiagram
    participant User as 사용자
    participant VSExt as VSCode Extension
    participant API as Backend API
    participant AI as AI Engine
    participant Cache as Cache Layer

    User->>VSExt: 코드 생성 요청
    VSExt->>VSExt: 컨텍스트 수집
    VSExt->>API: POST /api/v1/code/generate
    Note over VSExt,API: X-API-Key: hapa_xxxxx

    API->>API: 인증 & 권한 확인
    API->>API: Rate Limit 확인

    API->>Cache: 캐시 확인
    alt 캐시 적중
        Cache->>API: 캐시된 응답
    else 캐시 미스
        API->>AI: 코드 생성 요청
        AI->>AI: 모델 추론
        AI->>Cache: 결과 캐싱
        AI->>API: 생성된 코드
    end

    API->>VSExt: JSON 응답
    VSExt->>User: 코드 표시
```

#### **API 통신 인터페이스**

```typescript
// VSCode Extension - API 클라이언트
interface HAPAApiClient {
  // 코드 생성
  generateCode(request: CodeGenerationRequest): Promise<CodeGenerationResponse>;

  // 자동 완성
  completeCode(request: CompletionRequest): Promise<CompletionResponse>;

  // 피드백 제출
  submitFeedback(request: FeedbackRequest): Promise<FeedbackResponse>;

  // 코드 검증
  validateCode(request: ValidationRequest): Promise<ValidationResponse>;
}

// 요청 타입
interface CodeGenerationRequest {
  user_question: string;
  code_context?: string;
  language: "python";
  file_path?: string;
}

// 응답 타입
interface CodeGenerationResponse {
  generated_code: string;
  explanation?: string;
  status: "success" | "error";
  error_message?: string;
}
```

### **2.2 Frontend ↔ Backend 통신**

#### **Landing Page 통신**

```mermaid
sequenceDiagram
    participant Browser as 웹 브라우저
    participant LP as Landing Page
    participant API as Backend API

    Browser->>LP: 페이지 접속
    LP->>LP: React 앱 로드

    LP->>API: GET /health
    API->>LP: 서버 상태 응답

    LP->>API: GET /stats
    API->>LP: 성능 통계 응답

    LP->>LP: 대시보드 렌더링
```

#### **WebView 통신**

```typescript
// Extension WebView 통신
interface WebViewMessage {
  command: "generateCode" | "getContext" | "showResult";
  data: any;
}

// WebView -> Extension 메시지
vscode.postMessage({
  command: "generateCode",
  data: {
    question: "Hello World 함수 만들어줘",
    context: getCurrentContext(),
  },
});

// Extension -> WebView 메시지
panel.webview.postMessage({
  command: "showResult",
  data: {
    code: generatedCode,
    explanation: explanation,
  },
});
```

### **2.3 Backend 내부 컴포넌트 통신**

#### **API Layer ↔ Service Layer**

```python
# API Router -> Service 통신
@router.post("/generate", response_model=CodeGenerationResponse)
async def generate_code(
    request: CodeGenerationRequest,
    api_key: Dict[str, Any] = Depends(require_permission("code_generation"))
):
    # Service Layer 호출
    result = await ai_service.generate_python_code(
        prompt=request.user_question,
        context=request.code_context,
        user_id=api_key["user_id"]
    )

    return CodeGenerationResponse(
        generated_code=result["code"],
        explanation=result.get("explanation"),
        status="success"
    )
```

#### **Service Layer ↔ AI Engine**

```python
# AI Service 내부 통신
class AIModelService:
    async def generate_python_code(self, prompt: str, context: str = None, user_id: str = None) -> Dict[str, str]:
        # 캐시 확인
        cache_key = self._generate_cache_key(prompt, context)
        cached_result = await self.cache.get(cache_key)

        if cached_result:
            return cached_result

        # AI 모델 추론
        with performance_profiler.profile_function("ai_inference"):
            result = await self.model.predict_async(prompt, context)

        # 결과 캐싱
        await self.cache.set(cache_key, result, ttl=3600)

        return result
```

---

## 📋 **3. 데이터 흐름 아키텍처**

### **3.1 요청 처리 데이터 플로우**

```mermaid
flowchart TD
    Start([사용자 요청]) --> Ext[Extension 수신]
    Ext --> Validate{요청 유효성}
    Validate -->|실패| Error1[오류 응답]
    Validate -->|성공| Auth[API 인증]

    Auth --> AuthCheck{인증 확인}
    AuthCheck -->|실패| Error2[401 Unauthorized]
    AuthCheck -->|성공| Perm[권한 확인]

    Perm --> PermCheck{권한 검증}
    PermCheck -->|실패| Error3[403 Forbidden]
    PermCheck -->|성공| Rate[Rate Limit]

    Rate --> RateCheck{제한 확인}
    RateCheck -->|초과| Error4[429 Too Many Requests]
    RateCheck -->|통과| Cache[캐시 확인]

    Cache --> CacheHit{캐시 적중}
    CacheHit -->|적중| CacheReturn[캐시 응답]
    CacheHit -->|미스| AI[AI 추론]

    AI --> AIProcess[모델 처리]
    AIProcess --> CacheStore[결과 캐싱]
    CacheStore --> Success[성공 응답]

    CacheReturn --> Log[로깅]
    Success --> Log
    Error1 --> Log
    Error2 --> Log
    Error3 --> Log
    Error4 --> Log

    Log --> End([응답 완료])
```

### **3.2 보안 데이터 흐름**

```mermaid
flowchart LR
    subgraph "클라이언트"
        Client[VSCode Extension]
        APIKey[API Key 저장]
    end

    subgraph "보안 레이어"
        Headers[HTTP Headers]
        Validation[Key Validation]
        Hashing[SHA-256 Hash]
        Storage[Key Storage]
    end

    subgraph "백엔드"
        Auth[Auth Service]
        RBAC[Permission Check]
        Logger[Security Logger]
    end

    Client --> APIKey
    APIKey --> Headers
    Headers --> Validation
    Validation --> Hashing
    Hashing --> Storage
    Storage --> Auth
    Auth --> RBAC
    RBAC --> Logger
```

---

## 📋 **4. 성능 최적화 아키텍처**

### **4.1 캐싱 전략**

```mermaid
graph TD
    subgraph "Multi-Level Cache"
        L1[Level 1: In-Memory<br/>LRU Cache (128개)]
        L2[Level 2: File System<br/>JSON Cache]
        L3[Level 3: Response Cache<br/>Hash-based]
    end

    subgraph "Cache Keys"
        UserKey[User + Question Hash]
        ContextKey[Context Hash]
        CombinedKey[Combined Cache Key]
    end

    Request[API 요청] --> L1
    L1 -->|미스| L2
    L2 -->|미스| L3
    L3 -->|미스| AI[AI 처리]

    UserKey --> CombinedKey
    ContextKey --> CombinedKey
    CombinedKey --> L1

    AI --> Store[캐시 저장]
    Store --> L3
    Store --> L2
    Store --> L1
```

### **4.2 모니터링 아키텍처**

```mermaid
graph LR
    subgraph "Application"
        API[FastAPI App]
        Logger[Structured Logger]
        Metrics[Prometheus Metrics]
    end

    subgraph "Collection"
        LogFile[Log Files]
        MetricEndpoint[/metrics Endpoint]
    end

    subgraph "Analysis"
        Prometheus[Prometheus Server]
        Grafana[Grafana Dashboard]
        Alerts[Alert Manager]
    end

    API --> Logger
    API --> Metrics
    Logger --> LogFile
    Metrics --> MetricEndpoint

    LogFile --> Prometheus
    MetricEndpoint --> Prometheus
    Prometheus --> Grafana
    Prometheus --> Alerts
```

---

## 📋 **5. 배포 아키텍처**

### **5.1 개발 환경**

```mermaid
graph TB
    subgraph "로컬 개발"
        DevVSCode[VSCode + Extension]
        DevBackend[Local Backend<br/>uvicorn --reload]
        DevFrontend[Local Frontend<br/>npm run dev]
    end

    subgraph "개발 도구"
        DevDB[JSON File Storage]
        DevLogs[Console Logs]
        DevMetrics[Local /metrics]
    end

    DevVSCode --> DevBackend
    DevFrontend --> DevBackend
    DevBackend --> DevDB
    DevBackend --> DevLogs
    DevBackend --> DevMetrics
```

### **5.2 프로덕션 환경 (계획)**

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/HAProxy]
    end

    subgraph "Application Tier"
        API1[FastAPI Instance 1]
        API2[FastAPI Instance 2]
        API3[FastAPI Instance 3]
    end

    subgraph "Data Tier"
        Redis[Redis Cache]
        PostgreSQL[PostgreSQL DB]
        FileStorage[File Storage]
    end

    subgraph "Monitoring"
        Prometheus[Prometheus]
        Grafana[Grafana]
        ELK[ELK Stack]
    end

    LB --> API1
    LB --> API2
    LB --> API3

    API1 --> Redis
    API1 --> PostgreSQL
    API1 --> FileStorage

    API2 --> Redis
    API2 --> PostgreSQL
    API2 --> FileStorage

    API3 --> Redis
    API3 --> PostgreSQL
    API3 --> FileStorage

    API1 --> Prometheus
    API2 --> Prometheus
    API3 --> Prometheus

    Prometheus --> Grafana
    API1 --> ELK
    API2 --> ELK
    API3 --> ELK
```

---

## 📋 **6. 확장성 고려사항**

### **6.1 수평 확장 전략**

```mermaid
graph TD
    subgraph "확장 가능한 컴포넌트"
        APIGateway[API Gateway<br/>Kong/Zuul]
        ServiceMesh[Service Mesh<br/>Istio/Linkerd]
        Container[Container Runtime<br/>Docker/K8s]
    end

    subgraph "상태 분리"
        Stateless[Stateless Services<br/>FastAPI Instances]
        StatefulStorage[Stateful Storage<br/>Database/Cache]
    end

    subgraph "AI 확장"
        ModelServing[Model Serving<br/>TensorFlow Serving]
        ModelVersioning[Model Versioning<br/>MLflow]
    end

    APIGateway --> ServiceMesh
    ServiceMesh --> Container
    Container --> Stateless
    Stateless --> StatefulStorage

    ModelServing --> ModelVersioning
    ModelVersioning --> Stateless
```

### **6.2 마이크로서비스 분리 계획**

| 서비스                      | 책임         | 기술 스택               | 확장성          |
| --------------------------- | ------------ | ----------------------- | --------------- |
| **Auth Service**            | 인증/인가    | FastAPI + JWT           | Stateless       |
| **Code Generation Service** | AI 코드 생성 | FastAPI + AI Model      | GPU 확장        |
| **Validation Service**      | 코드 검증    | FastAPI + AST           | CPU 확장        |
| **Feedback Service**        | 피드백 수집  | FastAPI + Queue         | Message Queue   |
| **Analytics Service**       | 사용량 분석  | FastAPI + TimeSeries DB | 데이터 파티셔닝 |

---

## 📋 **7. 보안 아키텍처**

### **7.1 Security-by-Design**

```mermaid
graph TD
    subgraph "클라이언트 보안"
        SecureStorage[Secure Storage<br/>VSCode SecretStorage]
        TLS[TLS 1.3 Encryption]
    end

    subgraph "네트워크 보안"
        HTTPS[HTTPS Only]
        CORS[CORS Policy]
        RateLimiting[Rate Limiting]
    end

    subgraph "애플리케이션 보안"
        APIKeyAuth[API Key Auth]
        RBAC[Role-Based Access]
        InputValidation[Input Validation]
        OutputSanitization[Output Sanitization]
    end

    subgraph "인프라 보안"
        WAF[Web Application Firewall]
        IDS[Intrusion Detection]
        SecurityMonitoring[Security Monitoring]
    end

    SecureStorage --> TLS
    TLS --> HTTPS
    HTTPS --> CORS
    CORS --> RateLimiting

    RateLimiting --> APIKeyAuth
    APIKeyAuth --> RBAC
    RBAC --> InputValidation
    InputValidation --> OutputSanitization

    OutputSanitization --> WAF
    WAF --> IDS
    IDS --> SecurityMonitoring
```

---

## 📋 **8. 결론**

HAPA 시스템은 **모듈러 아키텍처**를 기반으로 하여 각 컴포넌트가 독립적으로 확장 가능하도록 설계되었습니다.

**핵심 설계 원칙**:

- ✅ **분리된 관심사**: 각 레이어별 명확한 책임 분리
- ✅ **확장 가능성**: 수평/수직 확장 모두 지원
- ✅ **보안 우선**: Security-by-Design 적용
- ✅ **모니터링**: 전 구간 관찰 가능성 확보
- ✅ **성능 최적화**: 다중 레벨 캐싱 및 최적화

현재 **v2.0 아키텍처**는 MVP 요구사항을 충족하면서도 향후 엔터프라이즈급 확장을 위한 기반을 마련했습니다.
