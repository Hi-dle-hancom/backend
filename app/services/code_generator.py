import random
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class PythonCodeGenerator:
    """Python 코드 생성을 담당하는 클래스"""
    
    async def generate_code(self, prompt: str, access_token: Optional[str] = None) -> str:
        """프롬프트를 기반으로 Python 코드 생성 (사용자 설정 반영)"""
        logger.info(f"generate_code 시작: prompt={prompt}, access_token={access_token}")
        
        # 사용자 설정 조회
        user_preferences = await self._get_user_preferences(access_token)
        logger.info(f"사용자 설정 조회 완료: {user_preferences}")
        
        prompt_lower = prompt.lower()
        
        # 키워드 기반 코드 생성
        if any(keyword in prompt_lower for keyword in ['함수', 'function', 'def']):
            result = self._generate_function(user_preferences)
            logger.info(f"함수 생성 완료: {type(result)}, length={len(result) if isinstance(result, str) else 'N/A'}")
            return result
        elif any(keyword in prompt_lower for keyword in ['클래스', 'class']):
            return self._generate_class(user_preferences)
        elif any(keyword in prompt_lower for keyword in ['리스트', 'list', '배열']):
            return self._generate_list_operations(user_preferences)
        elif any(keyword in prompt_lower for keyword in ['딕셔너리', 'dict', '사전']):
            return self._generate_dict_operations(user_preferences)
        elif any(keyword in prompt_lower for keyword in ['파일', 'file']):
            return self._generate_file_operations(user_preferences)
        elif any(keyword in prompt_lower for keyword in ['api', 'request', '요청']):
            return self._generate_api_code(user_preferences)
        else:
            return self._generate_basic_code(user_preferences)
    
    async def _get_user_preferences(self, access_token: Optional[str]) -> Dict[str, Any]:
        """사용자 개인화 설정 조회"""
        if not access_token:
            return self._get_default_preferences()
        
        try:
            # 순환 참조 방지를 위한 지연 import
            from app.services.user_service import user_service
            settings = await user_service.get_user_settings(access_token)
            if not settings:
                return self._get_default_preferences()
            
            # 설정을 파싱하여 사용하기 쉬운 형태로 변환
            preferences = self._get_default_preferences()
            
            for setting in settings:
                setting_type = setting.get('setting_type')
                option_value = setting.get('option_value')
                
                if setting_type == 'skill_level':
                    preferences['skill_level'] = option_value
                elif setting_type == 'code_style':
                    preferences['code_style'] = option_value
                elif setting_type == 'project_type':
                    preferences['project_type'] = option_value
                elif setting_type == 'comment_style':
                    preferences['comment_style'] = option_value
            
            logger.info(f"사용자 설정 로드 완료: {preferences}")
            return preferences
            
        except Exception as e:
            logger.error(f"사용자 설정 조회 실패: {e}")
            return self._get_default_preferences()
    
    def _get_default_preferences(self) -> Dict[str, Any]:
        """기본 사용자 설정"""
        return {
            'skill_level': 'intermediate',
            'code_style': 'balanced',
            'project_type': 'general',
            'comment_style': 'normal'
        }
    
    def generate_completion(self, prefix: str, max_suggestions: int = 3) -> List[str]:
        """코드 자동 완성 제안 생성"""
        suggestions = []
        
        # 함수 정의 완성
        if prefix.strip().startswith('def '):
            suggestions.extend([
                f"{prefix}():",
                f"{prefix}(self):",
                f"{prefix}(param1, param2):",
                f"{prefix}(*args, **kwargs):"
            ])
        
        # 클래스 정의 완성  
        elif prefix.strip().startswith('class '):
            suggestions.extend([
                f"{prefix}:",
                f"{prefix}():",
                f"{prefix}(object):",
                f"{prefix}(Exception):"
            ])
        
        # import 완성
        elif 'import' in prefix:
            common_imports = ['os', 'sys', 'json', 'requests', 'datetime', 'random']
            for imp in common_imports:
                if imp not in prefix:
                    suggestions.append(f"{prefix}{imp}")
        
        # 기본 완성
        else:
            suggestions.extend([
                f"{prefix}()",
                f"{prefix}.method()",
                f"{prefix} = ",
                f"{prefix} in "
            ])
        
        return suggestions[:max_suggestions]
    
    def _generate_function(self, preferences: Dict[str, Any]) -> str:
        """함수 코드 생성 (개인화 설정 반영)"""
        skill_level = preferences.get('skill_level', 'intermediate')
        comment_style = preferences.get('comment_style', 'normal')
        
        if skill_level == 'beginner':
            return self._generate_beginner_function(comment_style)
        elif skill_level == 'advanced' or skill_level == 'expert':
            return self._generate_advanced_function(comment_style)
        else:  # intermediate
            return self._generate_intermediate_function(comment_style)
    
    def _generate_beginner_function(self, comment_style: str) -> str:
        """초급자용 함수 (자세한 설명 포함)"""
        if comment_style == 'verbose':
            return '''def calculate_sum(numbers):
    """
    숫자 리스트의 합계를 계산하는 함수
    
    Parameters:
    numbers (list): 합계를 구할 숫자들의 리스트
    
    Returns:
    int 또는 float: 리스트에 있는 모든 숫자의 합
    
    Example:
    >>> calculate_sum([1, 2, 3, 4, 5])
    15
    """
    # 결과를 저장할 변수 초기화
    total = 0
    
    # 리스트의 각 숫자를 순회하면서 합계 계산
    for number in numbers:
        total = total + number  # 각 숫자를 total에 더하기
    
    # 최종 합계 반환
    return total

# 함수 사용 예시
my_numbers = [1, 2, 3, 4, 5]
result = calculate_sum(my_numbers)
print(f"합계: {result}")  # 출력: 합계: 15'''
        else:
            return '''def calculate_sum(numbers):
    """숫자 리스트의 합계를 계산합니다."""
    total = 0
    for number in numbers:
        total += number
    return total

# 사용 예시
numbers = [1, 2, 3, 4, 5]
result = calculate_sum(numbers)
print(f"합계: {result}")'''

    def _generate_intermediate_function(self, comment_style: str) -> str:
        """중급자용 함수"""
        templates = [
            '''def calculate_fibonacci(n):
    """피보나치 수열의 n번째 값을 계산합니다."""
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)''',
            
            '''def find_max(numbers):
    """리스트에서 최댓값을 찾습니다."""
    if not numbers:
        return None
    return max(numbers)''',
            
            '''def is_prime(n):
    """숫자가 소수인지 확인합니다."""
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True'''
        ]
        return random.choice(templates)

    def _generate_advanced_function(self, comment_style: str) -> str:
        """고급자용 함수 (복잡한 로직 포함)"""
        return '''def fibonacci_memoized(n: int, memo: dict = None) -> int:
    """
    메모이제이션을 사용한 효율적인 피보나치 수열 계산
    
    Args:
        n: 계산할 피보나치 수열의 위치
        memo: 메모이제이션을 위한 딕셔너리
    
    Returns:
        n번째 피보나치 수
    
    Time Complexity: O(n)
    Space Complexity: O(n)
    """
    if memo is None:
        memo = {}
    
    if n in memo:
        return memo[n]
    
    if n <= 1:
        return n
    
    memo[n] = fibonacci_memoized(n-1, memo) + fibonacci_memoized(n-2, memo)
    return memo[n]

# 성능 테스트
import time

start_time = time.time()
result = fibonacci_memoized(40)
end_time = time.time()

print(f"피보나치(40) = {result}")
print(f"실행 시간: {end_time - start_time:.4f}초")'''
    
    def _generate_class(self, preferences: Dict[str, Any]) -> str:
        """클래스 코드 생성 (개인화 설정 반영)"""
        skill_level = preferences.get('skill_level', 'intermediate')
        
        if skill_level == 'beginner':
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
        
        elif skill_level in ['advanced', 'expert']:
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
            '''# 리스트에서 중복 제거
def remove_duplicates(lst):
    return list(set(lst))

# 사용 예시
numbers = [1, 2, 2, 3, 3, 4, 5]
unique_numbers = remove_duplicates(numbers)
print(unique_numbers)  # [1, 2, 3, 4, 5]''',
            
            '''# 리스트 정렬
def sort_list(lst, reverse=False):
    return sorted(lst, reverse=reverse)

# 사용 예시
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
sorted_numbers = sort_list(numbers)
print(sorted_numbers)  # [1, 1, 2, 3, 4, 5, 6, 9]'''
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
    
    def _generate_api_code(self, preferences: Dict[str, Any]) -> str:
        """API 요청 코드 생성"""
        return '''import requests
import json

def make_api_request(url, method='GET', data=None, headers=None):
    """API 요청을 보내고 응답을 반환합니다."""
    try:
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, headers=headers)
        elif method.upper() == 'PUT':
            response = requests.put(url, json=data, headers=headers)
        else:
            raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")
        
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"API 요청 실패: {e}")
        return None

# 사용 예시
result = make_api_request('https://api.example.com/data')
if result:
    print("API 응답:", result)'''
    
    def _generate_basic_code(self, preferences: Dict[str, Any]) -> str:
        """기본 Python 코드 생성"""
        templates = [
            '''# Hello World 예시
def greet(name="World"):
    """인사말을 출력하는 함수"""
    print(f"Hello, {name}!")

greet("HAPA")''',
            
            '''# 간단한 계산 예시
def calculate_area(radius):
    """원의 넓이를 계산합니다."""
    import math
    return math.pi * radius ** 2

# 사용 예시
radius = 5
area = calculate_area(radius)
print(f"반지름 {radius}인 원의 넓이: {area:.2f}")''',
            
            '''# 데이터 처리 예시
def process_numbers(numbers):
    """숫자 리스트를 처리합니다."""
    return {
        'sum': sum(numbers),
        'average': sum(numbers) / len(numbers) if numbers else 0,
        'max': max(numbers) if numbers else None,
        'min': min(numbers) if numbers else None
    }

# 사용 예시
data = [1, 2, 3, 4, 5]
result = process_numbers(data)
print(result)'''
        ]
        return random.choice(templates) 