"""환자별 JSON 파일에서 건강검진 데이터를 읽는다."""

import re
from pathlib import Path

from app.health.models import HealthData

# 파일 경로에 들어가는 값이라 허용 문자를 제한한다. "../" 같은 입력이 디렉토리 밖으로 나가지 못하게
_PATIENT_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class PatientRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def get(self, patient_id: str) -> HealthData | None:
        if not _PATIENT_ID.fullmatch(patient_id):
            return None
        path = self._data_dir / f"{patient_id}.json"
        if not path.is_file():
            return None
        return HealthData.model_validate_json(path.read_text(encoding="utf-8"))

    def ids(self) -> list[str]:
        return sorted(p.stem for p in self._data_dir.glob("*.json"))
