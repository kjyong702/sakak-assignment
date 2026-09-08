import httpx
import pytest

from app.agent.graph import build_graph
from app.agent.health_client import HealthApiClient, PatientNotFound
from app.agent.metrics import select_metrics, wants_history
from app.agent.prompts import SYSTEM_PROMPT, build_prompt, render_context
from app.agent.verify import unsupported_numbers
from app.main import create_app
from tests.fakes import FakeLLM


@pytest.fixture
async def health_client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as http:
        yield HealthApiClient(http)


def test_select_metrics_by_keyword():
    assert select_metrics("콜레스테롤 수치가 어때요?") == [
        "totalCholesterol",
        "HDLCholesterol",
        "LDLCholesterol",
    ]
    assert select_metrics("간 수치 괜찮나요?") == ["AST", "ALT", "yGPT"]
    assert select_metrics("혈압이랑 혈당 괜찮아요?") == ["bloodPressure", "fastingBloodGlucose"]
    assert select_metrics("LDL이 높은가요") == ["LDLCholesterol"]


def test_select_metrics_returns_nothing_for_overview_questions():
    assert select_metrics("최근 건강검진 결과는 어때요?") == []
    assert select_metrics("시간이 없어서 짧게 알려주세요") == []  # '시간'의 '간'은 간이 아니다


def test_wants_history():
    assert wants_history("작년보다 좋아졌나요?")
    assert not wants_history("혈압 어때요?")


async def test_render_context_marks_values_units_and_verdicts(health_client):
    data = await health_client.get("1")

    text = render_context(data, ["bloodPressure", "fastingBloodGlucose"], include_previous=False)

    assert "환자 이름: 홍길동" in text
    assert "검진일 2025-08-15 (서울병원)" in text
    assert "- 혈압: 125/82 mmHg -> 정상(B)" in text
    assert "- 공복혈당: 95 mg/dL -> 정상(A)" in text
    assert "정상(A) 100미만" in text  # 참고치도 같이 준다
    assert "총콜레스테롤" not in text


async def test_render_context_without_selection_lists_every_metric(health_client):
    data = await health_client.get("1")

    text = render_context(data, [], include_previous=False)

    assert "- 키: 175 Cm" in text and "- 골다공증: T-score -0.8 -> 정상(A)" in text
    assert "- 허리둘레: 85 Cm -> 판정 없음 (성별에 따라 판정이 다름" in text


async def test_render_context_uses_latest_checkup_first(health_client):
    data = await health_client.get("2")

    latest_only = render_context(data, ["bloodPressure"], include_previous=False)
    both = render_context(data, ["bloodPressure"], include_previous=True)

    assert "145/92" in latest_only and "138/88" not in latest_only
    assert both.index("[최근 검진] 검진일 2025-08-15") < both.index("[이전 검진] 검진일 2024-08-10")


def test_unsupported_numbers():
    context = "혈압: 125/82 mmHg, 검진일 2025-08-15, BMI 23.5"

    assert unsupported_numbers("혈압 125/82로 정상(B)입니다. 8월 15일 검진.", context) == []
    assert unsupported_numbers("혈당이 250으로 높습니다", context) == ["250"]
    assert unsupported_numbers("3가지를 권합니다", context) == []


def test_build_prompt_puts_retry_reason_first():
    assert build_prompt("C", "Q").startswith("[검진 데이터]\nC")
    assert build_prompt("C", "Q", "250").startswith("이전 답변에 데이터에 없는 수치(250)")


async def test_graph_answers_from_health_data(health_client):
    llm = FakeLLM("8월 15일 검진 결과 혈압이 125/82로 정상(B)입니다.")
    graph = build_graph(health_client, llm, default_model="fake")

    result = await graph.ainvoke({"patient_id": "1", "question": "혈압 어때요?"})

    assert result["answer"].startswith("8월 15일")
    assert result["metric_keys"] == ["bloodPressure"]
    assert result["verified"] is True and result["attempts"] == 1
    assert len(llm.calls) == 1
    prompt = llm.calls[0]["prompt"]
    assert "125/82" in prompt and "정상(B)" in prompt and "혈압 어때요?" in prompt
    assert llm.calls[0]["system"] == SYSTEM_PROMPT


async def test_graph_retries_once_when_answer_has_unsupported_numbers(health_client):
    llm = FakeLLM("혈당이 250mg/dL로 높습니다.", "혈당은 95mg/dL로 정상(A)입니다.")
    graph = build_graph(health_client, llm, default_model="fake")

    result = await graph.ainvoke({"patient_id": "1", "question": "혈당 어때요?"})

    assert result["attempts"] == 2 and result["verified"] is True
    assert result["answer"] == "혈당은 95mg/dL로 정상(A)입니다."
    assert "250" in llm.calls[1]["prompt"]


async def test_graph_gives_up_after_max_attempts(health_client):
    llm = FakeLLM("혈당이 250입니다.")
    graph = build_graph(health_client, llm, default_model="fake", max_attempts=2)

    result = await graph.ainvoke({"patient_id": "1", "question": "혈당?"})

    assert result["attempts"] == 2 and result["verified"] is False


async def test_unknown_patient_raises(health_client):
    graph = build_graph(health_client, FakeLLM("x"), default_model="fake")

    with pytest.raises(PatientNotFound):
        await graph.ainvoke({"patient_id": "999", "question": "?"})
