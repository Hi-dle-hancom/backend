"""
vLLM 멀티 LoRA 서버 통합 서비스
- 4가지 모델 타입별 코드 생성
- 실시간 스트리밍 응답 처리
- 한국어/영어 자동 번역 파이프라인 지원
- 사용자 선택 옵션 최적화
- 🆕 청크 버퍼링 및 배치 처리 최적화
"""

import asyncio
import json
import re
import time
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

from app.core.config import settings
from app.core.structured_logger import StructuredLogger
from app.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    ModelType,
)

# 🆕 AI 성능 메트릭 import 추가
from app.services.performance_profiler import ai_performance_metrics

logger = StructuredLogger("vllm_integration")


class VLLMModelType(str, Enum):
    """vLLM 서버에서 지원하는 모델 타입"""

    AUTOCOMPLETE = "autocomplete"  # 코드 자동완성 (번역 없음)
    PROMPT = "prompt"  # 일반 코드 생성 (전체 번역)
    COMMENT = "comment"  # 주석/docstring 생성 (주석만 번역)
    ERROR_FIX = "error_fix"  # 버그 수정 (전체 번역)


class ChunkBuffer:
    """청크 버퍼링 클래스 - 의미있는 단위로 청크 그룹화 및 후처리 (극한 성능 최적화)"""
    
    def __init__(self, buffer_size: int = 80, buffer_timeout: float = 0.1):
        # 🚀 극한 성능 최적화 설정 (99.9% 청크 감소 목표: 30-50개 청크)
        self.buffer_size = buffer_size  # 극한 감소: 500 → 80자
        self.buffer_timeout = buffer_timeout  # 극한 감소: 2.0 → 0.1초
        self.min_chunk_size = 200  # 극한 증가: 120 → 200자 (더 큰 청크 강제)
        self.max_chunk_size = 800  # 감소: 1200 → 800자
        self.optimal_chunk_size = 400  # 증가: 300 → 400자
        self.buffer = ""
        self.last_flush_time = time.time()
        
        # 성능 모니터링 변수들
        self.total_chunks_processed = 0
        self.total_bytes_processed = 0
        self.small_chunks_count = 0  # 200자 미만 청크 개수
        self.large_chunks_count = 0  # 800자 초과 청크 개수
        self.optimal_chunks_count = 0  # 200-400자 청크 개수
        
        # 🔥 극도로 엄격한 청크 생성 정책
        self.force_meaningful_boundaries = True
        self.strict_size_enforcement = True
        self.ultra_strict_mode = True  # 새로운 극한 모드
        
        # 🔥 극도로 엄격한 의미 구분자 패턴 (오직 완전한 코드 블록만)
        self.meaningful_delimiters = [
            # 최고 우선순위: 완전한 함수/클래스 블록만 (최소 10줄 이상)
            r'def\s+\w+\([^)]*\):\s*\n(?:\s{4}.*\n){10,}',     # 함수 정의 (10줄 이상)
            r'class\s+\w+[^:]*:\s*\n(?:\s{4}.*\n){10,}',       # 클래스 정의 (10줄 이상)
            r'async\s+def\s+\w+\([^)]*\):\s*\n(?:\s{4}.*\n){8,}', # async 함수 (8줄 이상)
            
            # 고우선순위: 완전한 제어 구조 (최소 8줄)
            r'if\s+[^:]+:\s*\n(?:\s{4}.*\n){8,}(?:else:\s*\n(?:\s{4}.*\n)*)?', # if-else (8줄 이상)
            r'for\s+[^:]+:\s*\n(?:\s{4}.*\n){6,}',            # for 루프 (6줄 이상)
            r'while\s+[^:]+:\s*\n(?:\s{4}.*\n){6,}',          # while 루프 (6줄 이상)
            r'try:\s*\n(?:\s{4}.*\n){4,}except[^:]*:\s*\n(?:\s{4}.*\n){4,}', # try-except (각 4줄 이상)
            
            # 중우선순위: 완전한 docstring이나 긴 주석 블록 (100자 이상)
            r'"""\s*\n[^"]{100,}\n\s*"""',                    # 긴 docstring (100자 이상)
            r"'''\s*\n[^']{100,}\n\s*'''",                    # 긴 docstring (100자 이상)
            r'\n\s*#[^\n]{100,}\n',                           # 긴 주석 (100자 이상)
        ]
        
        # 완전한 코드 요소 감지 패턴 (더 엄격하게)
        self.complete_code_patterns = [
            r'def\s+\w+\([^)]*\):\s*\n(?:\s{4}.*\n){8,}',     # 완전한 함수 (8줄 이상)
            r'class\s+\w+[^:]*:\s*\n(?:\s{4}.*\n){8,}',       # 완전한 클래스 (8줄 이상)
            r'if\s+[^:]+:\s*\n(?:\s{4}.*\n){4,}else:\s*\n(?:\s{4}.*\n)+', # 완전한 if-else
            r'try:\s*\n(?:\s{4}.*\n)+except[^:]*:\s*\n(?:\s{4}.*\n)+', # 완전한 try-except
        ]
        
        # 🎯 실제 vLLM stop token 패턴 (제거용)
        self.special_token_patterns = [
            r'\n# --- Generation Complete ---.*$',            # vLLM 완료 마커 및 이후 내용
            r'<｜fim▁begin｜>.*$',                           # FIM 시작 토큰 및 이후 내용
            r'<｜fim▁hole｜>.*$',                            # FIM 홀 토큰 및 이후 내용
            r'<｜fim▁end｜>.*$',                             # FIM 종료 토큰 및 이후 내용
            r'<\|endoftext\|>.*$',                            # GPT 종료 토큰 및 이후 내용
            
            # 백업용 일반적인 토큰들
            r'<\|im_end\|>.*$',                               # ChatML 종료 토큰
            r'<\|im_start\|>[^|]*\|>',                        # ChatML 시작 토큰
            r'<\|assistant\|>',                               # assistant 토큰
            r'<\|user\|>',                                    # user 토큰
            r'<\|system\|>',                                  # system 토큰
            r'<\|end[^>]*\|>',                                # 기타 end 토큰
            r'<\|[^>]*\|>',                                   # 기타 특수 토큰
            r'</?\w+[^>]*>',                                  # HTML 태그 유사 패턴
            r'\[INST\]|\[/INST\]',                            # 명령 토큰
            r'<s>|</s>',                                      # 시작/종료 토큰
            r'<unk>|<pad>|<eos>|<bos>',                       # 특수 토큰들
            r'Assistant:|Human:|User:',                       # 역할 라벨
        ]
        
        # 🚀 불필요한 패턴 제거 (Specific Pattern Removal)
        self.unwanted_patterns = [
            # 셔뱅 및 스크립트 헤더
            r'#!/usr/bin/env python3?.*\n',                   # 셔뱅 라인
            r'#!/bin/python3?.*\n',                           # 간단한 셔뱅
            r'# -\*- coding: utf-8 -\*-.*\n',                # 인코딩 선언
            
            # 파일 메타데이터 및 주석 헤더
            r'# --- File Comment -*\n',                       # 파일 주석 헤더
            r'# Created on\s*:.*\n',                          # 생성 날짜
            r'# Author\s*:.*\n',                              # 작성자
            r'# @Author\s*:.*\n',                             # @Author 형식
            r'# Email\s*:.*\n',                               # 이메일
            r'# Version\s*:.*\n',                             # 버전
            r'# Last modified\s*:.*\n',                       # 수정일
            r'# Description\s*:.*\n',                         # 설명
            
            # 긴 구분선 및 장식 주석
            r'# -{20,}.*\n',                                  # 긴 대시 라인
            r'# ={20,}.*\n',                                  # 긴 등호 라인  
            r'# \*{20,}.*\n',                                 # 긴 별표 라인
            r'# _{20,}.*\n',                                  # 긴 언더스코어 라인
            
            # 날짜/시간 패턴
            r'\d{4}/\d{1,2}/\d{1,2}.*\d{1,2}:\d{2}:\d{2}',   # 날짜시간 형식
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',          # ISO 날짜시간
            
            # HTML/XML 태그 잔재
            r'</c>',                                          # HTML 태그 잔재
            r'<[^>]+>',                                       # 기타 HTML 태그
            
            # 이메일 주소
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', # 이메일 패턴
            
            # 불필요한 독스트링 템플릿
            r'"""[\s\S]*?"""',                                # 멀티라인 독스트링 (선택적)
            r"'''[\s\S]*?'''",                                # 멀티라인 독스트링 (선택적)
        ]
    
    def add_chunk(self, chunk: str) -> Optional[str]:
        """청크를 버퍼에 추가하고 필요시 플러시 - 극한 성능 최적화된 로직"""
        
        # 개발 환경에서만 상세 로그
        if settings.should_log_debug():
            print(f"🔍 [ChunkBuffer] 청크 입력: '{chunk[:30]}...' (길이: {len(chunk)})")
        
        # 먼저 im_end 토큰 체크 - 발견되면 즉시 중단
        if self._contains_end_token(chunk):
            if settings.should_log_performance():
                print(f"🛑 [ChunkBuffer] 종료 토큰 감지: '{chunk[:20]}...'")
            # im_end 토큰 이전 부분만 추출
            clean_chunk = self._extract_content_before_end_token(chunk)
            if clean_chunk:
                self.buffer += clean_chunk
            # 즉시 플러시하고 중단 신호 반환
            final_content = self.flush()
            return final_content if final_content.strip() else "[END_OF_GENERATION]"
        
        # 일반적인 특수 토큰 제거 (im_end 제외)
        cleaned_chunk = self._clean_special_tokens(chunk)
        
        # 빈 내용이면 무시
        if not cleaned_chunk.strip():
            return None
            
        self.buffer += cleaned_chunk
        current_time = time.time()
        
        # 🔥 극도로 엄격한 플러시 조건 (30-50 청크 목표)
        if self.ultra_strict_mode:
            # 극도로 엄격한 모드: 최소 크기의 3배 미달 시 절대 플러시 금지
            if len(self.buffer) < self.min_chunk_size * 3:  # 600자 미만
                # 극도로 제한된 예외: 오직 최대 크기 2배 초과나 강제 종료시만
                if (len(self.buffer) >= self.max_chunk_size * 2 or  # 1600자 이상
                    self._contains_end_token(self.buffer)):
                    should_flush = True
                else:
                    should_flush = False
            else:
                # 최소 크기 3배 충족 시에만 다른 조건 검토
                should_flush = (
                    # 1. 최적 크기 3배 도달 + 완전한 코드 요소만
                    (len(self.buffer) >= self.optimal_chunk_size * 3 and  # 1200자 이상
                     self._has_complete_code_element()) or
                    
                    # 2. 완전한 코드 요소 완성 + 최소 600자 이상
                    (len(self.buffer) >= 600 and
                     self._has_complete_code_element() and
                     self._has_strong_meaningful_boundary()) or
                    
                    # 3. 버퍼 크기 4배 초과 (강제 플러시)
                    len(self.buffer) >= self.buffer_size * 4.0 or  # 320자 이상
                    
                    # 4. 최대 크기 2배 초과 (무조건 플러시)
                    len(self.buffer) >= self.max_chunk_size * 2 or  # 1600자 이상
                    
                    # 5. 매우 엄격한 시간 기반 조건 (거의 발생 안함)
                    (current_time - self.last_flush_time >= self.buffer_timeout * 10.0 and  # 1초 이상
                     len(self.buffer) >= self.min_chunk_size * 4 and  # 800자 이상
                     self._has_complete_code_element() and  # 완전한 코드 요소
                     self._has_strong_meaningful_boundary())  # 강한 경계만
                )
        else:
            # 기존 로직 (호환성)
            should_flush = (
                len(self.buffer) >= self.min_chunk_size and (
                    len(self.buffer) >= self.buffer_size * 1.8 or
                    current_time - self.last_flush_time >= self.buffer_timeout or
                    self._has_complete_code_element() or
                    len(self.buffer) >= self.max_chunk_size
                )
            )
        
        # 성능 모니터링 및 청크 품질 분류
        if should_flush:
            buffer_length = len(self.buffer)
            
            # 청크 크기별 분류 (새로운 기준)
            if buffer_length < self.min_chunk_size:
                self.small_chunks_count += 1
                if settings.should_log_performance():
                    print(f"⚠️ [ChunkBuffer] 작은 청크 플러시: {buffer_length}자 (비정상)")
            elif buffer_length <= self.optimal_chunk_size:
                self.optimal_chunks_count += 1
                if settings.should_log_debug():
                    print(f"✅ [ChunkBuffer] 최적 청크 플러시: {buffer_length}자")
            else:
                self.large_chunks_count += 1
                if settings.should_log_performance():
                    print(f"📦 [ChunkBuffer] 대형 청크 플러시: {buffer_length}자")
            
            result = self.flush()
            
            # 플러시 상세 로그
            if settings.should_log_performance():
                chunk_quality = "최적" if self.min_chunk_size <= buffer_length <= self.optimal_chunk_size else "비정상"
                print(f"📤 [ChunkBuffer] {chunk_quality} 플러시 완료: {buffer_length}자 → {len(result)}자")
            
            return result
        else:
            if settings.should_log_debug():
                print(f"🔄 [ChunkBuffer] 버퍼링 중: {len(self.buffer)}/{self.buffer_size}자")
        
        return None
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """강화된 성능 통계 반환"""
        total_chunks = max(self.total_chunks_processed, 1)
        avg_chunk_size = (self.total_bytes_processed / total_chunks)
        
        # 청크 품질 분석
        small_ratio = round(self.small_chunks_count / total_chunks * 100, 2)
        optimal_ratio = round(self.optimal_chunks_count / total_chunks * 100, 2)
        large_ratio = round(self.large_chunks_count / total_chunks * 100, 2)
        
        # 성능 등급 평가
        if small_ratio <= 5 and optimal_ratio >= 70:
            performance_grade = "A"  # 우수
        elif small_ratio <= 15 and optimal_ratio >= 50:
            performance_grade = "B"  # 양호
        elif small_ratio <= 30:
            performance_grade = "C"  # 보통
        else:
            performance_grade = "D"  # 개선 필요
        
        return {
            "total_chunks": self.total_chunks_processed,
            "total_bytes": self.total_bytes_processed,
            "avg_chunk_size": round(avg_chunk_size, 2),
            
            # 청크 크기별 분류
            "small_chunks_count": self.small_chunks_count,
            "optimal_chunks_count": self.optimal_chunks_count,
            "large_chunks_count": self.large_chunks_count,
            
            # 비율 분석
            "small_chunks_ratio": small_ratio,
            "optimal_chunks_ratio": optimal_ratio,
            "large_chunks_ratio": large_ratio,
            
            # 성능 지표
            "performance_grade": performance_grade,
            "buffer_efficiency": round(optimal_ratio + (large_ratio * 0.7), 2),  # 효율성 점수
            
            # 현재 상태
            "current_buffer_size": len(self.buffer),
            "buffer_utilization": round(len(self.buffer) / self.buffer_size * 100, 2),
            
            # 설정 정보
            "min_chunk_size": self.min_chunk_size,
            "optimal_chunk_size": self.optimal_chunk_size,
            "max_chunk_size": self.max_chunk_size,
            "strict_mode": self.strict_size_enforcement
        }
    
    def _clean_special_tokens(self, text: str) -> str:
        """AI 모델 특수 토큰 제거"""
        cleaned_text = text
        for pattern in self.special_token_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
        return cleaned_text
    
    def _remove_unwanted_patterns(self, text: str) -> str:
        """🚀 불필요한 패턴 제거 (Specific Pattern Removal)"""
        cleaned_text = text
        
        # 첫 번째로 종료 마커 기반 트렁케이션 적용
        cleaned_text = self._extract_content_before_end_token(cleaned_text)
        
        # 두 번째로 불필요한 패턴들 제거
        for pattern in self.unwanted_patterns:
            before_length = len(cleaned_text)
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.MULTILINE | re.IGNORECASE)
            after_length = len(cleaned_text)
            
            # 로그: 패턴이 제거되었을 때만
            if before_length != after_length and settings.should_log_performance():
                print(f"🧹 [패턴제거] '{pattern[:30]}...' 제거: {before_length-after_length}자")
        
        # 최종 정리: 과도한 공백 및 줄바꿈 제거
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)  # 3개 이상 줄바꿈 → 2개
        cleaned_text = re.sub(r'[ \t]+\n', '\n', cleaned_text)  # 줄 끝 공백 제거
        cleaned_text = re.sub(r'\n[ \t]+', '\n', cleaned_text)  # 줄 시작 공백 제거 (들여쓰기 제외)
        
        return cleaned_text.strip()
    
    def _has_complete_code_element(self) -> bool:
        """완전한 코드 요소(함수, 클래스 등)가 있는지 확인"""
        for pattern in self.complete_code_patterns:
            if re.search(pattern, self.buffer, re.MULTILINE | re.DOTALL):
                return True
        return False
    
    def _has_strong_meaningful_boundary(self) -> bool:
        """강한 의미 경계가 있는지 확인 (오직 최고 우선순위 패턴만)"""
        # 오직 첫 번째 패턴만 체크: 완전한 함수 정의 (5줄 이상)
        pattern = self.meaningful_delimiters[0]  # def 함수 (5줄 이상)만
        if re.search(pattern, self.buffer, re.MULTILINE | re.DOTALL):
            return True
        return False
    
    def _has_meaningful_boundary(self) -> bool:
        """의미있는 경계가 있는지 확인 (상위 패턴만)"""
        # 상위 7개 패턴만 체크 (함수, 클래스, async함수, if-else, for, while, try-except)
        for pattern in self.meaningful_delimiters[:7]:
            if re.search(pattern, self.buffer, re.MULTILINE | re.DOTALL):
                return True
        return False
    
    def flush(self) -> str:
        """버퍼 내용을 플러시하고 후처리 (통계는 add_chunk에서 이미 처리됨)"""
        content = self.buffer
        self.buffer = ""
        self.last_flush_time = time.time()
        
        # 전역 통계만 업데이트 (크기별 분류는 add_chunk에서 이미 처리됨)
        self.total_chunks_processed += 1
        self.total_bytes_processed += len(content)
        
        # 🚀 강화된 텍스트 정리 (2단계 방법 적용)
        if content:
            # 1단계: 종료 마커 기반 트렁케이션 + 불필요한 패턴 제거
            content = self._remove_unwanted_patterns(content)
            
            # 2단계: AI 모델 특수 토큰 제거 (백업)
            content = self._clean_special_tokens(content)
            
            # 3단계: 코드 블록 정리
            content = re.sub(r'\n{3,}```', '\n\n```', content)  # 코드 블록 앞 과도한 줄바꿈
            content = re.sub(r'```\n{3,}', '```\n\n', content)  # 코드 블록 뒤 과도한 줄바꿈
        
        return content.strip()
    
    def force_flush(self) -> Optional[str]:
        """강제 플러시 (스트리밍 종료 시) - 🚀 2단계 정리 적용"""
        if self.buffer:
            content = self.flush()
            # 🚀 추가적인 불필요한 패턴 제거 (더 강력한 정리)
            content = self._remove_unwanted_patterns(content)
            content = self._clean_special_tokens(content)
            return content if content.strip() else None
        return None

    def _contains_end_token(self, text: str) -> bool:
        """실제 vLLM stop token 확인 - FIM 토큰 포함"""
        # 🎯 실제 vLLM에서 사용하는 stop token들
        end_patterns = [
            r'\n# --- Generation Complete ---',               # vLLM 완료 마커
            r'<｜fim▁begin｜>',                              # FIM 시작 토큰 (일본어 ｜)
            r'<｜fim▁hole｜>',                               # FIM 홀 토큰 (일본어 ｜)
            r'<｜fim▁end｜>',                                # FIM 종료 토큰 (일본어 ｜)
            r'<\|endoftext\|>',                               # GPT 스타일 종료 (영어 |)
            
            # 백업용 일반적인 종료 패턴들
            r'<\|im_end\|>',                                  # ChatML 종료
            r'</s>',                                          # 시퀀스 종료
            r'<eos>',                                         # End of Sequence
            r'\[DONE\]',                                      # 커스텀 완료 신호
        ]
        
        for pattern in end_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False
    
    def _extract_content_before_end_token(self, text: str) -> str:
        """🚀 종료 마커 기반 트렁케이션 (Stop Marker Truncation)"""
        # 🎯 실제 vLLM에서 사용하는 stop token들 (우선순위 순)
        end_patterns = [
            r'\n# --- Generation Complete ---',               # vLLM 완료 마커
            r'<｜fim▁begin｜>',                              # FIM 시작 토큰 (일본어 ｜)
            r'<｜fim▁hole｜>',                               # FIM 홀 토큰 (일본어 ｜)
            r'<｜fim▁end｜>',                                # FIM 종료 토큰 (일본어 ｜)
            r'<\|endoftext\|>',                               # GPT 스타일 종료 (영어 |)
            
            # 백업용 일반적인 종료 패턴들
            r'<\|im_end\|>',                                  # ChatML 종료
            r'</s>',                                          # 시퀀스 종료
            r'<eos>',                                         # End of Sequence
            r'\[DONE\]',                                      # 커스텀 완료 신호
            
            # 🚀 추가 트렁케이션 패턴들 (불필요한 내용 차단)
            r'#!/usr/bin/env python',                         # 셔뱅 시작점에서 차단
            r'# --- File Comment',                            # 파일 주석 시작점에서 차단
            r'# Created on\s*:',                              # 메타데이터 시작점에서 차단
            r'# Author\s*:',                                  # 작성자 정보 시작점에서 차단
            r'# @Author',                                     # @Author 시작점에서 차단
            r'@\w+\.\w+',                                     # 이메일 시작점에서 차단 (예: jiaoyu_li@deepseeks.com)
            r'</c>',                                          # HTML 태그 잔재에서 차단
        ]
        
        # 가장 먼저 발견되는 패턴에서 트렁케이션
        earliest_match = None
        earliest_position = len(text)
        earliest_pattern = None
        
        for pattern in end_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match and match.start() < earliest_position:
                earliest_position = match.start()
                earliest_match = match
                earliest_pattern = pattern
        
        if earliest_match:
            # 가장 빠른 종료 마커 이전 부분만 반환
            content_before = text[:earliest_position].strip()
            if settings.should_log_performance():
                print(f"✂️ [트렁케이션] '{earliest_pattern}' 감지 → 차단: '{content_before[:50]}...'")
            return content_before
        
        return text


