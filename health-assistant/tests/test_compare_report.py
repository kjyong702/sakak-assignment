from scripts.compare_models import QUESTIONS, Row, render_report


def test_render_report_has_summary_and_per_question_sections():
    row = Row("m1", "1", QUESTIONS[0][1], QUESTIONS[0][2], "혈압 125/82로 정상(B)입니다.", 8300.0, 8500.0, 1, True, [])
    failed = Row("m2", "1", QUESTIONS[0][1], QUESTIONS[0][2], "", 0, 0, 0, False, [], "모델 없음")

    text = render_report({"m1": (12000.0, [row]), "m2": (None, [failed]), "m3": (None, [])})

    assert "| m1 | 12.0s | 8.3s | 8.5s | 1/1 | 0 | 0 |" in text
    assert "| m3 | 실행 실패 |" in text
    assert "### 1. 환자 1: 최근 건강검진 결과는 어때요?" in text
    assert "> 혈압 125/82로 정상(B)입니다." in text
    assert "**m2**: 실패 (모델 없음)" in text
