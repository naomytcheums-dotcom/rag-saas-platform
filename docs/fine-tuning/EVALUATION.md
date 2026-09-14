# Evaluation

## Real reuse, not a second engine

`POST /fine-tuning/models/{id}/evaluate` (`{dataset_id}` -- a real,
EXISTING `EvaluationDataset` id, Partie 7.1.1, not a
`FineTuningDataset`) is a real, thin wrapper:

1. `create_evaluation_job(db, dataset_id, model_config={"provider":
   model.provider, "model": model.provider_model_id})` -- the fine-
   tuned model is passed as a real, candidate LLM configuration,
   exactly like any other real candidate this codebase's own
   comparison jobs (Partie 7.3) already test.
2. `run_evaluation_job` -- the real, existing Evaluation Lab engine
   answers every real question in the dataset using the real
   fine-tuned model, computing every real Partie 7.2 metric
   (`answer_relevance`, `faithfulness`, ...).
3. A real `FineTuningEvaluation` row summarizes the run: `score` is
   the real average `answer_relevance` across every real result
   (the closest real, single scalar this codebase already computes to
   "how good was this model's own real answer"), `metrics` carries the
   real result count.

The full, real, per-question detail stays in the real
`EvaluationResult`/`EvaluationJob` rows this reuses -- `FineTuningEvaluation`
is a summary, not a duplicate.

## Endpoints

- `POST /fine-tuning/models/{id}/evaluate` -- real, synchronous (runs
  inline). `evaluate_fine_tuned_model` (Celery) is available
  separately for a real, large evaluation dataset a caller doesn't
  want to wait on inline.
- `GET /fine-tuning/models/{id}/evaluations` -- every real evaluation
  this model has had, most recent first.
