import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class CheckpointType(Enum):
    """체크포인트 유형"""

    INITIAL_PROMPT = "initial_prompt"  # 초기 프롬프트
    AGENT_SELECTED = "agent_selected"  # 에이전트 선택
    CODE_GENERATED = "code_generated"  # 코드 생성 완료
    CODE_MODIFIED = "code_modified"  # 코드 수정
    CODE_REFINED = "code_refined"  # 코드 개선
    USER_FEEDBACK = "user_feedback"  # 사용자 피드백
    FINAL_RESULT = "final_result"  # 최종 결과


@dataclass
class CodeSnapshot:
    """코드 스냅샷"""

    code: str
    explanation: str
    language: str = "python"
    file_path: Optional[str] = None
    line_count: int = 0
    character_count: int = 0
    complexity_score: float = 0.0

    def __post_init__(self):
        if self.code:
            self.line_count = len(self.code.split("\n"))
            self.character_count = len(self.code)
            self.complexity_score = self._calculate_complexity()

    def _calculate_complexity(self) -> float:
        """간단한 코드 복잡도 계산"""
        complexity_keywords = [
            "if",
            "elif",
            "else",
            "for",
            "while",
            "try",
            "except",
            "finally",
            "with",
            "def",
            "class",
            "lambda",
            "and",
            "or",
        ]

        score = 0.0
        lines = self.code.split("\n")

        for line in lines:
            line = line.strip().lower()
            for keyword in complexity_keywords:
                if keyword in line:
                    score += 1

        # 줄 수 대비 복잡도 정규화
        return round(score / max(len(lines), 1), 2)


@dataclass
class Checkpoint:
    """체크포인트 정보"""

    checkpoint_id: str
    session_id: str
    user_id: str
    checkpoint_type: CheckpointType
    timestamp: datetime
    title: str
    description: str
    code_snapshot: CodeSnapshot
    context: Dict[str, Any]
    parent_checkpoint_id: Optional[str] = None
    agent_info: Optional[Dict[str, Any]] = None
    user_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["checkpoint_type"] = self.checkpoint_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """딕셔너리에서 객체 생성"""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["checkpoint_type"] = CheckpointType(data["checkpoint_type"])
        data["code_snapshot"] = CodeSnapshot(**data["code_snapshot"])
        return cls(**data)


