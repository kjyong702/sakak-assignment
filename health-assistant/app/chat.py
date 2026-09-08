"""터미널 대화. 서버를 따로 띄우지 않고 앱을 직접 만들어 그래프를 돌린다.

uv run python -m app.chat                       # 환자 1, 기본 모델, 대화 모드
uv run python -m app.chat --patient 2 --model gemma3:4b
uv run python -m app.chat -q "콜레스테롤 수치가 어때요?"   # 한 번만 묻고 종료
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.agent.health_client import PatientNotFound
from app.agent.llm import LLMUnavailable
from app.agent.service import AnswerResult, HealthAssistant
from app.main import create_app


def format_result(result: AnswerResult) -> str:
    metrics = ", ".join(result.metric_keys) if result.metric_keys else "전체"
    verified = "통과" if result.verified else f"미통과 ({result.verification})"
    meta = (
        f"항목: {metrics} / 검증: {verified} / 시도 {result.attempts}회 / "
        f"모델 {result.model} / LLM {result.llm_ms / 1000:.1f}초"
    )
    return f"답변: {result.answer}\n({meta})"


async def ask_and_print(assistant: HealthAssistant, patient_id: str, question: str, model: str | None) -> int:
    try:
        result = await assistant.ask(patient_id, question, model)
    except PatientNotFound as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    except LLMUnavailable as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    print(format_result(result))
    return 0


async def run(args: argparse.Namespace) -> int:
    assistant: HealthAssistant = create_app().state.assistant
    model = args.model or assistant.default_model
    if args.question:
        return await ask_and_print(assistant, args.patient, args.question, model)

    print(f"[환자 {args.patient} / 모델 {model}] 질문을 입력하세요. 종료는 빈 줄이나 Ctrl+C")
    while True:
        try:
            question = input("질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            return 0
        code = await ask_and_print(assistant, args.patient, question, model)
        if code == 2:
            return code
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="건강검진 결과 Q&A")
    parser.add_argument("--patient", default="1", help="환자 ID (data/patients/*.json)")
    parser.add_argument("--model", default=None, help="Ollama 모델 이름. 비우면 설정의 기본 모델")
    parser.add_argument("-q", "--question", default=None, help="한 번만 묻고 종료")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
