import httpx
import pytest

from app.agent.graph import build_graph
from app.agent.health_client import HealthApiClient, PatientNotFound
from app.agent.metrics import select_metrics, wants_history
from app.agent.prompts import SYSTEM_PROMPT, build_prompt, render_context
from app.agent.verify import (
    foreign_language,
    inconsistent_verdicts,
    unsupported_metrics,
    unsupported_numbers,
)
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
    assert select_metrics("간단하게 요약해 주세요") == []  # '간단'도 간이 아니다
    assert select_metrics("눈에 띄는 이상이 있나요?") == []
    assert select_metrics("키워드로 정리해 주세요") == []


def test_single_syllable_keywords_match_with_particles():
    assert select_metrics("간은 괜찮나요?") == ["AST", "ALT", "yGPT"]
    assert select_metrics("키가 몇이에요?") == ["height"]
    assert select_metrics("신장 기능은 괜찮나요?") == ["serumCreatinine", "GFR"]


def test_wants_history():
    assert wants_history("작년보다 좋아졌나요?")
    assert wants_history("콜레스테롤이 높아졌나요?")
    assert wants_history("지난 검진 결과는요?")
    assert not wants_history("혈압 어때요?")
    assert not wants_history("혈압 수치 좀 알려달라")
    assert not wants_history("정상 범위와 비교하면 어때요?")
    assert not wants_history("생활 습관 변화가 필요한가요?")


async def test_render_context_marks_values_units_and_verdicts(health_client):
    data = await health_client.get("1")

    text = render_context(data, ["bloodPressure", "fastingBloodGlucose"], include_previous=False)

    assert "환자 이름: 홍길동" in text
    assert "검진일 2025-08-15 (서울병원)" in text
    assert "- 혈압: 125/82 mmHg -> 정상(B)" in text
    assert "- 공복혈당: 95 mg/dL -> 정상(A)" in text
    assert "정상(A) 100미만" in text  # 참고치도 같이 준다
    assert "총콜레스테롤" not in text


async def test_overview_context_shows_attention_and_key_metrics_only(health_client):
    data = await health_client.get("1")

    text = render_context(data, [], include_previous=False)

    assert "- 혈압: 125/82 mmHg -> 정상(B)" in text  # 주의 항목
    assert "- 공복혈당: 95 mg/dL -> 정상(A)" in text  # 핵심 항목
    assert (
        text.index("[주의 항목")
        < text.index("- 혈압:")
        < text.index("[정상(A) 항목]")
        < text.index("- 공복혈당:")
    )
    assert "- 골다공증" not in text and "- 키: 175 Cm" not in text and "- 허리둘레" not in text
    assert "그 외 정상(A) 항목: 요단백, 혈색소, 혈청 크레아티닌, 감마-GTP, 흉부 X선, 골다공증" in text
    assert "판정하지 않은 항목" not in text  # 보류 항목은 요약에서 아예 언급하지 않는다


async def test_overview_context_always_includes_attention_items(health_client):
    data = await health_client.get("2")

    text = render_context(data, [], include_previous=False)

    assert "- 허리둘레: 91 Cm -> 질환의심" in text  # 핵심 항목이 아니어도 주의 항목이면 들어간다


async def test_direct_question_still_shows_unjudged_metric(health_client):
    data = await health_client.get("1")

    text = render_context(data, ["waists"], include_previous=False)

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
    assert build_prompt("C", "Q", "데이터에 없는 수치: 250").startswith(
        "이전 답변에 문제가 있었습니다 (데이터에 없는 수치: 250)"
    )


def test_unsupported_metrics_flags_items_outside_the_question():
    assert unsupported_metrics("콜레스테롤은 정상 범위에 있으니 안심하세요.", ["bloodPressure"]) == [
        "콜레스테롤"
    ]
    assert unsupported_metrics("LDL 콜레스테롤 165 mg/dL로 질환의심입니다.", ["LDLCholesterol"]) == []
    assert unsupported_metrics("혈압 145/92 mmHg로 질환의심입니다.", ["bloodPressure"]) == []
    assert unsupported_metrics("콜레스테롤과 혈압 모두 정상입니다.", []) == []  # 전체 개요는 검사하지 않는다


