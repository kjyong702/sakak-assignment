import pytest

from app.config import settings
from app.health.reference import (
    Interval,
    Verdict,
    judge,
    judge_all,
    parse_blood_pressure,
    parse_by_gender,
    parse_condition,
)
from app.health.repository import PatientRepository


@pytest.fixture(scope="module")
def references():
    data = PatientRepository(settings.data_dir).get("1")
    return {r.refType: r for r in data.referenceList}


def test_parse_single_bound():
    assert parse_condition("100미만") == [Interval(hi=100, hi_inclusive=False)]
    assert parse_condition("60이상") == [Interval(lo=60)]
    assert parse_condition("1.6이하") == [Interval(hi=1.6)]
    assert parse_condition("1.6초과") == [Interval(lo=1.6, lo_inclusive=False)]


def test_parse_range_and_alternatives():
    assert parse_condition("18.5-24.9") == [Interval(lo=18.5, hi=24.9)]
    assert parse_condition("18.5미만/25~29.9") == [
        Interval(hi=18.5, hi_inclusive=False),
        Interval(lo=25, hi=29.9),
    ]


def test_parse_exclusive_range_with_negative_numbers():
    assert parse_condition("-1~-2.5 초과") == [
        Interval(lo=-2.5, hi=-1, lo_inclusive=False, hi_inclusive=False)
    ]
    assert parse_condition("T-score -1 이상") == [Interval(lo=-1)]


def test_unreadable_text_gives_no_condition():
    assert parse_condition("") == []
    assert parse_condition("정상, 비활동성") == []
    assert parse_condition("100미만/이상한값") == []


def test_parse_by_gender():
    assert parse_by_gender("남: 13-16.5 / 여: 12-15.5") == {
        "남": [Interval(lo=13, hi=16.5)],
        "여": [Interval(lo=12, hi=15.5)],
    }
    assert parse_by_gender("남 90이상 / 여 85이상") == {"남": [Interval(lo=90)], "여": [Interval(lo=85)]}
    assert parse_by_gender("200미만") == {"*": [Interval(hi=200, hi_inclusive=False)]}


def test_parse_blood_pressure_rules():
    both = parse_blood_pressure("120미만 이며/80미만")
    either = parse_blood_pressure("140이상 또는 /90이상")

    assert both.require_both and not either.require_both
    assert both.contains(119, 79) and not both.contains(119, 80)
    assert either.contains(140, 70) and either.contains(100, 90) and not either.contains(139, 89)


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [
        ("BMI", "23.5", Verdict.NORMAL_A),
        ("BMI", "18.4", Verdict.NORMAL_B),
        ("BMI", "27.1", Verdict.NORMAL_B),
        ("BMI", "30", Verdict.SUSPICIOUS),
        ("fastingBloodGlucose", "99.9", Verdict.NORMAL_A),
        ("fastingBloodGlucose", "100", Verdict.NORMAL_B),
        ("fastingBloodGlucose", "125", Verdict.NORMAL_B),
        ("fastingBloodGlucose", "126", Verdict.SUSPICIOUS),
        ("totalCholesterol", "190", Verdict.NORMAL_A),
        ("totalCholesterol", "245", Verdict.SUSPICIOUS),
        ("HDLCholesterol", "60", Verdict.NORMAL_A),
        ("HDLCholesterol", "38", Verdict.SUSPICIOUS),
        ("LDLCholesterol", "165", Verdict.SUSPICIOUS),
        ("triglyceride", "210", Verdict.SUSPICIOUS),
        ("serumCreatinine", "1.6", Verdict.NORMAL_A),
        ("serumCreatinine", "1.7", Verdict.SUSPICIOUS),
        ("GFR", "60", Verdict.NORMAL_A),
        ("GFR", "59", Verdict.SUSPICIOUS),
        ("ALT", "52", Verdict.SUSPICIOUS),
        ("osteoporosis", "T-score -0.8", Verdict.NORMAL_A),
        ("osteoporosis", "T-score -1", Verdict.NORMAL_A),
        ("osteoporosis", "T-score -1.4", Verdict.NORMAL_B),
        ("osteoporosis", "T-score -2.5", Verdict.SUSPICIOUS),
        ("bloodPressure", "125/82", Verdict.NORMAL_B),
        ("bloodPressure", "119/79", Verdict.NORMAL_A),
        ("bloodPressure", "120/79", Verdict.NORMAL_B),
        ("bloodPressure", "139/89", Verdict.NORMAL_B),
        ("bloodPressure", "145/92", Verdict.SUSPICIOUS),
        ("bloodPressure", "119/90", Verdict.SUSPICIOUS),
        ("proteinuria", "음성", Verdict.NORMAL_A),
        ("proteinuria", "약양성±", Verdict.NORMAL_B),
        ("proteinuria", "양성(+1)", Verdict.SUSPICIOUS),
        ("chestXrayResult", "정상, 비활동성", Verdict.NORMAL_A),
        ("chestXrayResult", "활동성 의심", Verdict.SUSPICIOUS),
    ],
)
def test_judge(metric, value, expected, references):
    assert judge(metric, value, references).verdict == expected


def test_gender_split_metric_is_confirmed_only_when_both_agree(references):
    assert judge("hemoglobin", "15.0", references).verdict == Verdict.NORMAL_A
    assert judge("yGPT", "25", references).verdict == Verdict.NORMAL_A
    assert judge("waists", "91", references).verdict == Verdict.SUSPICIOUS

    held = judge("hemoglobin", "12.5", references)
    assert held.verdict == Verdict.UNKNOWN
    assert held.by_gender == {"남": Verdict.NORMAL_B, "여": Verdict.NORMAL_A}
    assert "성별" in held.note


def test_metrics_without_reference_are_not_judged(references):
    assert judge("height", "175", references).verdict == Verdict.UNKNOWN
    assert judge("vision", "1.0/0.8", references).verdict == Verdict.UNKNOWN


def test_unreadable_values_do_not_crash(references):
    assert judge("BMI", "측정불가", references).verdict == Verdict.UNKNOWN
    assert judge("bloodPressure", "높음", references).verdict == Verdict.UNKNOWN


def test_judge_all_patient_1_is_normal_except_gender_dependent_and_unreferenced():
    data = PatientRepository(settings.data_dir).get("1")

    verdicts = judge_all(data.overviewList[0], data.referenceList)

    assert verdicts["bloodPressure"].verdict == Verdict.NORMAL_B
    assert verdicts["waists"].verdict == Verdict.UNKNOWN  # 남 정상 / 여 질환의심
    unknown_ok = {"height", "weight", "vision", "hearing", "waists"}
    for key, judgement in verdicts.items():
        if key not in unknown_ok and key != "bloodPressure":
            assert judgement.verdict == Verdict.NORMAL_A, key
