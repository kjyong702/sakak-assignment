"""LLM 답변이 컨텍스트 밖의 내용을 말했는지 검사한다."""

import re

from app.services.metrics import LABELS, METRICS

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# 생활 습관 권고에 나오는 말은 무관 항목 검사에서 뺀다
LIFESTYLE_WORDS = frozenset({"체중", "몸무게", "비만", "복부", "허리", "신장", "키", "뼈"})
# 판정 말. 뒤에 숫자가 오면 참고치 인용이라 제외
_VERDICT = re.compile(r"(?:정상\(A\)|정상\(B\)|질환의심)(?!\s*\d)")
# 프롬프트가 정한 표현을 판정으로 되읽는다
_PHRASES = (("약간 높", "정상(B)"), ("약간 낮", "정상(B)"), ("진료 상담이 필요한 수치", "질환의심"))
# 제외 표현이 있는 문장은 공통 판정을 쓰지 않는다
_EXCLUSION = ("제외", "빼고", "외에", "외의")
# 문장 끝. 소수점은 제외
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
    """컨텍스트에 없는 항목을 가리키는 말. 전체 개요(allowed_keys 비어 있음)는 검사하지 않는다"""
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
    """컨텍스트의 항목별 판정. 이전 검진이 포함되면 한 항목에 판정이 둘일 수 있다"""
    verdicts: dict[str, set[str]] = {}
    for m in _CONTEXT_LINE.finditer(context):
        verdicts.setdefault(m["label"], set()).add(m["verdict"])
    return verdicts


def _said_verdict(window: str) -> str | None:
    if m := _VERDICT.search(window):
        return m[0]
    return next((verdict for phrase, verdict in _PHRASES if phrase in window), None)


def inconsistent_verdicts(answer: str, context: str) -> list[str]:
    """답변이 항목에 붙인 판정이 컨텍스트와 다른 경우. 나열 문장은 공통 판정을 모든 항목에 적용한다"""
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
    """한국어 답변이 아니면 이유를 돌려준다"""
    if _HAN.search(answer):
        return "한자나 중국어가 섞임"
    letters = [c for c in answer if c.isalpha()]
    if letters and len(_HANGUL.findall(answer)) < len(letters) * 0.5:
        return "한국어가 절반 미만"
    return None
