"""참고치 문자열을 파싱해 측정값을 판정한다.

참고치는 자유 문자열이라 자주 나오는 형태만 규칙으로 잡는다. 규칙 밖 문자열은 판정하지 않고
그대로 보여 준다. 잘못된 판정보다 판정 없음이 낫다. 판정 순서는 질환의심, 정상(B), 정상(A)로
겹치는 구간이 있으면 더 조심스러운 쪽이 이긴다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.health.models import Overview, Reference


class Verdict(str, Enum):
    NORMAL_A = "정상(A)"
    NORMAL_B = "정상(B)"
    SUSPICIOUS = "질환의심"
    UNKNOWN = "판정 없음"


JUDGE_ORDER = (Verdict.SUSPICIOUS, Verdict.NORMAL_B, Verdict.NORMAL_A)

# 수치 비교로 판정하는 항목. 골다공증은 "T-score -0.8"에서 숫자만 뽑아 쓴다
NUMERIC_METRICS = frozenset(
    {
        "waists", "BMI", "hemoglobin", "fastingBloodGlucose", "totalCholesterol", "HDLCholesterol",
        "triglyceride", "LDLCholesterol", "serumCreatinine", "GFR", "AST", "ALT", "yGPT", "osteoporosis",
    }
)
GENDERS = ("남", "여")
ANY = "*"

_NUM = r"-?\d+(?:\.\d+)?"
_BOUND = re.compile(rf"^({_NUM})\s*(미만|이하|이상|초과)$")
_RANGE = re.compile(rf"^({_NUM})\s*[-~]\s*({_NUM})\s*(초과)?$")
_GENDER = re.compile(r"남\s*:?\s*(.+?)\s*/\s*여\s*:?\s*(.+)")
_FLOAT = re.compile(_NUM)


@dataclass(frozen=True)
class Interval:
    lo: float | None = None
    hi: float | None = None
    lo_inclusive: bool = True
    hi_inclusive: bool = True

    def contains(self, x: float) -> bool:
        if self.lo is not None and (x < self.lo or (x == self.lo and not self.lo_inclusive)):
            return False
        if self.hi is not None and (x > self.hi or (x == self.hi and not self.hi_inclusive)):
            return False
        return True


def parse_condition(text: str) -> list[Interval]:
    """'100미만', '18.5-24.9', '18.5미만/25~29.9' 같은 문자열을 구간 목록(OR)으로 바꾼다.

    한 조각이라도 못 읽으면 빈 목록을 돌려 판정에 쓰지 않는다. '-1~-2.5 초과'처럼 '초과'가
    붙은 구간은 양 끝을 열린 구간으로 본다.
    """
    text = text.replace("T-score", "").strip()
    if not text:
        return []
    intervals: list[Interval] = []
    for part in text.split("/"):
        part = part.strip()
        if m := _BOUND.fullmatch(part):
            n, op = float(m[1]), m[2]
            intervals.append(
                {
                    "미만": Interval(hi=n, hi_inclusive=False),
                    "이하": Interval(hi=n),
                    "이상": Interval(lo=n),
                    "초과": Interval(lo=n, lo_inclusive=False),
                }[op]
            )
        elif m := _RANGE.fullmatch(part):
            lo, hi = sorted((float(m[1]), float(m[2])))
            exclusive = m[3] is not None
            intervals.append(Interval(lo=lo, hi=hi, lo_inclusive=not exclusive, hi_inclusive=not exclusive))
        else:
            return []
    return intervals


def parse_by_gender(text: str) -> dict[str, list[Interval]]:
    """'남: 13-16.5 / 여: 12-15.5' 형태를 성별로 나눈다. 분기가 없으면 '*' 키 하나."""
    if m := _GENDER.search(text):
        return {"남": parse_condition(m[1]), "여": parse_condition(m[2])}
    return {ANY: parse_condition(text)}


@dataclass(frozen=True)
class BloodPressureRule:
    """'120미만 이며/80미만'은 둘 다, '140이상 또는 /90이상'은 하나만 만족하면 해당."""

    systolic: list[Interval]
    diastolic: list[Interval]
    require_both: bool

    def contains(self, systolic: float, diastolic: float) -> bool:
        s = any(i.contains(systolic) for i in self.systolic)
        d = any(i.contains(diastolic) for i in self.diastolic)
        return (s and d) if self.require_both else (s or d)


def parse_blood_pressure(text: str) -> BloodPressureRule:
    require_both = "이며" in text
    left, _, right = text.replace("이며", "").replace("또는", "").partition("/")
    return BloodPressureRule(parse_condition(left.strip()), parse_condition(right.strip()), require_both)


@dataclass(frozen=True)
class Judgement:
    verdict: Verdict
    note: str | None = None
    by_gender: dict[str, Verdict] | None = None


def judge(metric: str, value: str, references: dict[str, Reference]) -> Judgement:
    """항목 하나의 측정값을 참고치 표로 판정한다. references는 refType별 행."""
    if metric == "bloodPressure":
        return _judge_blood_pressure(value, references)
    if metric == "proteinuria":
        return _judge_proteinuria(value)
    if metric == "chestXrayResult":
        return _judge_chest_xray(value)
    if metric in NUMERIC_METRICS:
        return _judge_numeric(metric, value, references)
    return Judgement(Verdict.UNKNOWN, "참고 범위가 없는 항목")


def judge_all(overview: Overview, references: list[Reference]) -> dict[str, Judgement]:
    by_type = {r.refType: r for r in references}
    from app.health.models import METRIC_KEYS

    return {key: judge(key, getattr(overview, key), by_type) for key in METRIC_KEYS}


def _reference_text(references: dict[str, Reference], verdict: Verdict, metric: str) -> str:
    row = references.get(verdict.value)
    return (getattr(row, metric, None) or "") if row else ""


def _first_match(x: float, conditions: dict[Verdict, list[Interval]]) -> Verdict:
    for verdict in JUDGE_ORDER:
        if any(i.contains(x) for i in conditions.get(verdict, [])):
            return verdict
    return Verdict.UNKNOWN


def _judge_numeric(metric: str, value: str, references: dict[str, Reference]) -> Judgement:
    m = _FLOAT.search(value)
    if not m:
        return Judgement(Verdict.UNKNOWN, f"수치로 읽을 수 없는 값: {value}")
    x = float(m[0])
    rules = {v: parse_by_gender(_reference_text(references, v, metric)) for v in JUDGE_ORDER}
    if all(not any(r.values()) for r in rules.values()):
        return Judgement(Verdict.UNKNOWN, "참고 범위가 없는 항목")
    if all(set(r) == {ANY} for r in rules.values()):
        return Judgement(_first_match(x, {v: r[ANY] for v, r in rules.items()}))

    # 성별 분기가 있는 항목. 환자 성별을 모르므로 남녀 판정이 같을 때만 확정한다
    by_gender = {
        g: _first_match(x, {v: r.get(g, r.get(ANY, [])) for v, r in rules.items()}) for g in GENDERS
    }
    if len(set(by_gender.values())) == 1:
        return Judgement(by_gender["남"], by_gender=by_gender)
    detail = ", ".join(f"{g} {v.value}" for g, v in by_gender.items())
    return Judgement(Verdict.UNKNOWN, f"성별에 따라 판정이 다름 ({detail})", by_gender=by_gender)


def _judge_blood_pressure(value: str, references: dict[str, Reference]) -> Judgement:
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", value)
    if not m:
        return Judgement(Verdict.UNKNOWN, f"수축기/이완기 형식이 아닌 값: {value}")
    systolic, diastolic = float(m[1]), float(m[2])
    for verdict in JUDGE_ORDER:
        rule = parse_blood_pressure(_reference_text(references, verdict, "bloodPressure"))
        if rule.contains(systolic, diastolic):
            return Judgement(verdict)
    return Judgement(Verdict.UNKNOWN, "참고 범위에 해당 없음")


def _judge_proteinuria(value: str) -> Judgement:
    v = value.replace(" ", "")
    if "약양성" in v or "±" in v:
        return Judgement(Verdict.NORMAL_B)
    if "음성" in v:
        return Judgement(Verdict.NORMAL_A)
    if "양성" in v or "+" in v:
        return Judgement(Verdict.SUSPICIOUS)
    return Judgement(Verdict.UNKNOWN, f"판정 기준에 없는 값: {value}")


def _judge_chest_xray(value: str) -> Judgement:
    v = re.sub(r"[\s,]", "", value)
    if not v:
        return Judgement(Verdict.UNKNOWN, "값 없음")
    if v in {"정상", "비활동성", "정상비활동성", "정상및비활동성"}:
        return Judgement(Verdict.NORMAL_A)
    return Judgement(Verdict.SUSPICIOUS)
