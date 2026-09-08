"""POST /api/chat"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.agent.health_client import HealthApiError, PatientNotFound
from app.agent.llm import LLMUnavailable
from app.agent.service import HealthAssistant

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    patientId: str = Field(min_length=1, max_length=64, examples=["1"])
    question: str = Field(min_length=1, max_length=500, examples=["최근 건강검진 결과는 어때요?"])
    # Ollama 모델 이름 형식만 허용한다 (예: qwen2.5:7b, hf.co/org/model:tag)
    model: str | None = Field(
        default=None, max_length=100, pattern=r"^[A-Za-z0-9._:/-]+$", description="비우면 서버 기본 모델"
    )

    @field_validator("question")
    @classmethod
    def question_must_have_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("질문이 비어 있습니다")
        return value.strip()


class ChatResponse(BaseModel):
    status: Literal["success"] = "success"
    answer: str
    patientName: str
    checkupDate: str | None
    metrics: list[str]
    verified: bool
    verification: str | None = Field(default=None, description="검증에 걸렸을 때 그 사유")
    attempts: int
    model: str
    llmMs: float


def get_assistant(request: Request) -> HealthAssistant:
    return request.app.state.assistant


Assistant = Annotated[HealthAssistant, Depends(get_assistant)]


@router.post(
    "",
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
