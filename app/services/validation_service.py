import ast
import sys
import json
import os
import uuid
import time
import re
import subprocess
import tempfile
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import logging

from app.schemas.validation import (
    CodeValidationRequest, 
    CodeValidationResponse, 
    ValidationIssue,
    ValidationStatus,
    ValidationSeverity,
    ValidationStats
)

# 로깅 설정
logger = logging.getLogger(__name__)

class SafeCodeExecutor:
    """안전한 코드 실행기"""
    
    FORBIDDEN_IMPORTS = {
        'os', 'sys', 'subprocess', 'shutil', 'glob', 'tempfile',
        'socket', 'urllib', 'requests', 'http', 'ftplib', 'smtplib',
        'pickle', 'marshal', 'shelve', 'dbm', 'sqlite3',
        'multiprocessing', 'threading', 'asyncio',
        '__import__', 'eval', 'exec', 'compile', 'open'
    }
    
    SAFE_BUILTINS = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'chr', 'dict',
        'dir', 'divmod', 'enumerate', 'filter', 'float', 'format',
        'frozenset', 'getattr', 'hasattr', 'hash', 'hex', 'id',
        'int', 'isinstance', 'issubclass', 'iter', 'len', 'list',
        'map', 'max', 'min', 'next', 'oct', 'ord', 'pow', 'print',
        'range', 'repr', 'reversed', 'round', 'set', 'slice',
        'sorted', 'str', 'sum', 'tuple', 'type', 'zip'
    }
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
    
    def is_safe_code(self, code: str) -> Tuple[bool, str]:
        """코드가 안전한지 검사"""
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # 위험한 함수 호출 검사
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                            return False, f"위험한 함수 호출 발견: {node.func.id}"
                
                # 위험한 import 검사
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.FORBIDDEN_IMPORTS:
                            return False, f"금지된 모듈 import: {alias.name}"
                
                if isinstance(node, ast.ImportFrom):
                    if node.module in self.FORBIDDEN_IMPORTS:
                        return False, f"금지된 모듈 import: {node.module}"
                
                # 파일 I/O 검사
                if isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name) and node.value.id == 'open':
                        return False, "파일 I/O 작업 발견"
            
            return True, "안전한 코드"
            
        except SyntaxError as e:
            return False, f"문법 오류로 인해 안전성 검사 실패: {e}"
    
    def execute_safely(self, code: str) -> Tuple[Optional[str], Optional[str], float]:
        """안전하게 코드 실행"""
        start_time = time.time()
        
        # 안전성 검사
        is_safe, safety_message = self.is_safe_code(code)
        if not is_safe:
            execution_time = time.time() - start_time
            return None, f"안전성 검사 실패: {safety_message}", execution_time
        
        try:
            # 출력 캡처를 위한 StringIO
            stdout_buffer = StringIO()
            stderr_buffer = StringIO()
            
            # 제한된 builtins 환경 생성
            safe_builtins = {name: getattr(__builtins__, name) 
                           for name in self.SAFE_BUILTINS 
                           if hasattr(__builtins__, name)}
            
            # 안전한 globals 환경
            safe_globals = {
                '__builtins__': safe_builtins,
                '__name__': '__main__',
                'print': lambda *args, **kwargs: print(*args, **kwargs, file=stdout_buffer)
            }
            
            # 코드 실행
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, safe_globals, {})
            
            execution_time = time.time() - start_time
            
            # 결과 수집
            stdout_result = stdout_buffer.getvalue()
            stderr_result = stderr_buffer.getvalue()
            
            if stderr_result:
                return None, stderr_result, execution_time
            else:
                return stdout_result if stdout_result else "코드가 성공적으로 실행되었습니다.", None, execution_time
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = f"{type(e).__name__}: {str(e)}"
            return None, error_message, execution_time

