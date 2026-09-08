"""답변이 컨텍스트 밖의 내용을 말했는지 검사한다.

완전한 검증은 아니다. 수치 환각과 "질문에 없는 항목 끼워 넣기"를 잡는 최소한의 그물이다.
10 미만 정수(문장 수, 날짜의 월 등)는 검진 수치로 보지 않는다.
"""

import re

from app.agent.metrics import LABELS, METRICS

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# 생활 습관 권고에 자연스럽게 나오는 말은 무관 항목 검사에서 뺀다.
# "체중 관리를 권합니다"는 몸무게 항목을 언급한 것이 아니다
LIFESTYLE_WORDS = frozenset({"체중", "몸무게", "비만", "복부", "허리", "신장", "키", "뼈"})
# 판정 말. 바로 뒤에 숫자가 오면 "정상(A) 120미만"처럼 참고치를 인용한 것이라 판정 말로 보지 않는다
_VERDICT = re.compile(r"(?:정상\(A\)|정상\(B\)|질환의심)(?!\s*\d)")
# 판정 이름 없이 표현만 쓴 문장도 대조한다. 프롬프트가 정상(B)를 "약간 높은(낮은) 편",
# 질환의심을 "진료 상담이 필요한 수치"로 쓰라고 정했으므로 그 표현을 판정으로 되읽는다
_PHRASES = (("약간 높", "정상(B)"), ("약간 낮", "정상(B)"), ("진료 상담이 필요한 수치", "질환의심"))
# "혈압을 제외한 나머지는 정상(A)" 같은 문장에서 제외된 항목에 공통 판정을 씌우지 않기 위한 표지
_EXCLUSION = ("제외", "빼고", "외에", "외의")
# 문장 끝. 소수점(23.5)은 문장 끝이 아니므로 뒤에 공백이나 끝이 오는 마침표만 본다
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_CONTEXT_LINE = re.compile(r"^- (?P<label>[^:]+): .*? -> (?P<verdict>정상\(A\)|정상\(B\)|질환의심)", re.M)


def numbers_in(text: str) -> set[float]:
    return {float(token) for token in _NUMBER.findall(text)}


def unsupported_numbers(answer: str, context: str) -> list[str]:
    """컨텍스트에 없는 수치 토큰. 비어 있으면 통과."""
    known = numbers_in(context)
    bad = []
    for token in _NUMBER.findall(answer):
        value = float(token)
        if (value >= 10 or "." in token) and value not in known and token not in bad:
            bad.append(token)
    return bad


def unsupported_metrics(answer: str, allowed_keys: list[str]) -> list[str]:
    """컨텍스트에 없는 항목을 가리키는 말. allowed_keys가 비어 있으면(전체 개요) 검사하지 않는다.

    한 키워드가 여러 항목에 걸치면(콜레스테롤은 총/HDL/LDL) 그중 하나라도 허용 항목이면 통과다.
    한 글자 키워드는 오탐이 많아 보지 않는다.
    """
    if not allowed_keys:
        return []
    allowed = set(allowed_keys)
    lowered = answer.lower()
    words: dict[str, set[str]] = {}
    for metric in METRICS:
        for word in (metric.label, *metric.keywords):
            if len(word) > 1 and word not in LIFESTYLE_WORDS:
                words.setdefault(word.lower(), set()).add(metric.key)
    bad = []
    for word, keys in words.items():
        if word in lowered and not (keys & allowed):
            bad.append(word)
    return bad


def context_verdicts(context: str) -> dict[str, set[str]]:
    """컨텍스트의 '- 항목: 값 -> 판정' 줄에서 항목별 판정을 읽는다.

    이전 검진이 같이 들어가면 한 항목에 판정이 둘일 수 있다. 답변이 어느 검진의 판정을 말하는지
    구분하지 않고 둘 중 하나와 맞으면 통과시킨다. 그래야 두 시점을 비교하는 답변을 오탐하지 않는다.
    """
    verdicts: dict[str, set[str]] = {}
    for m in _CONTEXT_LINE.finditer(context):
        verdicts.setdefault(m["label"], set()).add(m["verdict"])
    return verdicts


def _said_verdict(window: str) -> str | None:
    if m := _VERDICT.search(window):
        return m[0]
    return next((verdict for phrase, verdict in _PHRASES if phrase in window), None)


def inconsistent_verdicts(answer: str, context: str) -> list[str]:
    """답변이 항목에 붙인 판정이 컨텍스트의 판정과 다른 경우.

    문장 단위로 본다. 항목 이름 뒤부터 다음 항목 이름이나 문장 끝까지를 그 항목의 말로 보고
    그 안의 판정 말(판정 이름, 없으면 "약간 높은 편" 같은 정해진 표현)을 컨텍스트와 비교한다.
    "혈압, 혈당, BMI는 모두 정상(A)입니다"처럼 항목을 나열하고 판정을 하나 붙인 문장은 그 판정을
    나열된 모든 항목에 적용한다. 문장 안의 판정 말이 서로 다르거나 "제외" 같은 말이 있으면 그
    문장의 공통 판정은 쓰지 않는다. 판정 말이 전혀 없으면 검사하지 않는다.
    """
    expected = context_verdicts(context)
    labels = sorted((label for label in LABELS.values() if label in expected), key=len, reverse=True)
    problems: list[str] = []
    for sentence in _SENTENCE_END.split(answer):
        positions = sorted(
            (m.start(), label) for label in labels for m in re.finditer(re.escape(label), sentence)
        )
        if not positions:
            continue
        found = {m[0] for m in _VERDICT.finditer(sentence)}
        shared = found.pop() if len(found) == 1 and not any(w in sentence for w in _EXCLUSION) else None
        for i, (start, label) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(sentence)
            said = _said_verdict(sentence[start + len(label) : end]) or shared
            if said and said not in expected[label]:
                problem = f"{label}: 답변 {said}, 데이터 {'/'.join(sorted(expected[label]))}"
                if problem not in problems:
                    problems.append(problem)
    return problems


_HAN = re.compile(r"[\u4e00-\u9fff]")
_HANGUL = re.compile(r"[가-힣]")


def foreign_language(answer: str) -> str | None:
    """한국어 답변이 아니면 이유를 돌려준다.

    qwen 계열은 긴 답변 끝에서 중국어로 넘어가는 일이 있다. 한자가 하나라도 있거나 한글이 거의 없으면 걸린다.
    """
    if _HAN.search(answer):
        return "한자나 중국어가 섞임"
    letters = [c for c in answer if c.isalpha()]
    if letters and len(_HANGUL.findall(answer)) < len(letters) * 0.5:
        return "한국어가 절반 미만"
    return None
