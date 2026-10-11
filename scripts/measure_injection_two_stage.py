"""Measure the two-stage prompt-injection pipeline (classifier gate + language-model second opinion) on tests/data/injection_eval_set.json.

    RAG_ENV_FILE=.no-env PROMPT_INJECTION_CONFIRM_PROVIDER=ollama PROMPT_INJECTION_CONFIRM_MODEL=qwen2.5:3b OLLAMA_BASE_URL=http://127.0.0.1:11434 \
        python scripts/measure_injection_two_stage.py

Prints recall and false-positive rate for the classifier alone and for classifier + second opinion, and lists every item whose outcome changed or is still wrong.
Needs the classifier model in the local Hugging Face cache and a reachable local model server; no paid key is used."""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.services.prompt_injection_detection import detect_prompt_injection_confirmed  # noqa: E402

DATA = json.loads((Path(__file__).resolve().parents[1] / "tests" / "data" / "injection_eval_set.json").read_text(encoding="utf-8"))


async def main() -> None:
    started = time.time()
    rows = []
    for kind in ("attacks", "benign"):
        for text in DATA[kind]:
            result = await detect_prompt_injection_confirmed(text)
            rows.append((kind, text, result))
    attacks = [r for r in rows if r[0] == "attacks"]
    benign = [r for r in rows if r[0] == "benign"]
    stage1_tp = sum(1 for _, _, r in attacks if r["is_injection"] or r.get("overruled_by_llm"))
    stage1_fp = sum(1 for _, _, r in benign if r["is_injection"] or r.get("overruled_by_llm"))
    final_tp = sum(1 for _, _, r in attacks if r["is_injection"])
    final_fp = sum(1 for _, _, r in benign if r["is_injection"])
    print(f"classifier only      : recall={stage1_tp / len(attacks):.3f} ({stage1_tp}/{len(attacks)})  false_positive_rate={stage1_fp / len(benign):.3f} ({stage1_fp}/{len(benign)})")
    print(f"classifier + LLM     : recall={final_tp / len(attacks):.3f} ({final_tp}/{len(attacks)})  false_positive_rate={final_fp / len(benign):.3f} ({final_fp}/{len(benign)})")
    print(f"seconds: {time.time() - started:.0f}")
    for kind, text, r in rows:
        if kind == "attacks" and not r["is_injection"]:
            print("MISSED ATTACK  :", "(cleared by LLM)" if r.get("overruled_by_llm") else "(classifier)", text[:110])
        if kind == "benign" and r["is_injection"]:
            print("STILL FLAGGED  :", r["stage"], text[:110])
        if kind == "benign" and r.get("overruled_by_llm"):
            print("CLEARED BY LLM :", text[:110])


asyncio.run(main())
