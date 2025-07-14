#!/usr/bin/env python3
"""
ChunkBuffer 성능 테스트 스크립트
- 새로운 엄격한 설정 테스트
- 작은 청크 방지 효과 확인
- 성능 통계 분석
"""

import sys
import time
import json
from typing import List, Dict, Any

# ChunkBuffer 클래스를 임포트하기 위해 경로 추가
sys.path.append('./app')

# 모의 설정 클래스
class MockSettings:
    @staticmethod
    def should_log_performance():
        return True
    
    @staticmethod 
    def should_log_debug():
        return True

# 전역 settings 객체 생성 (ChunkBuffer에서 사용)
import app.core.config as config
config.settings = MockSettings()

from app.services.vllm_integration_service import ChunkBuffer

def simulate_ai_tokens() -> List[str]:
    """AI 모델이 생성하는 다양한 크기의 토큰들을 시뮬레이션"""
    return [
        # 매우 작은 토큰들 (기존 문제)
        "def", " ", "hello", "(", ")", ":", "\n",
        "    ", "print", "(", "\"", "Hello", ",", " ", "world", "!", "\"", ")", "\n",
        
        # 중간 크기 토큰들
        "def calculate_sum", "(", "numbers", ":", " ", "list", ")", ":", "\n",
        "    ", "total", " ", "=", " ", "0", "\n",
        "    ", "for", " ", "num", " ", "in", " ", "numbers", ":", "\n",
        "        ", "total", " ", "+=", " ", "num", "\n",
        "    ", "return", " ", "total", "\n\n",
        
        # 코드 블록
        "class DataProcessor:\n",
        "    def __init__(self, data):\n",
        "        self.data = data\n",
        "        self.processed = False\n\n",
        "    def process(self):\n",
        "        if not self.processed:\n",
        "            self.data = [x * 2 for x in self.data]\n",
        "            self.processed = True\n",
        "        return self.data\n\n",
        
        # 주석과 문서화
        "# 이 함수는 사용자 입력을 검증합니다\n",
        '"""Multi-line docstring explaining\n',
        'the purpose of this function and its\n',
        'parameters and return values."""\n\n',
        
        # 종료 토큰
        "<|im_end|>"
    ]

