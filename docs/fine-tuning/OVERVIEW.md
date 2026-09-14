# Fine-tuning (Partie 24)

Real, honest scope note first: a pre-build audit found real chat-
completion provider config, a real, mature Evaluation Lab, and a real
dataset-import precedent already built. None of it directly covers
provider fine-tuning submission itself -- this part closes that real
gap, reusing everything else.

## What already existed (reused as-is)

- `api/services/llm_providers.py`'s provider config
  (`OPENAI_API_KEY`/`MISTRAL_API_KEY`, etc.) -- reused directly for
  real provider authentication.
- The Evaluation Lab (`EvaluationDataset`/`EvaluationQuestion`,
  `create_evaluation_job`/`run_evaluation_job`, Partie 7.1-7.2) -- a
  fine-tuned model is evaluated as just another real, candidate
  `model_config` (`{"provider", "model"}`), exactly like any other
  candidate LLM configuration this codebase's own comparison jobs
  already test. No second, parallel evaluation engine.
- `api/services/document_storage.py`'s S3 client/key-scheme/"raise a
  clear ValueError" conventions -- reused for dataset storage.
- `httpx`, already a core dependency, reused directly for real
  provider REST calls -- same convention as every other paid
  third-party integration in this codebase (Twilio, Airbyte, Slack).

## What Partie 24 adds (the genuine gap)

- **`FineTuningDataset`**: real JSONL upload + validation (chat
  `messages` schema, min/max example counts) -- a genuinely new
  validator; no line-delimited-JSON validator existed anywhere before
  this part (`document_storage.py`'s own JSON detection requires the
  WHOLE file to be one JSON document, which real JSONL is not).
- **`FineTuningJob`**: real submission to OpenAI/Mistral's own real
  fine-tuning REST APIs, real status polling, real cancellation.
- **`FineTunedModel`**: created automatically once a real job succeeds
  (the provider's own real, returned model id), with real deploy/
  undeploy toggling.
- **`FineTuningEvaluation`**: a real, thin summary row over a real
  Evaluation Lab run.

See `DATASETS.md`, `JOBS.md`, `MODELS.md`, and `EVALUATION.md` for the
real detail on each piece.

## A real, honest, documented gap: Anthropic

Anthropic does not expose a public, standard-tier fine-tuning REST API
the way OpenAI (`/v1/fine_tuning/jobs`) and Mistral (`/v1/fine_tuning/jobs`)
do. `FINE_TUNING_SUPPORTED_PROVIDERS = ("openai", "mistral")` --
submitting a job with `provider="anthropic"` raises a real, clear
`ProviderNotSupportedError` upfront, the same documented-gap style
`api/services/embedding_config.py` already uses for embedding
providers it can't actually serve. Never a fabricated "submitted" job
for a provider this codebase cannot really reach.

## No real provider credentials in this environment

This part's own pre-build audit confirmed `OPENAI_API_KEY`/
`MISTRAL_API_KEY` default to empty strings, with no test fixture
setting real ones anywhere. Same real, established pattern as Stripe/
ElevenLabs elsewhere in this codebase: every real function fails with
a clear, honest error when its own required key is missing, and the
test suite mocks the real `httpx` boundary with response bodies shaped
exactly like each provider's own real, documented API (never a
fabricated guess at what a live call would return).

## Config

`FINE_TUNING_ENABLED`, `FINE_TUNING_MAX_DATASET_SIZE` (MB),
`FINE_TUNING_MIN_EXAMPLES`, `FINE_TUNING_MAX_EXAMPLES`,
`FINE_TUNING_DEFAULT_PROVIDER`, `FINE_TUNING_DEFAULT_BASE_MODEL`,
`FINE_TUNING_SUPPORTED_PROVIDERS` (`api/config.py`).
