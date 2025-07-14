#!/usr/bin/env python3
"""
간단한 ChunkBuffer 테스트
- VLLMIntegrationService 의존성 없이 직접 테스트
"""

import re
import time
from typing import Optional, Dict, Any, List

# 모의 설정
class MockSettings:
    @staticmethod
    def should_log_performance():
        return True
    
    @staticmethod 
    def should_log_debug():
        return True

# ChunkBuffer 클래스 직접 복사 (의존성 없이 테스트)
class ChunkBuffer:
    """청크 버퍼링 클래스 - 의미있는 단위로 청크 그룹화 및 후처리 (성능 최적화)"""
    
    def __init__(self, buffer_size: int = 300, buffer_timeout: float = 1.0):
        # 성능 최적화된 설정 (더 엄격한 기준)
        self.buffer_size = buffer_size  # 최대 버퍼 크기 (200 → 300자로 증가)
        self.buffer_timeout = buffer_timeout  # 버퍼 타임아웃 (0.5 → 1.0초로 증가)
        self.min_chunk_size = 80  # 최소 청크 크기 (50 → 80자로 증가)
        self.max_chunk_size = 800  # 최대 청크 크기 (500 → 800자로 증가)
        self.optimal_chunk_size = 150  # 최적 청크 크기 (새로 추가)
        self.buffer = ""
        self.last_flush_time = time.time()
        
        # 성능 모니터링 변수들
        self.total_chunks_processed = 0
        self.total_bytes_processed = 0
        self.small_chunks_count = 0  # 80자 미만 청크 개수
        self.large_chunks_count = 0  # 800자 초과 청크 개수
        self.optimal_chunks_count = 0  # 80-300자 청크 개수
        
        # 청크 품질 개선을 위한 설정
        self.force_meaningful_boundaries = True  # 의미 있는 경계에서만 플러시
        self.strict_size_enforcement = True  # 엄격한 크기 검증
        
        # 의미있는 단위 구분자 패턴
        self.meaningful_delimiters = [
            r'def\s+\w+\([^)]*\):\s*\n',      # 함수 정의
            r'class\s+\w+[^:]*:\s*\n',        # 클래스 정의
            r'[.!?]\s+[A-Z]',                 # 문장 경계
            r';\s*\n',                        # 세미콜론 후 줄바꿈
            r'}\s*\n',                        # 중괄호 닫힘 후 줄바꿈
            r'\n\s*\n',                       # 빈 줄
        ]
        
        # AI 모델 특수 토큰 패턴
        self.special_token_patterns = [
            r'<\|im_end\|>.*$',
            r'<\|im_start\|>[^|]*\|>',
            r'<\|assistant\|>',
            r'<\|user\|>',
        ]

    def add_chunk(self, chunk: str) -> Optional[str]:
        """청크를 버퍼에 추가하고 필요시 플러시"""
        
        # 종료 토큰 체크
        if self._contains_end_token(chunk):
            print(f"🛑 종료 토큰 감지: '{chunk[:20]}...'")
            clean_chunk = self._extract_content_before_end_token(chunk)
            if clean_chunk:
                self.buffer += clean_chunk
            final_content = self.flush()
            return final_content if final_content.strip() else "[END_OF_GENERATION]"
        
        # 특수 토큰 제거
        cleaned_chunk = self._clean_special_tokens(chunk)
        
        if not cleaned_chunk.strip():
            return None
            
        self.buffer += cleaned_chunk
        current_time = time.time()
        
        # 엄격한 플러시 조건
        if self.strict_size_enforcement:
            if len(self.buffer) < self.min_chunk_size:
                if len(self.buffer) >= self.max_chunk_size or self._contains_end_token(self.buffer):
                    should_flush = True
                else:
                    should_flush = False
            else:
                should_flush = (
                    (len(self.buffer) >= self.optimal_chunk_size and 
                     self._has_meaningful_boundary()) or
                    self._has_complete_code_element() or
                    len(self.buffer) >= self.buffer_size * 2.0 or
                    len(self.buffer) >= self.max_chunk_size or
                    (current_time - self.last_flush_time >= self.buffer_timeout * 2.0 and
                     len(self.buffer) >= self.min_chunk_size * 1.5 and
                     self._has_meaningful_boundary())
                )
        else:
            should_flush = (
                len(self.buffer) >= self.min_chunk_size and (
                    len(self.buffer) >= self.buffer_size * 1.8 or
                    current_time - self.last_flush_time >= self.buffer_timeout or
                    self._has_complete_code_element() or
                    len(self.buffer) >= self.max_chunk_size
                )
            )
        
        # 청크 품질 분류 및 플러시
        if should_flush:
            buffer_length = len(self.buffer)
            
            if buffer_length < self.min_chunk_size:
                self.small_chunks_count += 1
                print(f"⚠️ 작은 청크 플러시: {buffer_length}자 (비정상)")
            elif buffer_length <= self.buffer_size:
                self.optimal_chunks_count += 1
                print(f"✅ 최적 청크 플러시: {buffer_length}자")
            else:
                self.large_chunks_count += 1
                print(f"📦 대형 청크 플러시: {buffer_length}자")
            
            result = self.flush()
            print(f"📤 플러시 완료: {buffer_length}자 → {len(result)}자")
            return result
        else:
            print(f"🔄 버퍼링 중: {len(self.buffer)}/{self.buffer_size}자")
        
        return None

    def flush(self) -> str:
        """버퍼 내용을 플러시하고 후처리"""
        content = self.buffer
        self.buffer = ""
        self.last_flush_time = time.time()
        
        self.total_chunks_processed += 1
        self.total_bytes_processed += len(content)
        
        if content:
            content = self._clean_special_tokens(content)
            content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
            content = re.sub(r'[ \t]+', ' ', content)
            content = re.sub(r'[ \t]*\n[ \t]*', '\n', content)
        
        return content.strip()
    
    def force_flush(self) -> Optional[str]:
        """강제 플러시"""
        if self.buffer:
            content = self.flush()
            content = self._clean_special_tokens(content)
            return content if content.strip() else None
        return None
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        total_chunks = max(self.total_chunks_processed, 1)
        avg_chunk_size = (self.total_bytes_processed / total_chunks)
        
        small_ratio = round(self.small_chunks_count / total_chunks * 100, 2)
        optimal_ratio = round(self.optimal_chunks_count / total_chunks * 100, 2)
        large_ratio = round(self.large_chunks_count / total_chunks * 100, 2)
        
        if small_ratio <= 5 and optimal_ratio >= 70:
            performance_grade = "A"
        elif small_ratio <= 15 and optimal_ratio >= 50:
            performance_grade = "B"
        elif small_ratio <= 30:
            performance_grade = "C"
        else:
            performance_grade = "D"
        
        return {
            "total_chunks": self.total_chunks_processed,
            "total_bytes": self.total_bytes_processed,
            "avg_chunk_size": round(avg_chunk_size, 2),
            "small_chunks_count": self.small_chunks_count,
            "optimal_chunks_count": self.optimal_chunks_count,
            "large_chunks_count": self.large_chunks_count,
            "small_chunks_ratio": small_ratio,
            "optimal_chunks_ratio": optimal_ratio,
            "large_chunks_ratio": large_ratio,
            "performance_grade": performance_grade,
            "buffer_efficiency": round(optimal_ratio + (large_ratio * 0.7), 2),
            "min_chunk_size": self.min_chunk_size,
            "optimal_chunk_size": self.optimal_chunk_size,
            "max_chunk_size": self.max_chunk_size,
        }
    
    def _clean_special_tokens(self, text: str) -> str:
        """특수 토큰 제거"""
        cleaned_text = text
        for pattern in self.special_token_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
        return cleaned_text
    
    def _has_complete_code_element(self) -> bool:
        """완전한 코드 요소 확인"""
        return any(re.search(pattern, self.buffer) for pattern in self.meaningful_delimiters[:3])
    
    def _has_meaningful_boundary(self) -> bool:
        """의미 있는 경계 확인"""
        return any(re.search(pattern, self.buffer) for pattern in self.meaningful_delimiters)
    
    def _contains_end_token(self, text: str) -> bool:
        """종료 토큰 확인"""
        return '<|im_end|>' in text or '[DONE]' in text
    
    def _extract_content_before_end_token(self, text: str) -> str:
        """종료 토큰 이전 내용 추출"""
        for token in ['<|im_end|>', '[DONE]']:
            if token in text:
                return text.split(token)[0]
        return text

