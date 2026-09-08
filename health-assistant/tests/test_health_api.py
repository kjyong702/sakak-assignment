from pathlib import Path

from app.config import settings
from app.health.models import METRIC_KEYS, HealthData
from app.health.repository import PatientRepository


async def test_returns_spec_shape(client):
    response = await client.get("/api/health/1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert set(data) == {"patientName", "overviewList", "referenceList", "resultList"}
    assert data["patientName"] == "홍길동"
    overview = data["overviewList"][0]
    assert set(overview) == {"checkupDate", *METRIC_KEYS, "evaluation"}
    assert overview["bloodPressure"] == "125/82"
    assert data["resultList"][0]["questionnaire"] == []


async def test_reference_rows_keep_only_keys_in_spec(client):
    refs = (await client.get("/api/health/1")).json()["data"]["referenceList"]

    assert [r["refType"] for r in refs] == ["단위", "정상(A)", "정상(B)", "질환의심"]
    unit, _, normal_b, suspicious = refs
    assert unit["vision"] == ""  # 빈 문자열은 값이므로 남는다
    assert "height" not in normal_b  # 안내서에 없는 키는 만들지 않는다
    assert suspicious["bloodPressure"] == "140이상 또는 /90이상"


async def test_unknown_patient_returns_404_with_error_status(client):
    response = await client.get("/api/health/999")

    assert response.status_code == 404
    assert response.json() == {"status": "error", "message": "patient not found: 999"}


async def test_id_with_disallowed_characters_is_not_found(client):
    response = await client.get("/api/health/환자1")

    assert response.status_code == 404


def test_repository_rejects_path_like_ids(tmp_path: Path):
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    repo = PatientRepository(tmp_path / "patients")

    assert repo.get("../secret") is None
    assert repo.get("..") is None


def test_every_patient_file_matches_schema():
    repo = PatientRepository(settings.data_dir)

    ids = repo.ids()
    assert ids == ["1", "2"]
    for patient_id in ids:
        assert isinstance(repo.get(patient_id), HealthData)
