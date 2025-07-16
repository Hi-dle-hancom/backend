import asyncio
import asyncpg
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

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
from app.core.config import settings

# 로깅 설정
logger = logging.getLogger(__name__)


class DatabaseHistoryService:
    """PostgreSQL DB 기반 히스토리 관리 서비스"""

    def __init__(self):
        self.db_url = os.getenv("DB_MODULE_URL", "postgresql://postgres:password@localhost:5432/hapa_db")
        self.pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """데이터베이스 연결 풀 획득"""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    self.db_url,
                    min_size=2,
                    max_size=10,
                    timeout=30,
                    command_timeout=60
                )
                logger.info("✅ PostgreSQL 히스토리 서비스 연결 완료")
            except Exception as e:
                logger.error(f"❌ PostgreSQL 연결 실패: {e}")
                raise
        return self.pool

    async def create_session(
            self, request: SessionCreateRequest, user_id: int) -> ConversationSession:
        """새 세션 생성 (사용자별)"""
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        current_time = datetime.now()

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            try:
                # 세션 DB 저장
                query = """
                    INSERT INTO conversation_sessions 
                    (session_id, user_id, session_title, status, primary_language, tags, project_name,
                     created_at, updated_at, last_activity)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING *
                """
                
                session_title = request.session_title or f"Session {session_id[:8]}"
                tags_array = request.tags or []
                
                record = await connection.fetchrow(
                    query,
                    session_id,
                    user_id,
                    session_title,
                    ConversationStatus.ACTIVE.value,
                    request.primary_language or "python",
                    tags_array,
                    request.project_name,
                    current_time,
                    current_time,
                    current_time
                )

                session = ConversationSession(
                    session_id=record['session_id'],
                    session_title=record['session_title'],
                    status=ConversationStatus(record['status']),
                    primary_language=record['primary_language'],
                    tags=record['tags'] or [],
                    project_name=record['project_name'],
                    created_at=record['created_at'],
                    updated_at=record['updated_at'],
                    last_activity=record['last_activity'],
                )

                logger.info(f"✅ 새 세션 생성: {session_id} (사용자: {user_id})")
                return session

            except Exception as e:
                logger.error(f"❌ 세션 생성 실패: {e}")
                raise

    async def add_entry(self, request: HistoryCreateRequest, user_id: int) -> HistoryResponse:
        """히스토리 엔트리 추가 (사용자별)"""
        entry_id = f"entry_{uuid.uuid4().hex[:8]}"
        current_time = datetime.now()

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                try:
                    # 세션 존재 및 소유권 확인
                    session_check = await connection.fetchrow(
                        "SELECT id FROM conversation_sessions WHERE session_id = $1 AND user_id = $2",
                        request.session_id, user_id
                    )
                    
                    if not session_check:
                        raise ValueError(f"세션을 찾을 수 없거나 접근 권한이 없습니다: {request.session_id}")

                    # 엔트리 저장
                    entry_query = """
                        INSERT INTO conversation_entries 
                        (entry_id, session_id, user_id, conversation_type, content, language,
                         code_snippet, file_name, line_number, response_time, confidence_score, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """
                    
                    await connection.execute(
                        entry_query,
                        entry_id,
                        request.session_id,
                        user_id,
                        request.conversation_type.value,
                        request.content,
                        request.language,
                        request.code_snippet,
                        request.file_name,
                        request.line_number,
                        request.response_time,
                        request.confidence_score,
                        current_time
                    )

                    # 세션 통계 업데이트
                    await self._update_session_stats(connection, request.session_id, user_id)

                    logger.info(f"✅ 히스토리 엔트리 추가: {entry_id} (사용자: {user_id})")
                    
                    return HistoryResponse(
                        success=True,
                        entry_id=entry_id,
                        session_id=request.session_id,
                        message="히스토리 엔트리가 추가되었습니다.",
                        timestamp=current_time,
                    )

                except Exception as e:
                    logger.error(f"❌ 히스토리 엔트리 추가 실패: {e}")
                    raise

    async def get_session_history(
        self, session_id: str, limit: int = 50, user_id: int = None
    ) -> List[Dict[str, Any]]:
        """세션별 히스토리 조회 (사용자별)"""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            try:
                query = """
                    SELECT * FROM conversation_entries 
                    WHERE session_id = $1 AND user_id = $2
                    ORDER BY created_at DESC 
                    LIMIT $3
                """
                
                records = await connection.fetch(query, session_id, user_id, limit)
                
                result = []
                for record in records:
                    entry_dict = dict(record)
                    # datetime 객체를 ISO 문자열로 변환
                    if entry_dict.get('created_at'):
                        entry_dict['timestamp'] = entry_dict['created_at'].isoformat()
                    result.append(entry_dict)
                
                logger.info(f"✅ 세션 히스토리 조회: {len(result)}개 (세션: {session_id}, 사용자: {user_id})")
                return result

            except Exception as e:
                logger.error(f"❌ 세션 히스토리 조회 실패: {e}")
                return []

    async def get_recent_sessions(self, limit: int = 20, user_id: int = None) -> List[Dict[str, Any]]:
        """최근 세션 조회 (사용자별)"""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            try:
                query = """
                    SELECT * FROM conversation_sessions 
                    WHERE user_id = $1
                    ORDER BY last_activity DESC 
                    LIMIT $2
                """
                
                records = await connection.fetch(query, user_id, limit)
                
                result = []
                for record in records:
                    session_dict = dict(record)
                    # datetime 객체를 ISO 문자열로 변환
                    for field in ['created_at', 'updated_at', 'last_activity']:
                        if session_dict.get(field):
                            session_dict[field] = session_dict[field].isoformat()
                    result.append(session_dict)
                
                logger.info(f"✅ 최근 세션 조회: {len(result)}개 (사용자: {user_id})")
                return result

            except Exception as e:
                logger.error(f"❌ 최근 세션 조회 실패: {e}")
                return []

    async def search_history(
            self, request: HistorySearchRequest, user_id: int = None) -> List[Dict[str, Any]]:
        """히스토리 검색 (사용자별)"""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            try:
                # 기본 쿼리
                query = """
                    SELECT e.*, s.session_title 
                    FROM conversation_entries e 
                    JOIN conversation_sessions s ON e.session_id = s.session_id
                    WHERE e.user_id = $1 AND e.content ILIKE $2
                """
                params = [user_id, f"%{request.query}%"]
                param_count = 2

                # 추가 필터 조건들
                if request.session_ids:
                    param_count += 1
                    query += f" AND e.session_id = ANY(${param_count})"
                    params.append(request.session_ids)

                if request.language:
                    param_count += 1
                    query += f" AND e.language = ${param_count}"
                    params.append(request.language)

                if request.conversation_type:
                    param_count += 1
                    query += f" AND e.conversation_type = ${param_count}"
                    params.append(request.conversation_type.value)

                if request.date_from:
                    param_count += 1
                    query += f" AND e.created_at >= ${param_count}"
                    params.append(request.date_from)

                if request.date_to:
                    param_count += 1
                    query += f" AND e.created_at <= ${param_count}"
                    params.append(request.date_to)

                query += f" ORDER BY e.created_at DESC LIMIT ${param_count + 1}"
                params.append(request.limit)

                records = await connection.fetch(query, *params)
                
                result = []
                for record in records:
                    entry_dict = dict(record)
                    if entry_dict.get('created_at'):
                        entry_dict['timestamp'] = entry_dict['created_at'].isoformat()
                    result.append(entry_dict)
                
                logger.info(f"✅ 히스토리 검색: {len(result)}개 결과 (사용자: {user_id})")
                return result

            except Exception as e:
                logger.error(f"❌ 히스토리 검색 실패: {e}")
                return []

    async def get_stats(self, user_id: int = None) -> HistoryStats:
        """히스토리 통계 조회 (사용자별)"""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            try:
                # 기본 통계
                session_stats = await connection.fetchrow(
                    "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status = 'active') as active FROM conversation_sessions WHERE user_id = $1",
                    user_id
                )
                
                entry_stats = await connection.fetchrow(
                    "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE conversation_type = 'question') as questions, COUNT(*) FILTER (WHERE conversation_type = 'answer') as answers FROM conversation_entries WHERE user_id = $1",
                    user_id
                )

                # 언어별 분포
                lang_records = await connection.fetch(
                    "SELECT primary_language, COUNT(*) as count FROM conversation_sessions WHERE user_id = $1 GROUP BY primary_language",
                    user_id
                )
                language_dist = {record['primary_language']: record['count'] for record in lang_records}

                # 날짜별 통계
                today = datetime.now().date()
                week_ago = today - timedelta(days=7)

                daily_stats = await connection.fetchrow(
                    "SELECT COUNT(*) as today, COUNT(*) FILTER (WHERE created_at::date >= $2) as week FROM conversation_sessions WHERE user_id = $1 AND created_at::date = $2",
                    user_id, today
                )

                weekly_stats = await connection.fetchval(
                    "SELECT COUNT(*) FROM conversation_sessions WHERE user_id = $1 AND created_at::date >= $2",
                    user_id, week_ago
                )

                # 평균 세션 길이
                total_sessions = session_stats['total']
                total_entries = entry_stats['total']
                avg_length = total_entries / total_sessions if total_sessions > 0 else 0

                return HistoryStats(
                    total_sessions=total_sessions,
                    active_sessions=session_stats['active'],
                    total_entries=total_entries,
                    total_questions=entry_stats['questions'],
                    total_answers=entry_stats['answers'],
                    language_distribution=language_dist,
                    sessions_today=daily_stats['today'] if daily_stats else 0,
                    sessions_this_week=weekly_stats if weekly_stats else 0,
                    average_session_length=round(avg_length, 2),
                )

            except Exception as e:
                logger.error(f"❌ 히스토리 통계 조회 실패: {e}")
                return HistoryStats()

    async def delete_session(self, session_id: str, user_id: int = None) -> bool:
        """세션 삭제 (사용자별)"""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                try:
                    # 세션 소유권 확인 후 삭제
                    result = await connection.execute(
                        "DELETE FROM conversation_sessions WHERE session_id = $1 AND user_id = $2",
                        session_id, user_id
                    )
                    
                    deleted = result.split()[-1] == "1"  # "DELETE 1" -> True
                    
                    if deleted:
                        logger.info(f"✅ 세션 삭제: {session_id} (사용자: {user_id})")
                    else:
                        logger.warning(f"⚠️ 세션 삭제 실패: {session_id} (사용자: {user_id})")
                    
                    return deleted

                except Exception as e:
                    logger.error(f"❌ 세션 삭제 실패: {e}")
                    return False

    async def get_health_stats(self) -> Dict[str, Any]:
        """헬스체크용 익명 통계"""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            try:
                total_sessions = await connection.fetchval("SELECT COUNT(*) FROM conversation_sessions")
                total_entries = await connection.fetchval("SELECT COUNT(*) FROM conversation_entries")
                
                return {
                    "total_sessions": total_sessions,
                    "total_entries": total_entries,
                    "service_status": "healthy"
                }
            except Exception as e:
                logger.error(f"❌ 헬스체크 통계 조회 실패: {e}")
                return {"service_status": "unhealthy", "error": str(e)}

    async def _update_session_stats(self, connection, session_id: str, user_id: int):
        """세션 통계 업데이트"""
        try:
            stats = await connection.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_entries,
                    COUNT(*) FILTER (WHERE conversation_type = 'question') as question_count,
                    COUNT(*) FILTER (WHERE conversation_type = 'answer') as answer_count
                FROM conversation_entries 
                WHERE session_id = $1 AND user_id = $2
                """,
                session_id, user_id
            )
            
            await connection.execute(
                """
                UPDATE conversation_sessions 
                SET total_entries = $1, question_count = $2, answer_count = $3, 
                    updated_at = $4, last_activity = $4
                WHERE session_id = $5 AND user_id = $6
                """,
                stats['total_entries'],
                stats['question_count'], 
                stats['answer_count'],
                datetime.now(),
                session_id,
                user_id
            )
        except Exception as e:
            logger.error(f"❌ 세션 통계 업데이트 실패: {e}")


class SettingsService:
    """설정 관리 서비스 (기존 JSON 파일 방식 유지)"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = f"{settings.get_absolute_data_dir}/settings"
        self.data_dir = data_dir
        self.settings_file = os.path.join(data_dir, "user_settings.json")
        self._ensure_data_directory()

    def _ensure_data_directory(self):
        """데이터 디렉토리 확인 및 생성"""
        os.makedirs(self.data_dir, exist_ok=True)

        if not os.path.exists(self.settings_file):
            default_settings = {
                "ai_model": "gpt-3.5-turbo",
                "response_length": "medium",
                "default_language": "python",
                "auto_save": True,
                "dark_mode": False,
                "code_completion": True,
                "max_history": 100,
                "notification_enabled": True,
            }
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)

    def get_user_settings(self, user_id: int = None) -> Dict[str, Any]:
        """사용자별 설정 조회"""
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            # 사용자별 설정 지원하려면 DB 연동 필요 (향후 개선)
            return settings
        except BaseException:
            return {}

    def update_user_settings(self, settings: Dict[str, Any], user_id: int = None) -> bool:
        """사용자별 설정 업데이트"""
        try:
            current_settings = self.get_user_settings(user_id)
            current_settings.update(settings)
            current_settings["updated_at"] = datetime.now().isoformat()

            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(current_settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"❌ 설정 업데이트 실패: {e}")
            return False

    def reset_user_settings(self, user_id: int = None) -> bool:
        """사용자별 설정 초기화"""
        try:
            default_settings = {
                "ai_model": "gpt-3.5-turbo",
                "response_length": "medium",
                "default_language": "python",
                "auto_save": True,
                "dark_mode": False,
                "code_completion": True,
                "max_history": 100,
                "notification_enabled": True,
                "reset_at": datetime.now().isoformat(),
            }
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"❌ 설정 초기화 실패: {e}")
            return False


# 전역 서비스 인스턴스 (PostgreSQL 기반)
history_service = DatabaseHistoryService()
settings_service = SettingsService()
