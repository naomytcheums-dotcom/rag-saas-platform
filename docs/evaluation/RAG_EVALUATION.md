# RAG evaluation protocol (SQuAD 2.0 and enterprise datasets)

Status 2026-10-10: **the protocol and the tooling exist; no benchmark has been run, so this document contains no result.** Any number must come from
a run that records the fields in "Report" below. SQuAD 2.0 is a public Wikipedia reading-comprehension benchmark: a good score says nothing about
PDFs, tables, OCR, French or private enterprise content, access control or latency. Use it as a regression and sanity check, next to a
domain dataset (clearly marked synthetic or real, never mixed with the public benchmark results).

## What already exists
- Retrieval metrics: `api/services/retrieval_metrics.py` (`calculate_recall_at_1/3/5/10`, `calculate_mrr`, `calculate_ndcg`, `calculate_precision`) over
  `expected_documents = [{"document_id", "relevance_score"}]`; Eval Lab routes (`/organizations/{org_id}/datasets`, `/datasets/{id}/evaluate`, `/jobs/{id}/…`).
- New (Lot E): `api/services/squad_eval.py` — SQuAD v2.0 loader/validator, corpus builder, dataset-row builder, official normalization, EM, F1,
  best-over-gold, abstention precision/recall, `citation_support`. `import_questions(..., verify_documents=True)` /
  `POST /datasets/{id}/questions/import?verify_documents=true` rejects rows whose ground-truth documents do not exist in the organization.

## The five questions evaluated separately
| # | What is measured | Needs | Metric |
|---|---|---|---|
| 1 | Retrieval of the right passage | question → retrieved chunks → their document ids | Recall@1/3/5/10, MRR, NDCG@k (document level; chunk/passage level needs the gold `answer_start` mapped to chunks: not implemented) |
| 2 | Generation from a **correct** context | the gold context handed to the generator | HasAns EM / F1, NoAns accuracy |
| 3 | Generation from the **retrieved** context | the real pipeline end to end | same, compared with #2 (the gap = retrieval loss) |
| 4 | Citation quality | the cited passages | `citation_support` = a cited passage contains a gold answer. Pointing at the right document is **not** counted. Whether the passage *justifies* the answer needs human or LLM-judge annotation: define the method before reporting it |
| 5 | Abstention on unanswerable questions | the 33% `is_impossible` questions | abstention precision, recall, F1 (positive class = "abstained"); a false abstention on an answerable question lowers precision |

## Procedure (reproducible, local, free)
1. Take the SQuAD 2.0 **dev** file (≈ 4 MB, public; check the size and licence before downloading; do not download the train set). Pick a fixed subset by
   article (record the list) so that the run is repeatable and cheap.
2. `corpus = load_squad(json)`; ingest `corpus_documents(corpus)` into a **local throw-away organization on a disposable database**
   (`scripts/run_local_preview.py` and `tests/disposable_pg_guard.py` rules; never the production or Supabase database). Document name = `squad2::<key>`.
3. Map `key → real document id` (query the documents by name), build `questions_for_import(corpus, ids)`, import with `verify_documents=true`.
4. Run the Eval Lab on that dataset for retrieval metrics (#1). For #2-#5 run the generator and collect `{"answer", "abstained"}` per `squad_id`, then
   `score_predictions(corpus, predictions)` (a missing prediction raises: it is never scored as an abstention).
5. Cost control: use a local or free model, or a small paid budget approved in advance (record tokens). Do not call a paid provider from CI.

## Report (every run must state)
Commit SHA; dataset name, version and subset list; number of questions actually evaluated (answerable / unanswerable) and number failed or skipped;
retriever configuration (embedding model and dimension, hybrid on/off, reranker, top-k, thresholds); generator model and parameters; raw per-question results
and the aggregates; failure examples; duration and measured tokens/cost; limits; the exact commands. **Do not write a metric you did not run.**

## Known limits of this tooling
- Document-level retrieval only; `answer_start` is kept in the source file but not used to score passage-level retrieval.
- `import_questions` still stores a single `expected_answer` (the first gold answer); all gold answers stay in the SQuAD file and are used by `squad_eval`.
- The enterprise-domain dataset (synthetic, labelled as such) is not generated yet: BACKLOG.
