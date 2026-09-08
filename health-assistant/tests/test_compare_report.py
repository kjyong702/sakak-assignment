import json

from scripts.compare_models import QUESTIONS, Row, load_previous, render_report


def test_render_report_has_summary_and_per_question_sections():
    row = Row(
        "m1",
        "1",
        QUESTIONS[0][1],
        QUESTIONS[0][2],
        "혈압 125/82로 정상(B)입니다.",
        8300.0,
        8500.0,
        1,
        True,
        [],
    )
    failed = Row("m2", "1", QUESTIONS[0][1], QUESTIONS[0][2], "", 0, 0, 0, False, [], None, "모델 없음")

    text = render_report({"m1": (12000.0, [row]), "m2": (None, [failed]), "m3": (None, [])})

    assert "| m1 | 12.0s | 8.3s | 8.5s | 1/1 | 0 | 0 |" in text
    assert "| m3 | 실행 실패 |" in text
    assert "### 1. 환자 1: 최근 건강검진 결과는 어때요?" in text
    assert "> 혈압 125/82로 정상(B)입니다." in text
    assert "**m2**: 실패 (모델 없음)" in text


def test_render_report_shows_verification_reason_when_not_verified():
    row = Row(
        "m1", "1", QUESTIONS[0][1], QUESTIONS[0][2], "답", 100.0, 120.0, 2, False, [], "판정 불일치: 혈압"
    )

    text = render_report({"m1": (1000.0, [row])})

    assert "검증 미통과, 사유: 판정 불일치: 혈압" in text


def test_load_previous_round_trips_rows(tmp_path):
    row = Row("m1", "1", QUESTIONS[0][1], QUESTIONS[0][2], "답", 100.0, 120.0, 1, True, [], None, None)
    raw = tmp_path / "r.json"
    raw.write_text(
        json.dumps({"m1": {"load_ms": 5.0, "rows": [row.__dict__]}}, ensure_ascii=False), encoding="utf-8"
    )

    assert load_previous(raw) == {"m1": (5.0, [row])}
    assert load_previous(tmp_path / "missing.json") == {}
