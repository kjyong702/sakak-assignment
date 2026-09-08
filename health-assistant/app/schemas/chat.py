from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """건강검진 Q&A 요청 스키마"""

    patientId: str = Field(..., min_length=1, max_length=64, description="환자 ID", examples=["1"])
    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="사용자 질문",
        examples=["최근 건강검진 결과는 어때요?"],
    )
    model: str | None = Field(
        None, max_length=100, pattern=r"^[A-Za-z0-9._:/-]+$", description="Ollama 모델. 비우면 서버 기본 모델"
    )

    @field_validator("question")
    @classmethod
    def question_must_have_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("질문이 비어 있습니다")
        return value.strip()


class ChatResponse(BaseModel):
    """건강검진 Q&A 응답 스키마"""

    status: Literal["success"] = "success"
    answer: str = Field(..., description="LLM 답변")
    patientName: str = Field(..., description="환자 이름")
    checkupDate: str | None = Field(None, description="최근 검진일")
    metrics: list[str] = Field(..., description="답변에 쓴 검진 항목 키. 비어 있으면 전체 요약")
    verified: bool = Field(..., description="답변 검증 통과 여부")
    verification: str | None = Field(None, description="검증에 걸렸을 때 그 사유")
    attempts: int = Field(..., description="LLM 생성 시도 횟수")
    model: str = Field(..., description="답변을 만든 모델")
    llmMs: float = Field(..., description="LLM 생성에 걸린 시간(ms)")
