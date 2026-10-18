# Continuous improvement: benchmark -> decision -> change -> re-measure (spec 15.2.7)

A recurring process, not a one-off report. Once a week a scheduled workflow measures retrieval quality on a fixed real corpus, compares it with the committed baseline, and says
what to change; a human applies the change on a branch and the next cycle proves whether it helped.

## The loop

| Step | Who | What | Tool |
|---|---|---|---|
| 1. Measure | scheduled (Mondays 04:17 UTC) or `workflow_dispatch` | disposable PostgreSQL + Redis, API + worker on the runner, 155 FastAPI documentation pages indexed with the local embedding model, 50 questions with a known source page (15 held out), 8 retrieval configurations scored (Recall@1/3/5/10, MRR, NDCG@10) with the production retrieval code | `.github/workflows/continuous-improvement.yml`, `scripts/continuous_improvement_cycle.py run` |
| 2. Judge | same job | guardian thresholds of `agents.md` (Recall@5 < 0.80 / 0.70, Recall@10 < 0.85 / 0.75, MRR < 0.75 / 0.65, NDCG < 0.70 / 0.60), regression against the baseline (> 0.02 drop on any metric), improvement candidates (MRR +0.03 or more on another configuration without losing Recall@10, checked on the held-out split) | `continuous_improvement_cycle.py compare` |
| 3. Report | same job | dated Markdown + JSON as a workflow artifact; a GitHub issue is opened when the verdict is not healthy, with the report as its body | `gh issue create` |
| 4. Decide | a person | read the issue; adopt a candidate only if it is confirmed on the held-out questions; otherwise reject it in the issue with the reason | the report text |
| 5. Change | a person (or Bob, `agents.md` CHANGELAB) | branch `bob/auto-fix-*`, apply the change, `pytest tests/`, run the cycle locally against the branch (`run` then `compare`), commit with the measured numbers | `scripts/continuous_improvement_cycle.py`, `ruff`, `pytest` |
| 6. Lock in | a person | merge after review; refresh `docs/project-handover/e2e_evidence/retrieval_baseline.json` from the new full run (with the LLM configurations, locally) so the next cycle compares against the new reality; log the decision in `ROADMAP.md` under `[Bob-Auto-Fixes]` | `measure_retrieval_baseline.py` |

The workflow **proposes**; it never edits code, never pushes, never opens a pull request, and uses throw-away values only (no repository secret).

## Input from real usage

User feedback becomes evaluation questions through `POST /organizations/{id}/feedback/to-evaluation` (negative feedback with a correction), so the question set grows
from real failures. Add the exported questions to `data/test_set.json` (with their expected source document) when they are reviewed; the next cycle then measures them.

## What the numbers mean (and do not)

- They describe this corpus (technical documentation in English), this embedding model and this machine. They are a regression and tuning signal, not a general quality claim.
- The weekly job runs without a local LLM (`--no-llm`): HyDE, multi-query and MMR are measured only in the local full run (Ollama), which is the one that refreshes the baseline.
- The committed baseline is itself below the guardian thresholds on its default configuration (Recall@10 0.70 against a critical line of 0.75): the default retrieval settings
  (score threshold 0.5, top_k 5) discard relevant pages, and the report states it every week until the default is changed. That is the first improvement the loop proposes.

## Run it by hand

```
. scripts/test_env/e2e_stack_env.sh                      # disposable local stack, see docs/project-handover
python scripts/continuous_improvement_cycle.py run --base http://127.0.0.1:8010 --run-out retrieval_run.json            # add --no-llm without Ollama
python scripts/continuous_improvement_cycle.py compare --current retrieval_run.json                                    # exit 0 healthy, 1 warning/regression, 2 critical
```

First real turn on this machine: see `docs/operations/improvement/` (the dated reports) and `docs/project-handover/e2e_evidence/infra_registry.json`.
