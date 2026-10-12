# Phase 6 — real-model tests against a local Ollama (2026-10-12)

Setup: Docker `rag-test-ollama` (CPU only, NVIDIA driver 546.18 < 550), models `qwen2.5:7b`, `qwen2.5:3b`, `nomic-embed-text`. No paid API and no production service used.
Command: `RUN_REAL_LLM_TESTS=1 LOCAL_LLM_BASE_URL=http://127.0.0.1:11434 LOCAL_LLM_MODEL=qwen2.5:7b pytest tests/llm_optin -q`

## Executed results
| What | Result |
|---|---|
| Prompt-injection detector, classifier + qwen2.5:7b (`scripts/measure_injection_two_stage.py`, timeout 120 s, model preloaded, 538 s) | classifier only: recall 0.953 (41/43), false positives 0.122 (6/49); classifier + LLM: recall 0.930 (40/43), false positives 0.020 (1/49). Target recall >= 0.90 and FP <= 0.03: met. Earlier 3B: 0.930 / 0.082 (not met). |
| `tests/llm_optin` on 7B | 19 passed, 2 skipped (the 2 skipped need a paid Anthropic key, not run) |
| Agent orchestrator: plain run, answer grounded on retrieved chunks with another tenant's conflicting chunk present, function-calling loop with the calculator, autonomous agent plan + execution, streaming chat, streaming tool loop, Ollama embeddings, unknown embedding model | all passed |
| Tool loop stability on the real 7B after the fix | 5 runs out of 5 passed (before: 1 run in 3 failed) |
| Deterministic regression of touched areas (agents, LLM, embeddings, streaming, chat, tools, retrieval, generation, autonomous: 54 files) | 859 passed |

## Product defects found by the real runs and fixed (each with a test that fails without the fix)
1. **Ollama embeddings crashed** (`'dict' object has no attribute 'index'`): `api/services/embedding_providers.py`, `tests/test_embedding_dict_response.py`.
2. **Agent failed when the model re-requested a tool call it already had the result of** (all 8 iterations burnt): the repeated call is no longer run, the model is told to answer from the results, without tools. Same in the streaming loop. `api/services/agent_orchestrator.py`, `tests/test_agent_repeated_tool_call.py` (3 of 4 fail without the fix, the 4th is the control).
3. **Streaming tool calls on Ollama came back as plain text** (`ollama/` -> /api/generate): models are now sent as `ollama_chat/` (/api/chat), legacy `ollama/xxx` names converted. `api/services/llm_providers.py`, `tests/test_ollama_model_prefix.py`.

## Limits (not hidden)
- Ollama has no embedding provider in the product (only openai, voyage, cohere, sentence-transformers, huggingface); the Ollama embedding test exercises the shared call site, not a user-selectable provider, and the stored vectors are 384-d, so nomic (768-d) is not storable.
- Small models are non-deterministic: the tests assert what the product does with the model output, with LLM-based tool selection (the default) left on.
- CPU-only 7B: about 150 s to load, 30-170 s per agent test.
- Not tested with a real model: voice agents, workflows with LLM blocks, the Eval Lab judge, hosted providers (Anthropic, OpenAI, Mistral...).
