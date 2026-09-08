"""LLM 호출. Ollama의 /api/generate 하나만 쓴다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class LLMUnavailable(RuntimeError):
    """Ollama에 연결할 수 없거나 모델이 없을 때. 사용자에게 그대로 보여 줄 메시지를 담는다."""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    total_duration_ms: float = 0.0
    eval_count: int = 0


class LLMClient(Protocol):
    async def generate(self, prompt: str, *, system: str, model: str | None = None) -> LLMResponse: ...


class OllamaGenerateClient:
    DEFAULT_OPTIONS: dict[str, Any] = {"temperature": 0.2, "num_ctx": 8192}

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        http: httpx.AsyncClient | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout_seconds
        self._http = http or httpx.AsyncClient()
        self._options = {**self.DEFAULT_OPTIONS, **(options or {})}

    async def generate(self, prompt: str, *, system: str, model: str | None = None) -> LLMResponse:
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": self._options,
        }
        try:
            response = await self._http.post(
                f"{self._base_url}/api/generate", json=payload, timeout=self._timeout
            )
        except httpx.ConnectError as e:
            raise LLMUnavailable(
                f"Ollama 서버({self._base_url})에 연결할 수 없습니다. 'ollama serve'가 실행 중인지 확인하세요."
            ) from e
        except httpx.TimeoutException as e:
            raise LLMUnavailable(f"Ollama 응답이 {self._timeout:.0f}초 안에 오지 않았습니다.") from e
        if response.status_code == 404:
            raise LLMUnavailable(
                f"모델을 찾을 수 없습니다: {payload['model']}. 'ollama pull {payload['model']}'로 받으세요."
            )
        response.raise_for_status()
        body = response.json()
        return LLMResponse(
            text=body.get("response", "").strip(),
            model=body.get("model", payload["model"]),
            total_duration_ms=body.get("total_duration", 0) / 1_000_000,
            eval_count=body.get("eval_count", 0),
        )

    async def aclose(self) -> None:
        await self._http.aclose()
