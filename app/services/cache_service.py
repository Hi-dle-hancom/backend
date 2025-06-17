import json
import os
import time
import hashlib
import pickle
from pathlib import Path
from typing import Any, Optional, Dict, Union
from datetime import datetime, timedelta
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class PersistentCache:
    """파일 기반 영속성 캐시 시스템"""
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 캐시 설정
        self.max_cache_size = settings.MAX_CACHE_SIZE
        self.default_ttl = settings.CACHE_TTL
        
        # 메타데이터 파일
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()
        
        # 정리 작업 (시작시 한 번)
        self._cleanup_expired()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """캐시 메타데이터 로드"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"캐시 메타데이터 로드 실패: {e}")
        
        return {
            "entries": {},
            "stats": {
                "hits": 0,
                "misses": 0,
                "total_entries": 0,
                "last_cleanup": time.time()
            }
        }
    
    def _save_metadata(self):
        """캐시 메타데이터 저장"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"캐시 메타데이터 저장 실패: {e}")
    
    def _generate_key_hash(self, key: str) -> str:
        """키를 안전한 파일명으로 변환"""
        return hashlib.md5(key.encode('utf-8')).hexdigest()
    
    def _get_cache_file_path(self, key: str) -> Path:
        """캐시 파일 경로 생성"""
        key_hash = self._generate_key_hash(key)
        return self.cache_dir / f"{key_hash}.cache"
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """캐시에 값 저장"""
        try:
            if ttl is None:
                ttl = self.default_ttl
            
            # 만료 시간 계산
            expires_at = time.time() + ttl
            
            # 캐시 파일에 저장
            cache_file = self._get_cache_file_path(key)
            cache_data = {
                "value": value,
                "created_at": time.time(),
                "expires_at": expires_at,
                "key": key,
                "access_count": 0
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # 메타데이터 업데이트
            key_hash = self._generate_key_hash(key)
            self.metadata["entries"][key_hash] = {
                "key": key,
                "created_at": time.time(),
                "expires_at": expires_at,
                "file_path": str(cache_file),
                "size": cache_file.stat().st_size if cache_file.exists() else 0
            }
            
            self.metadata["stats"]["total_entries"] = len(self.metadata["entries"])
            self._save_metadata()
            
            # 캐시 크기 제한 확인
            self._enforce_size_limit()
            
            logger.debug(f"캐시 저장 완료: {key} (TTL: {ttl}초)")
            return True
            
        except Exception as e:
            logger.error(f"캐시 저장 실패: {key} - {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """캐시에서 값 조회"""
        try:
            cache_file = self._get_cache_file_path(key)
            
            if not cache_file.exists():
                self.metadata["stats"]["misses"] += 1
                self._save_metadata()
                logger.debug(f"캐시 미스: {key} (파일 없음)")
                return default
            
            # 캐시 데이터 로드
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            # 만료 확인
            if cache_data["expires_at"] < time.time():
                self.delete(key)
                self.metadata["stats"]["misses"] += 1
                self._save_metadata()
                logger.debug(f"캐시 미스: {key} (만료됨)")
                return default
            
            # 접근 횟수 증가
            cache_data["access_count"] += 1
            cache_data["last_accessed"] = time.time()
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            self.metadata["stats"]["hits"] += 1
            self._save_metadata()
            
            logger.debug(f"캐시 히트: {key}")
            return cache_data["value"]
            
        except Exception as e:
            logger.error(f"캐시 조회 실패: {key} - {e}")
            self.metadata["stats"]["misses"] += 1
            self._save_metadata()
            return default
    
    def delete(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        try:
            cache_file = self._get_cache_file_path(key)
            key_hash = self._generate_key_hash(key)
            
            # 파일 삭제
            if cache_file.exists():
                cache_file.unlink()
            
            # 메타데이터에서 제거
            if key_hash in self.metadata["entries"]:
                del self.metadata["entries"][key_hash]
                self.metadata["stats"]["total_entries"] = len(self.metadata["entries"])
                self._save_metadata()
            
            logger.debug(f"캐시 삭제 완료: {key}")
            return True
            
        except Exception as e:
            logger.error(f"캐시 삭제 실패: {key} - {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """캐시 키 존재 여부 확인"""
        cache_file = self._get_cache_file_path(key)
        
        if not cache_file.exists():
            return False
        
        try:
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            # 만료 확인
            if cache_data["expires_at"] < time.time():
                self.delete(key)
                return False
            
            return True
            
        except Exception:
            self.delete(key)
            return False
    
    def clear(self) -> bool:
        """모든 캐시 삭제"""
        try:
            # 모든 캐시 파일 삭제
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            
            # 메타데이터 초기화
            self.metadata = {
                "entries": {},
                "stats": {
                    "hits": 0,
                    "misses": 0,
                    "total_entries": 0,
                    "last_cleanup": time.time()
                }
            }
            self._save_metadata()
            
            logger.info("모든 캐시 삭제 완료")
            return True
            
        except Exception as e:
            logger.error(f"캐시 삭제 실패: {e}")
            return False
    
    def _cleanup_expired(self):
        """만료된 캐시 엔트리 정리"""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key_hash, entry in self.metadata["entries"].items():
                if entry["expires_at"] < current_time:
                    expired_keys.append(entry["key"])
            
            # 만료된 키들 삭제
            for key in expired_keys:
                self.delete(key)
            
            self.metadata["stats"]["last_cleanup"] = current_time
            self._save_metadata()
            
            if expired_keys:
                logger.info(f"만료된 캐시 {len(expired_keys)}개 정리 완료")
                
        except Exception as e:
            logger.error(f"캐시 정리 실패: {e}")
    
    def _enforce_size_limit(self):
        """캐시 크기 제한 적용"""
        try:
            entries = list(self.metadata["entries"].items())
            
            if len(entries) <= self.max_cache_size:
                return
            
            # 접근 시간 기준으로 정렬 (LRU)
            entries.sort(key=lambda x: x[1].get("created_at", 0))
            
            # 오래된 항목부터 삭제
            remove_count = len(entries) - self.max_cache_size
            for i in range(remove_count):
                key_hash, entry = entries[i]
                self.delete(entry["key"])
            
            logger.info(f"캐시 크기 제한으로 {remove_count}개 항목 삭제")
            
        except Exception as e:
            logger.error(f"캐시 크기 제한 적용 실패: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보 반환"""
        stats = self.metadata["stats"].copy()
        
        # 히트율 계산
        total_requests = stats["hits"] + stats["misses"]
        if total_requests > 0:
            stats["hit_rate"] = stats["hits"] / total_requests
        else:
            stats["hit_rate"] = 0.0
        
        # 캐시 크기 정보
        total_size = 0
        for entry in self.metadata["entries"].values():
            total_size += entry.get("size", 0)
        
        stats["total_size_bytes"] = total_size
        stats["total_size_mb"] = total_size / (1024 * 1024)
        
        return stats
    
    def get_cache_info(self) -> Dict[str, Any]:
        """상세 캐시 정보 반환"""
        return {
            "stats": self.get_stats(),
            "settings": {
                "max_cache_size": self.max_cache_size,
                "default_ttl": self.default_ttl,
                "cache_dir": str(self.cache_dir)
            },
            "entries": len(self.metadata["entries"])
        }

# 전역 캐시 인스턴스
cache = PersistentCache()

# 편의 함수들
def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """캐시에 값 저장"""
    return cache.set(key, value, ttl)

def cache_get(key: str, default: Any = None) -> Any:
    """캐시에서 값 조회"""
    return cache.get(key, default)

def cache_delete(key: str) -> bool:
    """캐시에서 값 삭제"""
    return cache.delete(key)

def cache_clear() -> bool:
    """모든 캐시 삭제"""
    return cache.clear()

def cache_exists(key: str) -> bool:
    """캐시 키 존재 여부 확인"""
    return cache.exists(key)

def cache_stats() -> Dict[str, Any]:
    """캐시 통계 반환"""
    return cache.get_stats()

def cache_info() -> Dict[str, Any]:
    """캐시 정보 반환"""
    return cache.get_cache_info() 