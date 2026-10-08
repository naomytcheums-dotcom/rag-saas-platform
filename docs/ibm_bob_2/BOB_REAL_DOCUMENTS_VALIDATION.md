# Validation on Bob's Real Documents

## Context

IBM Bob 2.0 created the organization `948f4b6e-0093-4150-b7af-a8d7b59c3235`
("Organisation de bob-lab-v2@rag-saas-test.internal") and uploaded 154 real
FastAPI documents. However, Bob's execution was blocked at Phase 9 by the
MCP scope (`documents:read`) before it could run the closed-loop evaluation.

## What We Found

The 154 documents in Bob's organization were **completed and indexed**:
- 154 documents (status = completed)
- 1534 chunks (already embedded)

What was missing: an **agent** and an **evaluation dataset**.

## Post-Bob Validation on Bob's Real Documents

### Dataset

We mapped the original 50 questions from `data/test_set.json` (the same
dataset Bob was meant to use) to Bob's 154 real documents:

**Result: 50/50 questions matched** (100%)

Each question's `expected_document` was mapped to its real document UUID
in Bob's organization.

### Agent

Created `BOB-LAB-BASELINE-V2` (`457e8ef4-...`) with `top_k=5`, `strategy=hybrid`.

### GUARDIAN Baseline

Ran `run_eval_benchmark` on the 50 questions.
Job ID: `7776f206-95f7-40b7-9bb2-8a7cfe0f7a2f`
**Result: pending completion**

### Findings

- The documents Bob uploaded are REAL and properly indexed
- The 1534 chunks are the real chunks from the 154 real FastAPI documents
- The question → document mapping is 100% (50/50)
- The retrieval uses `all-MiniLM-L6-v2` (Bob's original model)

### Honest Limitations

- The retrieval runs locally because the Render Free instance (512 MB RAM)
  cannot load the HuggingFace embedding model alongside the FastAPI backend.
- This validation is explicitly labeled **Post-Bob Local Validation** and
  is NOT presented as Bob's own execution.
- The closed-loop workflow uses the same MCP tools Bob created.

## Evidence

- Organization: `948f4b6e-0093-4150-b7af-a8d7b59c3235`
- Agent: `457e8ef4-54cc-41e8-9287-3fe44e67407f`
- Dataset: `2e647e29-1590-4f61-ae14-28ec2c85aaaa` (50 questions)
- Job: `7776f206-95f7-40b7-9bb2-8a7cfe0f7a2f`

## Conclusion

IBM Bob 2.0's real documents (154 docs, 1534 chunks) are functional.
The 50-question benchmark is mapped 100% and is being evaluated to
demonstrate the closed-loop RAG improvement workflow.
