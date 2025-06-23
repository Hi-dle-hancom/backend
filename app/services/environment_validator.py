"""
환경 변수 검증 서비스
운영 환경에서 필수 환경 변수들이 올바르게 설정되었는지 검증합니다.
"""

import os
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """검증 오류 심각도"""
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """검증 결과"""
    key: str
    is_valid: bool
    severity: ValidationSeverity
    message: str
    current_value: Optional[str] = None
    expected_format: Optional[str] = None


class EnvironmentValidator:
    """환경 변수 검증 클래스"""
    
    def __init__(self):
        self.validation_rules = self._init_validation_rules()
    
    def _init_validation_rules(self) -> Dict[str, Dict[str, Any]]:
        """검증 규칙 초기화"""
        return {
            # 필수 보안 설정
            "SECRET_KEY": {
                "required": True,
                "min_length": 32,
                "forbidden_values": [
                    "secret", "test", "dev", "password",
                    "hapa_secret_key_for_development_only_change_in_production"
                ],
                "severity": ValidationSeverity.CRITICAL,
                "description": "JWT 및 암호화용 비밀 키"
            },
            
            "AI_MODEL_API_KEY": {
                "required_in_production": True,
                "min_length": 16,
                "severity": ValidationSeverity.ERROR,
                "description": "AI 모델 API 인증 키"
            },
            
            # 데이터베이스 설정
            "DATABASE_URL": {
                "required_in_production": True,
                "pattern": r"^(postgresql|sqlite):\/\/.*",
                "severity": ValidationSeverity.ERROR,
                "description": "데이터베이스 연결 URL"
            },
            
            # 보안 설정
            "DEBUG": {
                "required": False,
                "production_value": "false",
                "severity": ValidationSeverity.WARNING,
                "description": "디버그 모드 (운영환경에서는 false)"
            },
            
            "CORS_ORIGINS": {
                "required_in_production": True,
                "forbidden_patterns": [r"\*"],
                "severity": ValidationSeverity.ERROR,
                "description": "CORS 허용 도메인 (운영환경에서는 * 금지)"
            },
            
            # 성능 설정
            "MAX_WORKERS": {
                "required": False,
                "type": "int",
                "min_value": 1,
                "max_value": 32,
                "severity": ValidationSeverity.WARNING,
                "description": "최대 워커 수"
            },
            
            "RATE_LIMIT_ENABLED": {
                "required": False,
                "production_value": "true",
                "severity": ValidationSeverity.WARNING,
                "description": "Rate Limiting 활성화"
            }
        }
    
    def validate_all(self) -> List[ValidationResult]:
        """모든 환경 변수 검증"""
        results = []
        environment = os.getenv("ENVIRONMENT", "development")
        is_production = environment == "production"
        
        for key, rules in self.validation_rules.items():
            result = self._validate_single(key, rules, is_production)
            if result:
                results.append(result)
        
        return results
    
    def _validate_single(self, key: str, rules: Dict[str, Any], is_production: bool) -> Optional[ValidationResult]:
        """단일 환경 변수 검증"""
        value = os.getenv(key)
        
        # 필수 값 검증
        if rules.get("required", False) or (is_production and rules.get("required_in_production", False)):
            if not value:
                return ValidationResult(
                    key=key,
                    is_valid=False,
                    severity=rules["severity"],
                    message=f"필수 환경 변수 '{key}'가 설정되지 않았습니다.",
                    expected_format=rules.get("description", "")
                )
        
        # 값이 없으면 다른 검증 생략
        if not value:
            return None
        
        # 최소 길이 검증
        if "min_length" in rules and len(value) < rules["min_length"]:
            return ValidationResult(
                key=key,
                is_valid=False,
                severity=rules["severity"],
                message=f"'{key}' 값이 너무 짧습니다. (현재: {len(value)}자, 최소: {rules['min_length']}자)",
                current_value=value[:10] + "..." if len(value) > 10 else value
            )
        
        # 금지된 값 검증
        if "forbidden_values" in rules and value in rules["forbidden_values"]:
            return ValidationResult(
                key=key,
                is_valid=False,
                severity=rules["severity"],
                message=f"'{key}'에 안전하지 않은 기본값이 설정되어 있습니다.",
                current_value="[HIDDEN]"
            )
        
        # 패턴 검증
        if "pattern" in rules and not re.match(rules["pattern"], value):
            return ValidationResult(
                key=key,
                is_valid=False,
                severity=rules["severity"],
                message=f"'{key}' 값이 올바른 형식이 아닙니다.",
                expected_format=rules.get("description", "")
            )
        
        # 금지된 패턴 검증
        if "forbidden_patterns" in rules:
            for pattern in rules["forbidden_patterns"]:
                if re.search(pattern, value):
                    return ValidationResult(
                        key=key,
                        is_valid=False,
                        severity=rules["severity"],
                        message=f"'{key}'에 금지된 패턴이 포함되어 있습니다: {pattern}",
                        current_value=value
                    )
        
        # 운영 환경 전용 값 검증
        if is_production and "production_value" in rules and value.lower() != rules["production_value"].lower():
            return ValidationResult(
                key=key,
                is_valid=False,
                severity=rules["severity"],
                message=f"운영 환경에서 '{key}'는 '{rules['production_value']}'이어야 합니다.",
                current_value=value
            )
        
        # 타입 검증
        if "type" in rules:
            if not self._validate_type(value, rules["type"], rules):
                return ValidationResult(
                    key=key,
                    is_valid=False,
                    severity=rules["severity"],
                    message=f"'{key}' 값의 타입이 올바르지 않습니다. (기대: {rules['type']})",
                    current_value=value
                )
        
        return None
    
    def _validate_type(self, value: str, expected_type: str, rules: Dict[str, Any]) -> bool:
        """타입 검증"""
        try:
            if expected_type == "int":
                int_value = int(value)
                if "min_value" in rules and int_value < rules["min_value"]:
                    return False
                if "max_value" in rules and int_value > rules["max_value"]:
                    return False
            elif expected_type == "bool":
                if value.lower() not in ["true", "false", "1", "0"]:
                    return False
            return True
        except ValueError:
            return False
    
    def get_validation_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """검증 결과 요약"""
        critical_count = sum(1 for r in results if r.severity == ValidationSeverity.CRITICAL)
        error_count = sum(1 for r in results if r.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
        
        return {
            "total_issues": len(results),
            "critical": critical_count,
            "errors": error_count,
            "warnings": warning_count,
            "is_production_ready": critical_count == 0 and error_count == 0,
            "environment": os.getenv("ENVIRONMENT", "development")
        }
    
    def log_validation_results(self, results: List[ValidationResult]) -> None:
        """검증 결과 로깅"""
        if not results:
            logger.info("✅ 모든 환경 변수 검증 통과")
            return
        
        summary = self.get_validation_summary(results)
        
        # 요약 로그
        logger.warning(
            f"🔍 환경 변수 검증 완료: "
            f"심각 {summary['critical']}개, "
            f"오류 {summary['errors']}개, "
            f"경고 {summary['warnings']}개"
        )
        
        # 개별 결과 로그
        for result in results:
            log_level = {
                ValidationSeverity.CRITICAL: logger.critical,
                ValidationSeverity.ERROR: logger.error,
                ValidationSeverity.WARNING: logger.warning
            }[result.severity]
            
            log_level(f"[{result.severity.value.upper()}] {result.key}: {result.message}")


# 글로벌 인스턴스
environment_validator = EnvironmentValidator()


def validate_environment_on_startup() -> bool:
    """
    애플리케이션 시작 시 환경 변수 검증
    Critical 오류가 있으면 False 반환
    """
    results = environment_validator.validate_all()
    environment_validator.log_validation_results(results)
    
    summary = environment_validator.get_validation_summary(results)
    
    # Critical 오류가 있으면 시작 중단
    if summary["critical"] > 0:
        logger.critical("🚨 Critical 환경 변수 오류로 인해 애플리케이션을 시작할 수 없습니다!")
        return False
    
    # Error가 있으면 경고만 출력
    if summary["errors"] > 0:
        logger.error("⚠️ 환경 변수 오류가 있습니다. 일부 기능이 제대로 작동하지 않을 수 있습니다.")
    
    return True


def get_environment_health() -> Dict[str, Any]:
    """환경 변수 상태 확인 (헬스 체크용)"""
    results = environment_validator.validate_all()
    summary = environment_validator.get_validation_summary(results)
    
    return {
        "environment_variables": {
            "status": "healthy" if summary["is_production_ready"] else "degraded",
            "issues": summary,
            "details": [
                {
                    "key": r.key,
                    "severity": r.severity.value,
                    "message": r.message
                }
                for r in results
            ]
        }
    } 