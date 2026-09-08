"""그래프를 감싼 서비스. 터미널 대화와 채팅 API가 같이 쓴다."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.graph import build_graph
from app.agent.health_client import HealthApiClient
from app.agent.llm import LLMClient


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    patient_name: str
    checkup_date: str | None
    metric_keys: list[str]
    verified: bool
    attempts: int
    model: str
    llm_ms: float
    context: str


class HealthAssistant:
    def __init__(self, health: HealthApiClient, llm: LLMClient, default_model: str, max_attempts: int = 2) -> None:
        self.default_model = default_model
        self._graph = build_graph(health, llm, default_model, max_attempts)

    async def ask(self, patient_id: str, question: str, model: str | None = None) -> AnswerResult:
        state = await self._graph.ainvoke(
            {"patient_id": patient_id, "question": question, "model": model or self.default_model}
        )
        health = state["health"]
        latest = max(health.overviewList, key=lambda o: o.checkupDate, default=None)
        return AnswerResult(
            answer=state["answer"],
            patient_name=health.patientName,
            checkup_date=latest.checkupDate if latest else None,
            metric_keys=state["metric_keys"],
            verified=state["verified"],
            attempts=state["attempts"],
            model=state["model"],
            llm_ms=state["llm_ms"],
            context=state["context"],
        )
