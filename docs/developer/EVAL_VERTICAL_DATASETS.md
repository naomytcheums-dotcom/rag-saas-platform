# Vertical evaluation datasets (spec 7.1.8)

`eval_datasets/verticals/` holds four ready-to-import question sets for the Eval Lab: `fastapi.csv`, `legal.csv`, `hr.csv`, `finance.csv` (15 questions each,
columns `question, expected_answer, difficulty, category`). They contain general-knowledge questions with a reference answer, written for this project.

**What they are for:** checking that an agent grounded in documents of that domain answers correctly. Upload the domain documents to the knowledge base
first, then import a set and run an evaluation job. **What they are not:** they do not contain the documents themselves, and 15 questions per domain is a
starting point, not a benchmark: grow them with the questions your own users ask (`POST /organizations/{id}/feedback/to-evaluation`).

Import into an existing dataset:

```
curl -X POST "$API/datasets/$DATASET_ID/questions/import?format=csv" -H "Authorization: Bearer $TOKEN" -F "file=@eval_datasets/verticals/legal.csv"
```

Use `POST /datasets/{id}/questions/assign-split` to keep part of the questions held out, so that the score you report was not tuned on.
