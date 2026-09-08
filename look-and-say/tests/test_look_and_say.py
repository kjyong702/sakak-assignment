from look_and_say.naive import middle_two, next_term


def test_next_term_follows_the_table():
    assert next_term("1") == "11"
    assert next_term("11") == "21"
    assert next_term("21") == "1211"
    assert next_term("1211") == "111221"
    assert next_term("111221") == "312211"
    assert next_term("312211") == "13112221"
    assert next_term("13112221") == "1113213211"


def test_middle_two_matches_the_examples():
    assert middle_two(5) == "12"
    assert middle_two(8) == "21"
