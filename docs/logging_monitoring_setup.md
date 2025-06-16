# HAPA 백엔드 로깅 및 모니터링 설정 문서

**작성일**: 2024년 12월 28일  
**버전**: v1.0  
**목적**: 종합적인 로깅 시스템 및 모니터링 구성 가이드

---

## 📋 **1. 로깅 시스템 개요**

### **1.1 로깅 아키텍처**

```
Application Layer
    ↓
StructuredLogger (JSON 형식)
    ↓
Multiple Handlers (Console + File)
    ↓
Log Aggregation (ELK Stack 연동 가능)
```

### **1.2 로그 레벨 정책**

- **DEBUG**: 상세한 디버그 정보 (개발 환경)
- **INFO**: 일반적인 정보 및 비즈니스 로직
- **WARNING**: 주의가 필요한 상황
- **ERROR**: 오류 발생 및 예외 상황

---

## 📋 **2. 구조화된 로깅 시스템 구현**

### **2.1 StructuredLogger 클래스** (`Backend/app/core/logging_config.py`)

```python
import logging
import logging.config
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

class StructuredLogger:
    """구조화된 로깅을 위한 클래스"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.setup_logger()

    def setup_logger(self):
        """로거 설정"""
        # 로그 레벨 설정
        log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(log_level)

        # 기존 핸들러 제거
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # 콘솔 핸들러 추가
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # 파일 핸들러 추가 (프로덕션 환경)
        if not settings.DEBUG:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            file_handler = logging.FileHandler(
                log_dir / f"hapa_{datetime.now().strftime('%Y%m%d')}.log"
            )
            file_handler.setLevel(log_level)
            self.logger.addHandler(file_handler)

        # 포맷터 설정
        formatter = StructuredFormatter()
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.propagate = False

    def info(self, message: str, **kwargs):
        """INFO 레벨 로그"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """WARNING 레벨 로그"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """ERROR 레벨 로그"""
        self._log(logging.ERROR, message, **kwargs)
        ERROR_COUNT.labels(error_type=kwargs.get('error_type', 'unknown')).inc()

    def debug(self, message: str, **kwargs):
        """DEBUG 레벨 로그"""
        self._log(logging.DEBUG, message, **kwargs)

    def _log(self, level: int, message: str, **kwargs):
        """내부 로깅 메서드"""
        extra = {
            'timestamp': datetime.now().isoformat(),
            'service': 'hapa-backend',
            'environment': 'development' if settings.DEBUG else 'production',
            **kwargs
        }
        self.logger.log(level, message, extra=extra)
```

### **2.2 JSON 구조화 포맷터**

```python
class StructuredFormatter(logging.Formatter):
    """JSON 구조화된 로그 포맷터"""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # extra 필드 추가
        if hasattr(record, 'timestamp'):
            log_entry.update({
                k: v for k, v in record.__dict__.items()
                if k not in ('name', 'msg', 'args', 'levelname', 'levelno',
                           'pathname', 'filename', 'module', 'lineno', 'funcName',
                           'created', 'msecs', 'relativeCreated', 'thread',
                           'threadName', 'processName', 'process', 'getMessage')
            })

        return json.dumps(log_entry, ensure_ascii=False)
```

### **2.3 로깅 설정 초기화**

```python
def setup_logging():
    """애플리케이션 로깅 설정"""

    # 기본 로깅 설정
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'structured': {
                '()': StructuredFormatter,
            },
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': settings.LOG_LEVEL.upper(),
                'formatter': 'structured' if not settings.DEBUG else 'simple',
                'stream': sys.stdout
            }
        },
        'loggers': {
            '': {
                'handlers': ['console'],
                'level': settings.LOG_LEVEL.upper(),
                'propagate': False
            },
            'uvicorn': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False
            },
            'fastapi': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False
            }
        }
    }

    logging.config.dictConfig(logging_config)
```

---

## 📋 **3. API 모니터링 시스템**

### **3.1 APIMonitor 클래스**

