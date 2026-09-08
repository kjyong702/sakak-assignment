from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.repositories.health_api import HealthApiError, PatientNotFound
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.assistant import HealthAssistant
from app.services.llm import LLMUnavailable

router = APIRouter(prefix="/api", tags=["chat"])


def get_assistant(request: Request) -> HealthAssistant:
    return request.app.state.assistant


Assistant = Annotated[HealthAssistant, Depends(get_assistant)]


@router.post(
    "/chat",
    summary="건강검진 Q&A",
    description="건강검진 데이터를 근거로 사용자 질문에 답합니다. Ollama 로컬 LLM을 사용합니다.",
    response_model=ChatResponse,
    responses={
        404: {"description": "환자 없음"},
        502: {"description": "건강 데이터 조회 실패"},
        503: {"description": "LLM 사용 불가"},
    },
)
async def chat(body: ChatRequest, assistant: Assistant):
    try:
        result = await assistant.ask(body.patientId, body.question, body.model)
    except PatientNotFound as e:
        return JSONResponse(status_code=404, content={"status": "error", "message": str(e)})
    except HealthApiError as e:
        return JSONResponse(status_code=502, content={"status": "error", "message": str(e)})
    except LLMUnavailable as e:
        return JSONResponse(status_code=503, content={"status": "error", "message": str(e)})
    return ChatResponse(
        answer=result.answer,
        patientName=result.patient_name,
        checkupDate=result.checkup_date,
        metrics=result.metric_keys,
        verified=result.verified,
        verification=result.verification,
        attempts=result.attempts,
        model=result.model,
        llmMs=round(result.llm_ms, 1),
    )
