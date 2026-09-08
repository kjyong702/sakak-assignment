def next_term(term: str) -> str:
    """이전 항을 읽어 다음 항을 만든다"""
    result = ""
    current = term[0]
    count = 0

    for ch in term:
        if ch == current:
            count += 1
        else:
            result += str(count) + current
            current = ch
            count = 1

    result += str(count) + current
    return result


def middle_two(n: int) -> str:
    """n번째 항의 가운데 두 자리"""
    term = "1"
    for _ in range(n - 1):
        term = next_term(term)

    mid = len(term) // 2
    return term[mid - 1 : mid + 1]
