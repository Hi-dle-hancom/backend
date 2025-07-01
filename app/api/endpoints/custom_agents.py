from pydantic import BaseModel
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.logging_config import api_monitor
from app.core.security import APIKeyModel, check_permission, check_rate_limit_dependency
from app.schemas.code_generation import CodeGenerationResponse
from app.services.custom_agent_service import (
    AgentRole,
    CustomAgent,
    custom_agent_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic 스키마 정의


class AgentCreationRequest(BaseModel):
    """에이전트 생성 요청 모델"""

    name: str
    role: str  # AgentRole enum value
    custom_instructions: Optional[str] = ""
    specialty_areas: Optional[List[str]] = None


class AgentResponse(BaseModel):
    """에이전트 응답 모델"""

    agent_id: str
    name: str
    role: str
    custom_instructions: str
    specialty_areas: List[str]
    created_at: str
    usage_count: int


class AgentCodeGenerationRequest(BaseModel):
    """에이전트 코드 생성 요청 모델"""

    agent_id: str
    user_question: str
    code_context: Optional[str] = None


class AgentListResponse(BaseModel):
    """에이전트 목록 응답 모델"""

    agents: List[AgentResponse]
    total_count: int


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    request: Request,
    api_key: APIKeyModel = Depends(check_permission("agent_access")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/agents", 50)),
):
    """
    사용 가능한 AI 에이전트 목록 조회

    - 사전 정의된 에이전트들 (웹 개발자, 데이터 사이언티스트 등)
    - 사용자가 생성한 커스텀 에이전트들
    """
    try:
        client_ip = request.client.host if request.client else "unknown"

        api_monitor.logger.info(
            "에이전트 목록 조회 요청", user_id=api_key.user_id, client_ip=client_ip
        )

        # 사용자별 에이전트 목록 조회
        agents = await custom_agent_service.list_agents(user_id=api_key.user_id)

        # 응답 형식으로 변환
        agent_responses = []
        for agent in agents:
            agent_responses.append(
                AgentResponse(
                    agent_id=agent.agent_id,
                    name=agent.name,
                    role=agent.role.value,
                    custom_instructions=agent.custom_instructions,
                    specialty_areas=agent.specialty_areas,
                    created_at=agent.created_at.isoformat(),
                    usage_count=agent.usage_count,
                )
            )

        api_monitor.logger.info(
            f"에이전트 목록 조회 성공: {len(agent_responses)}개",
            user_id=api_key.user_id,
        )

        return AgentListResponse(
            agents=agent_responses, total_count=len(agent_responses)
        )

    except Exception as e:
        api_monitor.log_error(e,
                              {"endpoint": "/agents",
                               "user_id": api_key.user_id,
                               "client_ip": client_ip},
                              )
        raise HTTPException(
            status_code=500, detail="에이전트 목록 조회 중 오류가 발생했습니다"
        )


@router.post("/agents", response_model=AgentResponse)
async def create_custom_agent(
    request_data: AgentCreationRequest,
    request: Request,
    api_key: APIKeyModel = Depends(check_permission("agent_create")),
    rate_limit_check: APIKeyModel = Depends(check_rate_limit_dependency("/agents", 10)),
):
    """
    사용자 커스텀 에이전트 생성

    사용자의 개인화 설정을 기반으로 특화된 AI 에이전트를 생성합니다.
    """
    try:
        client_ip = request.client.host if request.client else "unknown"

        api_monitor.logger.info(
            f"커스텀 에이전트 생성 요청: {request_data.name}",
            user_id=api_key.user_id,
            role=request_data.role,
            client_ip=client_ip,
        )

        # 역할 유효성 검사
        try:
            agent_role = AgentRole(request_data.role)
        except ValueError:
            valid_roles = [role.value for role in AgentRole]
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 에이전트 역할입니다. 사용 가능한 역할: {valid_roles}",
            )

        # 커스텀 에이전트 생성
        agent = await custom_agent_service.create_custom_agent(
            user_id=api_key.user_id,
            name=request_data.name,
            role=agent_role,
            access_token=api_key.access_token,
            custom_instructions=request_data.custom_instructions or "",
            specialty_areas=request_data.specialty_areas,
        )

        api_monitor.logger.info(
            f"커스텀 에이전트 생성 성공: {agent.name}",
            user_id=api_key.user_id,
            agent_id=agent.agent_id,
        )

        return AgentResponse(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role.value,
            custom_instructions=agent.custom_instructions,
            specialty_areas=agent.specialty_areas,
            created_at=agent.created_at.isoformat(),
            usage_count=agent.usage_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(
            e,
            {
                "endpoint": "/agents",
                "user_id": api_key.user_id,
                "agent_name": request_data.name,
                "client_ip": client_ip,
            },
        )
        raise HTTPException(
            status_code=500, detail="커스텀 에이전트 생성 중 오류가 발생했습니다"
        )


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    request: Request,
    api_key: APIKeyModel = Depends(check_permission("agent_access")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/agents/{agent_id}", 50)
    ),
):
    """특정 에이전트 정보 조회"""
    try:
        client_ip = request.client.host if request.client else "unknown"

        api_monitor.logger.info(
            f"에이전트 정보 조회: {agent_id}",
            user_id=api_key.user_id,
            client_ip=client_ip,
        )

        agent = await custom_agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다")

        # 권한 검사 (커스텀 에이전트는 생성자만 접근 가능)
        if agent.agent_id.startswith(
            f"custom_{api_key.user_id}_"
        ) or agent.agent_id.startswith("default_"):
            pass  # 접근 허용
        else:
            raise HTTPException(
                status_code=403, detail="해당 에이전트에 접근할 권한이 없습니다"
            )

        return AgentResponse(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role.value,
            custom_instructions=agent.custom_instructions,
            specialty_areas=agent.specialty_areas,
            created_at=agent.created_at.isoformat(),
            usage_count=agent.usage_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(
            e,
            {
                "endpoint": f"/agents/{agent_id}",
                "user_id": api_key.user_id,
                "client_ip": client_ip,
            },
        )
        raise HTTPException(
            status_code=500, detail="에이전트 정보 조회 중 오류가 발생했습니다"
        )


@router.post("/agents/generate", response_model=CodeGenerationResponse)
async def generate_code_with_agent(
    request_data: AgentCodeGenerationRequest,
    request: Request,
    api_key: APIKeyModel = Depends(check_permission("code_generation")),
    rate_limit_check: APIKeyModel = Depends(
        check_rate_limit_dependency("/agents/generate", 30)
    ),
):
    """
    특정 에이전트를 사용한 코드 생성

    선택한 에이전트의 특화된 역할과 사용자 개인화 설정을 적용하여 코드를 생성합니다.
    """
    try:
        client_ip = request.client.host if request.client else "unknown"

        api_monitor.logger.info(
            f"에이전트 코드 생성 요청: {request_data.agent_id}",
            user_id=api_key.user_id,
            prompt_length=len(request_data.user_question),
            client_ip=client_ip,
        )

        # 요청 데이터 검증
        if not request_data.user_question.strip():
            raise HTTPException(status_code=400, detail="질문 내용이 비어있습니다")

        # 에이전트 권한 확인
        agent = await custom_agent_service.get_agent(request_data.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다")

        # 커스텀 에이전트 접근 권한 확인
        if agent.agent_id.startswith(
            f"custom_") and not agent.agent_id.startswith(
            f"custom_{
                api_key.user_id}_"):
            raise HTTPException(
                status_code=403, detail="해당 에이전트에 접근할 권한이 없습니다"
            )

        # AI 에이전트를 통한 코드 생성
        ai_start_time = time.time()

        response = await custom_agent_service.generate_code_with_agent(
            agent_id=request_data.agent_id,
            prompt=request_data.user_question,
            context=request_data.code_context,
        )

        ai_duration = time.time() - ai_start_time

        # 성능 메트릭 로깅
        api_monitor.log_ai_inference(
            duration=ai_duration,
            prompt_length=len(request_data.user_question),
            response_length=(
                len(response.generated_code) if response.generated_code else 0
            ),
            cached=ai_duration < 0.1,
        )

        api_monitor.logger.info(
            f"에이전트 코드 생성 성공: {
                agent.name}",
            user_id=api_key.user_id,
            agent_id=request_data.agent_id,
            ai_duration=ai_duration,
            code_length=len(
                response.generated_code) if response.generated_code else 0,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        api_monitor.log_error(
            e,
            {
                "endpoint": "/agents/generate",
                "user_id": api_key.user_id,
                "agent_id": request_data.agent_id,
                "client_ip": client_ip,
            },
        )
        raise HTTPException(
            status_code=500, detail="에이전트 코드 생성 중 오류가 발생했습니다"
        )


@router.get("/agent-roles")
async def get_available_agent_roles(
    request: Request, api_key: APIKeyModel = Depends(check_permission("agent_access"))
):
    """
    사용 가능한 에이전트 역할 목록 조회

    커스텀 에이전트 생성 시 선택할 수 있는 역할들의 목록과 설명을 제공합니다.
    """
    try:
        client_ip = request.client.host if request.client else "unknown"

        api_monitor.logger.info(
            "에이전트 역할 목록 조회", user_id=api_key.user_id, client_ip=client_ip
        )

        role_descriptions = {
            AgentRole.WEB_DEVELOPER.value: {
                "name": "웹 개발자 AI",
                "description": "FastAPI, Django, Flask 등 웹 개발 전문가로 보안과 성능을 고려한 코드를 생성합니다.",
                "specialties": ["FastAPI", "Django", "Flask", "REST API", "웹 보안"],
                "best_for": ["웹 애플리케이션 개발", "API 서버 구축", "웹 보안 구현"],
            },
            AgentRole.DATA_SCIENTIST.value: {
                "name": "데이터 사이언티스트 AI",
                "description": "pandas, numpy, 머신러닝을 활용한 데이터 분석 및 시각화 전문가입니다.",
                "specialties": [
                    "pandas",
                    "numpy",
                    "matplotlib",
                    "scikit-learn",
                    "데이터 분석",
                ],
                "best_for": ["데이터 분석", "머신러닝 모델", "데이터 시각화"],
            },
            AgentRole.AUTOMATION_EXPERT.value: {
                "name": "자동화 전문가 AI",
                "description": "시스템 자동화, 배치 처리, 스케줄링 전문가로 안정적인 자동화 솔루션을 제공합니다.",
                "specialties": ["파일 처리", "스케줄링", "시스템 자동화", "로깅"],
                "best_for": ["업무 자동화", "배치 처리", "시스템 관리"],
            },
            AgentRole.CODE_REVIEWER.value: {
                "name": "코드 리뷰어 AI",
                "description": "코드 품질, 성능, 보안을 종합적으로 검토하고 개선 방안을 제시합니다.",
                "specialties": ["코드 품질", "성능 최적화", "모범 사례", "리팩토링"],
                "best_for": ["코드 품질 향상", "성능 분석", "리팩토링"],
            },
            AgentRole.PERFORMANCE_OPTIMIZER.value: {
                "name": "성능 최적화 AI",
                "description": "시간/공간 복잡도 최적화 및 성능 튜닝 전문가입니다.",
                "specialties": [
                    "성능 최적화",
                    "메모리 관리",
                    "병렬 처리",
                    "프로파일링",
                ],
                "best_for": ["성능 최적화", "대용량 데이터 처리", "메모리 효율화"],
            },
            AgentRole.SECURITY_AUDITOR.value: {
                "name": "보안 감사 AI",
                "description": "보안 취약점 분석 및 보안 모범 사례 적용 전문가입니다.",
                "specialties": ["보안 취약점", "입력 검증", "암호화", "인증"],
                "best_for": ["보안 감사", "취약점 분석", "보안 코드 작성"],
            },
            AgentRole.BEGINNER_MENTOR.value: {
                "name": "초보자 멘토 AI",
                "description": "초보자를 위한 단계별 학습 가이드와 실습 예제를 제공합니다.",
                "specialties": ["기초 문법", "단계별 설명", "실습 예제", "디버깅"],
                "best_for": ["Python 학습", "기초 프로그래밍", "튜토리얼"],
            },
            AgentRole.ACADEMIC_RESEARCHER.value: {
                "name": "학술 연구자 AI",
                "description": "알고리즘 이론, 수학적 모델링, 연구 방법론 전문가입니다.",
                "specialties": [
                    "알고리즘",
                    "수학적 모델링",
                    "연구 방법론",
                    "논문 작성",
                ],
                "best_for": ["알고리즘 구현", "연구 프로젝트", "수학적 계산"],
            },
        }

        return {
            "available_roles": role_descriptions,
            "total_count": len(role_descriptions),
        }

    except Exception as e:
        api_monitor.log_error(
            e,
            {
                "endpoint": "/agent-roles",
                "user_id": api_key.user_id,
                "client_ip": client_ip,
            },
        )
        raise HTTPException(
            status_code=500, detail="에이전트 역할 목록 조회 중 오류가 발생했습니다"
        )
