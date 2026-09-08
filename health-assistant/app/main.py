"""FastAPI 앱. Mock API와 채팅 엔드포인트를 한 프로세스에서 띄운다."""

import httpx
from fastapi import FastAPI

from app.agent.health_client import HealthApiClient
from app.agent.llm import LLMClient, OllamaGenerateClient
from app.agent.router import router as chat_router
from app.agent.service import HealthAssistant
from app.config import settings
from app.health.repository import PatientRepository
from app.health.router import router as health_router


def create_app(llm: LLMClient | None = None) -> FastAPI:
    app = FastAPI(title="Health Checkup AI Assistant", version="0.1.0")
    app.state.repository = PatientRepository(settings.data_dir)
    app.include_router(health_router)

    # 에이전트는 Mock API를 HTTP 계층을 통해 읽는다. 같은 프로세스 안이라 네트워크를 타지 않고
    # ASGI로 직접 부르지만 라우터, 직렬화, 404 처리는 실제 요청과 같은 경로다
    health = HealthApiClient(httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://app"))
    llm = llm or OllamaGenerateClient(
        settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout_seconds
    )
    app.state.assistant = HealthAssistant(health, llm, settings.ollama_model)
    app.include_router(chat_router)
    return app


app = create_app()