async def test_graph_retries_when_answer_brings_in_unrelated_metric(health_client):
    llm = FakeLLM(
        "혈압 145/92 mmHg로 질환의심입니다. 콜레스테롤은 정상입니다.", "혈압 145/92 mmHg로 질환의심입니다."
    )
    graph = build_graph(health_client, llm, default_model="fake")

    result = await graph.ainvoke({"patient_id": "2", "question": "혈압이 괜찮은가요?"})

    assert result["attempts"] == 2 and result["verified"] is True
    assert "콜레스테롤" in llm.calls[1]["prompt"]


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


def test_inconsistent_verdicts_compares_answer_with_context():
    context = "- 혈압: 125/82 mmHg -> 정상(B) (참고치: ...)\n- 공복혈당: 95 mg/dL -> 정상(A) (참고치: ...)"

    assert (
        inconsistent_verdicts("혈압 125/82 mmHg로 정상(B)이며, 공복혈당 95 mg/dL은 정상(A)입니다.", context)
        == []
    )
    assert inconsistent_verdicts(
        "혈압 125/82 mmHg와 공복혈당 95 mg/dL은 정상(B) 범위에 속합니다.", context
    ) == ["공복혈당: 답변 정상(B), 데이터 정상(A)"]
    # 판정 말이 없는 문장은 검사하지 않는다
    assert inconsistent_verdicts("혈압과 공복혈당 수치를 확인했습니다.", context) == []


async def test_graph_retries_when_answer_contradicts_a_verdict(health_client):
    llm = FakeLLM("공복혈당 95 mg/dL은 정상(B) 범위입니다.", "공복혈당 95 mg/dL은 정상(A)입니다.")
    graph = build_graph(health_client, llm, default_model="fake")

    result = await graph.ainvoke({"patient_id": "1", "question": "혈당 어때요?"})

    assert result["attempts"] == 2 and result["verified"] is True
    assert "데이터 정상(A)" in llm.calls[1]["prompt"]


def test_inconsistent_verdicts_reads_fixed_expressions_without_verdict_names():
    context = "- 총콜레스테롤: 190 mg/dL -> 정상(A)\n- 혈압: 125/82 mmHg -> 정상(B)"

    assert inconsistent_verdicts(
        "총콜레스테롤이 약간 높은 편(190 mg/dL)이며, 혈압은 정상입니다.", context
    ) == ["총콜레스테롤: 답변 정상(B), 데이터 정상(A)"]
    assert inconsistent_verdicts("혈압 125/82 mmHg로 약간 높은 편입니다.", context) == []
    assert inconsistent_verdicts("혈압 125/82 mmHg는 정상(B)라 약간 높은 편입니다.", context) == []


def test_inconsistent_verdicts_applies_shared_verdict_to_listed_items():
    context = (
        "- 혈압: 125/82 mmHg -> 정상(B)\n- 공복혈당: 95 mg/dL -> 정상(A)\n"
        "- 체질량지수(BMI): 23.5 kg/m2 -> 정상(A)"
    )

    listed = "혈압 125/82 mmHg, 체질량지수(BMI) 23.5 kg/m2, 공복혈당 95 mg/dL 등은 모두 정상(A)입니다."
    assert inconsistent_verdicts(listed, context) == ["혈압: 답변 정상(A), 데이터 정상(B)"]
    excluded = "혈압 125/82 mmHg를 제외한 공복혈당 95 mg/dL, 체질량지수(BMI) 23.5 kg/m2는 정상(A)입니다."
    assert inconsistent_verdicts(excluded, context) == []
    mixed = "혈압 125/82 mmHg는 정상(B)이고 공복혈당 95 mg/dL는 정상(A)입니다."
    assert inconsistent_verdicts(mixed, context) == []