```python
class APIMonitor:
    """API 모니터링 클래스"""

    def __init__(self):
        self.logger = StructuredLogger("api_monitor")

    def log_request_start(self, method: str, endpoint: str, client_ip: str = None):
        """API 요청 시작 로그"""
        self.logger.info(
            f"API 요청 시작: {method} {endpoint}",
            method=method,
            endpoint=endpoint,
            client_ip=client_ip,
            event_type="request_start"
        )
        ACTIVE_CONNECTIONS.inc()

    def log_request_end(self, method: str, endpoint: str, status_code: int,
                       duration: float, client_ip: str = None):
        """API 요청 종료 로그"""
        self.logger.info(
            f"API 요청 완료: {method} {endpoint} - {status_code} ({duration:.4f}s)",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration,
            client_ip=client_ip,
            event_type="request_end"
        )

        # Prometheus 메트릭 업데이트
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
        REQUEST_DURATION.observe(duration)
        ACTIVE_CONNECTIONS.dec()

    def log_ai_inference(self, duration: float, prompt_length: int, response_length: int,
                        cached: bool = False):
        """AI 추론 로그"""
        self.logger.info(
            f"AI 추론 완료: {duration:.4f}s (입력: {prompt_length}자, 출력: {response_length}자, 캐시: {cached})",
            duration=duration,
            prompt_length=prompt_length,
            response_length=response_length,
            cached=cached,
            event_type="ai_inference"
        )

        if not cached:
            AI_INFERENCE_DURATION.observe(duration)

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """에러 로그"""
        self.logger.error(
            f"오류 발생: {type(error).__name__}: {str(error)}",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context or {},
            event_type="error"
        )

    def log_cache_metrics(self, hit_rate: float, cache_size: int):
        """캐시 메트릭 로그"""
        self.logger.info(
            f"캐시 상태: 적중률 {hit_rate:.2%}, 크기 {cache_size}",
            hit_rate=hit_rate,
            cache_size=cache_size,
            event_type="cache_metrics"
        )
        CACHE_HIT_RATE.set(hit_rate * 100)
```

---

## 📋 **4. Prometheus 모니터링 시스템**

### **4.1 메트릭 정의**

```python
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest

# Prometheus 메트릭 정의
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'API request duration')
AI_INFERENCE_DURATION = Histogram('ai_inference_duration_seconds', 'AI model inference duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Number of active connections')
ERROR_COUNT = Counter('api_errors_total', 'Total API errors', ['error_type'])
CACHE_HIT_RATE = Gauge('cache_hit_rate', 'Cache hit rate percentage')
```

### **4.2 성능 모니터링 클래스**

```python
class PerformanceMonitor:
    """성능 모니터링 클래스"""

    def __init__(self):
        self.logger = StructuredLogger("performance_monitor")
        self.metrics = {
            'requests_per_minute': 0,
            'average_response_time': 0.0,
            'error_rate': 0.0,
            'cache_hit_rate': 0.0
        }

    def update_metrics(self, **kwargs):
        """메트릭 업데이트"""
        self.metrics.update(kwargs)

        self.logger.info(
            "성능 메트릭 업데이트",
            metrics=self.metrics,
            event_type="performance_update"
        )

    def get_health_status(self) -> Dict[str, Any]:
        """시스템 헬스 상태 반환"""
        import psutil

        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'system': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent
            },
            'application': self.metrics,
            'checks': {
                'high_cpu': psutil.cpu_percent() > 80,
                'high_memory': psutil.virtual_memory().percent > 80,
                'high_error_rate': self.metrics['error_rate'] > 0.05
            }
        }

        # 전체 상태 결정
        if any(health_data['checks'].values()):
            health_data['status'] = 'unhealthy'

        return health_data
```

### **4.3 메트릭 엔드포인트**

```python
# Prometheus 메트릭 엔드포인트를 위한 함수
def get_prometheus_metrics():
    """Prometheus 메트릭 반환"""
    return generate_latest()

# FastAPI 엔드포인트
@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus 형식의 메트릭을 반환합니다."""
    return get_prometheus_metrics()
```

---

## 📋 **5. 로그 수집 및 분석**

### **5.1 로그 출력 예시**

**개발 환경 (단순 형식)**:

```
2024-12-28 10:30:00,123 - api_monitor - INFO - API 요청 시작: POST /api/v1/code/generate
```

**프로덕션 환경 (JSON 형식)**:

```json
{
  "timestamp": "2024-12-28T10:30:00.123456",
  "level": "INFO",
  "logger": "api_monitor",
  "message": "API 요청 시작: POST /api/v1/code/generate",
  "module": "code_generation",
  "function": "generate_code",
  "line": 42,
  "service": "hapa-backend",
  "environment": "production",
  "method": "POST",
  "endpoint": "/api/v1/code/generate",
  "client_ip": "192.168.1.100",
  "event_type": "request_start",
  "user_id": "user123"
}
```

### **5.2 로그 파일 관리**

**파일 저장 경로**:

