from __future__ import annotations

import re
from pathlib import Path

from app.core.settings import get_settings
from app.schemas.health import HealthData

# 파일 경로에 들어가는 값이라 허용 문자를 제한한다
_PATIENT_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _data_dir(data_dir: Path | None) -> Path:
    return data_dir or get_settings().data_dir


def get(patient_id: str, data_dir: Path | None = None) -> HealthData | None:
    """환자 ID로 건강검진 데이터 조회. 없으면 None"""
    if not _PATIENT_ID.fullmatch(patient_id):
        return None
    path = _data_dir(data_dir) / f"{patient_id}.json"
    if not path.is_file():
        return None
    return HealthData.model_validate_json(path.read_text(encoding="utf-8"))


def list_ids(data_dir: Path | None = None) -> list[str]:
    """등록된 환자 ID 목록"""
    return sorted(p.stem for p in _data_dir(data_dir).glob("*.json"))
