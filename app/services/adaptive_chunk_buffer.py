"""
적응형 청크 버퍼 - 요청 복잡도에 따른 동적 설정 조정
HAPA 스트리밍 시스템의 핵심 개선사항
"""

import re
import time
import asyncio
from typing import Dict, List, Optional, Union, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RequestComplexity(Enum):
    """요청 복잡도 레벨"""
    SIMPLE = "simple"      # 간단한 출력, 기본 문법
    MEDIUM = "medium"      # 함수 생성, 로직 포함
    COMPLEX = "complex"    # 클래스, 복잡한 알고리즘


@dataclass
class ChunkConfig:
    """청크 설정 클래스"""
    min_size: int
    optimal_size: int
    max_size: int
    timeout_ms: int
    batch_size: int
    stop_token_sensitivity: float  # 0.0(비활성) ~ 1.0(최고 민감도)
    html_cleaning: bool
    code_validation: bool


@dataclass
class ChunkMetrics:
    """청크 성능 메트릭"""
    total_chunks: int = 0
    total_bytes: int = 0
    avg_chunk_size: float = 0.0
    processing_time: float = 0.0
    false_positives: int = 0
    successful_completions: int = 0
    complexity_accuracy: float = 0.0
    last_updated: float = field(default_factory=time.time)


class ComplexityAnalyzer:
    """요청 복잡도 분석기"""
    
    def __init__(self):
        self.patterns = {
            RequestComplexity.SIMPLE: [
                r'출력',
                r'print',
                r'hello\s+world',
                r'간단한?',
                r'기본',
                r'보여줘?',
                r'나타내',
            ],
            RequestComplexity.MEDIUM: [
                r'함수',
                r'def\s+',
                r'function',
                r'계산',
                r'처리',
                r'로직',
                r'if\s+',
                r'for\s+',
                r'while\s+',
                r'리스트',
                r'딕셔너리',
            ],
            RequestComplexity.COMPLEX: [
                r'클래스',
                r'class\s+',
                r'알고리즘',
                r'최적화',
                r'데이터\s?구조',
                r'디자인\s?패턴',
                r'상속',
                r'다형성',
                r'재귀',
                r'복잡한?',
                r'고급',
                r'아키텍처',
            ]
        }
        
        # 가중치 점수
        self.weights = {
            RequestComplexity.SIMPLE: 1.0,
            RequestComplexity.MEDIUM: 2.0,
            RequestComplexity.COMPLEX: 3.0,
        }
    
    def analyze(self, prompt: str, context: Optional[str] = None) -> RequestComplexity:
        """요청 복잡도 분석"""
        full_text = f"{prompt} {context or ''}".lower()
        
        scores = {complexity: 0.0 for complexity in RequestComplexity}
        
        # 패턴 매칭 점수 계산
        for complexity, patterns in self.patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, full_text, re.IGNORECASE))
                scores[complexity] += matches * self.weights[complexity]
        
        # 텍스트 길이 기반 보정
        text_length = len(full_text)
        if text_length > 500:
            scores[RequestComplexity.COMPLEX] += 2.0
        elif text_length > 200:
            scores[RequestComplexity.MEDIUM] += 1.0
        else:
            scores[RequestComplexity.SIMPLE] += 0.5
        
        # 최고 점수 복잡도 반환
        best_complexity = max(scores.items(), key=lambda x: x[1])[0]
        
        logger.info(f"복잡도 분석 완료: {best_complexity.value} (점수: {scores})")
        return best_complexity


