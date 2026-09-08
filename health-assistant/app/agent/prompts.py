"""시스템 프롬프트와 검진 데이터 컨텍스트 렌더링."""

from __future__ import annotations

from app.agent.metrics import LABELS
from app.health.models import METRIC_KEYS, HealthData, Reference
from app.health.reference import Judgement, Verdict, judge_all

SYSTEM_PROMPT = """당신은 건강검진 결과를 설명하는 상담 도우미입니다. 아래 규칙을 지키세요.

1. 제공된 검진 데이터만 근거로 답합니다. 데이터에 없는 항목이나 수치는 말하지 않습니다.
2. 수치를 말할 때는 데이터의 값과 단위를 그대로 씁니다.
3. 정상 여부는 각 항목에 붙은 판정 결과를 그대로 따릅니다. 범위를 스스로 다시 계산하지 않습니다.
4. 정상(B)나 질환의심 항목이 있으면 그 항목을 먼저 말하고 생활 습관 권고와 전문의 상담을 권합니다. 진단을 내리지 않습니다.
5. 질문과 관련된 항목만 답합니다. 전체 결과를 물으면 주의가 필요한 항목 위주로 요약합니다.
6. 한국어 존댓말로 3~5문장으로 답합니다."""

RETRY_TEMPLATE = "이전 답변에 데이터에 없는 수치({numbers})가 들어 있었습니다. 데이터에 있는 수치만 사용해 다시 답하세요.\n\n"

REFERENCE_TYPES = ("정상(A)", "정상(B)", "질환의심")


def build_prompt(context: str, question: str, retry_reason: str | None = None) -> str:
    head = RETRY_TEMPLATE.format(numbers=retry_reason) if retry_reason else ""
    return f"{head}[검진 데이터]\n{context}\n\n[질문]\n{question}\n\n[답변]"


def render_context(data: HealthData, metric_keys: list[str], include_previous: bool = False) -> str:
    """선택한 항목의 값, 단위, 참고치, 코드가 계산한 판정을 LLM이 읽을 텍스트로 만든다."""
    overviews = sorted(data.overviewList, key=lambda o: o.checkupDate, reverse=True)
    if not overviews:
        return f"환자 이름: {data.patientName}\n검진 기록이 없습니다."
    chosen = overviews[:2] if include_previous else overviews[:1]
    keys = list(metric_keys) or list(METRIC_KEYS)
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
        for key in keys:
            lines.append(_metric_line(key, getattr(overview, key), by_type, judgements[key]))
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
