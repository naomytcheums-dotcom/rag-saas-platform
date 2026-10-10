# Part 6 - Citations and anti-hallucination. Facts read: response_quality.enrich_response_with_quality_metrics is called from api/services/generation.py and agent_orchestrator.py;
# agent_citation_required / agent_context_only are used by chat_stream.py and the orchestrator; citation_preview.py is not imported anywhere in api/ or frontend/lib.
VC, PI, NI, IU, BE, BR, AM = ("VERIFIED_COMPLETE", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "IMPLEMENTED_UNVERIFIED",
                              "BLOCKED_EXTERNAL", "BROKEN", "AMBIGUOUS_REQUIREMENT")
CIT = "api/routers/citations.py, api/services/citations.py"
UIC = "frontend/components/Citation.tsx, CitationList.tsx, CitationModal.tsx, CitationTooltip.tsx"
RQ = "api/services/response_quality.py (wired in generation.py and agent_orchestrator.py)"
V = {
"6.1.1": (VC, "MEDIUM", CIT + "; " + UIC, "tests/test_citation_chunk.py and citation tests; frontend ChatMarkdown.test.tsx", "citation access is org-scoped (P0 chat isolation)", "end-to-end browser click not run", "none", "INFO", "none"),
"6.1.2": (VC, "MEDIUM", "api/services/citation_documents.py + " + CIT, "citation tests", "org-scoped", "none found", "none", "INFO", "none"),
"6.1.3": (VC, "MEDIUM", "api/services/citation_location.py (page/section)", "tests for citation location", "none", "none found", "none", "INFO", "none"),
"6.1.4": (VC, "MEDIUM", "api/services/citation_url.py", "tests for citation URL", "link targets from stored URLs; open-redirect/XSS handling in UI not re-read", "none found", "none", "LOW", "check link sanitisation in CitationList.tsx"),
"6.1.5": (VC, "MEDIUM", "api/services/citation_chunk.py", "tests/test_citation_chunk.py", "none", "none found", "none", "INFO", "none"),
"6.1.6": (VC, "MEDIUM", "api/services/citation_relevance.py", "tests for citation relevance", "none", "none found", "none", "INFO", "none"),
"6.1.7": (VC, "MEDIUM", "api/services/citation_passage.py; highlight in CitationModal.tsx", "tests for citation passage", "none", "none found", "none", "INFO", "none"),
"6.1.8": (PI, "MEDIUM", "UI hover tooltip frontend/components/CitationTooltip.tsx exists; backend api/services/citation_preview.py (tests/test_citation_preview.py) is imported by no router or UI module", "tests/test_citation_preview.py (service only)", "none", "the preview service is dead code from the app's point of view; the tooltip uses data already in the citation", "none", "LOW", "wire or remove citation_preview"),
"6.1.9": (VC, "MEDIUM", "api/services/citation_secondary.py used by citations.py", "citation tests", "none", "none found", "none", "INFO", "none"),
"6.1.10": (VC, "MEDIUM", "api/services/response_confidence.py used by generation.py and orchestrator", "tests for response confidence", "none", "score calibration never measured", "none", "LOW", "calibrate with Eval Lab"),
"6.2.1": (VC, "HIGH", "api/services/agent_citation_required.py used by chat_stream.py and the orchestrator", "tests/test_agent_citation_required.py", "none", "none found", "none", "INFO", "none"),
"6.2.2": (VC, "HIGH", "api/services/agent_context_only.py used by chat_stream.py and the orchestrator", "tests/test_agent_context_only.py", "none", "compliance by the real LLM not measured", LLMB if False else "LLM provider", "LOW", "measure with SQuAD-style unanswerable set"),
"6.2.3": (VC, "HIGH", "api/services/agent_idk.py used by agent_factory/orchestrator", "tests/test_agent_idk.py", "none", "threshold calibration not measured", "none", "LOW", "calibrate"),
"6.2.4": (VC, "MEDIUM", "api/services/confidence_estimation.py", "confidence tests", "none", "calibration not measured", "none", "LOW", "calibrate"),
"6.2.5": (IU, "MEDIUM", "api/services/unsupported_claims.py via " + RQ, "tests/test_unsupported_claims*.py (heuristics/LLM mocked)", "none", "detection accuracy never measured on real data", "LLM provider", "MEDIUM", "evaluate on a labelled set"),
"6.2.6": (IU, "MEDIUM", "api/services/claim_verification.py via " + RQ, "claim verification tests (mocked)", "none", "accuracy not measured", "LLM provider", "MEDIUM", "evaluate"),
"6.2.7": (IU, "MEDIUM", "api/services/contradiction_detection.py via " + RQ, "contradiction tests (mocked)", "none", "accuracy not measured", "LLM provider", "LOW", "evaluate"),
"6.2.8": (IU, "MEDIUM", "api/services/source_consistency.py via " + RQ, "source consistency tests", "none", "accuracy not measured", "none", "LOW", "evaluate"),
"6.2.9": (IU, "MEDIUM", "api/services/hallucination_detector.py via " + RQ, "hallucination detector tests (mocked)", "none", "accuracy not measured", "LLM provider", "MEDIUM", "evaluate with SQuAD 2.0 and a hallucination set"),
"6.2.10": (IU, "MEDIUM", "api/services/groundedness.py via " + RQ, "groundedness tests", "none", "score meaning not validated", "none", "LOW", "validate"),
"6.2.11": (IU, "MEDIUM", "api/services/faithfulness.py via " + RQ, "faithfulness tests", "none", "score meaning not validated", "none", "LOW", "validate"),
"6.2.12": (PI, "MEDIUM", "frontend/app/dashboard/quality/page.tsx manages quality ALERT rules and history (api calls to /organizations/{id}/quality-alerts); api/routers/quality_dashboard.py exists", "page tests not located", "org-scoped", "page shown manages alert rules; display of per-answer scores (groundedness/faithfulness) in a dashboard not confirmed", "none", "LOW", "confirm scores are visualised"),
}
