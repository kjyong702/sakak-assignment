"""GET /api/health/{patientId}"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.health.models import HealthResponse
from app.health.repository import PatientRepository

router = APIRouter(prefix="/api/health", tags=["health"])


def get_repository(request: Request) -> PatientRepository:
    return request.app.state.repository


@router.get(
    "/{patient_id}",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    responses={404: {"description": "환자 없음"}},
)
def get_health(patient_id: str, repo: PatientRepository = Depends(get_repository)):
    data = repo.get(patient_id)
    if data is None:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"patient not found: {patient_id}"},
        )
    return HealthResponse(data=data)