def test_inconsistent_verdicts_accepts_either_checkup_when_previous_is_included():
    context = (
        "[최근 검진] 검진일 2025-08-15\n- 혈압: 145/92 mmHg -> 질환의심\n\n"
        "[이전 검진] 검진일 2024-08-10\n- 혈압: 138/88 mmHg -> 정상(B)"
    )

    assert inconsistent_verdicts("혈압 145/92 mmHg로 질환의심이니 진료 상담을 권합니다.", context) == []
    assert (
        inconsistent_verdicts(
            "최근 혈압 145/92 mmHg는 질환의심이고, 이전 혈압 138/88 mmHg는 정상(B)였습니다.", context
        )
        == []
    )
    assert inconsistent_verdicts("혈압 145/92 mmHg로 정상(A)입니다.", context) == [
        "혈압: 답변 정상(A), 데이터 정상(B)/질환의심"
    ]


async def test_graph_does_not_reject_correct_answer_about_previous_checkup(health_client):
    llm = FakeLLM("최근 혈압 145/92 mmHg는 질환의심이고 이전 혈압 138/88 mmHg는 정상(B)였습니다.")
    graph = build_graph(health_client, llm, default_model="fake")

    result = await graph.ainvoke({"patient_id": "2", "question": "작년과 비교해서 혈압이 어떻게 달라졌나요?"})

    assert result["include_previous"] is True
    assert result["attempts"] == 1 and result["verified"] is True


async def test_history_question_for_single_checkup_patient_says_no_previous(health_client):
    data = await health_client.get("1")

    text = render_context(data, ["bloodPressure"], include_previous=True)

    assert "이전 검진 기록: 없음" in text


def test_unsupported_metrics_ignores_lifestyle_words():
    assert (
        unsupported_metrics(
            "혈압이 약간 높은 편이니 체중 관리와 염분 섭취 조절을 권합니다.", ["bloodPressure"]
        )
        == []
    )


def test_inconsistent_verdicts_ignores_reference_citations():
    context = (
        "- 혈압: 125/82 mmHg -> 정상(B) (참고치: 정상(A) 120미만 이며/80미만 / 정상(B) 120-139 또는 /80-89)"
    )

    assert (
        inconsistent_verdicts("혈압 125/82 mmHg는 정상(A) 120미만 기준을 넘어 정상(B)입니다.", context) == []
    )


def test_unsupported_numbers_allow_numbers_from_question():
    assert (
        unsupported_numbers("혈압 125 mmHg는 130을 넘지 않습니다.", "혈압: 125/82 mmHg\n혈압이 130 넘나요?")
        == []
    )


def test_foreign_language_catches_chinese_and_non_korean_answers():
    assert (
        foreign_language("감마-GTP는 성별에 따라 다릅니다. 김영희女士, 请告知我您的性别。")
        == "한자나 중국어가 섞임"
    )
    assert foreign_language("Your blood pressure is 145/92 mmHg, which is high.") == "한국어가 절반 미만"
    assert (
        foreign_language("혈압 145/92 mmHg로 질환의심이니 진료 상담을 권합니다. ALT 52 U/L도 높습니다.")
        is None
    )


async def test_graph_retries_when_answer_switches_language(health_client):
    llm = FakeLLM(
        "ALT 52 U/L로 질환의심입니다. 请告知我您的性别。", "ALT 52 U/L로 질환의심이니 진료 상담을 권합니다."
    )
    graph = build_graph(health_client, llm, default_model="fake")

    result = await graph.ainvoke({"patient_id": "2", "question": "간 수치는 어떤가요?"})

    assert result["attempts"] == 2 and result["verified"] is True
    assert "중국어" in llm.calls[1]["prompt"]