```
logs/
├── hapa_20241228.log    # 일별 로그 파일
├── hapa_20241227.log
└── error_20241228.log   # 오류 전용 로그
```

**로그 로테이션 설정**:

```python
from logging.handlers import RotatingFileHandler

# 크기 기반 로테이션 (10MB, 5개 백업)
rotating_handler = RotatingFileHandler(
    'logs/hapa.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

---

## 📋 **6. 실시간 모니터링 대시보드**

### **6.1 Grafana 대시보드 설정**

**데이터 소스 설정**:

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "hapa-backend"
    static_configs:
      - targets: ["localhost:8000"]
    metrics_path: "/metrics"
    scrape_interval: 5s
```

**주요 모니터링 지표**:

1. **API 응답 시간**: `api_request_duration_seconds`
2. **요청 수**: `api_requests_total`
3. **오류율**: `api_errors_total`
4. **AI 추론 시간**: `ai_inference_duration_seconds`
5. **시스템 리소스**: CPU, 메모리, 디스크 사용률

### **6.2 알림 설정**

**Alertmanager 규칙 예시**:

```yaml
groups:
  - name: hapa-backend-alerts
    rules:
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, api_request_duration_seconds_bucket) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API response time"
          description: "95th percentile response time is above 2 seconds"

      - alert: HighErrorRate
        expr: rate(api_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate"
          description: "Error rate is above 10%"
```

---

## 📋 **7. 로그 분석 및 디버깅**

### **7.1 로그 검색 쿼리 예시**

**특정 사용자의 요청 추적**:

```bash
grep "user123" logs/hapa_20241228.log | jq '.message'
```

**오류 발생 패턴 분석**:

```bash
grep "ERROR" logs/hapa_20241228.log | jq '.error_type' | sort | uniq -c
```

**API 응답 시간 분석**:

```bash
grep "request_end" logs/hapa_20241228.log | jq '.duration' | awk '{sum+=$1} END {print "Average:", sum/NR}'
```

### **7.2 ELK Stack 연동 (선택사항)**

**Logstash 설정**:

```conf
input {
  file {
    path => "/path/to/logs/hapa_*.log"
    type => "hapa-backend"
    codec => "json"
  }
}

filter {
  if [type] == "hapa-backend" {
    date {
      match => [ "timestamp", "ISO8601" ]
    }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "hapa-backend-%{+YYYY.MM.dd}"
  }
}
```

---

## 📋 **8. 환경별 설정 관리**

### **8.1 환경 설정** (`.env` 파일)

```env
# 로깅 설정
LOG_LEVEL=INFO
DEBUG=False

# 모니터링 설정
ENABLE_METRICS=True
METRICS_PORT=8000

# 로그 파일 설정
LOG_DIRECTORY=logs
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5
```

### **8.2 Docker 환경 로깅**

```dockerfile
# Dockerfile
COPY logging.conf /app/logging.conf
ENV LOG_LEVEL=INFO
ENV LOG_DIRECTORY=/app/logs

# 로그 볼륨 마운트
VOLUME ["/app/logs"]
```

```yaml
# docker-compose.yml
version: "3.8"
services:
  hapa-backend:
    build: .
    environment:
      - LOG_LEVEL=INFO
      - DEBUG=False
    volumes:
      - ./logs:/app/logs
    ports:
      - "8000:8000"
```

---

## 📋 **9. 성능 최적화 및 모범 사례**

### **9.1 로깅 성능 최적화**

1. **비동기 로깅**: 높은 처리량을 위한 큐 기반 로깅
2. **로그 레벨 필터링**: 불필요한 로그 제거
3. **버퍼링**: 배치 단위 로그 기록

### **9.2 로깅 모범 사례**

1. **일관된 구조**: 표준화된 로그 형식 사용
2. **민감정보 보호**: 개인정보 및 API Key 로깅 금지
3. **적절한 로그 레벨**: 목적에 맞는 로그 레벨 사용
4. **컨텍스트 정보**: 요청 ID, 사용자 ID 등 추적 가능한 정보 포함

---

## 📋 **10. 결론**

HAPA 백엔드의 로깅 및 모니터링 시스템은 **구조화된 JSON 로깅**, **Prometheus 메트릭 수집**, **실시간 성능 모니터링**을 통해 운영 안정성과 디버깅 효율성을 크게 향상시켰습니다. 특히 API 요청부터 AI 추론까지 전 과정의 추적이 가능하며, 실시간 알림을 통한 능동적 장애 대응이 가능합니다.
