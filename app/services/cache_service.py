import hashlib
import json
import logging
import os
import pickle
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union

import psutil

from app.core.config import settings

logger = logging.getLogger(__name__)


class PersistentCache:
    """메모리 제한 및 고급 TTL 정책을 가진 영속적 캐시 시스템"""

    def __init__(
            self,
            cache_dir: str = None,
            max_memory_mb: int = 200):
        # 통일된 데이터 경로 사용
        if cache_dir is None:
            cache_dir = f"{settings.get_absolute_data_dir}/cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 메타데이터 파일 경로 설정
        self.metadata_file = self.cache_dir / "metadata.json"

        # 메모리 제한 설정
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_cache_size = 2000  # 최대 엔트리 수

        # TTL 정책 설정
        self.ttl_policies = {
            "short": 300,  # 5분 - 자주 변경되는 데이터
            "medium": 1800,  # 30분 - 일반적인 데이터
            "long": 7200,  # 2시간 - 안정적인 데이터
            "extended": 86400,  # 24시간 - 거의 변경되지 않는 데이터
        }
        self.default_ttl = self.ttl_policies["medium"]

        # 메타데이터 로드
        self.metadata = self._load_metadata()
        
        # 메타데이터 구조 검증 및 보정
        self._validate_metadata()

        # 초기화 시 정리 작업 수행
        try:
            self._cleanup_expired()
            self._enforce_memory_limit()
        except Exception as e:
            logger.warning(f"캐시 초기화 정리 작업 실패: {e}")

        logger.info(
            f"PersistentCache 초기화 완료 - 디렉토리: {self.cache_dir}, 메모리 제한: {max_memory_mb}MB"
        )

    def _load_metadata(self) -> Dict[str, Any]:
        """캐시 메타데이터 로드"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"캐시 메타데이터 로드 실패: {e}")

        return {
            "entries": {},
            "stats": {
                "hits": 0,
                "misses": 0,
                "total_entries": 0,
                "last_cleanup": time.time(),
            },
        }

    def _validate_metadata(self):
        """메타데이터 구조 검증 및 보정"""
        try:
            # 필수 키 확인 및 추가
            if "entries" not in self.metadata:
                self.metadata["entries"] = {}
                logger.warning("메타데이터에 'entries' 키 추가")
            
            if "stats" not in self.metadata:
                self.metadata["stats"] = {
                    "hits": 0,
                    "misses": 0,
                    "total_entries": 0,
                    "last_cleanup": time.time(),
                }
                logger.warning("메타데이터에 'stats' 키 추가")
            
            # stats 하위 키 확인
            required_stats_keys = ["hits", "misses", "total_entries", "last_cleanup"]
            for key in required_stats_keys:
                if key not in self.metadata["stats"]:
                    self.metadata["stats"][key] = 0 if key != "last_cleanup" else time.time()
                    logger.warning(f"메타데이터 stats에 '{key}' 키 추가")
            
            # 메타데이터 저장
            self._save_metadata()
            logger.debug("메타데이터 구조 검증 완료")
            
        except Exception as e:
            logger.error(f"메타데이터 검증 실패: {e}")
            # 완전히 새로운 메타데이터 생성
            self.metadata = self._load_metadata()

    def _save_metadata(self):
        """캐시 메타데이터 저장"""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"캐시 메타데이터 저장 실패: {e}")

    def _generate_key_hash(self, key: str) -> str:
        """키를 안전한 파일명으로 변환 (보안 강화: SHA-256 + Salt)"""
        salt = "hapa_cache_salt_2024"
        return hashlib.sha256(f"{salt}:{key}".encode("utf-8")).hexdigest()

    def _get_cache_file_path(self, key: str) -> Path:
        """캐시 파일 경로 생성"""
        key_hash = self._generate_key_hash(key)
        return self.cache_dir / f"{key_hash}.cache"

    def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[int] = None,
            policy: str = "medium") -> bool:
        """캐시에 값 저장 (향상된 TTL 정책 및 메모리 제한 적용)"""
        try:
            # TTL 정책 적용
            if ttl is None:
                ttl = self.ttl_policies.get(policy, self.default_ttl)

            # 메모리 제한 사전 체크
            if not self._check_memory_before_add(value):
                logger.warning(f"메모리 부족으로 캐시 저장 실패: {key}")
                return False

            key_hash = self._generate_key_hash(key)
            cache_file = self._get_cache_file_path(key)
            expires_at = time.time() + ttl

            # 값 크기 계산
            serialized_value = pickle.dumps(value)
            value_size = len(serialized_value)

            cache_data = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "access_count": 0,
                "size": value_size,
                "ttl_policy": policy,
                "key": key,
            }

            # 파일에 저장
            with open(cache_file, "wb") as f:
                pickle.dump(cache_data, f)

            # 메타데이터 업데이트
            self.metadata["entries"][key_hash] = {
                "key": key,
                "file_path": str(cache_file),
                "expires_at": expires_at,
                "created_at": cache_data["created_at"],
                "size": value_size,
                "ttl_policy": policy,
            }

            self.metadata["stats"]["total_entries"] = len(
                self.metadata["entries"])
            self._save_metadata()

            # 메모리 제한 적용
            self._enforce_memory_limit()

            logger.debug(f"캐시 저장 완료: {key} (TTL: {ttl}초, Policy: {policy}, Size: {value_size} bytes)")
            return True

        except Exception as e:
            logger.error(f"캐시 저장 실패: {key} - {e}")
            return False

    def _check_memory_before_add(self, value: Any) -> bool:
        """메모리 추가 전 용량 확인"""
        try:
            value_size = len(pickle.dumps(value))
            current_memory = self._calculate_total_memory()

            # 여유 공간이 충분한지 확인 (90% 임계값)
            if current_memory + value_size > self.max_memory_bytes * 0.9:
                # 메모리 확보를 위해 LRU 정리 시도
                self._cleanup_lru(target_free_bytes=value_size * 2)

                # 다시 확인
                current_memory = self._calculate_total_memory()
                if current_memory + value_size > self.max_memory_bytes:
                    return False

            return True
        except Exception as e:
            logger.error(f"메모리 확인 오류: {e}")
            return False

    def _calculate_total_memory(self) -> int:
        """현재 캐시가 사용하는 총 메모리 계산"""
        total_size = sum(
            entry.get("size", 0) for entry in self.metadata["entries"].values()
        )
        return total_size

    def _enforce_memory_limit(self):
        """메모리 제한 적용 (LRU 기반 정리)"""
        try:
            current_memory = self._calculate_total_memory()

            if current_memory > self.max_memory_bytes:
                target_memory = int(self.max_memory_bytes * 0.8)  # 80%까지 줄이기
                bytes_to_free = current_memory - target_memory

                # 메모리 사용량 MB 계산
                current_memory_mb = current_memory / 1024 / 1024
                bytes_to_free_mb = bytes_to_free / 1024 / 1024

                logger.warning(f"메모리 제한 초과 ({current_memory_mb:.2f}MB), {bytes_to_free_mb:.2f}MB 정리 중...")
                self._cleanup_lru(bytes_to_free)

        except Exception as e:
            logger.error(f"메모리 제한 적용 실패: {e}")

    def _cleanup_lru(self, target_free_bytes: int):
        """LRU 기반 캐시 정리"""
        try:
            # 접근 시간 기준으로 정렬 (오래된 것부터)
            entries = list(self.metadata["entries"].items())
            entries.sort(key=lambda x: x[1].get("created_at", 0))

            freed_bytes = 0
            removed_count = 0

            for key_hash, entry in entries:
                if freed_bytes >= target_free_bytes:
                    break

                try:
                    freed_bytes += entry.get("size", 0)
                    self.delete(entry["key"])
                    removed_count += 1
                except Exception as e:
                    logger.error(f"LRU 정리 중 삭제 실패: {entry['key']} - {e}")

            if removed_count > 0:
                freed_mb = freed_bytes / 1024 / 1024
                logger.info(f"LRU 정리 완료: {removed_count}개 항목, {freed_mb:.2f}MB 확보")

        except Exception as e:
            logger.error(f"LRU 정리 실패: {e}")

    def get_advanced_stats(self) -> Dict[str, Any]:
        """고급 캐시 통계 정보 반환"""
        basic_stats = self.get_stats()

        # TTL 정책별 통계
        policy_stats = {}
        for policy in self.ttl_policies.keys():
            policy_entries = [
                entry
                for entry in self.metadata["entries"].values()
                if entry.get("ttl_policy") == policy
            ]
            policy_stats[policy] = {
                "count": len(policy_entries),
                "total_size_mb": sum(e.get("size", 0) for e in policy_entries)
                / 1024
                / 1024,
            }

        # 메모리 사용률
        current_memory = self._calculate_total_memory()
        memory_usage_percent = (current_memory / self.max_memory_bytes) * 100

        return {
            **basic_stats,
            "memory_management": {
                "current_memory_mb": current_memory /
                1024 /
                1024,
                "max_memory_mb": self.max_memory_bytes /
                1024 /
                1024,
                "memory_usage_percent": memory_usage_percent,
                "memory_status": "HIGH" if memory_usage_percent > 80 else "NORMAL",
            },
            "ttl_policies": self.ttl_policies,
            "policy_statistics": policy_stats,
        }

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
            with open(cache_file, "rb") as f:
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

            with open(cache_file, "wb") as f:
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
                self.metadata["stats"]["total_entries"] = len(
                    self.metadata["entries"])
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
            with open(cache_file, "rb") as f:
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
                    "last_cleanup": time.time(),
                },
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
                "cache_dir": str(self.cache_dir),
            },
            "entries": len(self.metadata["entries"]),
        }


class AdvancedCacheMonitor:
    """고급 캐시 모니터링 및 알림 시스템"""

    def __init__(self, cache_instance):
        self.cache = cache_instance
        self.monitoring_enabled = True
        self.alert_thresholds = {
            "memory_usage_mb": 500,  # 500MB 초과 시 알림
            "hit_rate_threshold": 0.6,  # 히트율 60% 미만 시 알림
            "max_entries": 2000,  # 엔트리 2000개 초과 시 알림
        }
        self.alert_history = []
        self.monitoring_thread = None
        self._start_monitoring()

    def _start_monitoring(self):
        """백그라운드 모니터링 스레드 시작"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self.monitoring_thread.start()
            logger.info("캐시 모니터링 스레드 시작됨")

    def _monitor_loop(self):
        """모니터링 루프 (30초 간격)"""
        while self.monitoring_enabled:
            try:
                self._check_performance()
                time.sleep(30)
            except Exception as e:
                logger.error(f"캐시 모니터링 오류: {e}")
                time.sleep(60)  # 오류 시 1분 대기

    def _check_performance(self):
        """성능 지표 확인 및 알림"""
        try:
            stats = self.cache.get_stats()
        except Exception as e:
            logger.error(f"캐시 통계 조회 실패: {e}")
            # 안전한 기본 stats로 fallback
            stats = {
                "hits": 0,
                "misses": 0,
                "total_entries": 0,
                "hit_rate": 0.0,
                "total_size_mb": 0.0
            }

        # 메모리 사용량 확인 (안전한 접근)
        memory_mb = stats.get("total_size_mb", 0)
        if memory_mb > self.alert_thresholds["memory_usage_mb"]:
            threshold_mb = self.alert_thresholds['memory_usage_mb']
            self._send_alert(
                "HIGH_MEMORY_USAGE", f"캐시 메모리 사용량이 {memory_mb:.2f}MB를 초과했습니다 (임계값: {threshold_mb}MB)")

        # 히트율 확인 (안전한 접근)
        hit_rate = stats.get("hit_rate", 0)
        if hit_rate < self.alert_thresholds["hit_rate_threshold"]:
            threshold_rate = self.alert_thresholds['hit_rate_threshold']
            self._send_alert(
                "LOW_HIT_RATE", f"캐시 히트율이 {hit_rate:.2%}로 낮습니다 (임계값: {threshold_rate:.2%})")

        # 엔트리 수 확인 (안전한 접근)
        entry_count = stats.get("total_entries", 0)
        if entry_count > self.alert_thresholds["max_entries"]:
            max_entries = self.alert_thresholds['max_entries']
            self._send_alert(
                "HIGH_ENTRY_COUNT", f"캐시 엔트리 수가 {entry_count}개를 초과했습니다 (임계값: {max_entries}개)")

        # 시스템 메모리 확인
        try:
            system_memory = psutil.virtual_memory()
            if system_memory.percent > 85:
                self._send_alert(
                    "HIGH_SYSTEM_MEMORY",
                    f"시스템 메모리 사용률이 {system_memory.percent:.1f}%입니다",
                )
        except Exception as e:
            logger.warning(f"시스템 메모리 확인 실패: {e}")

    def _send_alert(self, alert_type: str, message: str):
        """알림 발송 (로그 및 히스토리 저장)"""
        alert = {
            "timestamp": datetime.now(),
            "type": alert_type,
            "message": message}

        # 중복 알림 방지 (10분 내 동일 타입 알림 무시)
        recent_alerts = [
            a
            for a in self.alert_history
            if a["type"] == alert_type
            and (datetime.now() - a["timestamp"]) < timedelta(minutes=10)
        ]

        if not recent_alerts:
            logger.warning(f"🚨 [CACHE ALERT] {message}")
            self.alert_history.append(alert)

            # 히스토리 크기 제한 (최근 100개만 유지)
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]

    def get_monitoring_status(self) -> Dict[str, Any]:
        """모니터링 상태 반환"""
        return {
            "monitoring_enabled": self.monitoring_enabled,
            "alert_thresholds": self.alert_thresholds,
            "recent_alerts": self.alert_history[-10:],  # 최근 10개 알림
            "thread_alive": (
                self.monitoring_thread.is_alive() if self.monitoring_thread else False
            ),
        }

    def update_thresholds(self, thresholds: Dict[str, Any]):
        """알림 임계값 업데이트"""
        self.alert_thresholds.update(thresholds)
        logger.info(f"캐시 모니터링 임계값 업데이트: {thresholds}")

    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_enabled = False
        logger.info("캐시 모니터링 중지됨")


# 전역 캐시 인스턴스 (PersistentCache만 제공 - hybrid_cache_service.py 사용 권장)
persistent_cache = PersistentCache()
cache_monitor = AdvancedCacheMonitor(persistent_cache)

# 편의 함수들은 제거됨 - hybrid_cache_service.py의 단일 진입점 사용
