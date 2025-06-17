import random
import logging
from typing import List

logger = logging.getLogger(__name__)

class PythonCodeGenerator:
    """Python 코드 생성을 담당하는 클래스"""
    
    def generate_code(self, prompt: str) -> str:
        """프롬프트를 기반으로 Python 코드 생성"""
        prompt_lower = prompt.lower()
        
        # 키워드 기반 코드 생성
        if any(keyword in prompt_lower for keyword in ['함수', 'function', 'def']):
            return self._generate_function()
        elif any(keyword in prompt_lower for keyword in ['클래스', 'class']):
            return self._generate_class()
        elif any(keyword in prompt_lower for keyword in ['리스트', 'list', '배열']):
            return self._generate_list_operations()
        elif any(keyword in prompt_lower for keyword in ['딕셔너리', 'dict', '사전']):
            return self._generate_dict_operations()
        elif any(keyword in prompt_lower for keyword in ['파일', 'file']):
            return self._generate_file_operations()
        elif any(keyword in prompt_lower for keyword in ['api', 'request', '요청']):
            return self._generate_api_code()
        else:
            return self._generate_basic_code()
    
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
    
    def _generate_function(self) -> str:
        """함수 코드 생성"""
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
    
    def _generate_class(self) -> str:
        """클래스 코드 생성"""
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
        self.result = 0'''
    
    def _generate_list_operations(self) -> str:
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
    
    def _generate_dict_operations(self) -> str:
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
    
    def _generate_file_operations(self) -> str:
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
    
    def _generate_api_code(self) -> str:
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
    
    def _generate_basic_code(self) -> str:
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