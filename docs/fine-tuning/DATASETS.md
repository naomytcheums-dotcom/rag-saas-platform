# Datasets

## Format

Real JSONL (line-delimited JSON) only today -- `.csv`/`.parquet`
(named in the model's own `format` column) are real, stated future
work, not silently faked. Each real line must be a real JSON object
with a `messages` array, each real message carrying a real `role`
(`system`/`user`/`assistant`) and non-empty `content`:

```jsonl
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

## Upload and validation

`POST /fine-tuning/datasets?org_id=...` (multipart: `name`,
`description?`, `dataset_type?`, `file`) -- real, upfront checks
before anything touches S3: file extension (`.jsonl` only), real size
cap (`FINE_TUNING_MAX_DATASET_SIZE`, default 100MB). Then real,
line-by-line validation (`validate_jsonl_dataset`): a real malformed
line 400 of 5000 is reported, not silently dropped or aborting the
other 4999 real, valid ones.

**A real, deliberate choice**: a dataset with SOME invalid lines is
still stored (`status="error"`, real `validation_errors` populated),
never rejected outright -- the uploader can see exactly what's wrong
and fix it, rather than re-uploading blind. `POST
/fine-tuning/datasets/{id}/validate` re-runs the same real check
against the already-stored file (e.g. after fixing
`FINE_TUNING_MIN_EXAMPLES` config, or just to re-confirm before
submitting a real job).

## Storage

Reuses `document_storage.py`'s own real, private S3 bucket
(`S3_DOCUMENTS_BUCKET_NAME`), under a real, separate `fine-tuning/`
key prefix (`fine-tuning/{organization_id}/{dataset_id}/{filename}`).

## Endpoints

- `GET /fine-tuning/datasets?org_id=...` -- list.
- `GET /fine-tuning/datasets/{id}` -- one dataset.
- `DELETE /fine-tuning/datasets/{id}` -- real S3 object + row deletion.
- `POST /fine-tuning/datasets/{id}/validate` -- re-validate.
