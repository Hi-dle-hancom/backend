import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Set

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """JWT 토큰 블랙리스트 관리 서비스"""

    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True
            )
            # Redis 연결 테스트
            self.redis_client.ping()
            self.use_redis = True
        except Exception:
            logger.warning("Redis 연결 실패, 로컬 메모리 사용")
            self.use_redis = False
            self.memory_blacklist: Set[str] = set()

    async def add_to_blacklist(self, token: str, reason: str = "logout"):
        """토큰을 블랙리스트에 추가"""
        blacklist_data = {
            "token": token,
            "reason": reason,
            "blacklisted_at": datetime.utcnow().isoformat(),
        }

        if self.redis_client:
            # Redis에 저장 (토큰 만료시간까지)
            self.redis_client.setex(
                f"blacklist:{token}",
                timedelta(days=30),  # 최대 30일
                json.dumps(blacklist_data),
            )
        else:
            # 로컬 메모리에 저장
            self.memory_blacklist.add(token)

    async def is_blacklisted(self, token: str) -> bool:
        """토큰이 블랙리스트에 있는지 확인"""
        if self.redis_client:
            return self.redis_client.exists(f"blacklist:{token}")
        else:
            return token in self.memory_blacklist

    async def revoke_user_tokens(self, user_id: str):
        """특정 사용자의 모든 토큰 무효화"""
        # 사용자별 토큰 버전 관리
        if self.redis_client:
            current_version = self.redis_client.get(
                f"user_token_version:{user_id}")
            new_version = int(current_version or 0) + 1
            self.redis_client.set(f"user_token_version:{user_id}", new_version)

    async def check_token_version(self, user_id: str, token_version: int) -> bool:
        """토큰 버전이 유효한지 확인"""
        if self.redis_client:
            current_version = self.redis_client.get(
                f"user_token_version:{user_id}")
            return int(current_version or 0) <= token_version
        return True


# 싱글톤 인스턴스
token_blacklist_service = TokenBlacklistService()
