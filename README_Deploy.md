# HAPA 배포 가이드

HAPA (Hancom AI Python Assistant) 시스템의 배포 방법을 설명합니다.

## 📋 배포 전 체크리스트

### 1. 환경 설정 확인

- [ ] `.env` 파일 설정 완료
- [ ] `.env.production` 파일 설정 완료 (프로덕션 배포시)
- [ ] API 키 및 보안 설정 확인
- [ ] 데이터베이스 설정 확인

### 2. 보안 설정 확인

- [ ] SECRET_KEY 변경 (프로덕션)
- [ ] CORS_ORIGINS 설정
- [ ] API Key 보안 설정
- [ ] SSL/TLS 인증서 준비 (프로덕션)

### 3. 시스템 요구사항

- [ ] Python 3.12+
- [ ] Node.js 18+
- [ ] Docker & Docker Compose (선택사항)

## 🚀 배포 방법

### A. 로컬 개발 환경

#### 1. 백엔드 실행

```bash
cd Backend

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 설정 확인
cp .env.example .env
# .env 파일 편집

# 데이터 디렉토리 생성
mkdir -p data/database data/cache data/logs

# 서버 실행
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. 프론트엔드 실행 (랜딩페이지)

```bash
cd Frontend/landing-page

# 의존성 설치
npm install

# 환경 설정
cp .env.local.example .env.local
# .env.local 파일 편집

# 개발 서버 실행
npm start
```

#### 3. VSCode 확장 개발

```bash
cd Frontend/vscode-extension

# 의존성 설치
npm install

# 컴파일
npm run compile

# VSCode에서 F5로 디버그 실행
```

### B. Docker를 이용한 배포

#### 1. 전체 시스템 배포

```bash
# 프로젝트 루트에서
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 상태 확인
docker-compose ps
```

#### 2. 개별 서비스 배포

```bash
# 백엔드만 배포
docker-compose up -d backend

# 프론트엔드만 배포
docker-compose up -d frontend

# 데이터베이스만 배포
docker-compose up -d database
```

### C. 프로덕션 배포

#### 1. 환경 설정

```bash
# 프로덕션 환경 변수 설정
cp Backend/.env.production Backend/.env

# 보안 설정 업데이트
# - SECRET_KEY 변경
# - API 키 설정
# - 데이터베이스 URL 설정
# - CORS 도메인 설정
```

#### 2. SSL/TLS 설정

```bash
# SSL 인증서 준비 (Let's Encrypt 예시)
sudo certbot certonly --nginx -d your-domain.com

# nginx 설정 업데이트
# ssl_certificate 및 ssl_certificate_key 경로 설정
```

#### 3. 프로덕션 배포 실행

```bash
# 프로덕션 모드로 배포
ENVIRONMENT=production docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 헬스체크 확인
curl http://your-domain.com/health
```

## 🔧 설정 관리

### 환경별 설정 파일

#### 개발 환경 (`.env`)

```env
DEBUG=true
ENVIRONMENT=development
ENABLE_DEMO_API_KEY=true
CORS_ORIGINS=["http://localhost:3000", "vscode-webview://*"]
```

#### 프로덕션 환경 (`.env.production`)

```env
DEBUG=false
ENVIRONMENT=production
ENABLE_DEMO_API_KEY=false
CORS_ORIGINS=["https://your-domain.com"]
SECRET_KEY=your_super_secure_production_key
```

### API 키 관리

#### 개발 환경

```bash
# 개발용 데모 키 사용 (자동 생성)
DEMO_API_KEY=hapa_demo_20241228_secure_key_for_testing
```

#### 프로덕션 환경

```bash
# 실제 API 키 생성 및 설정
python -c "
from app.core.security import api_key_manager
key = api_key_manager.generate_api_key('production_user', ['code_generation', 'code_completion'])
print(f'Generated API Key: {key}')
"
```

## 📊 모니터링 및 로깅

### 1. 헬스체크 엔드포인트

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 상세 성능 정보
curl http://localhost:8000/stats
```

### 2. 캐시 모니터링

```bash
# 캐시 통계 (관리자 권한 필요)
curl -H "X-API-Key: your_admin_api_key" http://localhost:8000/api/v1/cache/stats

# 캐시 정보
curl -H "X-API-Key: your_admin_api_key" http://localhost:8000/api/v1/cache/info
```

### 3. Prometheus 메트릭

```bash
# 메트릭 확인
curl http://localhost:8000/metrics

# Prometheus UI 접속 (Docker Compose 사용시)
open http://localhost:9090
```

### 4. 로그 확인

```bash
# Docker 로그
docker-compose logs -f backend

# 로컬 로그 파일
tail -f Backend/logs/app.log
```

## 🔒 보안 설정

### 1. API 보안

- API Key 기반 인증 활성화
- Rate Limiting 설정
- CORS 도메인 제한
- HTTPS 강제 사용 (프로덕션)

### 2. 데이터 보안

- 데이터베이스 암호화
- 캐시 데이터 TTL 설정
- 민감한 정보 환경변수 분리

### 3. 네트워크 보안

- 방화벽 설정
- VPN 접근 제한 (내부 API)
- SSL/TLS 인증서 자동 갱신

## 🚨 트러블슈팅

### 1. 일반적인 문제

#### 포트 충돌

```bash
# 포트 사용 확인
lsof -i :8000
lsof -i :3000

# 프로세스 종료
kill -9 <PID>
```

#### 권한 문제

```bash
# 데이터 디렉토리 권한 설정
chmod 755 Backend/data
chown -R $USER:$USER Backend/data
```

#### 의존성 문제

```bash
# 가상환경 재생성
rm -rf Backend/venv
python -m venv Backend/venv
source Backend/venv/bin/activate
pip install -r Backend/requirements.txt
```

### 2. Docker 관련 문제

#### 컨테이너 재시작

```bash
# 모든 서비스 재시작
docker-compose restart

# 특정 서비스 재시작
docker-compose restart backend
```

#### 볼륨 초기화

```bash
# 모든 데이터 초기화 (주의!)
docker-compose down -v
docker-compose up -d
```

#### 이미지 재빌드

```bash
# 캐시 없이 재빌드
docker-compose build --no-cache
docker-compose up -d
```

### 3. 성능 문제

#### 캐시 최적화

```bash
# 캐시 통계 확인
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/v1/cache/stats

# 캐시 초기화
curl -X DELETE -H "X-API-Key: your_api_key" http://localhost:8000/api/v1/cache/clear
```

#### 메모리 사용량 확인

```bash
# 시스템 리소스 모니터링
docker stats

# 특정 컨테이너 리소스 확인
docker stats hapa_backend
```

## 📈 확장성 고려사항

### 1. 수평 확장

- 로드 밸런서 설정
- 다중 인스턴스 배포
- 세션 상태 외부화

### 2. 수직 확장

- CPU/메모리 리소스 증설
- 데이터베이스 성능 튜닝
- 캐시 시스템 최적화

### 3. 마이크로서비스 아키텍처

- API Gateway 도입
- 서비스 분리
- 독립적 배포 파이프라인

## 📞 지원

문제가 발생하거나 도움이 필요한 경우:

1. 로그 파일 확인
2. 헬스체크 엔드포인트 확인
3. GitHub Issues 등록
4. 기술 지원팀 연락

---

**주의사항**: 프로덕션 배포 전에 반드시 모든 보안 설정을 검토하고, 테스트 환경에서 충분히 검증한 후 배포하시기 바랍니다.
