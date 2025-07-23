import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.settings_mapper import SettingsMapper
from app.schemas.code_generation import CodeGenerationRequest, CodeGenerationResponse
from app.services.enhanced_ai_model import enhanced_ai_service

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """사전 정의된 에이전트 역할"""

    WEB_DEVELOPER = "web_developer"
    DATA_SCIENTIST = "data_scientist"
    AUTOMATION_EXPERT = "automation_expert"
    CODE_REVIEWER = "code_reviewer"
    PERFORMANCE_OPTIMIZER = "performance_optimizer"
    SECURITY_AUDITOR = "security_auditor"
    BEGINNER_MENTOR = "beginner_mentor"
    ACADEMIC_RESEARCHER = "academic_researcher"


class CustomAgent:
    """개별 커스텀 에이전트"""
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        role: AgentRole,
        user_preferences: Dict[str, Any],
        custom_instructions: str = "",
        specialty_areas: List[str] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.user_preferences = user_preferences
        self.custom_instructions = custom_instructions
        self.specialty_areas = specialty_areas or []
        self.created_at = datetime.now()
        self.usage_count = 0
        
        # 역할별 특화 설정 적용
        self._apply_role_specialization()
    
    def _apply_role_specialization(self):
        """역할별 특화 설정 적용"""
        role_configs = {
            AgentRole.WEB_DEVELOPER: {
                "project_context": "web_development",
                "language_features": ["async_await", "type_hints", "f_strings"],
                "code_style": "detailed",
                "error_handling": "comprehensive",
                "focus_areas": ["FastAPI", "Django", "Flask", "REST API", "웹 보안"],
            },
            AgentRole.DATA_SCIENTIST: {
                "project_context": "data_science",
                "language_features": ["type_hints", "comprehensions", "f_strings"],
                "code_style": "comprehensive",
                "comment_style": "educational",
                "focus_areas": [
                    "pandas",
                    "numpy",
                    "matplotlib",
                    "scikit-learn",
                    "데이터 분석",
                ],
            },
            AgentRole.AUTOMATION_EXPERT: {
                "project_context": "automation",
                "language_features": ["context_managers", "generators", "f_strings"],
                "code_style": "detailed",
                "error_handling": "comprehensive",
                "focus_areas": ["파일 처리", "스케줄링", "시스템 자동화", "로깅"],
            },
            AgentRole.CODE_REVIEWER: {
                "project_context": "general_purpose",
                "language_features": ["type_hints", "dataclasses", "comprehensions"],
                "code_style": "comprehensive",
                "comment_style": "detailed",
                "focus_areas": ["코드 품질", "성능 최적화", "모범 사례", "리팩토링"],
            },
            AgentRole.PERFORMANCE_OPTIMIZER: {
                "project_context": "enterprise",
                "language_features": ["generators", "async_await", "type_hints"],
                "code_style": "detailed",
                "error_handling": "comprehensive",
                "focus_areas": [
                    "성능 최적화",
                    "메모리 관리",
                    "병렬 처리",
                    "프로파일링",
                ],
            },
            AgentRole.SECURITY_AUDITOR: {
                "project_context": "enterprise",
                "language_features": ["type_hints", "context_managers", "decorators"],
                "code_style": "comprehensive",
                "error_handling": "production_ready",
                "focus_areas": ["보안 취약점", "입력 검증", "암호화", "인증"],
            },
            AgentRole.BEGINNER_MENTOR: {
                "project_context": "academic",
                "language_features": ["f_strings", "comprehensions"],
                "code_style": "minimal",
                "comment_style": "educational",
                "skill_level": "beginner",
                "focus_areas": ["기초 문법", "단계별 설명", "실습 예제", "디버깅"],
            },
            AgentRole.ACADEMIC_RESEARCHER: {
                "project_context": "academic",
                "language_features": ["type_hints", "dataclasses", "generators"],
                "code_style": "comprehensive",
                "comment_style": "educational",
                "focus_areas": [
                    "알고리즘",
                    "수학적 모델링",
                    "연구 방법론",
                    "논문 작성",
                ],
            },
        }
        
        # 역할별 설정을 사용자 선호도에 덮어쓰기
        if self.role in role_configs:
            config = role_configs[self.role]
            for key, value in config.items():
                if key != "focus_areas":
                    self.user_preferences[key] = value
                else:
                    self.specialty_areas.extend(value)

    def get_specialized_prompt(self, base_prompt: str) -> str:
        """에이전트 역할에 특화된 프롬프트 생성"""
        role_prompts = {
            AgentRole.WEB_DEVELOPER: f"""
당신은 웹 개발 전문가입니다. 다음 요청을 처리할 때:
- 웹 프레임워크 모범 사례 적용 (FastAPI, Django, Flask)
- 보안, 성능, 확장성 고려
- REST API 설계 원칙 준수
- 웹 표준 및 HTTP 프로토콜 준수

요청: {base_prompt}
""",
            AgentRole.DATA_SCIENTIST: f"""
당신은 데이터 사이언스 전문가입니다. 다음 요청을 처리할 때:
- pandas, numpy, matplotlib 등 데이터 과학 라이브러리 활용
- 데이터 전처리, 분석, 시각화 모범 사례 적용
- 통계적 검증 및 해석 포함
- 재현 가능한 분석 코드 작성

요청: {base_prompt}
""",
            AgentRole.AUTOMATION_EXPERT: f"""
당신은 자동화 전문가입니다. 다음 요청을 처리할 때:
- 안정성과 에러 처리를 최우선으로 고려
- 로깅 및 모니터링 기능 포함
- 스케줄링 및 배치 처리 최적화
- 시스템 리소스 효율적 사용

요청: {base_prompt}
""",
            AgentRole.CODE_REVIEWER: f"""
당신은 코드 리뷰 전문가입니다. 다음 코드를 분석할 때:
- 코드 품질, 가독성, 유지보수성 평가
- 성능 개선점 및 최적화 제안
- 보안 취약점 및 잠재적 버그 식별
- 모범 사례 및 리팩토링 제안

분석 대상: {base_prompt}
""",
            AgentRole.PERFORMANCE_OPTIMIZER: f"""
당신은 성능 최적화 전문가입니다. 다음 요청을 처리할 때:
- 시간/공간 복잡도 최적화
- 메모리 사용량 최소화
- 병렬 처리 및 비동기 처리 활용
- 프로파일링 및 벤치마킹 코드 포함

최적화 대상: {base_prompt}
""",
            AgentRole.SECURITY_AUDITOR: f"""
당신은 보안 감사 전문가입니다. 다음 요청을 처리할 때:
- 보안 취약점 식별 및 해결
- 입력 검증 및 데이터 무결성 보장
- 암호화 및 인증 모범 사례 적용
- OWASP 가이드라인 준수

보안 검토 대상: {base_prompt}
""",
            AgentRole.BEGINNER_MENTOR: f"""
당신은 초보자를 위한 멘토입니다. 다음 요청을 처리할 때:
- 단계별로 상세하게 설명
- 기초 개념부터 차근차근 설명
- 실행 가능한 예제와 함께 제공
- 일반적인 실수와 해결 방법 포함

학습 요청: {base_prompt}
""",
            AgentRole.ACADEMIC_RESEARCHER: f"""
당신은 학술 연구자입니다. 다음 요청을 처리할 때:
- 수학적/이론적 배경 설명
- 알고리즘의 원리와 복잡도 분석
- 연구 방법론 및 실험 설계 고려
- 학술적 참고 자료 및 논문 스타일 적용

연구 과제: {base_prompt}
""",
        }
        
        return role_prompts.get(self.role, base_prompt)