def test_performance_improvement():
    """성능 개선 테스트"""
    print("🧪 ChunkBuffer 성능 개선 테스트")
    print("=" * 50)
    
    # 시뮬레이션 토큰들 (1000+ 개 작은 토큰)
    tokens = []
    for i in range(100):
        tokens.extend([
            "def", " ", "func", str(i), "(", ")", ":", "\n",
            "    ", "print", "(", "\"hello\"", ")", "\n",
            "    ", "return", " ", str(i), "\n\n"
        ])
    
    print(f"입력 토큰 수: {len(tokens)}")
    print(f"평균 토큰 크기: {sum(len(t) for t in tokens) / len(tokens):.1f}자")
    
    # 기존 설정 테스트
    print("\n1️⃣ 기존 설정 (완화 모드)")
    old_buffer = ChunkBuffer(buffer_size=200, buffer_timeout=0.5)
    old_buffer.strict_size_enforcement = False
    
    old_chunks = []
    start_time = time.time()
    
    for token in tokens:
        result = old_buffer.add_chunk(token)
        if result:
            old_chunks.append(result)
    
    final_old = old_buffer.force_flush()
    if final_old:
        old_chunks.append(final_old)
    
    old_duration = time.time() - start_time
    old_stats = old_buffer.get_performance_stats()
    
    print(f"📊 기존 결과: {len(old_chunks)}개 청크, 평균 {old_stats['avg_chunk_size']:.1f}자")
    
    # 새로운 엄격한 설정
    print("\n2️⃣ 새로운 엄격한 설정")
    new_buffer = ChunkBuffer(buffer_size=300, buffer_timeout=1.0)
    new_buffer.strict_size_enforcement = True
    
    new_chunks = []
    start_time = time.time()
    
    for token in tokens:
        result = new_buffer.add_chunk(token)
        if result:
            new_chunks.append(result)
    
    final_new = new_buffer.force_flush()
    if final_new:
        new_chunks.append(final_new)
    
    new_duration = time.time() - start_time
    new_stats = new_buffer.get_performance_stats()
    
    print(f"📊 새로운 결과: {len(new_chunks)}개 청크, 평균 {new_stats['avg_chunk_size']:.1f}자")
    
    # 성능 개선 분석
    reduction = ((len(old_chunks) - len(new_chunks)) / len(old_chunks)) * 100
    size_improvement = new_stats['avg_chunk_size'] / old_stats['avg_chunk_size']
    
    print(f"\n📈 성능 개선:")
    print(f"   청크 수 감소: {reduction:.1f}% ({len(old_chunks)} → {len(new_chunks)})")
    print(f"   평균 크기 증가: {size_improvement:.1f}배")
    print(f"   성능 등급: {new_stats['performance_grade']}")
    print(f"   최적 청크 비율: {new_stats['optimal_chunks_ratio']:.1f}%")
    
    if reduction >= 70:
        print("🏆 목표 달성: 70% 이상 청크 감소!")
    else:
        print("⚠️ 목표 미달: 추가 최적화 필요")

if __name__ == "__main__":
    test_performance_improvement() 