class CodeValidationService:
    """코드 검증 서비스"""
    
    def __init__(self, data_dir: str = "data/validation"):
        """
        코드 검증 서비스 초기화
        
        Args:
            data_dir: 검증 데이터를 저장할 디렉토리
        """
        self.data_dir = data_dir
        self.validation_file = os.path.join(data_dir, "validations.json")
        self.executor = SafeCodeExecutor()
        self._ensure_data_directory()
    
    def _ensure_data_directory(self):
        """데이터 디렉토리가 존재하는지 확인하고 생성"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.validation_file):
            with open(self.validation_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            logger.info(f"검증 데이터 파일 생성: {self.validation_file}")
    
    def _load_validation_data(self) -> List[Dict[str, Any]]:
        """검증 데이터를 JSON 파일에서 로드"""
        try:
            with open(self.validation_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"검증 데이터 로드 실패: {e}")
            return []
    
    def _save_validation_data(self, validation_data: List[Dict[str, Any]]):
        """검증 데이터를 JSON 파일에 저장"""
        try:
            with open(self.validation_file, 'w', encoding='utf-8') as f:
                json.dump(validation_data, f, ensure_ascii=False, indent=2, default=str)
            logger.info("검증 데이터 저장 완료")
        except Exception as e:
            logger.error(f"검증 데이터 저장 실패: {e}")
            raise Exception(f"검증 데이터 저장에 실패했습니다: {e}")
    
    def _analyze_syntax(self, code: str, language: str = "python") -> List[ValidationIssue]:
        """코드 문법 분석"""
        issues = []
        
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                issues.append(ValidationIssue(
                    line_number=e.lineno or 1,
                    column_number=e.offset,
                    severity=ValidationSeverity.ERROR,
                    issue_type="SyntaxError",
                    message=str(e.msg),
                    suggestion=self._get_syntax_suggestion(e.msg)
                ))
            except Exception as e:
                issues.append(ValidationIssue(
                    line_number=1,
                    column_number=0,
                    severity=ValidationSeverity.ERROR,
                    issue_type=type(e).__name__,
                    message=str(e),
                    suggestion="코드 구문을 다시 확인해주세요."
                ))
        
        return issues
    
    def _get_syntax_suggestion(self, error_msg: str) -> str:
        """문법 오류에 대한 수정 제안"""
        suggestions = {
            "invalid syntax": "구문이 잘못되었습니다. 괄호, 콜론, 들여쓰기를 확인해주세요.",
            "unexpected EOF": "코드가 완료되지 않았습니다. 괄호나 따옴표가 닫히지 않았을 수 있습니다.",
            "unindent does not match": "들여쓰기가 일치하지 않습니다. 공백과 탭을 일관되게 사용해주세요.",
            "expected ':'": "콜론(:)이 누락되었습니다. if, for, def, class 등 뒤에 콜론을 추가해주세요.",
            "invalid character": "잘못된 문자가 포함되어 있습니다. 특수문자를 확인해주세요."
        }
        
        for key, suggestion in suggestions.items():
            if key in error_msg.lower():
                return suggestion
        
        return "문법 오류를 수정해주세요."
    
    def _analyze_code_structure(self, code: str) -> Dict[str, int]:
        """코드 구조 분석"""
        try:
            tree = ast.parse(code)
            
            functions_count = 0
            classes_count = 0
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions_count += 1
                elif isinstance(node, ast.ClassDef):
                    classes_count += 1
            
            lines_of_code = len([line for line in code.split('\n') if line.strip()])
            
            return {
                "lines_of_code": lines_of_code,
                "functions_count": functions_count,
                "classes_count": classes_count
            }
            
        except Exception as e:
            logger.warning(f"코드 구조 분석 실패: {e}")
            return {
                "lines_of_code": len(code.split('\n')),
                "functions_count": 0,
                "classes_count": 0
            }
    
    def _calculate_cyclomatic_complexity(self, code: str) -> Optional[int]:
        """순환 복잡도 계산 (단순 버전)"""
        try:
            tree = ast.parse(code)
            complexity = 1  # 기본 복잡도
            
            for node in ast.walk(tree):
                # 조건문, 반복문 등 복잡도 증가 요소
                if isinstance(node, (ast.If, ast.While, ast.For, ast.Try, 
                                   ast.ExceptHandler, ast.With)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            
            return complexity
            
        except Exception as e:
            logger.warning(f"순환 복잡도 계산 실패: {e}")
            return None
    
    def validate_code(self, request: CodeValidationRequest) -> CodeValidationResponse:
        """
        코드를 검증합니다.
        
        Args:
            request: 코드 검증 요청
            
        Returns:
            코드 검증 응답
        """
        start_time = time.time()
        validation_id = f"val_{uuid.uuid4().hex[:8]}"
        
        try:
            logger.info(f"코드 검증 시작: {validation_id} - {request.language}")
            
            # 1. 문법 분석
            syntax_issues = self._analyze_syntax(request.code, request.language)
            
            # 2. 코드 구조 분석
            structure_info = self._analyze_code_structure(request.code)
            
            # 3. 순환 복잡도 계산
            cyclomatic_complexity = self._calculate_cyclomatic_complexity(request.code)
            
            # 4. 실행 가능성 검사
            execution_result = None
            execution_error = None
            execution_time = None
            is_executable = False
            
            if request.check_execution and request.language == "python" and not syntax_issues:
                execution_result, execution_error, execution_time = self.executor.execute_safely(request.code)
                is_executable = execution_error is None
            
            # 5. 검증 상태 결정
            error_count = sum(1 for issue in syntax_issues if issue.severity == ValidationSeverity.ERROR)
            warning_count = sum(1 for issue in syntax_issues if issue.severity == ValidationSeverity.WARNING)
            
            if error_count > 0:
                status = ValidationStatus.INVALID
            elif warning_count > 0:
                status = ValidationStatus.WARNING
            elif is_executable:
                status = ValidationStatus.EXECUTABLE
            else:
                status = ValidationStatus.VALID
            
            validation_time = time.time() - start_time
            
            # 6. 응답 생성
            response = CodeValidationResponse(
                validation_id=validation_id,
                status=status,
                is_valid=error_count == 0,
                is_executable=is_executable,
                issues=syntax_issues,
                total_issues=len(syntax_issues),
                error_count=error_count,
                warning_count=warning_count,
                lines_of_code=structure_info["lines_of_code"],
                cyclomatic_complexity=cyclomatic_complexity,
                functions_count=structure_info["functions_count"],
                classes_count=structure_info["classes_count"],
                execution_result=execution_result,
                execution_error=execution_error,
                execution_time=execution_time,
                validation_time=validation_time,
                timestamp=datetime.now()
            )
            
            # 7. 검증 이력 저장
            self._save_validation_history(request, response)
            
            logger.info(f"코드 검증 완료: {validation_id} - 상태: {status}")
            return response
            
        except Exception as e:
            validation_time = time.time() - start_time
            logger.error(f"코드 검증 실패: {e}")
            
            # 오류 시 기본 응답 반환
            return CodeValidationResponse(
                validation_id=validation_id,
                status=ValidationStatus.ERROR,
                is_valid=False,
                is_executable=False,
                issues=[ValidationIssue(
                    line_number=1,
                    column_number=0,
                    severity=ValidationSeverity.CRITICAL,
                    issue_type="ValidationError",
                    message=f"검증 중 오류 발생: {str(e)}",
                    suggestion="코드를 다시 확인하고 재시도해주세요."
                )],
                total_issues=1,
                error_count=1,
                warning_count=0,
                lines_of_code=len(request.code.split('\n')),
                functions_count=0,
                classes_count=0,
                validation_time=validation_time,
                timestamp=datetime.now()
            )
    
    def _save_validation_history(self, request: CodeValidationRequest, response: CodeValidationResponse):
        """검증 이력을 저장합니다."""
        try:
            history_data = {
                "validation_id": response.validation_id,
                "session_id": request.session_id,
                "language": request.language,
                "file_name": request.file_name,
                "code_length": len(request.code),
                "status": response.status.value,
                "is_valid": response.is_valid,
                "is_executable": response.is_executable,
                "total_issues": response.total_issues,
                "error_count": response.error_count,
                "warning_count": response.warning_count,
                "validation_time": response.validation_time,
                "timestamp": response.timestamp.isoformat()
            }
            
            all_validations = self._load_validation_data()
            all_validations.append(history_data)
            self._save_validation_data(all_validations)
            
        except Exception as e:
            logger.warning(f"검증 이력 저장 실패: {e}")
    
    def get_validation_stats(self) -> ValidationStats:
        """검증 통계를 조회합니다."""
        try:
            all_validations = self._load_validation_data()
            
            if not all_validations:
                return ValidationStats(
                    total_validations=0,
                    valid_code_count=0,
                    invalid_code_count=0,
                    average_validation_time=0.0,
                    most_common_issues=[],
                    language_distribution={}
                )
            
            total_validations = len(all_validations)
            valid_code_count = sum(1 for v in all_validations if v.get("is_valid", False))
            invalid_code_count = total_validations - valid_code_count
            
            # 평균 검증 시간
            validation_times = [v.get("validation_time", 0) for v in all_validations]
            average_validation_time = sum(validation_times) / len(validation_times) if validation_times else 0
            
            # 언어별 분포
            language_distribution = {}
            for v in all_validations:
                lang = v.get("language", "unknown")
                language_distribution[lang] = language_distribution.get(lang, 0) + 1
            
            # 가장 흔한 이슈 (간단한 예시)
            most_common_issues = ["SyntaxError", "IndentationError", "NameError"]
            
            return ValidationStats(
                total_validations=total_validations,
                valid_code_count=valid_code_count,
                invalid_code_count=invalid_code_count,
                average_validation_time=round(average_validation_time, 3),
                most_common_issues=most_common_issues,
                language_distribution=language_distribution
            )
            
        except Exception as e:
            logger.error(f"검증 통계 조회 실패: {e}")
            raise Exception(f"검증 통계 조회에 실패했습니다: {e}")

# 전역 검증 서비스 인스턴스
validation_service = CodeValidationService() 