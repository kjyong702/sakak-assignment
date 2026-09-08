from app.services.llm import LLMResponse


class FakeLLM:
    """준비한 답변을 순서대로 돌려주고 마지막 답변은 반복한다. 받은 프롬프트를 기록한다."""

    def __init__(self, *answers: str, model: str = "fake") -> None:
        self._answers = list(answers)
        self.model = model
        self.calls: list[dict] = []

    async def generate(self, prompt: str, *, system: str, model: str | None = None) -> LLMResponse:
        self.calls.append({"prompt": prompt, "system": system, "model": model or self.model})
        text = self._answers.pop(0) if len(self._answers) > 1 else (self._answers[0] if self._answers else "")
        return LLMResponse(text=text, model=model or self.model, total_duration_ms=12.5)
