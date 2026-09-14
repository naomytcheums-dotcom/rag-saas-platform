# Fine-tuning

Full documentation: [`docs/fine-tuning/OVERVIEW.md`](../fine-tuning/OVERVIEW.md),
[`DATASETS.md`](../fine-tuning/DATASETS.md), [`JOBS.md`](../fine-tuning/JOBS.md),
[`MODELS.md`](../fine-tuning/MODELS.md), [`EVALUATION.md`](../fine-tuning/EVALUATION.md).

## Supported providers

OpenAI and Mistral, via direct REST clients
(`api/services/fine_tuning_providers.py`, `httpx`-based, since
litellm's own fine-tuning support doesn't cover Mistral).

## Anthropic is not supported — a real, honest gap

Anthropic does not expose a public, standard-tier fine-tuning REST API.
A job targeting Anthropic is rejected upfront with a clear
`ProviderNotSupportedError`, the same pattern used elsewhere in this
codebase for genuinely unsupported provider/operation combinations
(e.g. `embedding_config.py`). No job is ever fabricated as "submitted"
for a provider the platform can't actually reach.

## Datasets

Uploaded as JSONL, validated line-by-line against a real chat-message
schema before being accepted — see [Datasets](../fine-tuning/DATASETS.md).

## Evaluating a fine-tuned model

Reuses the platform's real Evaluation Lab rather than a separate,
parallel evaluation engine — the fine-tuned model is passed in as a
regular model candidate, exactly like any other model comparison. See
[Evaluation](../fine-tuning/EVALUATION.md).
