# Part 7 - Evaluation Lab. Facts read: metric functions in api/services/retrieval_metrics.py (calculate_recall_at_1/3/5/10, calculate_mrr, calculate_ndcg);
# UI pages frontend/app/dashboard/eval (+ components/eval); NO real metric value has ever been produced (audit R-06); no train/held-out split field exists in the evaluation models, schemas or services
# (only A/B traffic_split); no vertical datasets are seeded (tests/eval/dataset_demo.json is the only dataset file).
VC, PI, NI, IU, BE, BR, AM = ("VERIFIED_COMPLETE", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "IMPLEMENTED_UNVERIFIED",
                              "BLOCKED_EXTERNAL", "BROKEN", "AMBIGUOUS_REQUIREMENT")
NOREAL = "no run on a real dataset has produced a baseline (audit R-06)"
RM = "api/services/retrieval_metrics.py"
V = {
"7.1.1": (VC, "MEDIUM", "api/routers/evaluation_datasets.py, api/services/evaluation_datasets.py; UI frontend/app/dashboard/eval/page.tsx, components/eval/DatasetForm.tsx, DatasetList.tsx", "tests/test_evaluation_datasets.py, tests/test_evaluation_datasets_endpoints.py, tests/test_evaluation_idor.py", "IDOR test exists", "none found", "none", "INFO", "none"),
"7.1.2": (VC, "MEDIUM", "api/routers/question_sets.py, api/services/question_sets.py; components/eval/QuestionList.tsx", "tests/test_question_sets.py, tests/test_question_sets_endpoints.py", "org-scoped", "none found", "none", "INFO", "none"),
"7.1.3": (VC, "MEDIUM", "api/services/ground_truth_answers.py", "tests/test_ground_truth_answers.py", "org-scoped", "none found", "none", "INFO", "none"),
"7.1.4": (VC, "MEDIUM", "api/services/ground_truth_documents.py", "tests/test_ground_truth_documents.py", "org-scoped", "none found", "none", "INFO", "none"),
"7.1.5": (VC, "MEDIUM", "api/services/question_difficulty.py", "tests/test_question_difficulty.py", "none", "none found", "none", "INFO", "none"),
"7.1.6": (VC, "MEDIUM", "api/routers/benchmark_versions.py, api/services/benchmark_versions.py", "tests/test_benchmark_versions.py, tests/test_benchmark_versions_endpoints.py", "org-scoped", "none found", "none", "INFO", "none"),
"7.1.7": (NI, "MEDIUM", "none. Searched api/models/evaluation.py, api/schemas/evaluation*.py, services/evaluation_datasets.py, question_sets.py, benchmark_versions.py for train/test/held-out/split fields: only A/B traffic_split found", "none", "n/a", "no tuning versus held-out separation: tuning on a benchmark would leak into the reported score", "none", "MEDIUM", "add a split attribute on questions and enforce held-out use in evaluation runs"),
"7.1.8": (NI, "HIGH", "none. No seeded vertical datasets (FastAPI, Legal, HR, Finance); only tests/eval/dataset_demo.json", "none", "n/a", "verticals absent", "none", "LOW", "build datasets, e.g. from open corpora"),
"7.2.1": (VC, "HIGH", RM + ":59 calculate_recall_at_1", "tests/test_retrieval_metrics.py", "none", NOREAL, "none", "LOW", "produce a baseline"),
"7.2.2": (VC, "HIGH", RM + ":65 calculate_recall_at_3", "tests/test_retrieval_metrics.py", "none", NOREAL, "none", "LOW", "produce a baseline"),
"7.2.3": (VC, "HIGH", RM + ":70 calculate_recall_at_5", "tests/test_retrieval_metrics.py", "none", NOREAL, "none", "LOW", "produce a baseline"),
"7.2.4": (VC, "HIGH", RM + ":75 calculate_recall_at_10", "tests/test_retrieval_metrics.py", "none", NOREAL, "none", "LOW", "produce a baseline"),
"7.2.5": (VC, "HIGH", RM + ":80 calculate_mrr", "tests/test_retrieval_metrics.py", "none", NOREAL, "none", "LOW", "produce a baseline"),
"7.2.6": (VC, "HIGH", RM + ":86 calculate_ndcg", "tests/test_retrieval_metrics.py", "none", NOREAL, "none", "LOW", "produce a baseline"),
"7.2.7": (VC, "MEDIUM", "precision calculation in " + RM, "tests/test_retrieval_metrics.py", "none", NOREAL, "none", "LOW", "produce a baseline"),
"7.2.8": (IU, "MEDIUM", "api/services/faithfulness.py + answer_quality_metrics.py feeding evaluation_results.py", "tests/test_faithfulness.py, tests/test_answer_quality_metrics.py", "none", "score validity not measured against human labels; " + NOREAL, "LLM provider", "MEDIUM", "validate on a labelled set"),
"7.2.9": (IU, "MEDIUM", "answer relevance in api/services/answer_quality_metrics.py", "tests/test_answer_quality_metrics.py", "none", NOREAL, "LLM provider", "MEDIUM", "validate"),
"7.2.10": (IU, "MEDIUM", "api/services/context_relevance.py", "context relevance tests", "none", NOREAL, "LLM provider", "LOW", "validate"),
"7.2.11": (IU, "MEDIUM", "api/services/citation_correctness.py", "tests/test_citation_correctness.py", "none", NOREAL, "none", "LOW", "validate"),
"7.2.12": (IU, "MEDIUM", "api/services/hallucination_rate.py", "tests/test_hallucination_rate.py", "none", NOREAL, "LLM provider", "MEDIUM", "validate with unanswerable questions"),
"7.2.13": (VC, "MEDIUM", "api/services/latency_metrics.py", "tests/test_latency_metrics.py", "none", "none found", "none", "INFO", "none"),
"7.2.14": (VC, "MEDIUM", "api/services/token_usage.py", "tests/test_token_usage.py", "none", "none found", "none", "INFO", "none"),
"7.2.15": (VC, "MEDIUM", "api/services/cost_tracking.py", "tests/test_cost_tracking.py", "none", "price tables may be stale (provider prices change)", "none", "LOW", "review prices periodically"),
"7.3.1": (IU, "MEDIUM", "api/routers/evaluation_jobs.py, api/services/evaluation_jobs.py, api/tasks/evaluation_jobs.py; UI dashboard/eval/[datasetId]/jobs/[jobId]", "tests/test_evaluation_jobs.py, tests/test_evaluation_jobs_endpoints.py", "org-scoped", "jobs run in Celery (no production worker, audit R-02); never run on real data", "Celery worker, LLM provider", "MEDIUM", "run a real job locally and in staging"),
"7.3.2": (VC, "MEDIUM", "api/routers/manual_evaluations.py, api/services/manual_evaluations.py", "tests/test_manual_evaluations.py, tests/test_manual_evaluations_endpoints.py", "org-scoped", "no UI page found for manual scoring", "none", "LOW", "confirm UI"),
"7.3.3": (VC, "MEDIUM", "api/routers/regression_detection.py, api/services/regression_detection.py", "tests/test_regression_detection.py, tests/test_regression.py", "org-scoped", "none found", "none", "INFO", "none"),
"7.3.4": (VC, "MEDIUM", "api/routers/evaluation_comparisons.py, api/services/evaluation_comparisons.py; UI dashboard/eval/runs/[runId]/comparison", "tests/test_evaluation_comparisons.py", "org-scoped", "none found", "none", "INFO", "none"),
"7.3.5": (VC, "MEDIUM", "evaluation_comparisons covers retriever configs", "tests/test_evaluation_comparisons.py", "org-scoped", "retriever-specific test not isolated", "none", "LOW", "add retriever comparison test"),
"7.3.6": (VC, "MEDIUM", "evaluation_comparisons covers reranker configs", "tests/test_evaluation_comparisons.py", "org-scoped", "reranker-specific test not isolated", "none", "LOW", "add reranker comparison test"),
"7.3.7": (VC, "MEDIUM", "evaluation_comparisons covers prompt variants", "tests/test_evaluation_comparisons.py", "org-scoped", "prompt-specific test not isolated", "none", "LOW", "add prompt comparison test"),
"7.3.8": (VC, "MEDIUM", "api/routers/deployment_evaluations.py, api/services/deployment_evaluations.py", "tests/test_deployment_evaluations.py, tests/test_deployment_evaluations_endpoints.py", "org-scoped", "whether a deployment is actually blocked by the gate in the deploy path is not confirmed", "none", "MEDIUM", "trace the gate into agent deployment"),
"7.3.9": (VC, "MEDIUM", "api/services/regression_thresholds.py DEFAULT_REGRESSION_THRESHOLDS; api/routers/regression_thresholds.py", "tests/test_regression_thresholds.py, tests/test_regression_thresholds_endpoints.py", "org-scoped", "default value (spec: 5%) not confirmed by this audit", "none", "LOW", "confirm default threshold"),
"7.3.10": (VC, "MEDIUM", "api/routers/ab_tests.py, api/services/ab_tests.py; UI dashboard/ab-tests pages", "tests/test_ab_tests.py, tests/test_ab_tests_endpoints.py", "org-scoped", "none found", "none", "INFO", "none"),
}
