"""답변에 데이터에 없는 수치가 들어갔는지 검사한다.

완전한 검증은 아니다. 수치 환각을 잡는 최소한의 그물이고 10 미만 정수(문장 수, 날짜의 월 등)는
검진 수치로 보지 않는다.
"""

import re

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


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
