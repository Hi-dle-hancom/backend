from pydantic import BaseModel
import logging
import time
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.security import APIKeyModel, check_permission, check_rate_limit_dependency
from app.schemas.code_generation import CodeGenerationResponse
from app.services.custom_agent_service import (
    AgentRole,
    CustomAgent,
    custom_agent_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# =============================================================================
# 누락된 Pydantic 스키마 정의들
# =============================================================================

class AgentCreationRequest(BaseModel):
    """에이전트 생성 요청 모델"""
    name: str
    role: str  # AgentRole enum value
    custom_instructions: Optional[str] = ""
    specialty_areas: Optional[List[str]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Python Expert",
                "role": "senior_developer",
                "custom_instructions": "Python 최적화와 성능에 특화된 에이전트",
                "specialty_areas": ["performance", "algorithms", "optimization"]
            }
        }


class AgentCodeGenerationRequest(BaseModel):
    """에이전트 코드 생성 요청 모델"""
    agent_id: str
    user_question: str
    code_context: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "custom_user123_python_expert",
                "user_question": "리스트를 효율적으로 정렬하는 방법을 알려주세요",
                "code_context": "# 기존 코드\ndata = [3, 1, 4, 1, 5]"
            }
        }


class AgentResponse(BaseModel):
    """에이전트 응답 모델"""
    agent_id: str
    name: str
    role: str
    custom_instructions: str
    specialty_areas: List[str]
    created_at: str
    usage_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "custom_user123_python_expert",
                "name": "Python Expert",
                "role": "senior_developer",
                "custom_instructions": "Python 최적화와 성능에 특화된 에이전트",
                "specialty_areas": ["performance", "algorithms", "optimization"],
                "created_at": "2025-01-10T10:30:00Z",
                "usage_count": 15
            }
        }


class AgentListResponse(BaseModel):
    """에이전트 목록 응답 모델"""
    agents: List[AgentResponse]
    total_count: int
    user_agents_count: int
    system_agents_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "agents": [
                    {
                        "agent_id": "custom_user123_python_expert",
                        "name": "Python Expert",
                        "role": "senior_developer",
                        "custom_instructions": "Python 최적화 전문",
                        "specialty_areas": ["performance"],
                        "created_at": "2025-01-10T10:30:00Z",
                        "usage_count": 15
                    }
                ],
                "total_count": 5,
                "user_agents_count": 3,
                "system_agents_count": 2
            }
        }


# =============================================================================
# API 엔드포인트들
# =============================================================================


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

        logger.info(f"에이전트 목록 조회 요청 - 사용자: {api_key.user_id}, IP: {client_ip}")

        # 사용자별 커스텀 에이전트 조회
        user_agents = await custom_agent_service.get_user_agents(api_key.user_id)

        # 시스템 기본 에이전트 조회
        system_agents = await custom_agent_service.get_system_agents()

        # 응답 형식으로 변환
        agent_responses = []
        for agent in user_agents + system_agents:
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

        logger.info(f"에이전트 목록 조회 성공: {len(agent_responses)}개 - 사용자: {api_key.user_id}")

        return AgentListResponse(
            agents=agent_responses,
            total_count=len(agent_responses),
            user_agents_count=len(user_agents),
            system_agents_count=len(system_agents)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 목록 조회 실패 - 사용자: {api_key.user_id}, 오류: {e}")
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

        logger.info(f"커스텀 에이전트 생성 요청: {request_data.name} - 사용자: {api_key.user_id}, 역할: {request_data.role}, IP: {client_ip}")

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

        logger.info(f"커스텀 에이전트 생성 성공: {agent.name} - 사용자: {api_key.user_id}, 에이전트ID: {agent.agent_id}")

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
        logger.error(f"커스텀 에이전트 생성 실패 - 사용자: {api_key.user_id}, 에이전트명: {request_data.name}, 오류: {e}")
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

        logger.info(f"에이전트 정보 조회: {agent_id} - 사용자: {api_key.user_id}, IP: {client_ip}")

        # 에이전트 조회
        agent = await custom_agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다")

        # 권한 확인 (커스텀 에이전트인 경우)
        if agent.agent_id.startswith("custom_") and not agent.agent_id.startswith(
            f"custom_{api_key.user_id}_"
        ):
            raise HTTPException(
                status_code=403, detail="해당 에이전트에 접근할 권한이 없습니다"
            )

        response = AgentResponse(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role.value,
            custom_instructions=agent.custom_instructions,
            specialty_areas=agent.specialty_areas,
            created_at=agent.created_at.isoformat(),
            usage_count=agent.usage_count,
        )

        logger.info(f"에이전트 정보 조회 성공: {agent.name} - 사용자: {api_key.user_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 정보 조회 실패 - 사용자: {api_key.user_id}, 에이전트ID: {agent_id}, 오류: {e}")
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

        logger.info(f"에이전트 코드 생성 요청: {request_data.agent_id} - 사용자: {api_key.user_id}, 프롬프트 길이: {len(request_data.user_question)}, IP: {client_ip}")

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

        logger.info(
            f"에이전트 코드 생성 성공: {agent.name} - 사용자: {api_key.user_id}, "
            f"에이전트ID: {request_data.agent_id}, 처리시간: {ai_duration:.2f}초, "
            f"코드길이: {len(response.generated_code) if response.generated_code else 0}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 코드 생성 실패 - 사용자: {api_key.user_id}, 에이전트ID: {request_data.agent_id}, 오류: {e}")
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

        logger.info(f"에이전트 역할 목록 조회 - 사용자: {api_key.user_id}, IP: {client_ip}")

        # 사용 가능한 역할 목록 반환
        roles = [
            {"value": role.value, "name": role.name, "description": role.value.replace("_", " ").title()}
            for role in AgentRole
        ]

        logger.info(f"에이전트 역할 목록 조회 성공: {len(roles)}개 - 사용자: {api_key.user_id}")
        return {"roles": roles, "total_count": len(roles)}

    except Exception as e:
        logger.error(f"에이전트 역할 목록 조회 실패 - 사용자: {api_key.user_id}, 오류: {e}")
        raise HTTPException(
            status_code=500, detail="에이전트 역할 목록 조회 중 오류가 발생했습니다"
        )
