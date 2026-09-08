"""검진 항목 이름표와 질문에서 항목을 고르는 키워드 표."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    keywords: tuple[str, ...]


METRICS: tuple[Metric, ...] = (
    Metric("height", "키", ("키", "신장")),
    Metric("weight", "몸무게", ("몸무게", "체중")),
    Metric("waists", "허리둘레", ("허리", "복부")),
    Metric("BMI", "체질량지수(BMI)", ("bmi", "체질량", "비만")),
    Metric("vision", "시력", ("시력", "눈")),
    Metric("hearing", "청력", ("청력", "귀")),
    Metric("bloodPressure", "혈압", ("혈압",)),
    Metric("proteinuria", "요단백", ("요단백", "단백뇨", "소변")),
    Metric("hemoglobin", "혈색소", ("혈색소", "헤모글로빈", "빈혈")),
    Metric("fastingBloodGlucose", "공복혈당", ("혈당", "당뇨")),
    Metric("totalCholesterol", "총콜레스테롤", ("콜레스테롤", "고지혈", "지질")),
    Metric("HDLCholesterol", "HDL 콜레스테롤", ("hdl", "콜레스테롤", "고지혈", "지질")),
    Metric("triglyceride", "중성지방", ("중성지방", "고지혈", "지질")),
    Metric("LDLCholesterol", "LDL 콜레스테롤", ("ldl", "콜레스테롤", "고지혈", "지질")),
    Metric("serumCreatinine", "혈청 크레아티닌", ("크레아티닌", "신장", "콩팥")),
    Metric("GFR", "사구체여과율(GFR)", ("gfr", "사구체", "신장", "콩팥")),
    Metric("AST", "AST", ("ast", "간")),
    Metric("ALT", "ALT", ("alt", "간")),
    Metric("yGPT", "감마-GTP", ("감마", "gtp", "ygpt", "간")),
    Metric("chestXrayResult", "흉부 X선", ("흉부", "엑스레이", "x선", "폐", "결핵")),
    Metric("osteoporosis", "골다공증", ("골다공증", "골밀도", "뼈")),
)

LABELS = {m.key: m.label for m in METRICS}

# 이전 검진과 비교해 달라는 뜻으로 읽는 말
HISTORY_WORDS = ("이전", "지난번", "지난 번", "예전", "작년", "변화", "추이", "비교", "달라", "좋아졌", "나빠졌")


def _matches(question: str, keyword: str) -> bool:
    # 한 글자 키워드는 단어 첫 글자여야 한다. "간"이 "시간"에 걸리지 않게
    if len(keyword) == 1:
        return re.search(rf"(?<![가-힣a-z0-9]){re.escape(keyword)}", question) is not None
    return keyword in question


def select_metrics(question: str) -> list[str]:
    """질문이 가리키는 항목 키. 아무것도 없으면 빈 목록이고 전체 개요로 답한다."""
    q = question.lower()
    return [m.key for m in METRICS if any(_matches(q, k) for k in m.keywords)]


def wants_history(question: str) -> bool:
    return any(word in question for word in HISTORY_WORDS)
