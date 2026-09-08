"""시스템 프롬프트와 검진 데이터 컨텍스트 렌더링."""

from __future__ import annotations

from app.agent.metrics import LABELS
from app.health.models import METRIC_KEYS, HealthData, Reference
from app.health.reference import Judgement, Verdict, judge_all

SYSTEM_RULES = (
    "제공된 검진 데이터만 근거로 답합니다. 데이터에 없는 항목이나 수치는 말하지 않습니다.",
    "언급하는 항목마다 데이터의 값과 단위를 그대로 인용합니다. 항목 이름도 데이터의 이름을 씁니다.",
    "판정은 각 항목에 붙은 판정 결과를 그대로 따르고 범위를 다시 계산하지 않습니다. "
    "정상(A)는 정상, 정상(B)는 경계 범위(약간 높거나 낮은 편), "
    "질환의심은 진료 상담이 필요한 상태입니다.",
    "판정 없음은 괜찮다는 뜻이 아니라 판정을 못 한 것입니다. 괄호 안의 이유를 그대로 말합니다. "
    "성별에 따라 다르다고 적힌 항목만 성별 정보가 필요하다고 말하고 성별별 판정을 알려 줍니다.",
    "전체 결과를 물으면 검진일을 먼저 말하고, 정상(B)와 질환의심 항목을 값과 함께 먼저 말한 뒤, "
    "정상인 항목은 '[항목] [값 단위], [항목] [값 단위]는 정상입니다'처럼 한 문장으로 묶습니다. "
    "정상 항목 사이에 '다만'이나 '이지만'을 쓰지 않습니다.",
    "진단을 내리지 않습니다. 경계나 질환의심 항목에는 생활 습관 권고와 전문의 상담을 권합니다.",
    "한국어 존댓말로 3~5문장으로 답합니다.",
    "정상(B)는 '약간 높은(낮은) 편'으로, 질환의심은 '진료 상담이 필요한 수치'로 표현합니다.",
    "정상(A) 항목에는 주의나 권고를 붙이지 않습니다. 주의 항목이 하나뿐이면 그것만 말하고 "
    "나머지는 정상으로 묶습니다.",
)

SYSTEM_PROMPT = "당신은 건강검진 결과를 설명하는 상담 도우미입니다. 아래 규칙을 지키세요.\n\n" + "\n".join(
    f"{i}. {rule}" for i, rule in enumerate(SYSTEM_RULES, 1)
)

RETRY_TEMPLATE = (
    "이전 답변에 문제가 있었습니다 ({reason}). 제공된 데이터에 있는 항목과 수치만 사용해 다시 답하세요.\n\n"
)

REFERENCE_TYPES = ("정상(A)", "정상(B)", "질환의심")

# 전체 요약에 항상 넣는 핵심 항목. 주의 항목(정상(B), 질환의심)은 여기 없어도 항상 들어간다
KEY_METRICS = frozenset(
    {
        "BMI",
        "bloodPressure",
        "fastingBloodGlucose",
        "totalCholesterol",
        "HDLCholesterol",
        "LDLCholesterol",
        "triglyceride",
        "AST",
        "ALT",
        "GFR",
    }
)


def build_prompt(context: str, question: str, retry_reason: str | None = None) -> str:
    head = RETRY_TEMPLATE.format(reason=retry_reason) if retry_reason else ""
    return f"{head}[검진 데이터]\n{context}\n\n[질문]\n{question}\n\n[답변]"


def render_context(data: HealthData, metric_keys: list[str], include_previous: bool = False) -> str:
    """선택한 항목의 값, 단위, 참고치, 코드가 계산한 판정을 LLM이 읽을 텍스트로 만든다.

    항목을 지정하지 않은 전체 요약에서는 주의 항목과 핵심 항목만 줄로 보여 주고 나머지는 각주로 알린다.
    판정된 항목 16개를 전부 주면 7b 모델이 전부 나열하다 판정을 잘못 읽는 일이 생겼고, 보류 항목을
    주면 그것을 요약의 중심에 세웠다. 항목을 직접 물으면 보류 항목까지 그대로 보여 준다.
    """
    overviews = sorted(data.overviewList, key=lambda o: o.checkupDate, reverse=True)
    if not overviews:
        return f"환자 이름: {data.patientName}\n검진 기록이 없습니다."
    chosen = overviews[:2] if include_previous else overviews[:1]
    no_previous = include_previous and len(overviews) == 1
    keys = list(metric_keys) or list(METRIC_KEYS)
    summary = not metric_keys
    by_type = {r.refType: r for r in data.referenceList}
    organizations = {r.checkupDate: r.organizationName for r in data.resultList}

    lines = [f"환자 이름: {data.patientName}"]
    for i, overview in enumerate(chosen):
        title = "최근 검진" if i == 0 else "이전 검진"
        org = organizations.get(overview.checkupDate)
        lines += [
            "",
            f"[{title}] 검진일 {overview.checkupDate}" + (f" ({org})" if org else ""),
            f"종합 소견: {overview.evaluation}",
        ]
        judgements = judge_all(overview, data.referenceList)
        other_normal = []
        for key in keys:
            verdict = judgements[key].verdict
            if summary and verdict is Verdict.UNKNOWN:
                continue
            if summary and verdict is Verdict.NORMAL_A and key not in KEY_METRICS:
                other_normal.append(LABELS[key])
                continue
            lines.append(_metric_line(key, getattr(overview, key), by_type, judgements[key]))
        if other_normal:
            lines.append("그 외 정상(A) 항목: " + ", ".join(other_normal))
        # 판정하지 않은 항목(unjudged)은 요약에 적지 않는다. 적어 주면 모델이 그것을 설명하느라
        # 문장을 낭비하고 성별 이야기를 지어냈다. 직접 물으면 성별별 판정까지 그대로 보여 준다
    if no_previous:
        lines += ["", "이전 검진 기록: 없음. 비교할 이전 검진이 없으므로 변화를 말할 수 없다"]
    lines += [
        "",
        "판정 기준: 정상(A)는 정상, 정상(B)는 경계 범위라 생활 습관 주의, 질환의심은 진료 상담 필요. "
        "판정은 참고치 표로 계산한 결과입니다.",
    ]
    return "\n".join(lines)


def _metric_line(key: str, value: str, by_type: dict[str, Reference], judgement: Judgement) -> str:
    units = by_type.get("단위")
    unit = (getattr(units, key, None) or "") if units else ""
    shown = f"{value} {unit}".strip()
    if judgement.verdict is Verdict.UNKNOWN and judgement.note:
        verdict = f"판정 없음 ({judgement.note})"
    else:
        verdict = judgement.verdict.value
    references = [
        f"{ref_type} {getattr(by_type[ref_type], key)}"
        for ref_type in REFERENCE_TYPES
        if ref_type in by_type and getattr(by_type[ref_type], key, None)
    ]
    line = f"- {LABELS[key]}: {shown} -> {verdict}"
    if references:
        line += " (참고치: " + " / ".join(references) + ")"
    return line