class VLLMIntegrationService:
    """vLLM 멀티 LoRA 서버와의 통합 서비스"""

    def __init__(self):
        self.vllm_base_url = settings.VLLM_SERVER_URL
        self.timeout = aiohttp.ClientTimeout(total=settings.VLLM_TIMEOUT_SECONDS)
        self.session = None
        
        # 🚀 청크 버퍼링 설정 극한 강화 (30-50 청크 목표)
        self.chunk_buffering_enabled = True
        self.default_buffer_size = 80  # 극한 감소: 500 → 80자
        self.default_buffer_timeout = 0.1  # 극한 감소: 2.0 → 0.1초
        
        # 성능 최적화 설정
        self.enable_performance_logging = settings.should_log_performance()
        self.enable_debug_logging = settings.should_log_debug()
        self.enable_chunk_details = getattr(settings, 'should_log_chunk_details', lambda: False)() 
        
        if self.enable_performance_logging:
            print(f"⚙️ [vLLM] 서비스 초기화: 버퍼크기={self.default_buffer_size}, 타임아웃={self.default_buffer_timeout}초")

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp 세션 생성 및 재사용"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            )
        return self.session

    async def check_health(self) -> Dict[str, Any]:
        """vLLM 서버 상태 확인"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.vllm_base_url}/health") as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 환경별 조건부 로깅
                    if settings.should_log_debug():
                        logger.log_system_event(
                            "vLLM 서버 상태 확인", "success", {"server_status": result}
                        )
                    
                    return {"status": "healthy", "details": result}
                else:
                    logger.log_system_event(
                        "vLLM 서버 상태 확인",
                        "failed",
                        {"http_status": response.status},
                    )
                    return {
                        "status": "unhealthy",
                        "http_status": response.status}
        except Exception as e:
            logger.log_error(e, "vLLM 서버 연결")
            return {"status": "error", "error": str(e)}

    async def get_available_models(self) -> Dict[str, Any]:
        """사용 가능한 모델 목록 조회"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.vllm_base_url}/models") as response:
                if response.status == 200:
                    models = await response.json()
                    
                    # 환경별 조건부 로깅
                    if settings.should_log_debug():
                        logger.log_system_event(
                            "사용 가능한 모델 조회", "success", {"model_count": len(models)}
                        )
                    
                    return {"status": "success", "models": models}
                else:
                    return {"status": "error", "http_status": response.status}
        except Exception as e:
            logger.log_error(e, "모델 목록 조회")
            return {"status": "error", "error": str(e)}

    def _map_hapa_to_vllm_model(self, hapa_model: ModelType) -> VLLMModelType:
        """HAPA 모델 타입을 vLLM 모델 타입으로 매핑"""
        mapping = {
            ModelType.CODE_COMPLETION: VLLMModelType.AUTOCOMPLETE,
            ModelType.CODE_GENERATION: VLLMModelType.PROMPT,
            ModelType.CODE_EXPLANATION: VLLMModelType.COMMENT,
            ModelType.BUG_FIX: VLLMModelType.ERROR_FIX,
            ModelType.CODE_REVIEW: VLLMModelType.PROMPT,
            ModelType.CODE_OPTIMIZATION: VLLMModelType.PROMPT,
            ModelType.UNIT_TEST_GENERATION: VLLMModelType.PROMPT,
            ModelType.DOCUMENTATION: VLLMModelType.COMMENT,
        }
        return mapping.get(hapa_model, VLLMModelType.PROMPT)

    def _prepare_vllm_request(
        self, request: CodeGenerationRequest, user_id: str
    ) -> Dict[str, Any]:
        """HAPA 요청을 vLLM 요청 형식으로 변환 - 극한 성능 최적화"""
        vllm_model = self._map_hapa_to_vllm_model(request.model_type)

        # 🚀 요청 복잡도 분석 및 동적 파라미터 최적화
        complexity_analysis = self._analyze_request_complexity(request.prompt)
        optimized_params = self._get_optimized_parameters(complexity_analysis, vllm_model)
        
        # 🚀 강화된 프롬프트 최적화 (간결성 강제)
        optimized_prompt = self._optimize_prompt_for_model(
            request.prompt, vllm_model, request, complexity_analysis
        )

        # 사용자 선택 옵션 매핑
        user_select_options = self._map_user_options(request)

        # user_id를 숫자로 변환 (해시 사용)
        try:
            numeric_user_id = abs(hash(user_id)) % 1000000  # 1-1000000 범위
        except BaseException:
            numeric_user_id = 12345  # 기본값

        # 🎯 실제 vLLM에서 사용하는 stop token 설정
        stop_tokens = [
            "\n# --- Generation Complete ---",  # vLLM 완료 마커
            "<｜fim▁begin｜>",                  # FIM 시작 토큰 (일본어 ｜)
            "<｜fim▁hole｜>",                   # FIM 홀 토큰 (일본어 ｜)
            "<｜fim▁end｜>",                    # FIM 종료 토큰 (일본어 ｜)
            "<|endoftext|>",                    # GPT 스타일 종료 토큰 (영어 |)
        ]
        
        # 간단한 요청에 대해서는 더 엄격한 종료 조건 추가
        if complexity_analysis["level"] == "simple":
            stop_tokens.extend([
                "\n\n```",       # 코드 블록 후 즉시 종료
                "\n\n#",         # 주석 시작 시 종료
                "\nprint(",      # 추가 print문 방지
                "\n# 설명",      # 설명 시작 시 종료
                "\n# 예시",      # 예시 시작 시 종료
            ])

        vllm_request = {
            "user_id": numeric_user_id,
            "model_type": vllm_model.value,
            "prompt": optimized_prompt,
            "user_select_options": user_select_options,
            "temperature": optimized_params["temperature"],
            "top_p": optimized_params["top_p"],
            "max_tokens": optimized_params["max_tokens"],
            "stop": stop_tokens,  # 🚀 종료 토큰 추가
        }

        # 환경별 조건부 로깅 - 요청 상세 정보
        if settings.should_log_request_response():
            logger.log_system_event(
                f"vLLM 요청 준비 (최적화됨)",
                "success",
                {
                    "user_id": user_id,
                    "numeric_user_id": numeric_user_id,
                    "model_type": vllm_model.value,
                    "prompt_length": len(optimized_prompt),
                    "complexity": complexity_analysis["level"],
                    "max_tokens": optimized_params["max_tokens"],
                    "temperature": optimized_params["temperature"],
                },
            )

        return vllm_request
    
    def _analyze_request_complexity(self, prompt: str) -> Dict[str, Any]:
        """요청 복잡도 분석 - 간단/중간/복잡 분류"""
        prompt_lower = prompt.lower()
        
        # 🔍 간단한 요청 패턴 감지
        simple_patterns = [
            # 출력 관련
            r'(출력|print|display).*["\']?\w{1,10}["\']?',  # "jay 출력", "hello world 출력"
            r'["\']?\w{1,10}["\']?.*출력',                 # "jay를 출력"
            r'print\s*\(["\']?\w{1,20}["\']?\)',           # print("jay")
            
            # 변수 선언
            r'^[a-zA-Z_]\w*\s*=\s*["\']?\w{1,20}["\']?$',  # name = "jay"
            
            # 간단한 함수 호출
            r'^\w+\(\)$',                                  # func()
            
            # 한 줄 코드
            r'^.{1,50}$',                                  # 50자 이하
        ]
        
        # 🔍 복잡한 요청 패턴 감지
        complex_patterns = [
            # 클래스/함수 정의
            r'(class|def|async def)',
            r'(algorithm|알고리즘)',
            r'(database|데이터베이스|db)',
            r'(api|rest|graphql)',
            r'(optimization|최적화)',
            r'(machine learning|머신러닝|ml)',
            r'(data structure|자료구조)',
            r'(design pattern|디자인패턴)',
            
            # 복잡한 기능
            r'(error handling|예외처리)',
            r'(unit test|테스트)',
            r'(documentation|문서화)',
            r'(refactor|리팩토링)',
        ]
        
        # 길이 기반 분석
        char_count = len(prompt)
        word_count = len(prompt.split())
        
        # 패턴 매칭
        simple_matches = sum(1 for pattern in simple_patterns if re.search(pattern, prompt, re.IGNORECASE))
        complex_matches = sum(1 for pattern in complex_patterns if re.search(pattern, prompt, re.IGNORECASE))
        
        # 복잡도 결정
        if simple_matches > 0 and char_count <= 50 and complex_matches == 0:
            complexity_level = "simple"
            confidence = 0.9
        elif complex_matches > 0 or char_count > 200 or word_count > 30:
            complexity_level = "complex"
            confidence = 0.8
        else:
            complexity_level = "medium"
            confidence = 0.7
        
        return {
            "level": complexity_level,
            "confidence": confidence,
            "char_count": char_count,
            "word_count": word_count,
            "simple_matches": simple_matches,
            "complex_matches": complex_matches,
            "patterns_detected": []
        }
    
    def _get_optimized_parameters(self, complexity_analysis: Dict[str, Any], model_type: VLLMModelType) -> Dict[str, Any]:
        """복잡도 분석 결과에 따른 최적화된 파라미터 반환"""
        complexity_level = complexity_analysis["level"]
        
        # 🚀 복잡도별 극한 최적화 파라미터
        if complexity_level == "simple":
            # 간단한 요청: 극한 최적화 (3-5초, 30-50 청크 목표)
            return {
                "max_tokens": 50,      # 극한 감소: 1024 → 50 토큰
                "temperature": 0.1,    # 극한 감소: 0.3 → 0.1 (정확성 우선)
                "top_p": 0.8,          # 감소: 0.95 → 0.8 (집중도 증가)
            }
        elif complexity_level == "medium":
            # 중간 복잡도: 적당한 최적화
            return {
                "max_tokens": 200,     # 크게 감소: 1024 → 200 토큰
                "temperature": 0.2,    # 감소: 0.3 → 0.2
                "top_p": 0.85,         # 감소: 0.95 → 0.85
            }
        else:  # complex
            # 복잡한 요청: 보수적 최적화
            return {
                "max_tokens": 500,     # 중간 감소: 1024 → 500 토큰
                "temperature": 0.25,   # 약간 감소: 0.3 → 0.25
                "top_p": 0.9,          # 약간 감소: 0.95 → 0.9
            }

    def _optimize_prompt_for_model(
        self,
        prompt: str,
        model_type: VLLMModelType,
        request: CodeGenerationRequest,
        complexity_analysis: Dict[str, Any]) -> str:
        """모델 타입에 따른 프롬프트 최적화 - 간결성 강제"""
        
        complexity_level = complexity_analysis["level"]
        
        # 🚀 간단한 요청에 대한 강화된 프롬프트 최적화
        if complexity_level == "simple":
            # 간단한 요청: 극도로 간결한 응답 강제
            if model_type == VLLMModelType.AUTOCOMPLETE:
                return prompt
            
            # 간단한 출력 요청 최적화
            if re.search(r'(출력|print)', prompt, re.IGNORECASE):
                # "jay 출력" -> 강제로 한 줄 코드만 요청
                return f"""다음 요청에 대해 Python 코드 한 줄만 작성하세요. 설명이나 주석 없이 코드만 반환하세요.

요청: {prompt}

조건:
- 한 줄 코드만 작성
- print() 함수 사용
- 설명 금지
- 예시나 추가 내용 금지

코드:"""
            
            else:
                return f"""다음 요청에 대해 최소한의 Python 코드만 작성하세요. 간결하고 핵심적인 코드만 반환하세요.

요청: {prompt}

조건:
- 최대 3줄 코드
- 필수 코드만 작성
- 설명 최소화
- 예시 금지

코드:"""
        
        # 기존 로직 (중간/복잡한 요청)
        if model_type == VLLMModelType.AUTOCOMPLETE:
            # 자동완성: 컨텍스트 중심으로 간단한 프롬프트
            return prompt

        elif model_type == VLLMModelType.COMMENT:
            # 주석/문서화: 코드 해석 및 문서화 프롬프트
            context_prefix = (
                f"# 대상 코드:\n{request.context}\n\n" if request.context else ""
            )
            return f"{context_prefix}# 문서화 요청: {prompt}"

        elif model_type == VLLMModelType.ERROR_FIX:
            # 버그 수정: 오류 분석 및 수정 프롬프트
            context_prefix = (
                f"# 오류가 있는 코드:\n{request.context}\n\n" if request.context else ""
            )
            return f"""{context_prefix}# 버그 수정 요청: {prompt}

# 수정 가이드라인:
1. 오류 원인 명확히 분석
2. 최소한의 수정으로 문제 해결
3. 간단하고 명확한 코드 작성

## 수정된 코드:"""

        else:  # PROMPT (기본)
            # 일반 코드 생성: 요구사항을 명확히 표현
            if complexity_level == "medium":
                context_prefix = (
                    f"# 컨텍스트:\n{request.context}\n\n" if request.context else ""
                )
                return f"""{context_prefix}# 요청사항: {prompt}

조건:
- 간결하고 실용적인 코드 작성
- 필수 기능만 구현
- 과도한 설명 금지

코드:"""
            else:  # complex
                context_prefix = (
                    f"# 컨텍스트:\n{request.context}\n\n" if request.context else ""
                )
                return f"{context_prefix}# 요청사항: {prompt}"

    def _map_user_options(
            self, request: CodeGenerationRequest) -> Dict[str, Any]:
        """HAPA 사용자 옵션을 vLLM 형식으로 매핑"""
        options = {}

        # 프로그래밍 기술 수준 매핑
        if hasattr(request, "programming_level"):
            level_mapping = {
                "beginner": "beginner",
                "intermediate": "intermediate",
                "advanced": "advanced",
                "expert": "advanced",
            }
            options["python_skill_level"] = level_mapping.get(
                request.programming_level, "intermediate"
            )
        else:
            options["python_skill_level"] = "intermediate"

        # 설명 스타일 매핑
        if hasattr(request, "explanation_detail"):
            detail_mapping = {
                "minimal": "brief",
                "standard": "standard",
                "detailed": "detailed",
                "comprehensive": "detailed",
            }
            options["explanation_style"] = detail_mapping.get(
                request.explanation_detail, "standard"
            )
        else:
            options["explanation_style"] = "standard"

        # 추가 옵션들
        if hasattr(request, "include_comments"):
            options["include_comments"] = request.include_comments

        if hasattr(request, "code_style"):
            options["code_style"] = request.code_style

        return options

    async def generate_code_stream(
        self, request: CodeGenerationRequest, user_id: str
    ) -> AsyncGenerator[str, None]:
        """vLLM 서버로부터 스트리밍 코드 생성 (개선된 청크 처리)"""

        vllm_request = self._prepare_vllm_request(request, user_id)
        
        # 청크 버퍼 초기화
        chunk_buffer = ChunkBuffer(
            buffer_size=self.default_buffer_size,
            buffer_timeout=self.default_buffer_timeout
        ) if self.chunk_buffering_enabled else None

        if self.enable_performance_logging:
            print(f"🔧 [vLLM] 청크 버퍼링 설정: 활성화={self.chunk_buffering_enabled}, 버퍼크기={self.default_buffer_size}, 타임아웃={self.default_buffer_timeout}")
            if chunk_buffer:
                print(f"✅ [vLLM] ChunkBuffer 생성 완료")

        try:
            session = await self._get_session()

            async with session.post(
                f"{self.vllm_base_url}/generate/stream", json=vllm_request
            ) as response:

                if response.status != 200:
                    error_msg = f"vLLM 서버 오류: HTTP {response.status}"
                    logger.log_system_event(
                        "vLLM 서버 오류",
                        "failed",
                        {"user_id": user_id, "status": response.status},
                    )
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    return

                # 스트리밍 시작 로그 (성능 로그로 분류)
                if self.enable_performance_logging:
                    logger.log_system_event(
                        "vLLM 스트리밍 시작",
                        "started",
                        {"user_id": user_id, "model": vllm_request["model_type"]},
                    )

                chunk_count = 0
                total_content_length = 0
                streaming_start_time = time.time()

                async for line in response.content:
                    try:
                        line_text = line.decode("utf-8").strip()

                        if not line_text:
                            continue

                        # Server-Sent Events 형식 처리
                        if line_text.startswith("data: "):
                            data_content = line_text[6:]  # 'data: ' 제거

                            # 스트림 종료 신호 감지 - 강화된 처리
                            if data_content == "[DONE]" or data_content.strip() == "[DONE]":
                                # 버퍼에 남은 내용 플러시
                                if chunk_buffer:
                                    final_content = chunk_buffer.force_flush()
                                    if final_content and final_content.strip():
                                        chunk_count += 1
                                        total_content_length += len(final_content)
                                        yield f"data: {json.dumps({'text': final_content})}\n\n"
                                        if self.enable_debug_logging:
                                            print(f"📤 [vLLM] 최종 버퍼 플러시: '{final_content[:30]}...'")
                                
                                # 완료 로그 (성능 로그로 분류)
                                streaming_duration = time.time() - streaming_start_time
                                if self.enable_performance_logging:
                                    # 버퍼 성능 통계 포함
                                    buffer_stats = chunk_buffer.get_performance_stats() if chunk_buffer else {}
                                    logger.log_system_event(
                                        "vLLM 스트리밍", "completed", {
                                            "user_id": user_id,
                                            "total_chunks": chunk_count,
                                            "total_content_length": total_content_length,
                                            "duration_seconds": round(streaming_duration, 2),
                                            "avg_chunk_size": round(total_content_length / max(chunk_count, 1), 1),
                                            "buffer_stats": buffer_stats
                                        })
                                    print(f"🏁 [vLLM] 스트리밍 완료: {chunk_count}개 청크, {total_content_length}자, {streaming_duration:.2f}초")
                                    
                                    # 성능 경고 확인
                                    if buffer_stats.get('small_chunks_ratio', 0) > 30:
                                        print(f"⚠️ [vLLM] 작은 청크 비율 높음: {buffer_stats.get('small_chunks_ratio', 0)}%")
                                
                                yield f"data: [DONE]\n\n"
                                return  # 확실한 종료

                            # JSON 데이터 파싱 및 처리
                            try:
                                parsed_data = json.loads(data_content)
                                
                                # 텍스트 콘텐츠 추출
                                text_content = parsed_data.get('text', '')
                                if text_content:
                                    total_content_length += len(text_content)
                                    
                                    # 디버그 로그는 개발 환경에서만
                                    if self.enable_debug_logging:
                                        print(f"📥 [vLLM] 원시 텍스트: '{text_content[:20]}...' (길이: {len(text_content)})")
                                    
                                    if chunk_buffer:
                                        # 버퍼링 처리
                                        buffered_content = chunk_buffer.add_chunk(text_content)
                                        if buffered_content and buffered_content.strip():
                                            chunk_count += 1
                                            
                                            # 성능 로그는 성능 모드에서만
                                            if self.enable_performance_logging:
                                                print(f"📤 [vLLM] 버퍼링 출력: #{chunk_count}, 길이={len(buffered_content)}")
                                            
                                            # END_OF_GENERATION 신호 감지 시 즉시 중단
                                            if buffered_content == "[END_OF_GENERATION]":
                                                streaming_duration = time.time() - streaming_start_time
                                                if self.enable_performance_logging:
                                                    logger.log_system_event(
                                                        "vLLM 스트리밍", "im_end_detected", {
                                                            "user_id": user_id,
                                                            "total_chunks": chunk_count,
                                                            "total_content_length": total_content_length,
                                                            "early_termination": True,
                                                            "duration_seconds": round(streaming_duration, 2)
                                                        })
                                                    print(f"🛑 [vLLM] END_OF_GENERATION 신호 - 조기 종료")
                                                yield f"data: [DONE]\n\n"
                                                return
                                            
                                            # 청크 상세 로그 (개발 환경에서만)
                                            if self.enable_chunk_details:
                                                logger.debug(
                                                    f"청크 전송: #{chunk_count}, 길이: {len(buffered_content)}"
                                                )
                                            
                                            yield f"data: {json.dumps({'text': buffered_content})}\n\n"
                                        # else: 버퍼링 중이므로 아무것도 하지 않음 (로그 생략)
                                    else:
                                        # 버퍼링 비활성화 시 직접 전송 (하지만 im_end 토큰 체크)
                                        if self.enable_debug_logging:
                                            print(f"🚫 [vLLM] 버퍼링 비활성화 - 직접 전송")
                                        
                                        # 🎯 실제 vLLM stop token + 트렁케이션 패턴 감지 시 즉시 중단
                                        vllm_stop_tokens = [
                                            "\n# --- Generation Complete ---",
                                            "<｜fim▁begin｜>",
                                            "<｜fim▁hole｜>",
                                            "<｜fim▁end｜>",
                                            "<|endoftext|>",
                                            # 🚀 추가 트렁케이션 패턴들
                                            "#!/usr/bin/env python",
                                            "# --- File Comment",
                                            "# Created on:",
                                            "# Author:",
                                            "# @Author",
                                            "</c>",
                                            "@deepseeks.com",
                                            "_li@",
                                        ]
                                        
                                        detected_stop_token = None
                                        for stop_token in vllm_stop_tokens:
                                            if stop_token in text_content:
                                                detected_stop_token = stop_token
                                                break
                                        
                                        if detected_stop_token:
                                            streaming_duration = time.time() - streaming_start_time
                                            if self.enable_performance_logging:
                                                logger.log_system_event(
                                                    "vLLM 스트리밍", "vllm_stop_token_detected_direct", {
                                                        "user_id": user_id,
                                                        "total_chunks": chunk_count,
                                                        "total_content_length": total_content_length,
                                                        "early_termination": True,
                                                        "stop_token": detected_stop_token,
                                                        "duration_seconds": round(streaming_duration, 2)
                                                    })
                                                print(f"🛑 [vLLM] 직접모드에서 실제 stop token 감지: {detected_stop_token}")
                                            yield f"data: [DONE]\n\n"
                                            return
                                        
                                        chunk_count += 1
                                        yield f"data: {data_content}\n\n"
                                else:
                                    # 텍스트가 없는 메타데이터 청크는 그대로 전송
                                    yield f"data: {data_content}\n\n"
                                    
                            except json.JSONDecodeError:
                                # JSON이 아닌 순수 텍스트인 경우
                                if chunk_buffer:
                                    buffered_content = chunk_buffer.add_chunk(data_content)
                                    if buffered_content and buffered_content.strip():
                                        chunk_count += 1
                                        yield f"data: {json.dumps({'text': buffered_content})}\n\n"
                                else:
                                    chunk_count += 1
                                    yield f"data: {data_content}\n\n"

                    except Exception as e:
                        # 라인 처리 오류는 디버그 환경에서만 로깅
                        if self.enable_debug_logging:
                            logger.log_error(e, f"스트림 라인 처리 - user_id: {user_id}")
                        continue

        except asyncio.TimeoutError:
            error_msg = "vLLM 서버 응답 시간 초과"
            logger.log_system_event("vLLM 응답", "timeout", {"user_id": user_id})
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

        except Exception as e:
            error_msg = f"vLLM 서버 연결 오류: {str(e)}"
            logger.log_error(e, f"vLLM 서버 연결 - user_id: {user_id}")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    async def generate_code_sync(
        self, request: CodeGenerationRequest, user_id: str
    ) -> CodeGenerationResponse:
        """동기식 코드 생성 (스트리밍 응답을 모두 수집)"""

        generated_content = []
        error_occurred = False
        error_message = ""

        async for chunk in self.generate_code_stream(request, user_id):
            try:
                if chunk.startswith("data: "):
                    data_content = chunk[6:].strip()

                    if data_content == "[DONE]":
                        break

                    # JSON 파싱 시도
                    try:
                        data = json.loads(data_content)
                        if "error" in data:
                            error_occurred = True
                            error_message = data["error"]
                            break
                        elif "text" in data:
                            generated_content.append(data["text"])
                        elif isinstance(data, str):
                            generated_content.append(data)
                    except json.JSONDecodeError:
                        # JSON이 아닌 경우 직접 텍스트로 처리
                        generated_content.append(data_content)

            except Exception as e:
                logger.log_error(e, f"동기식 응답 처리 - user_id: {user_id}")
                error_occurred = True
                error_message = str(e)
                break

        if error_occurred:
            return CodeGenerationResponse(
                success=False,
                generated_code="",
                error_message=error_message,
                model_used=self._map_hapa_to_vllm_model(
                    request.model_type).value,
                processing_time=0,
                token_usage={
                    "total_tokens": 0},
            )

        final_code = "".join(generated_content)

        return CodeGenerationResponse(
            success=True,
            generated_code=final_code,
            model_used=self._map_hapa_to_vllm_model(request.model_type).value,
            processing_time=0,  # 실제 처리 시간 계산 필요
            token_usage={"total_tokens": len(final_code.split())},  # 근사치
        )

    async def close(self):
        """세션 정리"""
        if self.session and not self.session.closed:
            await self.session.close()

    def __del__(self):
        """소멸자에서 세션 정리"""
        if hasattr(
                self,
                "session") and self.session and not self.session.closed:
            # 이벤트 루프가 실행 중인 경우에만 정리
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.session.close())
            except RuntimeError:
                pass


# 전역 서비스 인스턴스
vllm_service = VLLMIntegrationService()