class AdaptiveChunkBuffer:
    """적응형 청크 버퍼"""
    
    def __init__(self):
        self.analyzer = ComplexityAnalyzer()
        self.metrics = ChunkMetrics()
        self.buffer = ""
        self.current_config: Optional[ChunkConfig] = None
        self.current_complexity: Optional[RequestComplexity] = None
        self.chunk_count = 0
        self.start_time = time.time()
        self.last_flush_time = time.time()
        
        # 설정 템플릿
        self.config_templates = {
            RequestComplexity.SIMPLE: ChunkConfig(
                min_size=30,
                optimal_size=80,
                max_size=150,
                timeout_ms=500,
                batch_size=3,
                stop_token_sensitivity=0.8,
                html_cleaning=True,
                code_validation=False,  # 간단한 요청은 검증 생략
            ),
            RequestComplexity.MEDIUM: ChunkConfig(
                min_size=80,
                optimal_size=200,
                max_size=400,
                timeout_ms=1000,
                batch_size=5,
                stop_token_sensitivity=0.6,
                html_cleaning=True,
                code_validation=True,
            ),
            RequestComplexity.COMPLEX: ChunkConfig(
                min_size=150,
                optimal_size=350,
                max_size=600,
                timeout_ms=2000,
                batch_size=8,
                stop_token_sensitivity=0.4,  # 복잡한 요청은 덜 민감하게
                html_cleaning=True,
                code_validation=True,
            ),
        }
    
    def configure_for_request(self, prompt: str, context: Optional[str] = None) -> RequestComplexity:
        """요청에 맞는 설정 적용"""
        self.current_complexity = self.analyzer.analyze(prompt, context)
        self.current_config = self.config_templates[self.current_complexity]
        
        # 초기화
        self.buffer = ""
        self.chunk_count = 0
        self.start_time = time.time()
        self.last_flush_time = time.time()
        
        logger.info(f"청크 버퍼 설정: {self.current_complexity.value}")
        logger.info(f"설정 세부사항: {self.current_config}")
        
        return self.current_complexity
    
    def add_chunk(self, content: str) -> List[str]:
        """청크 추가 및 플러시 판단"""
        if not self.current_config:
            raise ValueError("configure_for_request()를 먼저 호출해야 합니다")
        
        if not content:
            return []
        
        # HTML 정리 (설정에 따라)
        if self.current_config.html_cleaning:
            content = self._clean_html_tags(content)
        
        # 버퍼에 추가
        self.buffer += content
        self.chunk_count += 1
        
        # 플러시 조건 확인
        ready_chunks = []
        if self._should_flush():
            ready_chunks = self._flush_buffer()
        
        return ready_chunks
    
    def _should_flush(self) -> bool:
        """플러시 필요 여부 판단"""
        config = self.current_config
        current_time = time.time()
        
        # 크기 기반 플러시
        if len(self.buffer) >= config.optimal_size:
            logger.debug(f"크기 기반 플러시: {len(self.buffer)} >= {config.optimal_size}")
            return True
        
        # 타임아웃 기반 플러시
        time_since_last_flush = (current_time - self.last_flush_time) * 1000
        if (time_since_last_flush >= config.timeout_ms and 
            len(self.buffer) >= config.min_size):
            logger.debug(f"타임아웃 기반 플러시: {time_since_last_flush}ms >= {config.timeout_ms}ms")
            return True
        
        # 강제 플러시 (최대 크기 초과)
        if len(self.buffer) >= config.max_size:
            logger.warning(f"강제 플러시: {len(self.buffer)} >= {config.max_size}")
            return True
        
        # 완전한 구문 감지 (복잡도에 따라)
        if (self.current_complexity == RequestComplexity.SIMPLE and 
            self._is_complete_statement(self.buffer)):
            logger.debug("완전한 구문 감지로 플러시")
            return True
        
        return False
    
    def _flush_buffer(self) -> List[str]:
        """버퍼 플러시 실행"""
        if not self.buffer:
            return []
        
        config = self.current_config
        content = self.buffer.strip()
        
        # 코드 검증 (설정에 따라)
        if config.code_validation:
            content = self._validate_and_fix_code(content)
        
        # 메트릭 업데이트
        self._update_metrics(content)
        
        # 버퍼 초기화
        self.buffer = ""
        self.last_flush_time = time.time()
        
        logger.debug(f"버퍼 플러시 완료: {len(content)}자")
        return [content] if content else []
    
    def force_flush(self) -> List[str]:
        """강제 플러시"""
        logger.info("강제 플러시 실행")
        return self._flush_buffer()
    
    def _clean_html_tags(self, content: str) -> str:
        """HTML 태그 정리"""
        # HTML 태그 제거
        content = re.sub(r'<[^>]+>', '', content)
        
        # 테이블 관련 메타데이터 제거
        content = re.sub(r'</?(td|tr|table|tbody|thead)[^>]*>', '', content)
        
        # Generation 마커 제거
        content = re.sub(r'#\s*-+\s*Gen(eration)?\s*(Complete)?', '', content, flags=re.IGNORECASE)
        
        # 기타 메타데이터 패턴 제거
        content = re.sub(r'```\s*(python|code)?\s*$', '', content, flags=re.MULTILINE)
        
        return content.strip()
    
    def _validate_and_fix_code(self, content: str) -> str:
        """코드 검증 및 수정"""
        try:
            # 간단한 Python 문법 확인
            if 'print(' in content:
                # 괄호 균형 확인
                open_parens = content.count('(')
                close_parens = content.count(')')
                
                if open_parens > close_parens:
                    content += ')' * (open_parens - close_parens)
                    logger.debug("괄호 불균형 수정")
                
                # 따옴표 균형 확인
                single_quotes = content.count("'")
                double_quotes = content.count('"')
                
                if single_quotes % 2 != 0:
                    content += "'"
                    logger.debug("단일 따옴표 불균형 수정")
                
                if double_quotes % 2 != 0:
                    content += '"'
                    logger.debug("이중 따옴표 불균형 수정")
            
            return content
            
        except Exception as e:
            logger.warning(f"코드 검증 실패: {e}")
            return content
    
    def _is_complete_statement(self, content: str) -> bool:
        """완전한 구문 여부 판단"""
        content = content.strip()
        
        # 간단한 print 구문 확인
        if content.startswith('print(') and content.endswith(')'):
            return True
        
        # 변수 할당 확인
        if re.match(r'^\w+\s*=\s*.+$', content, re.MULTILINE):
            return True
        
        # 함수 정의 완료 확인
        if 'def ' in content and content.count('\n') >= 2:
            return True
        
        return False
    
    def _update_metrics(self, content: str) -> None:
        """메트릭 업데이트"""
        chunk_size = len(content)
        
        self.metrics.total_chunks += 1
        self.metrics.total_bytes += chunk_size
        self.metrics.avg_chunk_size = self.metrics.total_bytes / self.metrics.total_chunks
        self.metrics.processing_time = time.time() - self.start_time
        self.metrics.last_updated = time.time()
    
    def get_metrics(self) -> Dict[str, Any]:
        """현재 메트릭 반환"""
        return {
            "complexity": self.current_complexity.value if self.current_complexity else None,
            "config": {
                "min_size": self.current_config.min_size if self.current_config else None,
                "optimal_size": self.current_config.optimal_size if self.current_config else None,
                "max_size": self.current_config.max_size if self.current_config else None,
                "timeout_ms": self.current_config.timeout_ms if self.current_config else None,
            },
            "metrics": {
                "total_chunks": self.metrics.total_chunks,
                "total_bytes": self.metrics.total_bytes,
                "avg_chunk_size": round(self.metrics.avg_chunk_size, 2),
                "processing_time": round(self.metrics.processing_time, 3),
                "chunks_per_second": round(self.metrics.total_chunks / max(self.metrics.processing_time, 0.001), 2),
            },
            "current_buffer": {
                "size": len(self.buffer),
                "content_preview": self.buffer[:100] + "..." if len(self.buffer) > 100 else self.buffer,
            }
        }
    
    def adjust_config_dynamically(self, performance_feedback: Dict[str, float]) -> None:
        """성능 피드백을 기반으로 동적 설정 조정"""
        if not self.current_config or not self.current_complexity:
            return
        
        # 응답 속도가 너무 느린 경우
        if performance_feedback.get('response_time', 0) > 5.0:
            self.current_config.optimal_size = max(50, self.current_config.optimal_size - 20)
            self.current_config.timeout_ms = max(200, self.current_config.timeout_ms - 100)
            logger.info("성능 개선을 위해 청크 크기 감소")
        
        # 너무 많은 작은 청크가 생성되는 경우
        if self.metrics.avg_chunk_size < 30:
            self.current_config.min_size += 10
            self.current_config.optimal_size += 20
            logger.info("청크 크기 증가로 효율성 개선")
        
        # false positive가 많은 경우
        if performance_feedback.get('false_positive_rate', 0) > 0.3:
            self.current_config.stop_token_sensitivity = max(0.1, self.current_config.stop_token_sensitivity - 0.1)
            logger.info("stop token 민감도 감소")
    
    def reset(self) -> None:
        """버퍼 리셋"""
        self.buffer = ""
        self.chunk_count = 0
        self.start_time = time.time()
        self.last_flush_time = time.time()
        self.metrics = ChunkMetrics()
        logger.info("적응형 청크 버퍼 리셋 완료")


