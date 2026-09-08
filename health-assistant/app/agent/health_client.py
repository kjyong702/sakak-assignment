"""Mock API를 HTTP로 호출해 건강 데이터를 가져온다."""

import httpx

from app.health.models import HealthData, HealthResponse


class PatientNotFound(LookupError):
    def __init__(self, patient_id: str) -> None:
        super().__init__(f"환자를 찾을 수 없습니다: {patient_id}")
        self.patient_id = patient_id


class HealthApiClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        # base_url은 http 클라이언트가 가진다. 테스트는 ASGITransport로 서버 없이 같은 경로를 탄다
        self._http = http

    async def get(self, patient_id: str) -> HealthData:
        response = await self._http.get(f"/api/health/{patient_id}")
        if response.status_code == 404:
            raise PatientNotFound(patient_id)
        response.raise_for_status()
        return HealthResponse.model_validate(response.json()).data