class CheckpointService:
    """체크포인트 관리 서비스"""

    def __init__(self):
        # session_id -> checkpoints
        self.checkpoints: Dict[str, List[Checkpoint]] = {}
        self.max_checkpoints_per_session = 50
        self.max_session_age_hours = 24

        # 정기적으로 오래된 세션 정리
        self._cleanup_old_sessions()

    def create_session(self, user_id: str) -> str:
        """새 세션 생성"""
        session_id = f"session_{user_id}_{uuid.uuid4().hex[:8]}"
        self.checkpoints[session_id] = []

        logger.info(f"새 체크포인트 세션 생성: {session_id}")
        return session_id

    def create_checkpoint(
        self,
        session_id: str,
        user_id: str,
        checkpoint_type: CheckpointType,
        title: str,
        description: str,
        code: str,
        explanation: str,
        context: Dict[str, Any],
        user_prompt: Optional[str] = None,
        agent_info: Optional[Dict[str, Any]] = None,
        parent_checkpoint_id: Optional[str] = None,
    ) -> str:
        """새 체크포인트 생성"""

        checkpoint_id = f"cp_{uuid.uuid4().hex[:12]}"

        # 코드 스냅샷 생성
        code_snapshot = CodeSnapshot(
            code=code,
            explanation=explanation,
            file_path=context.get("file_path"))

        # 체크포인트 생성
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            session_id=session_id,
            user_id=user_id,
            checkpoint_type=checkpoint_type,
            timestamp=datetime.now(),
            title=title,
            description=description,
            code_snapshot=code_snapshot,
            context=context,
            parent_checkpoint_id=parent_checkpoint_id,
            agent_info=agent_info,
            user_prompt=user_prompt,
        )

        # 세션에 체크포인트 추가
        if session_id not in self.checkpoints:
            self.checkpoints[session_id] = []

        self.checkpoints[session_id].append(checkpoint)

        # 최대 개수 초과 시 오래된 것 제거
        if len(self.checkpoints[session_id]
               ) > self.max_checkpoints_per_session:
            removed = self.checkpoints[session_id].pop(0)
            logger.info(f"오래된 체크포인트 제거: {removed.checkpoint_id}")

        logger.info(f"체크포인트 생성: {checkpoint_id} ({checkpoint_type.value})")
        return checkpoint_id

    def get_checkpoints(self, session_id: str) -> List[Checkpoint]:
        """세션의 모든 체크포인트 조회"""
        return self.checkpoints.get(session_id, [])

    def get_checkpoint(
        self, session_id: str, checkpoint_id: str
    ) -> Optional[Checkpoint]:
        """특정 체크포인트 조회"""
        checkpoints = self.checkpoints.get(session_id, [])
        return next(
            (cp for cp in checkpoints if cp.checkpoint_id == checkpoint_id),
            None)

    def rollback_to_checkpoint(
        self, session_id: str, checkpoint_id: str
    ) -> Optional[Checkpoint]:
        """특정 체크포인트로 롤백"""
        checkpoints = self.checkpoints.get(session_id, [])

        # 목표 체크포인트 찾기
        target_checkpoint = None
        target_index = -1

        for i, cp in enumerate(checkpoints):
            if cp.checkpoint_id == checkpoint_id:
                target_checkpoint = cp
                target_index = i
                break

        if target_checkpoint is None:
            logger.warning(f"체크포인트를 찾을 수 없음: {checkpoint_id}")
            return None

        # 롤백 후 체크포인트들 제거
        removed_checkpoints = self.checkpoints[session_id][target_index + 1:]
        self.checkpoints[session_id] = self.checkpoints[session_id][: target_index + 1]

        logger.info(
            f"체크포인트 롤백 완료: {checkpoint_id}, 제거된 체크포인트: {
                len(removed_checkpoints)}개")

        # 롤백 체크포인트 생성
        rollback_checkpoint_id = self.create_checkpoint(
            session_id=session_id,
            user_id=target_checkpoint.user_id,
            checkpoint_type=CheckpointType.CODE_MODIFIED,
            title=f"롤백: {target_checkpoint.title}",
            description=f"체크포인트 '{target_checkpoint.title}'로 롤백됨",
            code=target_checkpoint.code_snapshot.code,
            explanation=target_checkpoint.code_snapshot.explanation,
            context=target_checkpoint.context,
            parent_checkpoint_id=checkpoint_id,
        )

        return target_checkpoint

    def compare_checkpoints(
        self, session_id: str, checkpoint_id_1: str, checkpoint_id_2: str
    ) -> Dict[str, Any]:
        """두 체크포인트 비교"""
        cp1 = self.get_checkpoint(session_id, checkpoint_id_1)
        cp2 = self.get_checkpoint(session_id, checkpoint_id_2)

        if not cp1 or not cp2:
            return {"error": "체크포인트를 찾을 수 없습니다"}

        # 코드 변경 사항 분석
        code_diff = self._calculate_code_diff(
            cp1.code_snapshot.code, cp2.code_snapshot.code
        )

        comparison = {
            "checkpoint_1": {
                "id": cp1.checkpoint_id,
                "title": cp1.title,
                "timestamp": cp1.timestamp.isoformat(),
                "code_stats": {
                    "lines": cp1.code_snapshot.line_count,
                    "characters": cp1.code_snapshot.character_count,
                    "complexity": cp1.code_snapshot.complexity_score,
                },
            },
            "checkpoint_2": {
                "id": cp2.checkpoint_id,
                "title": cp2.title,
                "timestamp": cp2.timestamp.isoformat(),
                "code_stats": {
                    "lines": cp2.code_snapshot.line_count,
                    "characters": cp2.code_snapshot.character_count,
                    "complexity": cp2.code_snapshot.complexity_score,
                },
            },
            "differences": {
                "lines_changed": code_diff["lines_changed"],
                "lines_added": code_diff["lines_added"],
                "lines_removed": code_diff["lines_removed"],
                "similarity_score": code_diff["similarity_score"],
                "major_changes": code_diff["major_changes"],
            },
            "time_difference_minutes": int(
                (cp2.timestamp - cp1.timestamp).total_seconds() / 60
            ),
        }

        return comparison

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """세션 요약 정보"""
        checkpoints = self.checkpoints.get(session_id, [])

        if not checkpoints:
            return {"error": "세션을 찾을 수 없습니다"}

        # 통계 계산
        checkpoint_types = {}
        agents_used = set()
        total_code_lines = 0

        for cp in checkpoints:
            # 체크포인트 유형별 카운트
            cp_type = cp.checkpoint_type.value
            checkpoint_types[cp_type] = checkpoint_types.get(cp_type, 0) + 1

            # 사용된 에이전트
            if cp.agent_info:
                agents_used.add(cp.agent_info.get("name", "Unknown"))

            # 코드 줄 수
            total_code_lines += cp.code_snapshot.line_count

        first_checkpoint = checkpoints[0]
        last_checkpoint = checkpoints[-1]

        summary = {
            "session_id": session_id,
            "total_checkpoints": len(checkpoints),
            "checkpoint_types": checkpoint_types,
            "agents_used": list(agents_used),
            "session_duration_minutes": int(
                (last_checkpoint.timestamp - first_checkpoint.timestamp).total_seconds()
                / 60
            ),
            "total_code_lines": total_code_lines,
            "average_complexity": round(
                sum(cp.code_snapshot.complexity_score for cp in checkpoints)
                / len(checkpoints),
                2,
            ),
            "first_checkpoint": {
                "id": first_checkpoint.checkpoint_id,
                "title": first_checkpoint.title,
                "timestamp": first_checkpoint.timestamp.isoformat(),
            },
            "last_checkpoint": {
                "id": last_checkpoint.checkpoint_id,
                "title": last_checkpoint.title,
                "timestamp": last_checkpoint.timestamp.isoformat(),
            },
        }

        return summary

    def export_session(self, session_id: str) -> Dict[str, Any]:
        """세션 전체 내용 내보내기"""
        checkpoints = self.checkpoints.get(session_id, [])

        if not checkpoints:
            return {"error": "세션을 찾을 수 없습니다"}

        export_data = {
            "session_id": session_id,
            "export_timestamp": datetime.now().isoformat(),
            "checkpoints": [cp.to_dict() for cp in checkpoints],
            "summary": self.get_session_summary(session_id),
        }

        return export_data

    def _calculate_code_diff(self, code1: str, code2: str) -> Dict[str, Any]:
        """두 코드 간 차이점 계산"""
        lines1 = code1.split("\n")
        lines2 = code2.split("\n")

        # 간단한 라인 기반 diff
        lines_changed = 0
        lines_added = max(0, len(lines2) - len(lines1))
        lines_removed = max(0, len(lines1) - len(lines2))

        # 공통 줄 수 계산
        min_lines = min(len(lines1), len(lines2))
        for i in range(min_lines):
            if lines1[i].strip() != lines2[i].strip():
                lines_changed += 1

        # 유사도 계산 (Jaccard 유사도 사용)
        set1 = set(line.strip() for line in lines1 if line.strip())
        set2 = set(line.strip() for line in lines2 if line.strip())

        if not set1 and not set2:
            similarity_score = 1.0
        elif not set1 or not set2:
            similarity_score = 0.0
        else:
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            similarity_score = intersection / union

        # 주요 변경 사항 감지
        major_changes = []

        # 함수/클래스 정의 변경
        def_pattern_1 = [
            line for line in lines1 if line.strip().startswith(
                ("def ", "class "))]
        def_pattern_2 = [
            line for line in lines2 if line.strip().startswith(
                ("def ", "class "))]

        if def_pattern_1 != def_pattern_2:
            major_changes.append("함수 또는 클래스 정의 변경")

        # import 문 변경
        import_1 = [
            line for line in lines1 if line.strip().startswith(
                ("import ", "from "))]
        import_2 = [
            line for line in lines2 if line.strip().startswith(
                ("import ", "from "))]

        if import_1 != import_2:
            major_changes.append("import 문 변경")

        return {
            "lines_changed": lines_changed,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "similarity_score": round(similarity_score, 3),
            "major_changes": major_changes,
        }

    def _cleanup_old_sessions(self):
        """오래된 세션 정리"""
        current_time = datetime.now()
        cutoff_time = current_time - \
            timedelta(hours=self.max_session_age_hours)

        sessions_to_remove = []

        for session_id, checkpoints in self.checkpoints.items():
            if checkpoints and checkpoints[-1].timestamp < cutoff_time:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self.checkpoints[session_id]
            logger.info(f"오래된 세션 정리: {session_id}")

    def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        if session_id in self.checkpoints:
            del self.checkpoints[session_id]
            logger.info(f"세션 삭제: {session_id}")
            return True
        return False


# 싱글톤 인스턴스
checkpoint_service = CheckpointService()
