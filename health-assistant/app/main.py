"""FastAPI 앱. Mock API와 채팅 엔드포인트를 한 프로세스에서 띄운다."""

from fastapi import FastAPI

from app.config import settings
from app.health.repository import PatientRepository
from app.health.router import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Health Checkup AI Assistant", version="0.1.0")
    app.state.repository = PatientRepository(settings.data_dir)
    app.include_router(health_router)
    return app


app = create_app()
