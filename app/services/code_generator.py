import logging
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PythonCodeGenerator:
    """Python 코드 생성을 담당하는 클래스"""

    async def generate_code(
        self, prompt: str, access_token: Optional[str] = None
    ) -> str:
        """개인화된 Python 코드 생성"""
        # 사용자 개인화 설정 조회
        user_preferences = await self._get_user_preferences(access_token)

        prompt_lower = prompt.lower()

        # 프로젝트 컨텍스트별 특화 코드 생성
        project_context = user_preferences.get(
            "project_context", "general_purpose")
        if project_context == "web_development":
            if any(
                keyword in prompt_lower
                for keyword in ["api", "flask", "django", "fastapi"]
            ):
                return self._generate_web_api_code(user_preferences, prompt)
        elif project_context == "data_science":
            if any(
                keyword in prompt_lower
                for keyword in ["데이터", "data", "분석", "analysis", "pandas", "numpy"]
            ):
                return self._generate_data_science_code(
                    user_preferences, prompt)
        elif project_context == "automation":
            if any(
                keyword in prompt_lower
                for keyword in ["자동화", "automation", "스크립트", "script"]
            ):
                return self._generate_automation_code(user_preferences, prompt)

        # 기본 카테고리별 코드 생성 (개인화 적용)
        if any(
            keyword in prompt_lower for keyword in [
                "함수",
                "function",
                "def"]):
            return self._generate_function(user_preferences)
        elif any(keyword in prompt_lower for keyword in ["클래스", "class"]):
            return self._generate_class(user_preferences)
        elif any(
            keyword in prompt_lower for keyword in ["리스트", "list", "배열", "array"]
        ):
            return self._generate_list_operations(user_preferences)
        elif any(
            keyword in prompt_lower for keyword in ["딕셔너리", "dict", "dictionary"]
        ):
            return self._generate_dict_operations(user_preferences)
        elif any(keyword in prompt_lower for keyword in ["파일", "file"]):
            return self._generate_file_operations(user_preferences)
        elif any(keyword in prompt_lower for keyword in ["api", "request", "요청"]):
            return self._generate_api_code(user_preferences)
        else:
            return self._generate_basic_code(user_preferences)

    async def _get_user_preferences(
        self, access_token: Optional[str]
    ) -> Dict[str, Any]:
        """사용자 개인화 설정 조회 및 파싱 (중앙화된 매핑 사용)"""
        from app.core.settings_mapper import (
            get_default_user_preferences,
            map_db_to_preferences,
        )

        if not access_token:
            return get_default_user_preferences()

        try:
            # 순환 참조 방지를 위한 지연 import
            from app.services.user_service import user_service

            settings = await user_service.get_user_settings(access_token)

            if not settings:
                logger.info("DB 설정이 없어 기본 설정 사용")
                return get_default_user_preferences()

            # 중앙화된 매핑 시스템 사용
            preferences = map_db_to_preferences(settings)

            logger.info(f"사용자 설정 로드 완료: {preferences}")
            return preferences

        except Exception as e:
            logger.error(f"사용자 설정 조회 실패: {e}")
            return get_default_user_preferences()

    def _get_default_preferences(self) -> Dict[str, Any]:
        """기본 사용자 설정 (중앙화된 시스템 사용)"""
        from app.core.settings_mapper import get_default_user_preferences

        return get_default_user_preferences()

    def generate_completion(
            self,
            prefix: str,
            max_suggestions: int = 3) -> List[str]:
        """코드 자동 완성 제안 생성"""
        suggestions = []

        # 함수 정의 완성
        if prefix.strip().startswith("def "):
            suggestions.extend(
                [
                    f"{prefix}():",
                    f"{prefix}(self):",
                    f"{prefix}(param1, param2):",
                    f"{prefix}(*args, **kwargs):",
                ]
            )

        # 클래스 정의 완성
        elif prefix.strip().startswith("class "):
            suggestions.extend(
                [
                    f"{prefix}:",
                    f"{prefix}():",
                    f"{prefix}(object):",
                    f"{prefix}(Exception):",
                ]
            )

        # import 완성
        elif "import" in prefix:
            common_imports = [
                "os",
                "sys",
                "json",
                "requests",
                "datetime",
                "random"]
            for imp in common_imports:
                if imp not in prefix:
                    suggestions.append(f"{prefix}{imp}")

        # 기본 완성
        else:
            suggestions.extend([f"{prefix}()", f"{prefix}.method()", f"{
                prefix} = ", f"{prefix} in "])

        return suggestions[:max_suggestions]

    def _generate_function(self, preferences: Dict[str, Any]) -> str:
        """함수 코드 생성 (개인화 설정 반영)"""
        skill_level = preferences.get("skill_level", "intermediate")
        code_style = preferences.get("code_style", "standard")
        comment_style = preferences.get("comment_style", "standard")
        error_handling = preferences.get("error_handling", "basic")
        language_features = preferences.get("language_features", [])

        # 타입 힌트 사용 여부
        use_type_hints = "type_hints" in language_features
        use_f_strings = "f_strings" in language_features

        if skill_level == "beginner":
            return self._generate_beginner_function(
                comment_style, code_style, use_f_strings
            )
        elif skill_level in ["advanced", "expert"]:
            return self._generate_advanced_function(
                comment_style, code_style, error_handling, use_type_hints, use_f_strings)
        else:  # intermediate
            return self._generate_intermediate_function(
                comment_style, code_style, error_handling, use_type_hints, use_f_strings)

    def _generate_beginner_function(
        self, comment_style: str, code_style: str, use_f_strings: bool
    ) -> str:
        """초급자용 함수 (자세한 설명 포함)"""
        if comment_style == "educational":
            string_format = (
                'f"합계: {result}"' if use_f_strings else '"합계: " + str(result)'
            )

            if code_style == "comprehensive":
                return f'''def calculate_sum(numbers):
    """
    숫자 리스트의 합계를 계산하는 함수

    이 함수는 초급자를 위해 각 단계를 자세히 설명합니다.

    Parameters:
    numbers (list): 합계를 구할 숫자들의 리스트
                   예: [1, 2, 3, 4, 5]

    Returns:
    int 또는 float: 리스트에 있는 모든 숫자의 합
                    빈 리스트인 경우 0을 반환

    Example:
    >>> calculate_sum([1, 2, 3, 4, 5])
    15
    >>> calculate_sum([])
    0
    >>> calculate_sum([1.5, 2.5, 3.0])
    7.0
    """
    # 1단계: 입력값 검증
    if not numbers:  # 빈 리스트인지 확인
        print("빈 리스트가 입력되었습니다.")
        return 0

    # 2단계: 결과를 저장할 변수 초기화
    total = 0  # 합계를 저장할 변수

    # 3단계: 리스트의 각 숫자를 순회하면서 합계 계산
    print("계산 과정:")
    for i, number in enumerate(numbers):
        print(f"  단계 {{i+1}}: {{total}} + {{number}} = {{total + number}}")
        total = total + number  # 각 숫자를 total에 더하기

    # 4단계: 최종 결과 반환
    print({string_format})
    return total

# 함수 사용 예시 (다양한 경우)
if __name__ == "__main__":
    # 예시 1: 일반적인 정수 리스트
    my_numbers = [1, 2, 3, 4, 5]
    result1 = calculate_sum(my_numbers)

    # 예시 2: 소수점 숫자 리스트
    decimal_numbers = [1.5, 2.5, 3.0]
    result2 = calculate_sum(decimal_numbers)

    # 예시 3: 빈 리스트
    empty_list = []
    result3 = calculate_sum(empty_list)'''
            else:
                return f'''def calculate_sum(numbers):
    """숫자 리스트의 합계를 계산합니다."""
    # 빈 리스트 확인
    if not numbers:
        return 0

    # 합계 변수 초기화
    total = 0

    # 각 숫자를 더하기
    for number in numbers:
        total += number

    return total

# 사용 예시
numbers = [1, 2, 3, 4, 5]
result = calculate_sum(numbers)
print({string_format})'''
        else:
            return f'''def calculate_sum(numbers):
    """숫자 리스트의 합계를 계산합니다."""
    total = 0
    for number in numbers:
        total += number
    return total

# 사용 예시
numbers = [1, 2, 3, 4, 5]
result = calculate_sum(numbers)
print({string_format})'''

    def _generate_intermediate_function(
        self,
        comment_style: str,
        code_style: str,
        error_handling: str,
        use_type_hints: bool,
        use_f_strings: bool,
    ) -> str:
        """중급자용 함수"""
        type_annotation = ": List[Union[int, float]]" if use_type_hints else ""
        return_annotation = " -> Union[int, float]" if use_type_hints else ""
        string_format = (
            'f"결과: {result}"' if use_f_strings else '"결과: " + str(result)'
        )
        error_code = (
            self._get_error_handling_code(error_handling)
            if error_handling != "basic"
            else ""
        )

        if code_style == "comprehensive":
            return f'''{"from typing import List, Union" if use_type_hints else ""}

def calculate_statistics(numbers{type_annotation}){return_annotation}:
    """
    숫자 리스트의 다양한 통계를 계산합니다.

    Args:
        numbers: 계산할 숫자들의 리스트

    Returns:
        통계 정보가 담긴 딕셔너리

    Raises:
        ValueError: 빈 리스트가 입력된 경우
        TypeError: 숫자가 아닌 값이 포함된 경우
    """
    {error_code if error_code else '''if not numbers:
        raise ValueError("빈 리스트는 계산할 수 없습니다")

    if not all(isinstance(x, (int, float)) for x in numbers):
        raise TypeError("모든 요소는 숫자여야 합니다")'''}

    # 기본 통계 계산
    total = sum(numbers)
    count = len(numbers)
    average = total / count
    minimum = min(numbers)
    maximum = max(numbers)

    # 중앙값 계산
    sorted_numbers = sorted(numbers)
    middle = count // 2
    if count % 2 == 0:
        median = (sorted_numbers[middle-1] + sorted_numbers[middle]) / 2
    else:
        median = sorted_numbers[middle]

    return {{
        'sum': total,
        'count': count,
        'average': average,
        'median': median,
        'min': minimum,
        'max': maximum
    }}

# 사용 예시
if __name__ == "__main__":
    test_numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    stats = calculate_statistics(test_numbers)

    for key, value in stats.items():
        print({string_format.replace('result', f'{{key}}: {{value}}')})'''

        else:  # standard or minimal
            return f'''{"from typing import List" if use_type_hints else ""}

def fibonacci_sequence(n{': int' if use_type_hints else '):'}):
    """피보나치 수열을 n번째까지 생성합니다."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]

    sequence = [0, 1]
    for i in range(2, n):
        sequence.append(sequence[i-1] + sequence[i-2])

    return sequence

# 사용 예시
result = fibonacci_sequence(10)
print({string_format})'''

    def _generate_advanced_function(
        self,
        comment_style: str,
        code_style: str,
        error_handling: str,
        use_type_hints: bool,
        use_f_strings: bool,
    ) -> str:
        """고급자용 함수 (복잡한 로직 포함)"""
        use_dataclasses = "dataclasses" in code_style

        if use_type_hints:
            imports = """from typing import List, Dict, Optional, Union, Callable, TypeVar
from functools import wraps, lru_cache
from dataclasses import dataclass
import time
import logging"""
        else:
            imports = """from functools import wraps, lru_cache
import time
import logging"""

        error_code = self._get_error_handling_code(error_handling)

        return f'''{
            imports}

# 고급 성능 최적화를 위한 데코레이터
def performance_monitor(func{'): Callable' if use_type_hints else '):'}:
    """함수 실행 시간을 모니터링하는 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        {error_code if error_code else '''try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logging.info(f"{{func.__name__}} 실행 시간: {{execution_time:.4f}}초")
            return result
        except Exception as e:
            logging.error(f"{{func.__name__}} 실행 중 오류: {{e}}")
            raise'''}

    return wrapper

@dataclass
class Matrix:
    """행렬 연산을 위한 데이터 클래스"""
    data: {'List[List[Union[int, float]]]' if use_type_hints else 'list'}
    rows: {'int' if use_type_hints else 'int'} = 0
    cols: {'int' if use_type_hints else 'int'} = 0

    def __post_init__(self):
        self.rows = len(self.data)
        self.cols = len(self.data[0]) if self.data else 0

@lru_cache(maxsize=128)
@performance_monitor
def optimized_fibonacci(n{'): int' if use_type_hints else '):'}):
    """
    메모이제이션과 성능 모니터링을 적용한 피보나치 수열

    복잡도: O(n) 시간, O(n) 공간
    특징: LRU 캐시를 사용한 동적 프로그래밍
    """
    if n <= 1:
        return n

    # 반복적 방법으로 구현 (재귀보다 메모리 효율적)
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b

    return b

class AdvancedCalculator:
    """고급 계산기 클래스 - 체이닝 패턴 구현"""

    def __init__(self, initial_value{'): float = 0.0' if use_type_hints else ' = 0.0'}):
        self._value = float(initial_value)
        self._history{'): List[str] = []' if use_type_hints else ' = []'}

    def add(self, value{'): float' if use_type_hints else ''}){' -> "AdvancedCalculator"' if use_type_hints else ''}:
        """더하기 연산"""
        old_value = self._value
        self._value += value
        self._history.append({'f"{{old_value}} + {{value}} = {{self._value}}"' if use_f_strings else 'f"{old_value} + {value} = {self._value}"'})
        return self

    def multiply(self, value{'): float' if use_type_hints else ''}){' -> "AdvancedCalculator"' if use_type_hints else ''}:
        """곱하기 연산"""
        old_value = self._value
        self._value *= value
        self._history.append({'f"{{old_value}} * {{value}} = {{self._value}}"' if use_f_strings else 'f"{old_value} * {value} = {self._value}"'})
        return self

    def power(self, exponent{'): float' if use_type_hints else ''}){' -> "AdvancedCalculator"' if use_type_hints else ''}:
        """거듭제곱 연산"""
        old_value = self._value
        self._value = pow(self._value, exponent)
        self._history.append({'f"{{old_value}} ^ {{exponent}} = {{self._value}}"' if use_f_strings else 'f"{old_value} ^ {exponent} = {self._value}"'})
        return self

    @property
    def value(self){' -> float' if use_type_hints else ''}:
        return self._value

    @property
    def history(self){' -> List[str]' if use_type_hints else ''}:
        return self._history.copy()

# 사용 예시
if __name__ == "__main__":
    # 고급 계산기 체이닝 사용
    calc = AdvancedCalculator(10)
    result = calc.add(5).multiply(2).power(2).value

    print({'f"최종 결과: {{result}}"' if use_f_strings else 'f"최종 결과: {result}"'})
    print("계산 과정:")
    for step in calc.history:
        print({'f"  {{step}}"' if use_f_strings else 'f"  {step}"'})

    # 최적화된 피보나치 테스트
    fib_result = optimized_fibonacci(30)
    print({'f"피보나치 30번째: {{fib_result}}"' if use_f_strings else 'f"피보나치 30번째: {fib_result}"'})'''

    def _generate_class(self, preferences: Dict[str, Any]) -> str:
        """클래스 코드 생성 (개인화 설정 반영)"""
        skill_level = preferences.get("skill_level", "intermediate")

        if skill_level == "beginner":
            return '''class Calculator:
    """간단한 계산기 클래스 - 초급자용"""

    def __init__(self):
        """계산기를 초기화합니다. 결과값을 0으로 설정합니다."""
        self.result = 0

    def add(self, value):
        """숫자를 더합니다."""
        self.result = self.result + value
        return self.result

    def subtract(self, value):
        """숫자를 뺍니다."""
        self.result = self.result - value
        return self.result

    def get_result(self):
        """현재 결과값을 반환합니다."""
        return self.result

# 사용 예시
calc = Calculator()
calc.add(10)
calc.subtract(3)
print(f"결과: {calc.get_result()}")  # 결과: 7'''

        elif skill_level in ["advanced", "expert"]:
            return '''from typing import Union, Optional
from abc import ABC, abstractmethod

class CalculatorInterface(ABC):
    """계산기 인터페이스"""

    @abstractmethod
    def calculate(self, operation: str, operand: float) -> float:
        pass

class ScientificCalculator(CalculatorInterface):
    """과학 계산기 클래스"""

    def __init__(self, precision: int = 10):
        self._result: float = 0.0
        self._history: list = []
        self._precision = precision

    def calculate(self, operation: str, operand: float) -> float:
        """연산을 수행하고 결과를 반환합니다."""
        operations = {
            'add': lambda x, y: x + y,
            'subtract': lambda x, y: x - y,
            'multiply': lambda x, y: x * y,
            'divide': lambda x, y: x / y if y != 0 else None,
            'power': lambda x, y: x ** y
        }

        if operation not in operations:
            raise ValueError(f"지원되지 않는 연산: {operation}")

        prev_result = self._result
        self._result = operations[operation](self._result, operand)

        if self._result is None:
            raise ZeroDivisionError("0으로 나눌 수 없습니다")

        # 히스토리 저장
        self._history.append({
            'operation': operation,
            'operand': operand,
            'prev_result': prev_result,
            'result': self._result
        })

        return round(self._result, self._precision)

    @property
    def result(self) -> float:
        return round(self._result, self._precision)

    @property
    def history(self) -> list:
        return self._history.copy()'''

        else:  # intermediate
            return '''class Calculator:
    """간단한 계산기 클래스"""

    def __init__(self):
        self.result = 0

    def add(self, value):
        """값을 더합니다."""
        self.result += value
        return self.result

    def multiply(self, value):
        """값을 곱합니다."""
        self.result *= value
        return self.result

    def reset(self):
        """결과를 초기화합니다."""
        self.result = 0
        return self.result'''

    def _generate_list_operations(self, preferences: Dict[str, Any]) -> str:
        """리스트 조작 코드 생성"""
        templates = [
            """# 리스트에서 중복 제거
def remove_duplicates(lst):
    return list(set(lst))

# 사용 예시
numbers = [1, 2, 2, 3, 3, 4, 5]
unique_numbers = remove_duplicates(numbers)
print(unique_numbers)  # [1, 2, 3, 4, 5]""",
            """# 리스트 정렬
def sort_list(lst, reverse=False):
    return sorted(lst, reverse=reverse)

# 사용 예시
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
sorted_numbers = sort_list(numbers)
print(sorted_numbers)  # [1, 1, 2, 3, 4, 5, 6, 9]""",
        ]
        return random.choice(templates)

    def _generate_dict_operations(self, preferences: Dict[str, Any]) -> str:
        """딕셔너리 조작 코드 생성"""
        return '''# 딕셔너리 조작 예시
def process_user_data(users):
    """사용자 데이터를 처리합니다."""
    processed = {}

    for user_id, user_info in users.items():
        processed[user_id] = {
            'name': user_info.get('name', '').upper(),
            'age': user_info.get('age', 0),
            'email': user_info.get('email', '').lower()
        }

    return processed

# 사용 예시
users = {
    '001': {'name': 'Alice', 'age': 30, 'email': 'ALICE@EXAMPLE.COM'},
    '002': {'name': 'Bob', 'age': 25, 'email': 'BOB@EXAMPLE.COM'}
}

result = process_user_data(users)
print(result)'''

    def _generate_file_operations(self, preferences: Dict[str, Any]) -> str:
        """파일 조작 코드 생성"""
        return '''import json
import os

def read_json_file(filename):
    """JSON 파일을 읽어서 딕셔너리로 반환합니다."""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {filename}")
        return {}
    except json.JSONDecodeError:
        print(f"JSON 형식이 올바르지 않습니다: {filename}")
        return {}

def write_json_file(filename, data):
    """데이터를 JSON 파일로 저장합니다."""
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f"파일이 저장되었습니다: {filename}")
    except Exception as e:
        print(f"파일 저장 중 오류 발생: {e}")

# 사용 예시
data = {"name": "HAPA", "version": "1.0"}
write_json_file("config.json", data)
loaded_data = read_json_file("config.json")'''

    def _generate_api_code(
            self, preferences: Dict[str, Any], prompt: str) -> str:
        """API 요청 코드 생성"""
        skill_level = preferences.get("skill_level", "intermediate")
        code_style = preferences.get("code_style", "standard")
        error_handling = preferences.get("error_handling", "basic")
        language_features = preferences.get("language_features", [])

        if skill_level == "beginner":
            return '''from flask import Flask, jsonify, request

# Flask 웹 애플리케이션 생성
app = Flask(__name__)

@app.route('/api/hello', methods=['GET'])
def hello_api():
    """간단한 인사 API"""
    return jsonify({
        "message": "Hello, World!",
        "status": "success"
    })

@app.route('/api/user', methods=['POST'])
def create_user():
    """사용자 생성 API"""
    data = request.get_json()
    name = data.get('name', 'Unknown')

    return jsonify({
        "message": f"사용자 {name}가 생성되었습니다",
        "user": {"name": name, "id": 1}
    })

if __name__ == '__main__':
    app.run(debug=True)'''

        else:  # intermediate/advanced/expert
            type_hints = "type_hints" in language_features
            error_code = self._get_error_handling_code(error_handling)

            base_code = f'''from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
{'from typing import List, Optional' if type_hints else ''}
                import logging

# FastAPI 애플리케이션 생성
app = FastAPI(title="HAPA API", version="1.0.0")

class UserCreate(BaseModel):
    name: str
    email: {'Optional[str] = None' if type_hints else 'str = None'}

class UserResponse(BaseModel):
    id: int
    name: str
    email: {'Optional[str]' if type_hints else 'str'}

# 임시 데이터베이스
users_db = []

@app.get("/api/users", response_model={'List[UserResponse]' if type_hints else 'list'})
async def get_users():
    """모든 사용자 조회"""
    {error_code}
    return users_db

@app.post("/api/users", response_model=UserResponse)
async def create_user(user: UserCreate):
    """새 사용자 생성"""
    {error_code}

    new_user = {
                "id": len(users_db) + 1,
        "name": user.name,
        "email": user.email
    }
    users_db.append(new_user)
    return new_user

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)'''

            return base_code

    def _generate_data_science_code(
        self, preferences: Dict[str, Any], prompt: str
    ) -> str:
        """데이터 사이언스 특화 코드 생성"""
        skill_level = preferences.get("skill_level", "intermediate")
        code_style = preferences.get("code_style", "standard")
        error_handling = preferences.get("error_handling", "basic")

        if skill_level == "beginner":
            return '''import pandas as pd
import matplotlib.pyplot as plt

# CSV 파일 읽기
def load_data(file_path):
    """CSV 파일을 읽어서 DataFrame으로 반환"""
    try:
        data = pd.read_csv(file_path)
        print(f"데이터 로드 완료: {len(data)}행")
        return data
    except FileNotFoundError:
        print("파일을 찾을 수 없습니다.")
        return None

# 기본 데이터 분석
def analyze_data(df):
    """기본적인 데이터 분석 수행"""
    print("=== 데이터 기본 정보 ===")
    print(df.info())
    print("\\n=== 기술 통계 ===")
    print(df.describe())

    # 간단한 시각화
    df.hist(figsize=(10, 6))
    plt.title("데이터 분포")
    plt.show()

# 사용 예시
# data = load_data('sample.csv')
# if data is not None:
#     analyze_data(data)'''

        else:  # intermediate/advanced/expert
            error_code = self._get_error_handling_code(error_handling)

            return f'''import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataAnalyzer:
    """포괄적인 데이터 분석 클래스"""

    def __init__(self, data_path: str):
        self.data_path = data_path
        self.df = None
        self.scaler = StandardScaler()

    def load_and_preprocess(self):
        """데이터 로드 및 전처리"""
        {error_code}

        self.df = pd.read_csv(self.data_path)
        logger.info(f"데이터 로드 완료: {{self.df.shape}}")

        # 결측값 처리
        self.df = self.df.dropna()

        # 데이터 타입 최적화
        self._optimize_dtypes()

        return self.df

    def _optimize_dtypes(self):
        """데이터 타입 최적화로 메모리 사용량 줄이기"""
        for col in self.df.select_dtypes(include=['int64']).columns:
            self.df[col] = pd.to_numeric(self.df[col], downcast='integer')

        for col in self.df.select_dtypes(include=['float64']).columns:
            self.df[col] = pd.to_numeric(self.df[col], downcast='float')

    def exploratory_analysis(self):
        """탐색적 데이터 분석"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 상관관계 히트맵
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        sns.heatmap(self.df[numeric_cols].corr(), annot=True, ax=axes[0,0])
        axes[0,0].set_title('상관관계 히트맵')

        # 분포 플롯
        self.df[numeric_cols].hist(bins=30, ax=axes[0,1])
        axes[0,1].set_title('변수 분포')

        plt.tight_layout()
        plt.show()

        return self.df.describe()

# 사용 예시
# analyzer = DataAnalyzer('dataset.csv')
# df = analyzer.load_and_preprocess()
# stats = analyzer.exploratory_analysis()'''

    def _generate_automation_code(
        self, preferences: Dict[str, Any], prompt: str
    ) -> str:
        """자동화 스크립팅 특화 코드 생성"""
        skill_level = preferences.get("skill_level", "intermediate")
        error_handling = preferences.get("error_handling", "basic")
        language_features = preferences.get("language_features", [])

        async_support = "async_await" in language_features
        error_code = self._get_error_handling_code(error_handling)

        if skill_level == "beginner":
            return '''import os
import shutil
from datetime import datetime

def backup_files(source_folder, backup_folder):
    """파일들을 백업 폴더로 복사"""
    try:
        # 백업 폴더가 없으면 생성
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)

        # 날짜별 백업 폴더 생성
        today = datetime.now().strftime("%Y%m%d")
        daily_backup = os.path.join(backup_folder, today)

        if not os.path.exists(daily_backup):
            os.makedirs(daily_backup)

        # 파일 복사
        for filename in os.listdir(source_folder):
            source_file = os.path.join(source_folder, filename)
            if os.path.isfile(source_file):
                shutil.copy2(source_file, daily_backup)
                print(f"백업 완료: {filename}")

        print(f"모든 파일이 {daily_backup}에 백업되었습니다.")

    except Exception as e:
        print(f"백업 중 오류 발생: {e}")

# 사용 예시
# backup_files("./important_files", "./backup")'''

        else:  # intermediate/advanced/expert
            if async_support:
                return f'''import asyncio
import aiofiles
import aiohttp
from pathlib import Path
from datetime import datetime
import logging
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AsyncAutomationTool:
    """비동기 자동화 도구"""

    def __init__(self, config_path: str = "automation_config.json"):
        self.config_path = config_path
        self.config = {{}}

    async def load_config(self):
        """설정 파일 비동기 로드"""
        try:
        async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            self.config = json.loads(content)
        except Exception as e:
            logger.error(f"설정 로드 실패: {{e}}")
            self.config = {{}}

        logger.info("설정 로드 완료")

    async def batch_download(self, urls: list, download_dir: str):
        """URL 목록에서 파일들을 비동기로 다운로드"""
        Path(download_dir).mkdir(parents=True, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            tasks = [self._download_file(session, url, download_dir) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"다운로드 완료: {{successful}} /{{len(urls)}}  성공")

    async def _download_file(self, session, url: str, download_dir: str):
        """개별 파일 다운로드"""
        try:
            filename = Path(url).name or f"file_{{datetime.now().timestamp()}}"
        file_path = Path(download_dir) / filename

        async with session.get(url) as response:
            response.raise_for_status()

            async with aiofiles.open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)

                logger.info(f"다운로드 완료: {{filename}}")
        except Exception as e:
            logger.error(f"다운로드 실패: {{e}}")

# 사용 예시
async def main():
    tool = AsyncAutomationTool()
    await tool.load_config()

    urls = [
        "https://example.com/file1.pdf",
        "https://example.com/file2.zip"
    ]

    await tool.batch_download(urls, "./downloads")

# 실행
# asyncio.run(main())'''

            else:
                return f'''import os
import shutil
import requests
import schedule
import time
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutomationScheduler:
    """자동화 작업 스케줄러"""

    def __init__(self, config_file: str = "tasks.json"):
        self.config_file = config_file
        self.tasks = {{}}
        self.load_config()

    def load_config(self):
        """작업 설정 로드"""
        try:
        with open(self.config_file, 'r', encoding='utf-8') as f:
            self.tasks = json.load(f)
        except Exception as e:
            logger.error(f"설정 로드 실패: {{e}}")
            self.tasks = {{}}

        logger.info(f"{{len(self.tasks)}}개 작업 로드 완료")

    def backup_directory(self, source: str, target: str):
        """디렉토리 백업 작업"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{{timestamp}}"
        backup_path = Path(target) / backup_name

        try:
        shutil.copytree(source, backup_path)
        logger.info(f"백업 완료: {{source}} -> {{backup_path}}")
        except Exception as e:
            logger.error(f"백업 실패: {{e}}")

        # 7일 이전 백업 파일 정리
        self._cleanup_old_backups(target, days=7)

    def _cleanup_old_backups(self, backup_dir: str, days: int):
        """오래된 백업 파일 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        backup_path = Path(backup_dir)

        for item in backup_path.iterdir():
            if item.is_dir() and item.name.startswith("backup_"):
                if item.stat().st_mtime < cutoff_date.timestamp():
                    shutil.rmtree(item)
                    logger.info(f"오래된 백업 삭제: {{item.name}}")

    def run_scheduler(self):
        """스케줄러 실행"""
        # 매일 오전 2시에 백업 실행
        schedule.every().day.at("02:00").do(
            self.backup_directory,
            source="./important_data",
            target="./backups"
        )

        logger.info("스케줄러 시작됨")
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 확인

# 사용 예시
# scheduler = AutomationScheduler()
# scheduler.run_scheduler()'''

    def _get_error_handling_code(self, error_handling: str) -> str:
        """에러 처리 선호도에 따른 코드 생성"""
        if error_handling == "basic":
            return """try:
        # 메인 로직
        pass
    except Exception as e:
        print(f"오류 발생: {e}")"""

        elif error_handling == "detailed":
            return """try:
        # 메인 로직
        pass
    except FileNotFoundError as e:
        logger.error(f"파일을 찾을 수 없습니다: {e}")
        raise
    except PermissionError as e:
        logger.error(f"권한이 부족합니다: {e}")
        raise
    except Exception as e:
        logger.error(f"예상치 못한 오류가 발생했습니다: {e}")
        raise"""

        else:  # robust
            return """try:
        # 메인 로직
        pass
    except FileNotFoundError as e:
        logger.error(f"파일을 찾을 수 없습니다: {e}", exc_info=True)
        # 대체 로직 또는 복구 시도
        return None
    except PermissionError as e:
        logger.error(f"권한이 부족합니다: {e}", exc_info=True)
        # 권한 요청 또는 대안 제시
        return None
    except ConnectionError as e:
        logger.error(f"네트워크 연결 오류: {e}", exc_info=True)
        # 재시도 로직
        return None
    except Exception as e:
        logger.critical(f"시스템 오류: {e}", exc_info=True)
        # 시스템 상태 저장 및 복구
        return None
    finally:
        # 리소스 정리
        pass"""
