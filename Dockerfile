# 멀티스테이지 빌드로 최적화된 Docker 이미지
# Stage 1: 빌드 스테이지
FROM python:3.12-slim as builder

# 빌드 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 작업 디렉토리 설정
WORKDIR /build

# pip 업그레이드 및 의존성 설치 (휠 빌드)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Stage 2: 프로덕션 스테이지
FROM python:3.12-slim

# 보안을 위한 시스템 사용자 생성
RUN groupadd -r hapa && useradd -r -g hapa -s /bin/false hapa

# 작업 디렉토리 설정
WORKDIR /app

# 빌드 스테이지에서 Python 패키지 복사
COPY --from=builder /root/.local /home/hapa/.local

# Python PATH 설정
ENV PATH=/home/hapa/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 애플리케이션 코드 복사
COPY . .

# 데이터 디렉토리 생성
RUN mkdir -p data/database data/cache data/logs

# 데이터 디렉토리 권한 설정
RUN chmod 755 data data/database data/cache data/logs

# 비root 사용자 생성 및 권한 설정
RUN useradd --create-home --shell /bin/bash hapa && \
    chown -R hapa:hapa /app
USER hapa

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 포트 노출
EXPOSE 8000

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# 애플리케이션 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"] 