class CustomAgentService:
    """커스텀 에이전트 관리 서비스"""
    
    def __init__(self):
        self.agents: Dict[str, CustomAgent] = {}
        self.settings_mapper = SettingsMapper()
        self.ai_model_manager = enhanced_ai_service
        
        # 사전 정의된 에이전트 템플릿 로드
        self._load_predefined_agents()
    
    def _load_predefined_agents(self):
        """사전 정의된 에이전트 템플릿 로드"""
        logger.info("사전 정의된 에이전트 템플릿 로드 시작")
        
        # 각 역할별로 기본 에이전트 생성
        for role in AgentRole:
            agent_id = f"default_{role.value}"
            default_preferences = self.settings_mapper.get_default_preferences()
            
            agent = CustomAgent(
                agent_id=agent_id,
                name=self._get_role_display_name(role),
                role=role,
                user_preferences=default_preferences,
                custom_instructions=self._get_role_description(role),
            )
            
            self.agents[agent_id] = agent
        
        logger.info(f"사전 정의된 에이전트 {len(self.agents)}개 로드 완료")
    
    def _get_role_display_name(self, role: AgentRole) -> str:
        """역할별 표시 이름"""
        display_names = {
            AgentRole.WEB_DEVELOPER: "웹 개발자 AI",
            AgentRole.DATA_SCIENTIST: "데이터 사이언티스트 AI",
            AgentRole.AUTOMATION_EXPERT: "자동화 전문가 AI",
            AgentRole.CODE_REVIEWER: "코드 리뷰어 AI",
            AgentRole.PERFORMANCE_OPTIMIZER: "성능 최적화 AI",
            AgentRole.SECURITY_AUDITOR: "보안 감사 AI",
            AgentRole.BEGINNER_MENTOR: "초보자 멘토 AI",
            AgentRole.ACADEMIC_RESEARCHER: "학술 연구자 AI",
        }
        return display_names.get(role, role.value)
    
    def _get_role_description(self, role: AgentRole) -> str:
        """역할별 설명"""
        descriptions = {
            AgentRole.WEB_DEVELOPER: "FastAPI, Django, Flask 등 웹 개발 전문가로 보안과 성능을 고려한 코드를 생성합니다.",
            AgentRole.DATA_SCIENTIST: "pandas, numpy, 머신러닝을 활용한 데이터 분석 및 시각화 전문가입니다.",
            AgentRole.AUTOMATION_EXPERT: "시스템 자동화, 배치 처리, 스케줄링 전문가로 안정적인 자동화 솔루션을 제공합니다.",
            AgentRole.CODE_REVIEWER: "코드 품질, 성능, 보안을 종합적으로 검토하고 개선 방안을 제시합니다.",
            AgentRole.PERFORMANCE_OPTIMIZER: "시간/공간 복잡도 최적화 및 성능 튜닝 전문가입니다.",
            AgentRole.SECURITY_AUDITOR: "보안 취약점 분석 및 보안 모범 사례 적용 전문가입니다.",
            AgentRole.BEGINNER_MENTOR: "초보자를 위한 단계별 학습 가이드와 실습 예제를 제공합니다.",
            AgentRole.ACADEMIC_RESEARCHER: "알고리즘 이론, 수학적 모델링, 연구 방법론 전문가입니다.",
        }
        return descriptions.get(role, "")
    
    async def create_custom_agent(
        self,
        user_id: str,
        name: str,
        role: AgentRole,
        access_token: Optional[str] = None,
        custom_instructions: str = "",
        specialty_areas: List[str] = None,
    ) -> CustomAgent:
        """사용자 커스텀 에이전트 생성"""
        
        # 사용자 개인화 설정 조회
        user_preferences = await self._get_user_preferences(access_token)
        
        # 고유 에이전트 ID 생성
        agent_id = f"custom_{user_id}_{str(uuid.uuid4())[:8]}"
        
        # 커스텀 에이전트 생성
        custom_agent = CustomAgent(
            agent_id=agent_id,
            name=name,
            role=role,
            user_preferences=user_preferences,
            custom_instructions=custom_instructions,
            specialty_areas=specialty_areas,
        )
        
        # 메모리에 저장
        self.agents[agent_id] = custom_agent
        
        logger.info(f"커스텀 에이전트 생성 완료: {name} ({role.value})")
        return custom_agent
    
    async def get_agent(self, agent_id: str) -> Optional[CustomAgent]:
        """에이전트 조회"""
        return self.agents.get(agent_id)
    
    async def list_agents(self, user_id: Optional[str] = None) -> List[CustomAgent]:
        """에이전트 목록 조회"""
        if user_id:
            # 사용자별 에이전트 + 사전 정의된 에이전트
            user_agents = [
                agent
                for agent in self.agents.values()
                if agent.agent_id.startswith(f"custom_{user_id}_")
                or agent.agent_id.startswith("default_")
            ]
            return user_agents
        else:
            # 모든 사전 정의된 에이전트
            return [
                agent
                for agent in self.agents.values()
                if agent.agent_id.startswith("default_")
            ]
    
    async def generate_code_with_agent(
        self, agent_id: str, prompt: str, context: Optional[str] = None
    ) -> CodeGenerationResponse:
        """특정 에이전트를 사용한 코드 생성"""
        
        agent = await self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"에이전트를 찾을 수 없습니다: {agent_id}")
        
        # 에이전트 특화 프롬프트 생성
        specialized_prompt = agent.get_specialized_prompt(prompt)
        
        # AI 모델을 통한 코드 생성 (사용자 개인화 설정 적용)
        result = await self.ai_model_manager.generate_personalized_code(
            prompt=specialized_prompt,
            context=context,
            user_preferences=agent.user_preferences,
        )
        
        # 에이전트 사용 횟수 증가
        agent.usage_count += 1
        
        # 에이전트 정보를 응답에 추가
        response = CodeGenerationResponse(
            generated_code=result.get("code", ""),
            explanation=result.get("explanation", ""),
            status="success",
        )
        
        # 에이전트 메타데이터 추가
        response.agent_info = {
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "agent_role": agent.role.value,
            "usage_count": agent.usage_count,
            "specialty_areas": agent.specialty_areas,
        }
        
        logger.info(f"에이전트 코드 생성 완료: {agent.name}")
        return response
    
    async def _get_user_preferences(
        self, access_token: Optional[str]
    ) -> Dict[str, Any]:
        """사용자 개인화 설정 조회"""
        if not access_token:
            return self.settings_mapper.get_default_preferences()
        
        try:
            from app.services.user_service import user_service

            db_settings = await user_service.get_user_settings(access_token)
            
            if db_settings:
                return self.settings_mapper.map_db_settings_to_preferences(
                    db_settings)
            else:
                return self.settings_mapper.get_default_preferences()
        
        except Exception as e:
            logger.error(f"사용자 설정 조회 실패: {e}")
            return self.settings_mapper.get_default_preferences()


# 싱글톤 인스턴스
custom_agent_service = CustomAgentService() 
