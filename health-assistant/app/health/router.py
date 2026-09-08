"""GET /api/health/{patientId}"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.health.models import HealthResponse
from app.health.repository import PatientRepository

router = APIRouter(prefix="/api/health", tags=["health"])


def get_repository(request: Request) -> PatientRepository:
    return request.app.state.repository


Repository = Annotated[PatientRepository, Depends(get_repository)]


@router.get(
    "/{patientId}",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    responses={404: {"description": "환자 없음"}},
)
def get_health(patientId: str, repo: Repository):
    # 경로 변수 이름은 안내서 표기(patientId)를 그대로 따른다. 문서 화면에 그대로 보이기 때문이다
    data = repo.get(patientId)
    if data is None:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"patient not found: {patientId}"},
        )
    return HealthResponse(data=data)
