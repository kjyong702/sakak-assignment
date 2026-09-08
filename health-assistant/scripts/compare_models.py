"""후보 모델에 같은 질문 세트를 돌려 답변, 지연, 검증 결과를 남긴다.

    uv run python -m scripts.compare_models                       # 기본 후보 3개
    uv run python -m scripts.compare_models --models qwen2.5:7b   # 일부만
    uv run python -m scripts.compare_models --out docs/model-comparison.md

첫 호출은 모델을 메모리에 올리는 시간이 섞이므로 워밍업 1회를 따로 돌리고 표에서는 뺀다.
답변의 품질(판정 준수, 한국어 자연스러움)은 사람이 읽고 판단한다. 스크립트는 재료만 만든다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# 파일 경로로 직접 실행해도 app 패키지를 찾도록 프로젝트 루트를 경로에 넣는다
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.llm import LLMUnavailable  # noqa: E402
from app.agent.verify import unsupported_numbers  # noqa: E402
from app.main import create_app  # noqa: E402

DEFAULT_MODELS = ("qwen2.5:7b", "llama3.1:8b", "gemma3:4b")

# (환자, 질문, 무엇을 보는가)
QUESTIONS: tuple[tuple[str, str, str], ...] = (
    ("1", "최근 건강검진 결과는 어때요?", "안내서 예시 1. 전체 요약과 정상(B) 혈압 언급"),
    ("1", "콜레스테롤 수치가 어때요?", "안내서 예시 2. 총/HDL/LDL 수치와 단위 인용"),
    ("2", "혈압이 괜찮은가요?", "질환의심 145/92를 진단 없이 상담 권고로"),
    ("2", "간 수치는 어떤가요?", "ALT 52 질환의심, AST 38 정상, 감마 40 보류를 구분"),
    ("2", "작년과 비교해서 어떻게 달라졌나요?", "이전 검진 포함. 두 시점 수치를 섞지 않는가"),
    ("1", "저 당뇨인가요?", "혈당 95 정상(A). 진단 단정 금지"),
)


@dataclass
class Row:
    model: str
    patient_id: str
    question: str
    focus: str
    answer: str
    llm_ms: float
    wall_ms: float
    attempts: int
    verified: bool
    unsupported: list[str]
    error: str | None = None


async def run_model(assistant, model: str) -> tuple[float | None, list[Row]]:
    started = time.perf_counter()
    try:
        await assistant.ask("1", "혈압 어때요?", model)  # 워밍업. 모델 로딩 시간을 표에서 뺀다
    except LLMUnavailable as e:
        print(f"[{model}] 건너뜀: {e}", file=sys.stderr)
        return None, []
    load_ms = (time.perf_counter() - started) * 1000

    rows = []
    for patient_id, question, focus in QUESTIONS:
        started = time.perf_counter()
        try:
            result = await assistant.ask(patient_id, question, model)
        except LLMUnavailable as e:
            rows.append(Row(model, patient_id, question, focus, "", 0, 0, 0, False, [], str(e)))
            continue
        wall_ms = (time.perf_counter() - started) * 1000
        rows.append(
            Row(
                model=result.model,
                patient_id=patient_id,
                question=question,
                focus=focus,
                answer=result.answer,
                llm_ms=result.llm_ms,
                wall_ms=wall_ms,
                attempts=result.attempts,
                verified=result.verified,
                unsupported=unsupported_numbers(result.answer, result.context),
            )
        )
        print(f"[{model}] {question} -> {wall_ms / 1000:.1f}s, 시도 {result.attempts}, 검증 {'통과' if result.verified else '미통과'}", file=sys.stderr)
    return load_ms, rows


def render_report(results: dict[str, tuple[float | None, list[Row]]]) -> str:
    lines = ["# 모델 비교", "", "같은 질문 6개를 후보 모델에 돌린 결과. 수치는 실측이고 품질 판단은 아래 표 다음의 메모에 적는다.", ""]
    lines += ["## 요약", "", "| 모델 | 첫 호출(로딩 포함) | 평균 LLM 시간 | 평균 전체 시간 | 검증 통과 | 재생성 | 근거 없는 수치 |", "|---|---|---|---|---|---|---|"]
    for model, (load_ms, rows) in results.items():
        if not rows:
            lines.append(f"| {model} | 실행 실패 | | | | | |")
            continue
        ok = [r for r in rows if r.error is None]
        avg_llm = sum(r.llm_ms for r in ok) / len(ok) / 1000 if ok else 0
        avg_wall = sum(r.wall_ms for r in ok) / len(ok) / 1000 if ok else 0
        verified = sum(r.verified for r in ok)
        retries = sum(r.attempts - 1 for r in ok)
        bad = sum(len(r.unsupported) for r in ok)
        load = f"{load_ms / 1000:.1f}s" if load_ms is not None else "-"
        lines.append(f"| {model} | {load} | {avg_llm:.1f}s | {avg_wall:.1f}s | {verified}/{len(ok)} | {retries} | {bad} |")
    lines += ["", "## 질문별 답변", ""]
    for i, (patient_id, question, focus) in enumerate(QUESTIONS, 1):
        lines += [f"### {i}. 환자 {patient_id}: {question}", "", f"보는 점: {focus}", ""]
        for model, (_, rows) in results.items():
            row = next((r for r in rows if r.question == question and r.patient_id == patient_id), None)
            if row is None:
                continue
            if row.error:
                lines += [f"**{model}**: 실패 ({row.error})", ""]
                continue
            note = f"{row.wall_ms / 1000:.1f}s, 시도 {row.attempts}회, 검증 {'통과' if row.verified else '미통과'}"
            if row.unsupported:
                note += f", 근거 없는 수치: {', '.join(row.unsupported)}"
            lines += [f"**{model}** ({note})", "", "> " + row.answer.replace("\n", "\n> "), ""]
    lines += ["## 품질 메모", "", "(답변을 읽고 적는다: 판정을 따랐는가, 단위를 인용했는가, 진단을 단정하지 않았는가, 한국어가 자연스러운가)", ""]
    return "\n".join(lines)


async def main(args: argparse.Namespace) -> int:
    assistant = create_app().state.assistant
    results: dict[str, tuple[float | None, list[Row]]] = {}
    for model in args.models:
        results[model] = await run_model(assistant, model)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(results), encoding="utf-8")
    raw = out.with_suffix(".json")
    raw.write_text(
        json.dumps({m: {"load_ms": load, "rows": [asdict(r) for r in rows]} for m, (load, rows) in results.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"보고서: {out}\n원본: {raw}")
    return 0 if any(rows for _, rows in results.values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="후보 모델 비교")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--out", default="docs/model-comparison.md")
    sys.exit(asyncio.run(main(parser.parse_args())))
