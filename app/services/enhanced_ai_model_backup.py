"""
향상된 AI 모델 서비스 - vLLM 멀티 LoRA 서버 통합
- 기존 AI 모델과 vLLM 서버 모두 지원
- 자동 페일오버 및 로드 밸런싱
- 성능 모니터링 및 최적화
- 한국어/영어 자동 번역 지원
"""

import ast
import asyncio
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import httpx

from app.core.config import settings
from app.core.settings_mapper import get_default_user_preferences
from app.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelType,
    StreamingChunk,
    VLLMHealthStatus,
)
# AI 모델 서비스 - 기존 ai_model.py는 제거됨 (중복 기능)
from app.services.vllm_integration_service import VLLMModelType, vllm_service
from app.services.performance_profiler import ai_performance_metrics

logger = logging.getLogger(__name__)


class AIBackendType(str, Enum):
    """지원하는 AI 백엔드 타입"""

    VLLM = "vllm"  # vLLM 멀티 LoRA 서버 (기본)
    AUTO = "auto"  # 자동 선택 (vLLM만 사용)


class SafetyValidator:
    """코드 안전성 검증을 담당하는 클래스"""

    # 위험한 키워드 패턴
    DANGEROUS_PATTERNS = [
        r"os\.system\s*\(",
        r"subprocess\.",
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__\s*\(",
        r"open\s*\(.+[\'\"](w|a|r\+)",
        r"file\s*\(.+[\'\"](w|a|r\+)",
        r"input\s*\(",
        r"raw_input\s*\(",
        r"compile\s*\(",
        r"globals\s*\(",
        r"locals\s*\(",
        r"vars\s*\(",
        r"dir\s*\(",
        r"getattr\s*\(",
        r"setattr\s*\(",
        r"delattr\s*\(",
        r"hasattr\s*\(",
        r"isinstance\s*\(",
        r"issubclass\s*\(",
        r"__.*__",  # 매직 메소드
        r"import\s+os",
        r"import\s+sys",
        r"import\s+subprocess",
        r"from\s+os\s+import",
        r"from\s+sys\s+import",
        r"from\s+subprocess\s+import",
    ]

    # 허용되는 안전한 키워드
    SAFE_KEYWORDS = [
        "def",
        "class",
        "if",
        "else",
        "elif",
        "for",
        "while",
        "try",
        "except",
        "finally",
        "with",
        "return",
        "yield",
        "pass",
        "break",
        "continue",
        "print",
        "len",
        "str",
        "int",
        "float",
        "list",
        "dict",
        "set",
        "tuple",
        "range",
        "enumerate",
        "zip",
        "map",
        "filter",
        "sum",
        "max",
        "min",
        "sorted",
        "reversed",
        "any",
        "all",
    ]

    def validate_input_safety(self, user_input: str) -> Tuple[bool, List[str]]:
        """사용자 입력의 안전성을 검증합니다."""
        issues = []

        # 입력 길이 검증
        if len(user_input) > 10000:
            issues.append("입력이 너무 깁니다 (최대 10,000자)")

        # 악성 패턴 검출
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                issues.append(f"위험한 패턴 감지: {pattern}")

        # SQL 인젝션 패턴 검출
        sql_patterns = [
            r"DROP\s+TABLE",
            r"DELETE\s+FROM",
            r"INSERT\s+INTO",
            r"UPDATE\s+.*SET",
            r"UNION\s+SELECT",
            r";\s*--",
            r"\/\*.*\*\/",
        ]

        for pattern in sql_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                issues.append(f"SQL 인젝션 패턴 감지: {pattern}")

        # 스크립트 인젝션 검출
        script_patterns = [
            r"<script.*?>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
        ]

        for pattern in script_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                issues.append(f"스크립트 인젝션 패턴 감지: {pattern}")

        return len(issues) == 0, issues

    def validate_generated_code_safety(
            self, code: str) -> Tuple[bool, List[str]]:
        """생성된 코드의 안전성을 검증합니다."""
        issues = []

        # 기본 안전성 검증
        is_safe, basic_issues = self.validate_input_safety(code)
        issues.extend(basic_issues)

        # Python 문법 검증
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Python 문법 오류: {str(e)}")
        except Exception as e:
            issues.append(f"코드 파싱 오류: {str(e)}")

        # 보안 취약점 검증
        security_issues = self._check_security_vulnerabilities(code)
        issues.extend(security_issues)

        return len(issues) == 0, issues

    def _check_security_vulnerabilities(self, code: str) -> List[str]:
        """보안 취약점을 검사합니다."""
        vulnerabilities = []

        # 파일 시스템 접근 검사
        if re.search(r"open\s*\(.*[\'\"]/.*[\'\"]\s*,\s*[\'\"](w|a)", code):
            vulnerabilities.append("파일 시스템에 쓰기 접근 시도")

        # 네트워크 요청 검사
        network_patterns = [
            r"urllib\.request",
            r"requests\.",
            r"socket\.",
            r"http\.client",
            r"ftplib\.",
            r"smtplib\.",
        ]

        for pattern in network_patterns:
            if re.search(pattern, code):
                vulnerabilities.append(f"네트워크 접근 감지: {pattern}")

        # 시스템 명령 실행 검사
        if re.search(r"os\.system|subprocess|popen", code):
            vulnerabilities.append("시스템 명령 실행 감지")

        return vulnerabilities


class EnhancedAIModelService:
    """향상된 AI 모델 서비스 - vLLM 통합 및 페일오버 지원"""

    def __init__(self):
        self.vllm_available = False
        self.current_backend = AIBackendType.VLLM  # vLLM 전용
        self.health_check_interval = 60  # 1분마다 상태 확인
        self.last_health_check = datetime.min
        self.performance_stats = {
            "vllm": {
                "requests": 0,
                "successes": 0,
                "avg_response_time": 0.0},
        }

    async def initialize(self):
        """vLLM 전용 서비스 초기화"""
        try:
            logger.info("Enhanced AI 모델 서비스 (vLLM 전용) 초기화 시작")

            # vLLM 서버 상태 확인
            await self._check_vllm_health()

            # 성능 메트릭 초기화
            ai_performance_metrics.reset_metrics()

            logger.info(
                f"Enhanced AI 모델 서비스 초기화 완료",
                extra={
                    "vllm_available": self.vllm_available,
                    "backend": "vllm_only",
                },
            )

            if not self.vllm_available:
                logger.error("vLLM 서버를 사용할 수 없습니다. 서버 상태를 확인하세요.")

        except Exception as e:
            logger.error(f"Enhanced AI 모델 서비스 초기화 실패: {e}")
            self.vllm_available = False

    async def _check_vllm_health(self) -> bool:
        """vLLM 서버 상태 확인"""
        try:
            health_status = await vllm_service.check_health()
            self.vllm_available = health_status["status"] == "healthy"

            if self.vllm_available:
                logger.info("vLLM 서버 정상 상태 확인됨")
            else:
                logger.warning(f"vLLM 서버 상태 이상: {health_status}")

            return self.vllm_available

        except Exception as e:
            logger.error(f"vLLM 서버 상태 확인 실패: {e}")
            self.vllm_available = False
            return False

    async def _periodic_health_check(self):
        """주기적 vLLM 상태 확인"""
        now = datetime.now()
        if (now - self.last_health_check).total_seconds() >= self.health_check_interval:
            logger.debug("주기적 vLLM 상태 확인 시작")

            vllm_before = self.vllm_available
            await self._check_vllm_health()

            # 상태 변화 감지
            if vllm_before != self.vllm_available:
                logger.info(
                    f"vLLM 상태 변화 감지: {vllm_before} → {self.vllm_available}"
                )

            self.last_health_check = now

    async def generate_code(
        self,
        request: CodeGenerationRequest,
        user_id: str,
        preferred_backend: Optional[AIBackendType] = None,
    ) -> CodeGenerationResponse:
        """
        통합 코드 생성 메서드
        - 자동 백엔드 선택 또는 수동 지정
        - 페일오버 지원
        - 성능 추적 및 임계값 모니터링
        """
        start_time = time.time()

        # 주기적 상태 확인
        await self._periodic_health_check()

        # vLLM 백엔드만 사용
        backend = AIBackendType.VLLM

        logger.info(
            f"코드 생성 요청 처리 시작",
            extra={
                "user_id": user_id,
                "model_type": request.model_type.value,
                "backend": backend.value,
                "prompt_length": len(request.prompt),
            },
        )

        # vLLM 백엔드로 처리
        try:
            if self.vllm_available:
                response = await self._generate_with_vllm(request, user_id)
            else:
                # vLLM 사용 불가능한 경우 오류 응답
                response = CodeGenerationResponse(
                    success=False,
                    generated_code="",
                    error_message="vLLM 서버를 사용할 수 없습니다. 서버 상태를 확인하세요.",
                    model_used="vllm_unavailable",
                    processing_time=0.0,
                    token_usage={"total_tokens": 0},
                )

            # 성능 통계 업데이트
            processing_time = time.time() - start_time
            response.processing_time = processing_time

            # 토큰 수 계산 (정확한 토큰 수 또는 근사치)
            token_count = response.token_usage.get("total_tokens", 0)
            if token_count == 0:
                # 근사치 계산: 생성된 코드 길이 기반
                token_count = len(response.generated_code.split()) + len(response.explanation.split()) if response.explanation else 0

            # AI 성능 메트릭 기록
            ai_performance_metrics.record_ai_operation(
                model_name=response.model_used,
                response_time=processing_time,
                token_count=token_count,
                success=response.success,
                operation_type=request.model_type.value
            )

            self._update_performance_stats(
                backend.value.lower(), processing_time, response.success
            )

            logger.info(
                f"코드 생성 {'성공' if response.success else '실패'}",
                extra={
                    "user_id": user_id,
                    "backend": backend.value,
                    "processing_time": processing_time,
                    "token_count": token_count,
                    "token_speed": token_count / max(processing_time, 0.001),
                    "success": response.success,
                },
            )

            return response

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"코드 생성 중 예외 발생: {str(e)}"

            # 실패한 작업도 메트릭에 기록
            ai_performance_metrics.record_ai_operation(
                model_name=f"{backend.value}_error",
                response_time=processing_time,
                token_count=0,
                success=False,
                operation_type=request.model_type.value
            )

            logger.error(
                error_msg,
                extra={
                    "user_id": user_id,
                    "backend": backend.value,
                    "processing_time": processing_time,
                    "exception": str(e),
                },
            )

            return CodeGenerationResponse(
                success=False,
                generated_code="",
                error_message=error_msg,
                model_used=f"{backend.value}_error",
                processing_time=processing_time,
                token_usage={"total_tokens": 0},
            )

    async def _generate_with_vllm(
        self, request: CodeGenerationRequest, user_id: str
    ) -> CodeGenerationResponse:
        """vLLM 서버를 통한 코드 생성"""
        try:
            response = await vllm_service.generate_code_sync(request, user_id)

            # vLLM 응답 강화
            if response.success:
                response.translation_applied = self._check_translation_applied(
                    request.model_type, request.prompt
                )
                response.confidence_score = self._calculate_confidence_score(
                    response)

            return response

        except Exception as e:
            logger.error(f"vLLM 생성 실패: {e}")
            raise



    def _check_translation_applied(
            self,
            model_type: ModelType,
            prompt: str) -> bool:
        """번역 적용 여부 확인"""
        # 한국어 감지 로직 (간단한 휴리스틱)
        korean_chars = sum(
            1 for char in prompt if "\uac00" <= char <= "\ud7af")
        total_chars = len(prompt.replace(" ", ""))

        if total_chars == 0:
            return False

        korean_ratio = korean_chars / total_chars

        # vLLM 모델별 번역 전략에 따라 판단
        vllm_model = vllm_service._map_hapa_to_vllm_model(model_type)

        if vllm_model == VLLMModelType.AUTOCOMPLETE:
            return False  # 번역 없음
        elif vllm_model == VLLMModelType.COMMENT:
            return korean_ratio > 0.1  # 주석만 번역
        else:
            return korean_ratio > 0.1  # 전체 번역

    def _calculate_confidence_score(
            self, response: CodeGenerationResponse) -> float:
        """응답 품질 신뢰도 계산"""
        try:
            score = 0.5  # 기본 점수

            # 코드 길이 기반 점수 (적절한 길이면 가점)
            code_length = len(response.generated_code)
            if 50 <= code_length <= 2000:
                score += 0.2

            # 구문 검사 (간단한 파이썬 문법 체크)
            try:
                compile(response.generated_code, "<string>", "exec")
                score += 0.2  # 문법적으로 올바름
            except SyntaxError:
                score -= 0.1  # 문법 오류

            # 설명 품질 체크
            if response.explanation and len(response.explanation) > 20:
                score += 0.1

            return max(0.0, min(1.0, score))  # 0.0-1.0 범위로 제한

        except Exception:
            return 0.5  # 계산 실패 시 중간 점수

    def _update_performance_stats(
        self, backend: str, response_time: float, success: bool
    ):
        """성능 통계 업데이트"""
        try:
            if backend not in self.performance_stats:
                self.performance_stats[backend] = {
                    "requests": 0,
                    "successes": 0,
                    "avg_response_time": 0.0,
                }

            stats = self.performance_stats[backend]
            stats["requests"] += 1

            if success:
                stats["successes"] += 1

            # 지수 이동 평균으로 응답 시간 업데이트
            alpha = 0.1  # 가중치
            stats["avg_response_time"] = (
                alpha * response_time + (1 - alpha) * stats["avg_response_time"]
            )

        except Exception as e:
            logger.warning(f"성능 통계 업데이트 실패: {e}")

    async def get_backend_status(self) -> Dict[str, Any]:
        """vLLM 백엔드 상태 정보 조회 - 성능 메트릭 포함"""
        await self._periodic_health_check()
        
        # 성능 요약 보고서 생성
        performance_summary = ai_performance_metrics.get_performance_summary(time_window_hours=1)

        return {
            "backend_type": "vllm_only",
            "vllm": {
                "available": self.vllm_available,
                "stats": self.performance_stats.get("vllm", {}),
                "server_info": (
                    await vllm_service.get_available_models()
                    if self.vllm_available
                    else {}
                ),
            },
            "last_health_check": self.last_health_check.isoformat(),
            "health_check_interval": self.health_check_interval,
            "performance_metrics": {
                "summary": performance_summary,
                "thresholds": {
                    "response_time_target": 2.0,
                    "token_speed_target": 30.0,
                    "success_rate_target": 0.95
                },
                "alerts": self._get_active_performance_alerts()
            }
        }
    
    def _get_active_performance_alerts(self) -> List[Dict[str, Any]]:
        """현재 활성화된 성능 알림 조회"""
        recent_violations = [
            v for v in ai_performance_metrics.metrics_data["threshold_violations"]
            if (datetime.now() - v["timestamp"]).total_seconds() < 3600  # 최근 1시간
        ]
        
        alerts = []
        for violation_record in recent_violations:
            for violation in violation_record["violations"]:
                if violation["severity"] == "critical":
                    alerts.append({
                        "type": "critical",
                        "model": violation_record["model"],
                        "metric": violation["type"],
                        "message": violation["message"],
                        "timestamp": violation_record["timestamp"].isoformat()
                    })
        
        return alerts

    async def check_vllm_status(self) -> bool:
        """vLLM 서버 상태 확인 (외부 API용)"""
        return await self._check_vllm_health()

    async def close(self):
        """서비스 정리"""
        try:
            await vllm_service.close()
            logger.info("Enhanced AI 모델 서비스 정리 완료")
        except Exception as e:
            logger.error(f"서비스 정리 중 오류: {e}")


# 전역 서비스 인스턴스
enhanced_ai_service = EnhancedAIModelService()
