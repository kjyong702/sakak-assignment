import pytest

from look_and_say.naive import middle_two, next_term


def test_next_term_follows_the_table():
    assert next_term("1") == "11"
    assert next_term("11") == "21"
    assert next_term("21") == "1211"
    assert next_term("1211") == "111221"
    assert next_term("111221") == "312211"
    assert next_term("312211") == "13112221"
    assert next_term("13112221") == "1113213211"


def test_next_term_keeps_the_last_run():
    # 마지막 묶음은 뒤에 다른 숫자가 오지 않아 루프 안에서 기록되지 않는다. 따로 적는지 지킨다
    assert next_term("2") == "12"
    assert next_term("111") == "31"
    assert next_term("1122") == "2122"


def test_middle_two_matches_the_examples():
    assert middle_two(5) == "12"
    assert middle_two(8) == "21"


def test_middle_two_at_the_smallest_n():
    assert middle_two(4) == "21"  # L4 = 1211


def test_middle_two_rejects_n_outside_the_problem_range():
    with pytest.raises(ValueError):
        middle_two(3)
    with pytest.raises(ValueError):
        middle_two(100)
