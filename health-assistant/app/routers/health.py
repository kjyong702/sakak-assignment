from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories import patient
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get(
    "/{patientId}",
    summary="건강검진 데이터 조회",
    description="환자 ID로 건강검진 데이터를 조회합니다. 응답 형식은 안내서의 Response Format과 같습니다.",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    responses={404: {"description": "환자 없음"}},
)
def get_health(patientId: str):
    data = patient.get(patientId)
    if data is None:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"patient not found: {patientId}"},
        )
    return HealthResponse(data=data)
