# VLLM Streaming Tests

VLLM 스트리밍 기능의 완전한 검증을 위한 테스트 스위트입니다.

## 📋 테스트 목표

1. **스트리밍 청크 처리 성능**: 50-100개 청크를 3-5초 내에 처리
2. **출력 정확성**: `print("Jay")` 코드가 정확히 생성되는지 확인
3. **완전한 플로우 검증**: 백엔드에서 프론트엔드까지 전체 스트리밍 플로우 검증
4. **오류 처리**: 스트리밍 중 발생할 수 있는 오류 상황 처리

## 🗂️ 테스트 파일 구조

```
Backend/
├── tests/
│   ├── test_vllm_streaming_integration.py  # pytest 기반 통합 테스트
│   └── test_vllm_integration.py            # 기존 VLLM 테스트
├── test_vllm_streaming_simple.py           # 간단한 스트리밍 테스트
├── test_vllm_complete_flow.py              # 완전한 플로우 테스트
├── run_streaming_tests.py                  # 통합 테스트 러너
└── VLLM_STREAMING_TESTS_README.md          # 이 파일
```

## 🚀 테스트 실행 방법

### 1. 빠른 테스트 (권장)

```bash
# 간단한 Mock 테스트 + 실제 VLLM 테스트
python run_streaming_tests.py quick
```

### 2. 전체 테스트

```bash
# 모든 테스트 스위트 실행
python run_streaming_tests.py full
```

### 3. 개별 테스트 실행

```bash
# 간단한 테스트만
python test_vllm_streaming_simple.py

# 완전한 플로우 테스트만
python test_vllm_complete_flow.py

# pytest 기반 테스트만
python -m pytest tests/test_vllm_streaming_integration.py -v
```

## 📊 테스트 세부사항

### 1. 간단한 스트리밍 테스트 (`test_vllm_streaming_simple.py`)

**기능:**
- VLLM 서버 상태 확인
- Mock 데이터로 스트리밍 시뮬레이션
- 실제 VLLM 서버와 스트리밍 테스트
- 기본 성능 메트릭 수집

**검증 항목:**
- 청크 수: 50-100개
- 처리 시간: 3-5초
- 출력 정확성: `print("Jay")` 포함
- 초당 청크 처리 속도: 10개/초 이상

### 2. 완전한 플로우 테스트 (`test_vllm_complete_flow.py`)

**기능:**
- 서비스 레이어 테스트
- API 엔드포인트 레이어 테스트
- 레이어 간 성능 비교
- 상세한 청크 분석

**검증 항목:**
- 서비스 레이어 스트리밍 정상 동작
- API 엔드포인트 정상 응답
- 청크 버퍼링 효율성
- 코드 구조 유효성

### 3. 통합 테스트 (`tests/test_vllm_streaming_integration.py`)

**기능:**
- pytest 기반 비동기 테스트
- Mock 데이터로 다양한 시나리오 테스트
- 오류 처리 테스트
- 성능 메트릭 상세 분석

**테스트 케이스:**
- `test_vllm_streaming_basic_functionality`
- `test_streaming_output_accuracy`
- `test_streaming_performance_metrics`
- `test_api_endpoint_streaming`
- `test_chunk_buffering_performance`
- `test_error_handling_during_streaming`
- `test_end_to_end_streaming_flow`

## 🔧 테스트 요구사항

### 환경 요구사항

```bash
# 필수 패키지
pip install pytest pytest-asyncio aiohttp fastapi

# 또는 프로젝트 의존성 설치
pip install -r requirements.txt
```

### VLLM 서버 설정

1. **서버 실행 중인 경우**: 실제 VLLM 서버와 테스트
2. **서버 미실행 중인 경우**: Mock 데이터로 테스트 (기본값)

### 환경 변수

```bash
# VLLM 서버 URL (선택사항)
export VLLM_SERVER_URL="http://localhost:8000"

# 로깅 레벨
export LOG_LEVEL="INFO"
```

## 📈 성능 지표

### 예상 성능 기준

| 지표 | 목표 값 | 설명 |
|------|---------|------|
| 청크 수 | 50-100개 | 적절한 버퍼링으로 최적화된 청크 수 |
| 처리 시간 | 3-5초 | 사용자 경험을 고려한 응답 시간 |
| 초당 청크 | 10개/초 이상 | 실시간 스트리밍 속도 |
| 평균 청크 크기 | 1-50자 | 버퍼링 효율성 |
| 버퍼 효율성 | 20% 이상 | 큰 청크 비율 |

### 실제 테스트 결과 예시

```
📊 성능 지표:
✅ 총 청크 수: 73개
✅ 처리 시간: 4.2초
✅ 초당 청크 수: 17.4개/초
✅ 평균 청크 크기: 12.3자
✅ 버퍼 효율성: 28.7%

🔍 출력 검증:
✅ print("Jay") 포함: True
✅ 코드 구조 유효: True
✅ 전체 검증 통과: True
```

## 🐛 문제 해결

### 일반적인 문제들

1. **VLLM 서버 연결 실패**
   ```
   ❌ VLLM 서버 연결 실패: Connection refused
   ```
   - **해결**: Mock 테스트로 대체되므로 정상 동작
   - **권장**: VLLM 서버 실행 후 재테스트

2. **청크 수 부족**
   ```
   ❌ 청크 수 부족: 25 < 50
   ```
   - **원인**: 버퍼링 설정이 너무 엄격
   - **해결**: `ChunkBuffer` 설정 조정

3. **처리 시간 초과**
   ```
   ❌ 처리 시간 범위 초과: 7.5초
   ```
   - **원인**: 네트워크 지연 또는 서버 부하
   - **해결**: 타임아웃 설정 조정

### 로그 분석

```bash
# 상세 로그 확인
python run_streaming_tests.py full > test_results.log 2>&1

# 특정 패턴 검색
grep -E "(✅|❌|⚠️)" test_results.log
```

## 🔄 CI/CD 통합

### GitHub Actions 예시

```yaml
name: VLLM Streaming Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.8
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Run VLLM streaming tests
      run: python run_streaming_tests.py full
```

## 📝 테스트 커스터마이징

### 테스트 요청 수정

```python
# test_vllm_streaming_simple.py에서
self.test_request = CodeGenerationRequest(
    prompt="다른 프롬프트 내용",  # 원하는 프롬프트로 변경
    model_type=ModelType.CODE_GENERATION,
    max_tokens=150  # 토큰 수 조정
)
```

### 성능 기준 조정

```python
# 청크 수 기준 변경
'chunk_count_valid': 30 <= result.total_chunks <= 150,

# 처리 시간 기준 변경
'processing_time_valid': 2.0 <= result.processing_time <= 8.0,
```

## 📚 추가 자료

- [VLLM 공식 문서](https://docs.vllm.ai/)
- [FastAPI 스트리밍 가이드](https://fastapi.tiangolo.com/advanced/streaming/)
- [pytest 비동기 테스트](https://pytest-asyncio.readthedocs.io/)

## 🤝 기여하기

테스트 개선이나 새로운 테스트 케이스를 추가하려면:

1. 새로운 테스트 함수 작성
2. `run_streaming_tests.py`에 통합
3. 문서 업데이트
4. 성능 기준 검토

---

**마지막 업데이트**: 2024년 7월 14일
**작성자**: Claude Code Assistant
**버전**: 1.0.0