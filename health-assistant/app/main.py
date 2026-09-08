from __future__ import annotations

import httpx
from fastapi import FastAPI

from app.core.lifespan import lifespan_context
from app.core.settings import get_settings
from app.repositories.health_api import HealthApiClient
from app.routers.chat import router as chat
from app.routers.health import router as health
from app.services.assistant import HealthAssistant
from app.services.llm import LLMClient, OllamaGenerateClient


def create_app(llm: LLMClient | None = None) -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan_context,
    )

    # Routers
    app.include_router(health)
    app.include_router(chat)

    # 에이전트가 Mock API를 읽는 HTTP 클라이언트. 같은 프로세스의 ASGI 앱을 직접 부른다
    app.state.health_http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://app")
    app.state.llm = llm or OllamaGenerateClient(
        settings.ollama_base_url, settings.ollama_model, settings.ollama_timeout_seconds
    )
    app.state.assistant = HealthAssistant(
        HealthApiClient(app.state.health_http), app.state.llm, settings.ollama_model
    )
    return app


app = create_app()
