from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan_context(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        # Shutdown: 앱이 들고 있던 HTTP 클라이언트 정리
        await app.state.health_http.aclose()
        if hasattr(app.state.llm, "aclose"):
            await app.state.llm.aclose()
