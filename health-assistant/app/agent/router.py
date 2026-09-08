"""POST /api/chat"""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.health_client import PatientNotFound
from app.agent.llm import LLMUnavailable
from app.agent.service import HealthAssistant

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    patientId: str = Field(examples=["1"])
    question: str = Field(min_length=1, examples=["최근 건강검진 결과는 어때요?"])
    model: str | None = Field(default=None, description="비우면 서버 기본 모델")


class ChatResponse(BaseModel):
    status: Literal["success"] = "success"
    answer: str
    patientName: str
    checkupDate: str | None
    metrics: list[str]
    verified: bool
    attempts: int
    model: str
    llmMs: float


def get_assistant(request: Request) -> HealthAssistant:
    return request.app.state.assistant


@router.post(
    "",
    response_model=ChatResponse,
    responses={404: {"description": "환자 없음"}, 503: {"description": "LLM 사용 불가"}},
)
async def chat(body: ChatRequest, request: Request):
    assistant = get_assistant(request)
    try:
        result = await assistant.ask(body.patientId, body.question, body.model)
    except PatientNotFound as e:
        return JSONResponse(status_code=404, content={"status": "error", "message": str(e)})
    except LLMUnavailable as e:
        return JSONResponse(status_code=503, content={"status": "error", "message": str(e)})
    return ChatResponse(
        answer=result.answer,
        patientName=result.patient_name,
        checkupDate=result.checkup_date,
        metrics=result.metric_keys,
        verified=result.verified,
        attempts=result.attempts,
        model=result.model,
        llmMs=round(result.llm_ms, 1),
    )
