import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.schemas.history import (
    ConversationEntry,
    ConversationSession,
    ConversationStatus,
    ConversationType,
    HistoryCreateRequest,
    HistoryResponse,
    HistorySearchRequest,
    HistoryStats,
    SessionCreateRequest,
    SessionUpdateRequest,
)

# 로깅 설정
logger = logging.getLogger(__name__)


class DBModuleHistoryService:
    """DB-Module API 기반 히스토리 관리 서비스"""

    def __init__(self):
        # DB-Module API 설정
        self.db_module_url = os.getenv("DB_MODULE_URL", "http://localhost:8001")
        self.api_base_url = f"{self.db_module_url}/history"
        
        # HTTP 클라이언트 설정
        self.timeout = httpx.Timeout(30.0)
        
        logger.info(f"🔧 DB-Module API 설정 로드: {self.db_module_url}")
        logger.info(f"🔧 History API Base URL: {self.api_base_url}")

    def _get_auth_headers(self, user_id: int) -> Dict[str, str]:
        """JWT 토큰 기반 인증 헤더 생성"""
        try:
            # TODO: JWT 토큰 생성 로직 구현
            # 현재는 user_id만 전달
            return {
                "Content-Type": "application/json",
                "X-User-ID": str(user_id)  # 임시 인증 방식
            }
        except Exception as e:
            logger.error(f"❌ 인증 헤더 생성 실패: {e}")
            return {"Content-Type": "application/json"}

    async def _make_request(self, method: str, endpoint: str, user_id: int, **kwargs) -> Dict[str, Any]:
        """DB-Module API 요청 헬퍼"""
        url = f"{self.api_base_url}{endpoint}"
        headers = self._get_auth_headers(user_id)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ DB-Module API 요청 실패 ({method} {url}): {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ DB-Module API 연결 실패 ({method} {url}): {e}")
            raise

    async def create_session(self, request: SessionCreateRequest, user_id: int) -> ConversationSession:
        """새 세션 생성 (DB-Module API)"""
        try:
            response_data = await self._make_request(
                method="POST",
                endpoint="/sessions",
                user_id=user_id,
                json=request.dict()
            )
            
            # ConversationSession 객체로 변환
            session = ConversationSession(**response_data)
            
            logger.info(f"✅ 새 세션 생성 (DB-Module): {session.session_id} (사용자: {user_id})")
            return session

        except Exception as e:
            logger.error(f"❌ 세션 생성 실패 (DB-Module): {e}")
            raise

    async def add_entry(self, request: HistoryCreateRequest, user_id: int) -> HistoryResponse:
        """히스토리 엔트리 추가 (DB-Module API)"""
        try:
            response_data = await self._make_request(
                method="POST",
                endpoint="/entries",
                user_id=user_id,
                json=request.dict()
            )
            
            # HistoryResponse 객체로 변환
            response = HistoryResponse(**response_data)
            
            logger.info(f"✅ 히스토리 엔트리 추가 (DB-Module): {response.entry_id} (사용자: {user_id})")
            return response

        except Exception as e:
            logger.error(f"❌ 히스토리 엔트리 추가 실패 (DB-Module): {e}")
            raise

    async def get_session_history(self, session_id: str, limit: int = 50, user_id: int = None) -> List[Dict[str, Any]]:
        """세션별 히스토리 조회 (DB-Module API)"""
        try:
            response_data = await self._make_request(
                method="GET",
                endpoint=f"/sessions/{session_id}",
                user_id=user_id,
                params={"limit": limit}
            )
            
            logger.info(f"✅ 세션 히스토리 조회 (DB-Module): {len(response_data)}개 (세션: {session_id}, 사용자: {user_id})")
            return response_data

        except Exception as e:
            logger.error(f"❌ 세션 히스토리 조회 실패 (DB-Module): {e}")
            return []

    async def get_recent_sessions(self, limit: int = 20, user_id: int = None) -> List[Dict[str, Any]]:
        """최근 세션 목록 조회 (DB-Module API)"""
        try:
            response_data = await self._make_request(
                method="GET",
                endpoint="/sessions",
                user_id=user_id,
                params={"limit": limit}
            )
            
            logger.info(f"✅ 최근 세션 목록 조회 (DB-Module): {len(response_data)}개 (사용자: {user_id})")
            return response_data

        except Exception as e:
            logger.error(f"❌ 최근 세션 목록 조회 실패 (DB-Module): {e}")
            return []

    async def search_history(self, request: HistorySearchRequest, user_id: int = None) -> List[Dict[str, Any]]:
        """히스토리 검색 (DB-Module API)"""
        try:
            response_data = await self._make_request(
                method="POST",
                endpoint="/search",
                user_id=user_id,
                json=request.dict()
            )
            
            logger.info(f"✅ 히스토리 검색 (DB-Module): {len(response_data)}개 결과")
            return response_data

        except Exception as e:
            logger.error(f"❌ 히스토리 검색 실패 (DB-Module): {e}")
            return []


    async def get_stats(self, user_id: int = None) -> HistoryStats:
        """히스토리 통계 조회 (DB-Module API)"""
        try:
            response_data = await self._make_request(
                method="GET",
                endpoint="/stats",
                user_id=user_id
            )
            
            # HistoryStats 객체로 변환
            stats = HistoryStats(**response_data)
            
            logger.info(f"✅ 히스토리 통계 조회 (DB-Module): 총 {stats.total_sessions}개 세션 (사용자: {user_id})")
            return stats

        except Exception as e:
            logger.error(f"❌ 히스토리 통계 조회 실패 (DB-Module): {e}")
            return HistoryStats()

    async def delete_session(self, session_id: str, user_id: int) -> bool:
        """세션 및 관련 엔트리 삭제 (DB-Module API)"""
        try:
            response_data = await self._make_request(
                method="DELETE",
                endpoint=f"/sessions/{session_id}",
                user_id=user_id
            )
            
            success = response_data.get("success", False)
            if success:
                logger.info(f"✅ 세션 삭제 성공 (DB-Module): {session_id} (사용자: {user_id})")
            else:
                logger.warning(f"❌ 세션 삭제 실패 (DB-Module): {session_id} (사용자: {user_id})")
            
            return success
                
        except Exception as e:
            logger.error(f"❌ 세션 삭제 실패 (DB-Module): {e}")
            return False

    async def get_health_stats(self) -> Dict[str, Any]:
        """헬스 체크용 통계 (DB-Module API)"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.api_base_url}/health")
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"❌ 헬스 체크 통계 실패 (DB-Module): {e}")
            return {"total_sessions": 0, "total_entries": 0}


# 싱글톤 인스턴스 생성
history_service = DBModuleHistoryService()

# 설정 서비스는 별도 구현 필요 (기존 PostgreSQL 코드 유지하거나 별도 MongoDB 구현)
class SettingsService:
    """설정 서비스 (기존 로직 유지 또는 MongoDB 확장)"""
    
    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """사용자 설정 조회"""
        try:
            # 기본 설정 반환 (실제 구현에서는 데이터베이스에서 조회)
            default_settings = {
                "history_retention_days": 365,
                "auto_save_sessions": True,
                "search_include_code": True,
                "export_format": "json",
                "privacy_level": "standard",
                "notification_preferences": {
                    "session_created": True,
                    "session_deleted": False,
                    "stats_summary": True
                }
            }
            logger.info(f"사용자 설정 조회: {user_id}")
            return default_settings
        except Exception as e:
            logger.error(f"설정 조회 실패: {e}")
            return {}
    
    def update_user_settings(self, settings: Dict[str, Any], user_id: int) -> bool:
        """사용자 설정 업데이트 (기존 로직)"""
        try:
            # 기존 설정 업데이트 로직 유지
            logger.info(f"사용자 설정 업데이트: {user_id}, 설정: {settings}")
            return True
        except Exception as e:
            logger.error(f"설정 업데이트 실패: {e}")
            return False
    
    def reset_user_settings(self, user_id: int) -> bool:
        """사용자 설정 초기화"""
        try:
            # 설정 초기화 로직
            logger.info(f"사용자 설정 초기화: {user_id}")
            return True
        except Exception as e:
            logger.error(f"설정 초기화 실패: {e}")
            return False

# 설정 서비스 인스턴스
settings_service = SettingsService()