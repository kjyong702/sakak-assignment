"""LangGraph 워크플로.

START -> fetch_health -> select_metrics -> build_context -> generate_answer -> verify_answer -> END
                                                                 ^                    |
                                                                 +--- 재생성 (최대 max_attempts) ---+
LLM을 부르는 노드는 generate_answer 하나다. 나머지는 결정적이라 테스트가 쉽고 답이 흔들리지 않는다.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent.health_client import HealthApiClient
from app.agent.llm import LLMClient
from app.agent.metrics import select_metrics, wants_history
from app.agent.prompts import SYSTEM_PROMPT, build_prompt, render_context
from app.agent.state import AgentState
from app.agent.verify import inconsistent_verdicts, unsupported_metrics, unsupported_numbers


def build_graph(health: HealthApiClient, llm: LLMClient, default_model: str, max_attempts: int = 2):
    async def fetch_health(state: AgentState) -> AgentState:
        return {"health": await health.get(state["patient_id"])}

    def select(state: AgentState) -> AgentState:
        question = state["question"]
        return {"metric_keys": select_metrics(question), "include_previous": wants_history(question)}

    def build_context(state: AgentState) -> AgentState:
        context = render_context(state["health"], state["metric_keys"], state.get("include_previous", False))
        return {"context": context}

    async def generate_answer(state: AgentState) -> AgentState:
        prompt = build_prompt(state["context"], state["question"], state.get("verification"))
        response = await llm.generate(prompt, system=SYSTEM_PROMPT, model=state.get("model") or default_model)
        return {
            "answer": response.text,
            "model": response.model,
            "attempts": state.get("attempts", 0) + 1,
            "llm_ms": state.get("llm_ms", 0.0) + response.total_duration_ms,
        }

    def verify_answer(state: AgentState) -> AgentState:
        answer = state.get("answer", "")
        if not answer.strip():
            return {"verified": False, "verification": "빈 답변"}
        reasons = []
        # 질문에 나온 숫자("130 넘나요?")를 답변이 되풀이하는 것은 환각이 아니다
        if bad_numbers := unsupported_numbers(answer, state["context"] + "\n" + state["question"]):
            reasons.append("데이터에 없는 수치: " + ", ".join(bad_numbers))
        if bad_metrics := unsupported_metrics(answer, state.get("metric_keys", [])):
            reasons.append("질문과 무관해 데이터에 없는 항목: " + ", ".join(bad_metrics))
        if bad_verdicts := inconsistent_verdicts(answer, state["context"]):
            reasons.append("판정 불일치: " + ", ".join(bad_verdicts))
        if reasons:
            return {"verified": False, "verification": "; ".join(reasons)}
        return {"verified": True, "verification": None}

    def after_verify(state: AgentState) -> str:
        if state.get("verified") or state.get("attempts", 0) >= max_attempts:
            return "done"
        return "retry"

    graph = StateGraph(AgentState)
    graph.add_node("fetch_health", fetch_health)
    graph.add_node("select_metrics", select)
    graph.add_node("build_context", build_context)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("verify_answer", verify_answer)
    graph.add_edge(START, "fetch_health")
    graph.add_edge("fetch_health", "select_metrics")
    graph.add_edge("select_metrics", "build_context")
    graph.add_edge("build_context", "generate_answer")
    graph.add_edge("generate_answer", "verify_answer")
    graph.add_conditional_edges("verify_answer", after_verify, {"retry": "generate_answer", "done": END})
    return graph.compile()
