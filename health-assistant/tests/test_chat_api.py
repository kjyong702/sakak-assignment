import httpx

from app.agent.llm import LLMUnavailable
from app.agent.service import AnswerResult
from app.chat import format_result
from app.main import create_app
from tests.fakes import FakeLLM


class DownLLM:
    async def generate(self, prompt, *, system, model=None):
        raise LLMUnavailable("Ollama 서버에 연결할 수 없습니다.")


async def post_chat(llm, payload):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(llm=llm)), base_url="http://test"
    ) as c:
        return await c.post("/api/chat", json=payload)


async def test_chat_answers_with_metadata():
    response = await post_chat(
        FakeLLM("총 콜레스테롤 190mg/dL로 정상(A)입니다."),
        {"patientId": "1", "question": "콜레스테롤 수치가 어때요?", "model": "fake-model"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["answer"].startswith("총 콜레스테롤 190")
    assert body["patientName"] == "홍길동" and body["checkupDate"] == "2025-08-15"
    assert body["metrics"] == ["totalCholesterol", "HDLCholesterol", "LDLCholesterol"]
    assert body["verified"] is True and body["attempts"] == 1
    assert body["model"] == "fake-model"  # 요청의 모델이 그대로 LLM에 전달된다


async def test_chat_unknown_patient_is_404():
    response = await post_chat(FakeLLM("x"), {"patientId": "999", "question": "?"})

    assert response.status_code == 404
    assert response.json()["status"] == "error"


async def test_chat_without_llm_is_503_with_actionable_message():
    response = await post_chat(DownLLM(), {"patientId": "1", "question": "혈압?"})

    assert response.status_code == 503
    assert "Ollama" in response.json()["message"]


async def test_chat_rejects_empty_question():
    response = await post_chat(FakeLLM("x"), {"patientId": "1", "question": ""})

    assert response.status_code == 422


def test_format_result_shows_verification_and_timing():
    result = AnswerResult("답", "홍길동", "2025-08-15", [], True, None, 1, "qwen2.5:7b", 8300.0, "ctx")

    text = format_result(result)

    assert text.startswith("답변: 답\n")
    assert "항목: 전체" in text and "검증: 통과" in text and "LLM 8.3초" in text