def test_chunk_buffer_performance():
    """ChunkBuffer 성능 테스트"""
    print("🧪 ChunkBuffer 성능 테스트 시작")
    print("=" * 60)
    
    # 기존 설정 테스트
    print("\n1️⃣ 기존 설정 테스트 (완화 모드)")
    old_buffer = ChunkBuffer(buffer_size=200, buffer_timeout=0.5)
    old_buffer.strict_size_enforcement = False
    
    tokens = simulate_ai_tokens()
    old_chunks = []
    old_start = time.time()
    
    for token in tokens:
        result = old_buffer.add_chunk(token)
        if result:
            old_chunks.append(result)
    
    # 마지막 플러시
    final_old = old_buffer.force_flush()
    if final_old:
        old_chunks.append(final_old)
    
    old_duration = time.time() - old_start
    old_stats = old_buffer.get_performance_stats()
    
    print(f"📊 기존 모드 결과:")
    print(f"   총 청크 수: {len(old_chunks)}")
    print(f"   평균 청크 크기: {old_stats['avg_chunk_size']:.1f}자")
    print(f"   작은 청크 비율: {old_stats['small_chunks_ratio']:.1f}%")
    print(f"   처리 시간: {old_duration:.3f}초")
    print(f"   성능 등급: {old_stats.get('performance_grade', 'N/A')}")
    
    # 새로운 엄격한 설정 테스트
    print("\n2️⃣ 새로운 엄격한 설정 테스트")
    new_buffer = ChunkBuffer(buffer_size=300, buffer_timeout=1.0)
    new_buffer.strict_size_enforcement = True
    
    new_chunks = []
    new_start = time.time()
    
    for token in tokens:
        result = new_buffer.add_chunk(token)
        if result:
            new_chunks.append(result)
    
    # 마지막 플러시
    final_new = new_buffer.force_flush()
    if final_new:
        new_chunks.append(final_new)
    
    new_duration = time.time() - new_start
    new_stats = new_buffer.get_performance_stats()
    
    print(f"📊 엄격한 모드 결과:")
    print(f"   총 청크 수: {len(new_chunks)}")
    print(f"   평균 청크 크기: {new_stats['avg_chunk_size']:.1f}자")
    print(f"   작은 청크 비율: {new_stats['small_chunks_ratio']:.1f}%")
    print(f"   최적 청크 비율: {new_stats['optimal_chunks_ratio']:.1f}%")
    print(f"   처리 시간: {new_duration:.3f}초")
    print(f"   성능 등급: {new_stats.get('performance_grade', 'A')}")
    print(f"   버퍼 효율성: {new_stats.get('buffer_efficiency', 0):.1f}%")
    
    # 성능 개선 분석
    print("\n📈 성능 개선 분석:")
    chunk_reduction = ((len(old_chunks) - len(new_chunks)) / len(old_chunks)) * 100
    size_improvement = new_stats['avg_chunk_size'] / old_stats['avg_chunk_size']
    small_chunk_reduction = old_stats['small_chunks_ratio'] - new_stats['small_chunks_ratio']
    
    print(f"   청크 수 감소: {chunk_reduction:.1f}% ({len(old_chunks)} → {len(new_chunks)})")
    print(f"   평균 크기 증가: {size_improvement:.1f}배")
    print(f"   작은 청크 감소: {small_chunk_reduction:.1f}%p")
    
    # 청크 내용 예시 출력
    print("\n📋 청크 내용 예시 (처음 3개):")
    for i, chunk in enumerate(new_chunks[:3]):
        print(f"   청크 {i+1} ({len(chunk)}자): {repr(chunk[:50])}...")
    
    # 상세 통계 JSON 출력
    print(f"\n📄 상세 성능 통계:")
    print(json.dumps(new_stats, indent=2, ensure_ascii=False))
    
    return {
        'old_chunks': len(old_chunks),
        'new_chunks': len(new_chunks),
        'reduction_percentage': chunk_reduction,
        'new_stats': new_stats
    }

def test_edge_cases():
    """엣지 케이스 테스트"""
    print("\n\n🔬 엣지 케이스 테스트")
    print("=" * 40)
    
    buffer = ChunkBuffer()
    
    # 1. 빈 문자열 테스트
    print("1. 빈 문자열 테스트")
    result = buffer.add_chunk("")
    print(f"   결과: {result}")
    
    # 2. 특수 토큰 테스트
    print("2. 특수 토큰 제거 테스트")
    result = buffer.add_chunk("코드 생성 완료<|im_end|>")
    print(f"   결과: {repr(result)}")
    
    # 3. 매우 긴 단일 토큰 테스트
    print("3. 매우 긴 단일 토큰 테스트")
    long_token = "x" * 1000
    result = buffer.add_chunk(long_token)
    print(f"   결과 길이: {len(result) if result else 'None'}")
    
    # 4. 강제 플러시 테스트
    print("4. 강제 플러시 테스트")
    buffer.add_chunk("미완성 ")
    buffer.add_chunk("코드")
    result = buffer.force_flush()
    print(f"   강제 플러시 결과: {repr(result)}")

if __name__ == "__main__":
    try:
        # 메인 성능 테스트
        results = test_chunk_buffer_performance()
        
        # 엣지 케이스 테스트  
        test_edge_cases()
        
        # 최종 요약
        print(f"\n\n🎯 최종 요약:")
        print(f"✅ 청크 수 {results['reduction_percentage']:.1f}% 감소 달성!")
        print(f"✅ 성능 등급: {results['new_stats'].get('performance_grade', 'A')}")
        print(f"✅ 버퍼 효율성: {results['new_stats'].get('buffer_efficiency', 0):.1f}%")
        
        if results['reduction_percentage'] >= 70:
            print("🏆 목표 달성: 70% 이상 청크 감소 성공!")
        else:
            print("⚠️ 목표 미달: 추가 최적화 필요")
            
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc() 