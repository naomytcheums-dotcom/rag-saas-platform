# Tutorial: Fine-tune a Model

See [Fine-tuning](../advanced/FINE_TUNING.md) first — this only works
for OpenAI or Mistral base models; Anthropic is not supported.

## 1. Prepare your dataset

A JSONL file, one chat example per line:

```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

See [Datasets](../fine-tuning/DATASETS.md) for the exact validation
rules — invalid lines are rejected with a specific error rather than
silently dropped.

## 2. Upload the dataset

```bash
curl -X POST "https://your-instance.example.com/fine-tuning/datasets?org_id=$ORG_ID" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@training_data.jsonl"
```

## 3. Submit the job

```bash
curl -X POST "https://your-instance.example.com/fine-tuning/jobs?org_id=$ORG_ID" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"dataset_id": "...", "base_model": "gpt-4o-mini", "provider": "openai"}'
```

## 4. Track status

The job is polled automatically (Celery, every 10 minutes) — check
status via:

```bash
curl "https://your-instance.example.com/fine-tuning/jobs/$JOB_ID?org_id=$ORG_ID" \
  -H "Authorization: Bearer $API_KEY"
```

## 5. Evaluate and deploy

Once the job succeeds, a `FineTunedModel` is created automatically. Run
it through the Evaluation Lab (see [Evaluation](../fine-tuning/EVALUATION.md))
before deploying it for real use.
