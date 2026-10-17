# Part 4 - Multi-LLM and embeddings. Facts read: LLM calls go through litellm (api/services/llm_providers.py); embeddings through api/services/embedding_providers.py
# (OpenAI/Voyage/Cohere via litellm; Sentence Transformers and Hugging Face are the same sentence-transformers mechanism).
VC, PI, NI, IU, BE, BR, AM = ("VERIFIED_COMPLETE", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "IMPLEMENTED_UNVERIFIED",
                              "BLOCKED_EXTERNAL", "BROKEN", "AMBIGUOUS_REQUIREMENT")
LLM = "api/services/llm_providers.py (litellm dispatch), api/services/llm_config.py"
EMB = "api/services/embedding_providers.py, api/services/embedding_config.py"
V = {
"4.1.1": (BE, "MEDIUM", "Anthropic via " + LLM, "tests/test_llm_providers.py mocks litellm.acompletion", "keys per organization (BYOK, api/services/llm_byok.py)", "no real Anthropic call in the audit", "Anthropic API key", "MEDIUM", "run a live smoke test with a funded key"),
"4.1.2": (BE, "MEDIUM", "OpenAI via " + LLM, "tests/test_llm_providers.py (mocked)", "BYOK keys", "no real call", "OpenAI API key", "MEDIUM", "live smoke test"),
"4.1.3": (BE, "MEDIUM", "Gemini via litellm 'gemini/...' prefix in " + LLM, "tests/test_llm_providers.py (mocked)", "BYOK keys", "no real call", "Gemini API key", "MEDIUM", "live smoke test"),
"4.1.4": (BE, "MEDIUM", "Mistral via litellm 'mistral/...' prefix in " + LLM, "tests/test_llm_providers.py (mocked)", "BYOK keys", "no real call", "Mistral API key", "MEDIUM", "live smoke test"),
"4.1.5": (BE, "MEDIUM", "Ollama via litellm 'ollama/...' prefix; no SDK needed", "tests/test_llm_providers.py (mocked)", "outbound base URL must pass the SSRF guard (not re-read)", "no local Ollama server exercised", "Ollama server", "LOW", "test against a local Ollama"),
"4.1.6": (IU, "MEDIUM", "OpenAI-compatible base URL support in " + LLM, "tests/test_llm_providers.py, tests/test_default_models_are_routable.py", "custom base URL is an SSRF vector; confirm the guard (api/services/outbound_http.py) is applied", "guard application not confirmed in this pass", "compatible endpoint", "MEDIUM", "verify SSRF guard on custom base URLs"),
"4.1.7": (VC, "HIGH", "single dispatch layer " + LLM + " plus fallback chain api/services/fallback.py", "tests/test_llm_providers.py, tests/test_fallback.py", "none", "none found", "none", "INFO", "none"),
"4.2.1": (BE, "MEDIUM", "OpenAI embeddings via " + EMB, "tests/test_embedding_providers.py (mocked)", "BYOK keys", "no real call", "OpenAI key", "LOW", "live smoke test"),
"4.2.2": (BE, "MEDIUM", "Voyage embeddings via " + EMB, "tests/test_embedding_providers.py (mocked)", "BYOK keys", "no real call", "Voyage key", "LOW", "live smoke test"),
"4.2.3": (BE, "MEDIUM", "Cohere embeddings via " + EMB, "tests/test_embedding_providers.py (mocked)", "BYOK keys", "no real call", "Cohere key", "LOW", "live smoke test"),
"4.2.4": (VC, "MEDIUM", "sentence-transformers loader get_embedder via " + EMB, "tests/test_embedding_providers.py", "none", "model download on first use; memory on a 512 MB host", "model download", "LOW", "measure memory"),
"4.2.5": (VC, "MEDIUM", "same sentence-transformers mechanism loads any Hugging Face model id (module docstring of embedding_providers.py)", "tests/test_embedding_providers.py", "none", "same as 4.2.4", "model download", "LOW", "none"),
"4.2.6": (VC, "HIGH", "unified interface in " + EMB, "tests/test_embedding_providers.py, tests/test_embedding_dimension_safety.py", "none", "none found", "none", "INFO", "none"),
"4.3.1": (VC, "MEDIUM", "per-organization LLM config: api/models/organization_llm_config.py, " + LLM + ", UI frontend/app/dashboard/settings/llm-config/page.tsx", "tests/test_llm_config.py", "BYOK keys encrypted (secret_encryption.py)", "none found", "none", "INFO", "none"),
"4.3.2": (VC, "HIGH", "temperature (0-2) in api/schemas/organization_settings.py:126, passed to the model call", "tests/test_llm_sampling_params.py", "bounded", "none found", "none", "INFO", "none"),
"4.3.3": (VC, "HIGH", "top_p (0-1) in api/schemas/organization_settings.py:128", "tests/test_llm_sampling_params.py", "bounded", "none found", "none", "INFO", "none"),
"4.3.4": (VC, "MEDIUM", "system prompt in org settings and agent prompts (api/services/agent_prompts.py)", "tests/test_agent_prompts.py, tests/test_llm_config.py", "prompt injection module exists", "none found", "none", "INFO", "none"),
"4.3.5": (VC, "HIGH", "max_tokens in api/schemas/organization_settings.py:139", "tests/test_llm_sampling_params.py", "bounded", "none found", "none", "INFO", "none"),
}
