from typing import TypedDict

from app.schemas.health import HealthData


class AgentState(TypedDict, total=False):
    patient_id: str
    question: str
    model: str
    health: HealthData
    metric_keys: list[str]
    include_previous: bool
    context: str
    answer: str
    attempts: int
    verification: str | None
    verified: bool
    llm_ms: float
