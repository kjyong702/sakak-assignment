import json

import httpx
import pytest

from app.agent.llm import LLMUnavailable, OllamaGenerateClient


def make_client(handler):
    return OllamaGenerateClient(
        base_url="http://ollama:11434",
        model="qwen2.5:7b",
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


async def test_generate_calls_api_generate_without_streaming():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"model": "qwen2.5:7b", "response": " 답변입니다. ", "total_duration": 1_500_000_000, "eval_count": 42, "done": True},
        )

    result = await make_client(handler).generate("질문", system="규칙")

    assert seen["path"] == "/api/generate"
    assert seen["body"]["stream"] is False
    assert seen["body"]["system"] == "규칙" and seen["body"]["prompt"] == "질문"
    assert seen["body"]["options"]["temperature"] == 0.2
    assert result.text == "답변입니다." and result.model == "qwen2.5:7b"
    assert result.total_duration_ms == 1500.0 and result.eval_count == 42


async def test_model_override_per_call():
    seen = {}

    def handler(request):
        seen["model"] = json.loads(request.content)["model"]
        return httpx.Response(200, json={"model": "gemma3:4b", "response": "ok"})

    await make_client(handler).generate("q", system="s", model="gemma3:4b")

    assert seen["model"] == "gemma3:4b"


async def test_connection_error_becomes_llm_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMUnavailable, match="ollama serve"):
        await make_client(handler).generate("q", system="s")


async def test_missing_model_tells_how_to_pull():
    def handler(request):
        return httpx.Response(404, json={"error": "model 'qwen2.5:7b' not found"})

    with pytest.raises(LLMUnavailable, match="ollama pull qwen2.5:7b"):
        await make_client(handler).generate("q", system="s")
