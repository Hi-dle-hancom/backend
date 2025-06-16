import json
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from app.schemas.history import (
    ConversationEntry, ConversationSession, HistoryCreateRequest, 
    HistoryResponse, SessionCreateRequest, SessionUpdateRequest,
    HistoryStats, HistorySearchRequest, ConversationType, ConversationStatus
)

# 로깅 설정
logger = logging.getLogger(__name__)

class HistoryService:
    """히스토리 관리 서비스"""
    
    def __init__(self, data_dir: str = "data/history"):
        self.data_dir = data_dir
        self.sessions_file = os.path.join(data_dir, "sessions.json")
        self.entries_file = os.path.join(data_dir, "entries.json")
        self._ensure_data_directory()
    
    def _ensure_data_directory(self):
        """데이터 디렉토리 확인 및 생성"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        for file_path in [self.sessions_file, self.entries_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
    
    def create_session(self, request: SessionCreateRequest) -> ConversationSession:
        """새 세션 생성"""
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        current_time = datetime.now()
        
        session = ConversationSession(
            session_id=session_id,
            session_title=request.session_title or f"Session {session_id[:8]}",
            status=ConversationStatus.ACTIVE,
            primary_language=request.primary_language,
            tags=request.tags or [],
            project_name=request.project_name,
            created_at=current_time,
            updated_at=current_time,
            last_activity=current_time
        )
        
        # 세션 저장
        sessions = self._load_sessions()
        sessions.append(session.dict())
        self._save_sessions(sessions)
        
        logger.info(f"새 세션 생성: {session_id}")
        return session
    
    def add_entry(self, request: HistoryCreateRequest) -> HistoryResponse:
        """히스토리 엔트리 추가"""
        entry_id = f"entry_{uuid.uuid4().hex[:8]}"
        current_time = datetime.now()
        
        entry = ConversationEntry(
            entry_id=entry_id,
            session_id=request.session_id,
            conversation_type=request.conversation_type,
            content=request.content,
            language=request.language,
            code_snippet=request.code_snippet,
            file_name=request.file_name,
            line_number=request.line_number,
            response_time=request.response_time,
            confidence_score=request.confidence_score,
            timestamp=current_time
        )
        
        # 엔트리 저장
        entries = self._load_entries()
        entries.append(entry.dict())
        self._save_entries(entries)
        
        # 세션 통계 업데이트
        self._update_session_stats(request.session_id)
        
        return HistoryResponse(
            success=True,
            entry_id=entry_id,
            session_id=request.session_id,
            message="히스토리 엔트리가 추가되었습니다.",
            timestamp=current_time
        )
    
    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """세션별 히스토리 조회"""
        entries = self._load_entries()
        session_entries = [e for e in entries if e.get("session_id") == session_id]
        session_entries.sort(key=lambda x: x.get("timestamp", ""))
        return session_entries[-limit:]
    
    def get_recent_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """최근 세션 조회"""
        sessions = self._load_sessions()
        sessions.sort(key=lambda x: x.get("last_activity", ""), reverse=True)
        return sessions[:limit]
    
    def search_history(self, request: HistorySearchRequest) -> List[Dict[str, Any]]:
        """히스토리 검색"""
        entries = self._load_entries()
        
        # 필터 적용
        filtered_entries = []
        for entry in entries:
            # 텍스트 검색
            if request.query.lower() not in entry.get("content", "").lower():
                continue
            
            # 세션 ID 필터
            if request.session_ids and entry.get("session_id") not in request.session_ids:
                continue
            
            # 언어 필터
            if request.language and entry.get("language") != request.language:
                continue
            
            # 대화 유형 필터
            if request.conversation_type and entry.get("conversation_type") != request.conversation_type.value:
                continue
            
            # 날짜 필터
            entry_date = datetime.fromisoformat(entry.get("timestamp", "").replace("Z", "+00:00"))
            if request.date_from and entry_date < request.date_from:
                continue
            if request.date_to and entry_date > request.date_to:
                continue
            
            filtered_entries.append(entry)
        
        # 최신순 정렬 및 제한
        filtered_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return filtered_entries[:request.limit]
    
    def get_stats(self) -> HistoryStats:
        """히스토리 통계 조회"""
        sessions = self._load_sessions()
        entries = self._load_entries()
        
        # 기본 통계
        total_sessions = len(sessions)
        active_sessions = sum(1 for s in sessions if s.get("status") == "active")
        total_entries = len(entries)
        total_questions = sum(1 for e in entries if e.get("conversation_type") == "question")
        total_answers = sum(1 for e in entries if e.get("conversation_type") == "answer")
        
        # 언어별 분포
        language_dist = {}
        for session in sessions:
            lang = session.get("primary_language", "unknown")
            language_dist[lang] = language_dist.get(lang, 0) + 1
        
        # 날짜별 통계
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        sessions_today = sum(1 for s in sessions 
                           if datetime.fromisoformat(s.get("created_at", "")).date() == today)
        sessions_this_week = sum(1 for s in sessions 
                               if datetime.fromisoformat(s.get("created_at", "")).date() >= week_ago)
        
        # 평균 세션 길이
        avg_length = total_entries / total_sessions if total_sessions > 0 else 0
        
        return HistoryStats(
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            total_entries=total_entries,
            total_questions=total_questions,
            total_answers=total_answers,
            language_distribution=language_dist,
            sessions_today=sessions_today,
            sessions_this_week=sessions_this_week,
            average_session_length=round(avg_length, 2)
        )
    
    def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        sessions = self._load_sessions()
        entries = self._load_entries()
        
        # 세션 삭제
        original_count = len(sessions)
        sessions = [s for s in sessions if s.get("session_id") != session_id]
        
        if len(sessions) == original_count:
            return False
        
        # 관련 엔트리 삭제
        entries = [e for e in entries if e.get("session_id") != session_id]
        
        self._save_sessions(sessions)
        self._save_entries(entries)
        
        logger.info(f"세션 삭제 완료: {session_id}")
        return True
    
    def _load_sessions(self) -> List[Dict[str, Any]]:
        """세션 데이터 로드"""
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_sessions(self, sessions: List[Dict[str, Any]]):
        """세션 데이터 저장"""
        with open(self.sessions_file, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2, default=str)
    
    def _load_entries(self) -> List[Dict[str, Any]]:
        """엔트리 데이터 로드"""
        try:
            with open(self.entries_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_entries(self, entries: List[Dict[str, Any]]):
        """엔트리 데이터 저장"""
        with open(self.entries_file, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2, default=str)
    
    def _update_session_stats(self, session_id: str):
        """세션 통계 업데이트"""
        sessions = self._load_sessions()
        entries = self._load_entries()
        
        for session in sessions:
            if session.get("session_id") == session_id:
                # 세션 엔트리 통계 계산
                session_entries = [e for e in entries if e.get("session_id") == session_id]
                session["total_entries"] = len(session_entries)
                session["question_count"] = sum(1 for e in session_entries if e.get("conversation_type") == "question")
                session["answer_count"] = sum(1 for e in session_entries if e.get("conversation_type") == "answer")
                session["updated_at"] = datetime.now().isoformat()
                session["last_activity"] = datetime.now().isoformat()
                break
        
        self._save_sessions(sessions)


class SettingsService:
    """설정 관리 서비스"""
    
    def __init__(self, data_dir: str = "data/settings"):
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
                "notification_enabled": True
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)
    
    def get_settings(self) -> Dict[str, Any]:
        """설정 조회"""
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def update_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """설정 업데이트"""
        current_settings = self.get_settings()
        current_settings.update(settings)
        current_settings["updated_at"] = datetime.now().isoformat()
        
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(current_settings, f, ensure_ascii=False, indent=2)
        
        return current_settings

# 전역 서비스 인스턴스
history_service = HistoryService()
settings_service = SettingsService() 