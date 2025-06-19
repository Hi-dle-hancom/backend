import logging
import time
import asyncio
from typing import Optional, Dict, Any, List
from functools import lru_cache

from app.core.config import settings
from app.services.performance_profiler import profiler, response_timer
from app.services.ai_model import ai_model_manager
from app.services.response_parser import ResponseParser, ErrorDetector
from app.services.code_generator import PythonCodeGenerator
from app.services.cache_service import cache_get, cache_set, cache_exists

logger = logging.getLogger(__name__)

class OptimizedAIModelService:
    """최적화된 Python 코드 생성을 위한 AI 모델 서비스 클래스"""
    
    def __init__(self):
        """AI 모델 서비스 초기화"""
        self.code_generator = PythonCodeGenerator()
    
    def lazy_load_model(self):
        """Lazy Loading 방식의 AI 모델 로드"""
        ai_model_manager.lazy_load_model()

    def _generate_cache_key(self, prompt: str, context: Optional[str] = None, language: str = "python") -> str:
        """캐시 키 생성"""
        import hashlib
        
        cache_data = f"{prompt}|{context or ''}|{language}"
        return f"ai_inference:{hashlib.md5(cache_data.encode()).hexdigest()}"

    async def predict(self, prompt: str, context: Optional[str] = None, language: str = "python", access_token: Optional[str] = None) -> str:
        """AI 모델을 사용하여 Python 코드를 생성합니다."""
        # 모델 로딩 확인
        if not ai_model_manager.is_loaded():
            self.lazy_load_model()
        
        # 언어 검증
        if language and language.lower() != "python":
            raise ValueError("현재 Python 언어만 지원됩니다.")
        
        with profiler.profile_function("ai_prediction"):
            try:
                # 캐시 확인
                cache_key = self._generate_cache_key(prompt, context, language)
                
                cached_result = cache_get(cache_key)
                if cached_result:
                    logger.info(f"캐시된 응답 반환: {cache_key[:20]}")
                    return cached_result
                
                # 프롬프트 전처리
                processed_prompt = self._preprocess_prompt(prompt, context)
                
                # 코드 생성 (비동기)
                generated_code = await self.code_generator.generate_code(processed_prompt, access_token)
                
                # 결과 캐싱 (1시간 TTL)
                cache_set(cache_key, generated_code, ttl=3600)
                
                logger.info(f"Python 코드 생성 완료 - 길이: {len(generated_code)}")
                return generated_code
                
            except Exception as e:
                logger.error(f"Python 코드 생성 실패: {e}")
                raise Exception(f"Python 코드 생성 중 오류가 발생했습니다: {e}")
    
    async def predict_async(self, prompt: str, context: Optional[str] = None, language: str = "python") -> str:
        """비동기 Python 코드 생성"""
        return await self.predict(prompt, context, language)

    async def predict_and_parse(self, prompt: str, context: Optional[str] = None, language: str = "python", access_token: Optional[str] = None) -> Dict[str, Any]:
        """AI 모델을 사용하여 Python 코드를 생성하고 결과를 파싱합니다."""
        try:
            # 캐시 키 생성 (파싱 결과용)
            cache_key = self._generate_cache_key(f"parsed:{prompt}", context, language)
            
            # 캐시된 파싱 결과 확인
            cached_result = cache_get(cache_key)
            if cached_result:
                logger.info(f"캐시된 파싱 결과 반환: {cache_key[:20]}")
                return cached_result
            
            # 1. AI 모델로부터 원시 응답 생성
            raw_response = await self._generate_raw_model_response(prompt, context, language, access_token)
            
            # 2. 오류 패턴 감지
            if ErrorDetector.detect_error_patterns(raw_response):
                error_result = {
                    "generated_code": "",
                    "explanation": None,
                    "status": "error",
                    "error_message": ErrorDetector.extract_error_message(raw_response)
                }
                return error_result
            
            # 3. 응답 파싱
            parsed_result = ResponseParser.parse_model_response(raw_response)
            
            # 4. 성공적인 결과 생성
            result = {
                "generated_code": parsed_result["code"],
                "explanation": parsed_result["explanation"],
                "status": "success",
                "error_message": None
            }
            
            # 결과 캐싱 (30분 TTL)
            cache_set(cache_key, result, ttl=1800)
            
            return result
            
        except Exception as e:
            logger.error(f"AI 모델 추론 및 파싱 실패: {e}")
            return {
                "generated_code": "",
                "explanation": None,
                "status": "error",
                "error_message": f"AI 모델 처리 중 오류가 발생했습니다: {str(e)}"
            }

    async def _generate_raw_model_response(self, prompt: str, context: Optional[str], language: str, access_token: Optional[str] = None) -> str:
        """실제 AI 모델의 원시 응답을 시뮬레이션합니다."""
        # 원시 응답에 대한 캐시 확인
        cache_key = self._generate_cache_key(f"raw:{prompt}", context, language)
        
        cached_raw = cache_get(cache_key)
        if cached_raw:
            logger.info("캐시된 원시 응답 반환")
            return cached_raw
        
        processed_prompt = self._preprocess_prompt(prompt, context)
        
        # 오류 시뮬레이션
        if "오류" in prompt or "error" in prompt.lower():
            return "ERROR: 모델 처리 중 오류가 발생했습니다."
        
        # 코드 생성 (비동기)
        code = await self.code_generator.generate_code(processed_prompt, access_token)
        explanation = self._generate_simple_explanation(prompt)
        
        raw_response = f"""{explanation}

```python
{code}
```

위 코드를 사용하여 원하는 기능을 구현할 수 있습니다."""
        
        # 원시 응답 캐싱 (15분 TTL)
        cache_set(cache_key, raw_response, ttl=900)
        
        return raw_response

    def complete_code(self, prefix: str, language: str = "python", max_suggestions: int = 3) -> List[str]:
        """코드 자동 완성 제안을 생성합니다."""
        if language.lower() != "python":
            raise ValueError("현재 Python 언어만 지원됩니다.")
        
        # 자동완성 캐시 확인
        cache_key = self._generate_cache_key(f"completion:{prefix}", None, language)
        
        cached_completions = cache_get(cache_key)
        if cached_completions:
            logger.info("캐시된 자동완성 결과 반환")
            return cached_completions[:max_suggestions]
        
        # 새로운 자동완성 생성
        completions = self.code_generator.generate_completion(prefix, max_suggestions)
        
        # 자동완성 결과 캐싱 (10분 TTL)
        cache_set(cache_key, completions, ttl=600)
        
        return completions

    def _preprocess_prompt(self, prompt: str, context: Optional[str]) -> str:
        """프롬프트 전처리"""
        # 주석 트리거 정리
        cleaned_prompt = self._clean_comment_trigger(prompt)
        
        # 컨텍스트 포함
        if context:
            return f"컨텍스트: {context}\n\n요청: {cleaned_prompt}"
        
        return cleaned_prompt

    def _clean_comment_trigger(self, prompt: str) -> str:
        """주석 형태 트리거 제거"""
        # # 주석으로 시작하는 부분 제거
        if prompt.strip().startswith('#'):
            prompt = prompt.strip()[1:].strip()
        
        return prompt

    def _generate_simple_explanation(self, prompt: str) -> str:
        """간단한 설명 생성"""
        if "함수" in prompt or "function" in prompt.lower():
            return "요청하신 기능을 수행하는 Python 함수를 생성했습니다."
        elif "클래스" in prompt or "class" in prompt.lower():
            return "요청하신 기능을 구현한 Python 클래스를 생성했습니다."
        elif "리스트" in prompt or "list" in prompt.lower():
            return "리스트 조작을 위한 Python 코드를 생성했습니다."
        elif "파일" in prompt or "file" in prompt.lower():
            return "파일 처리를 위한 Python 코드를 생성했습니다."
        else:
            return "요청하신 Python 코드를 생성했습니다."

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보 반환"""
        from app.services.cache_service import cache_stats
        return cache_stats()

    def clear_cache(self) -> bool:
        """AI 추론 캐시 삭제"""
        from app.services.cache_service import cache_clear
        return cache_clear()

# 싱글톤 인스턴스
ai_model_service = OptimizedAIModelService() 