class IntelligentStopTokenDetector:
    """지능적 Stop Token 감지기"""
    
    def __init__(self, chunk_buffer: AdaptiveChunkBuffer):
        self.chunk_buffer = chunk_buffer
        
        # 패턴별 우선순위
        self.patterns = {
            'vllm_official': {
                'tokens': ['<|EOT|>', '[DONE]'],
                'priority': 1,
                'confidence': 0.9,
            },
            'model_specific': {
                'tokens': ['<|im_end|>', '</s>', '<|endoftext|>'],
                'priority': 2,
                'confidence': 0.8,
            },
            'content_based': {
                'tokens': ['```\n', '# END', '```python'],
                'priority': 3,
                'confidence': 0.6,
            },
            'completion_markers': {
                'tokens': ['완료', 'COMPLETE', 'FINISHED'],
                'priority': 4,
                'confidence': 0.4,
            }
        }
    
    def should_stop(self, content: str, context: Dict[str, Any]) -> tuple[bool, str]:
        """Stop 여부 판단"""
        if not self.chunk_buffer.current_config:
            return False, 'no_config'
        
        sensitivity = self.chunk_buffer.current_config.stop_token_sensitivity
        
        # 민감도가 낮으면 감지 비활성화
        if sensitivity < 0.1:
            return False, 'sensitivity_low'
        
        # 요청 타입별 다른 전략
        if context.get('request_type') == 'simple':
            # 간단한 요청: 완성된 구문 감지
            if self.chunk_buffer._is_complete_statement(content):
                return True, 'complete_statement'
        
        # 패턴 기반 감지
        for category, pattern_info in self.patterns.items():
            for token in pattern_info['tokens']:
                if token in content:
                    # 신뢰도와 민감도를 곱해서 최종 판단
                    final_confidence = pattern_info['confidence'] * sensitivity
                    
                    if final_confidence > 0.5:  # 임계값
                        return True, f'{category}:{token}'
        
        return False, 'continue'
    
    def get_detected_patterns(self, content: str) -> List[Dict[str, Any]]:
        """감지된 패턴들 반환 (디버깅용)"""
        detected = []
        
        for category, pattern_info in self.patterns.items():
            for token in pattern_info['tokens']:
                if token in content:
                    detected.append({
                        'category': category,
                        'token': token,
                        'priority': pattern_info['priority'],
                        'confidence': pattern_info['confidence'],
                        'position': content.find(token)
                    })
        
        return sorted(detected, key=lambda x: x['priority'])


# 팩토리 함수
def create_adaptive_system() -> tuple[AdaptiveChunkBuffer, IntelligentStopTokenDetector]:
    """적응형 시스템 생성"""
    chunk_buffer = AdaptiveChunkBuffer()
    stop_detector = IntelligentStopTokenDetector(chunk_buffer)
    
    logger.info("적응형 청크 시스템 생성 완료")
    return chunk_buffer, stop_detector 