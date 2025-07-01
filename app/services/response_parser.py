import ast
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResponseParser:
    """AI 모델 응답을 파싱하는 유틸리티 클래스"""

    @staticmethod
    def parse_model_response(raw_response: str) -> Dict[str, str]:
        """AI 모델의 원시 응답을 코드와 설명으로 분리"""
        try:
            # 1. 마크다운 코드 블록 추출
            code_blocks = ResponseParser._extract_code_blocks(raw_response)

            # 2. Python 코드 패턴 추출
            if not code_blocks:
                code_blocks = ResponseParser._extract_python_code_patterns(
                    raw_response)

            # 3. 최적의 코드 블록 선택
            best_code = ResponseParser._select_best_code_block(code_blocks)

            # 4. 설명 추출
            explanation = ResponseParser._extract_explanation(
                raw_response, code_blocks)

            return {"code": best_code, "explanation": explanation}

        except Exception as e:
            logger.error(f"응답 파싱 실패: {e}")
            return {"code": "", "explanation": "응답 파싱 중 오류가 발생했습니다."}

    @staticmethod
    def _extract_code_blocks(text: str) -> List[str]:
        """마크다운 코드 블록 추출"""
        # ```python 또는 ``` 로 감싸진 코드 블록 찾기
        patterns = [
            r"```python\n(.*?)\n```",
            r"```\n(.*?)\n```",
            r"`([^`]+)`",  # 인라인 코드
        ]

        code_blocks = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            code_blocks.extend(matches)

        # 빈 블록 제거 및 정리
        return [block.strip() for block in code_blocks if block.strip()]

    @staticmethod
    def _extract_python_code_patterns(text: str) -> List[str]:
        """Python 코드 패턴 추출 (마크다운이 없는 경우)"""
        patterns = [
            r"def\s+\w+\([^)]*\):\s*.*?(?=\n\n|\n[^\s]|\Z)",  # 함수 정의
            r"class\s+\w+[^:]*:\s*.*?(?=\n\n|\nclass|\ndef|\Z)",  # 클래스 정의
            r"for\s+.*?:\s*.*?(?=\n\n|\n[^\s]|\Z)",  # for 루프
            r"if\s+.*?:\s*.*?(?=\n\n|\n[^\s]|\Z)",  # if 문
            r"while\s+.*?:\s*.*?(?=\n\n|\n[^\s]|\Z)",  # while 루프
        ]

        code_blocks = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
            code_blocks.extend(matches)

        return [block.strip() for block in code_blocks if block.strip()]

    @staticmethod
    def _select_best_code_block(code_blocks: List[str]) -> str:
        """가장 적절한 코드 블록 선택"""
        if not code_blocks:
            return ""

        # 길이와 Python 구문 유효성을 기준으로 점수 계산
        scored_blocks = []
        for block in code_blocks:
            score = 0

            # 길이 점수 (너무 짧거나 길지 않은 것 선호)
            length = len(block)
            if 10 <= length <= 1000:
                score += 10
            elif length > 1000:
                score += 5

            # Python 구문 유효성 검사
            if ResponseParser._is_valid_python_syntax(block):
                score += 20

            # Python 키워드 포함 여부
            python_keywords = [
                "def",
                "class",
                "import",
                "for",
                "if",
                "while",
                "try",
                "except",
            ]
            for keyword in python_keywords:
                if keyword in block:
                    score += 5

            scored_blocks.append((block, score))

        # 가장 높은 점수의 블록 반환
        return max(scored_blocks, key=lambda x: x[1])[0]

    @staticmethod
    def _is_valid_python_syntax(code: str) -> bool:
        """Python 구문이 유효한지 확인"""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False
        except Exception:
            return False

    @staticmethod
    def _extract_explanation(raw_response: str, code_blocks: List[str]) -> str:
        """코드 블록을 제외한 설명 부분 추출"""
        explanation = raw_response

        # 마크다운 코드 블록 제거
        explanation = re.sub(r"```[^`]*```", "", explanation, flags=re.DOTALL)

        # 추출된 코드 블록들 제거
        for code in code_blocks:
            explanation = explanation.replace(code, "")

        # 여러 줄바꿈을 하나로 정리
        explanation = re.sub(r"\n{3,}", "\n\n", explanation)

        # 앞뒤 공백 제거
        explanation = explanation.strip()

        return explanation if explanation else "코드가 생성되었습니다."


class ErrorDetector:
    """AI 응답에서 오류를 감지하는 클래스"""

    @staticmethod
    def detect_error_patterns(raw_response: str) -> bool:
        """응답에서 오류 패턴 감지"""
        error_patterns = [
            r"ERROR:",
            r"오류가 발생했습니다",
            r"잘못된",
            r"실패",
            r"cannot|can\'t",
            r"unable to",
            r"failed to",
        ]

        for pattern in error_patterns:
            if re.search(pattern, raw_response, re.IGNORECASE):
                return True

        return False

    @staticmethod
    def extract_error_message(raw_response: str) -> str:
        """오류 메시지 추출"""
        error_patterns = [
            r"ERROR:\s*(.+)",
            r"오류가 발생했습니다:\s*(.+)",
            r"오류:\s*(.+)",
        ]

        for pattern in error_patterns:
            match = re.search(pattern, raw_response, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "AI 모델에서 오류가 발생했습니다."
