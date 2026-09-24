// Phase 5, Étape 14 -- Eval Lab UI client, wired to the REAL, already-
// existing backend surface (api/routers/evaluation_datasets.py,
// evaluation_jobs.py, evaluation_results.py -- Partie 7.1-7.3), not
// the illustrative `/eval/*` paths from this étape's own spec: this
// codebase's real, established convention is org-scoped creation
// (`/organizations/{org_id}/datasets`) then flat resource-id paths
// for everything nested under it (`/datasets/{id}`, `/jobs/{id}/...`),
// same shape as lib/services/ab-tests.ts.

import { api, fileUrl } from "@/lib/api";

export interface EvalDataset {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  version: number;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvalDatasetListResponse {
  items: EvalDataset[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvalQuestion {
  id: string;
  dataset_id: string;
  question: string;
  expected_answer: string | null;
  expected_documents: Record<string, unknown>[] | null;
  difficulty: string | null;
  category: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface EvalQuestionListResponse {
  items: EvalQuestion[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvalJob {
  id: string;
  dataset_id: string;
  question_set_id: string | null;
  agent_id: string | null;
  model_config: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  total_questions: number;
  completed_questions: number;
  results: { result_ids: string[]; total_questions: number; completed_questions: number; failed_questions: number } | null;
  error: string | null;
  created_by: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface EvalJobListResponse {
  items: EvalJob[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvalResult {
  id: string;
  question_id: string;
  agent_id: string | null;
  evaluation_job_id: string | null;
  model_config_json: Record<string, unknown>;
  retrieved_documents: Record<string, unknown>[];
  retrieved_chunks: Record<string, unknown>[];
  actual_answer: string;
  metrics: Record<string, number | boolean | Record<string, unknown> | null>;
  latency_ms: number;
  created_at: string;
}

export interface EvalResultListResponse {
  items: EvalResult[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvalFailure {
  id: string;
  evaluation_job_id: string;
  question_id: string;
  category: "retrieval" | "generation" | "other";
  error: string;
  created_at: string;
}

export interface EvalFailureListResponse {
  items: EvalFailure[];
  total: number;
}

export interface EvalFailureCategories {
  retrieval: number;
  generation: number;
  other: number;
  hallucination: number;
}

// -- Datasets ---------------------------------------------------------------

export const listDatasets = (orgId: string, limit = 50, offset = 0) =>
  api.get<EvalDatasetListResponse>(`/organizations/${orgId}/datasets?limit=${limit}&offset=${offset}`);

export const createDataset = (orgId: string, data: { name: string; description?: string }) =>
  api.post<EvalDataset>(`/organizations/${orgId}/datasets`, data);

export const getDataset = (id: string) => api.get<EvalDataset>(`/datasets/${id}`);

export const updateDataset = (id: string, data: Partial<Pick<EvalDataset, "name" | "description" | "is_active">>) =>
  api.patch<EvalDataset>(`/datasets/${id}`, data);

export const deleteDataset = (id: string) => api.delete(`/datasets/${id}`);

// -- Questions (test cases) --------------------------------------------------

export const listQuestions = (datasetId: string, limit = 50, offset = 0) =>
  api.get<EvalQuestionListResponse>(`/datasets/${datasetId}/questions?limit=${limit}&offset=${offset}`);

export const createQuestion = (datasetId: string, data: {
  question: string; expected_answer?: string; difficulty?: string; category?: string;
}) => api.post<EvalQuestion>(`/datasets/${datasetId}/questions`, data);

export const updateQuestion = (id: string, data: Partial<Pick<EvalQuestion, "question" | "expected_answer" | "difficulty" | "category">>) =>
  api.patch<EvalQuestion>(`/questions/${id}`, data);

export const deleteQuestion = (id: string) => api.delete(`/questions/${id}`);

export interface QuestionImportResult {
  imported: number;
  errors: string[];
}

export const importQuestions = (datasetId: string, file: File, format: "json" | "csv" = "json") =>
  api.postFile<QuestionImportResult>(`/datasets/${datasetId}/questions/import?format=${format}`, file);

export function exportQuestionsUrl(datasetId: string, format: "json" | "csv"): string {
  return fileUrl(`/datasets/${datasetId}/questions/export?format=${format}`);
}

// -- Jobs (runs) --------------------------------------------------------------

export const listJobs = (datasetId: string, limit = 50, offset = 0) =>
  api.get<EvalJobListResponse>(`/datasets/${datasetId}/jobs?limit=${limit}&offset=${offset}`);

export const createJob = (datasetId: string, data: { question_set_id?: string; agent_id?: string; model_config_override?: Record<string, unknown> } = {}) =>
  api.post<EvalJob>(`/datasets/${datasetId}/evaluate`, data);

export const getJob = (id: string) => api.get<EvalJob>(`/jobs/${id}`);

export const cancelJob = (id: string) => api.post<EvalJob>(`/jobs/${id}/cancel`);

export const getJobResults = (id: string, limit = 50, offset = 0) =>
  api.get<EvalResultListResponse>(`/jobs/${id}/results?limit=${limit}&offset=${offset}`);

export const getJobFailures = (id: string) => api.get<EvalFailureListResponse>(`/jobs/${id}/failures`);

export const getJobFailureCategories = (id: string) => api.get<EvalFailureCategories>(`/jobs/${id}/failures/categories`);
