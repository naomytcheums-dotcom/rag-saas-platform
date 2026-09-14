// Partie 24 -- fine-tuning API client, api/routers/fine_tuning.py's
// real surface. Every list/create endpoint here takes `orgId` as a
// real, required query parameter (the literal spec's own endpoint
// paths never nest under an organization, unlike media/autonomous-agents).

import { api } from "@/lib/api";

export type FineTuningDatasetStatus = "pending" | "validating" | "ready" | "error";
export type FineTuningJobStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";
export type FineTunedModelStatus = "available" | "deprecated";

export interface FineTuningDataset {
  id: string;
  organization_id: string;
  created_by: string | null;
  name: string;
  description: string | null;
  dataset_type: "llm" | "embedding";
  format: "jsonl" | "csv" | "parquet";
  size: number;
  status: FineTuningDatasetStatus;
  validation_errors: { line: number | null; error: string }[] | null;
  example_count: number | null;
  created_at: string;
}

export interface FineTuningDatasetListResponse {
  items: FineTuningDataset[];
  total: number;
  limit: number;
  offset: number;
}

export interface FineTuningJob {
  id: string;
  organization_id: string;
  dataset_id: string;
  created_by: string | null;
  name: string;
  base_model: string;
  provider: string;
  status: FineTuningJobStatus;
  hyperparameters: Record<string, unknown>;
  metrics: Record<string, unknown>;
  provider_job_id: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface FineTuningJobListResponse {
  items: FineTuningJob[];
  total: number;
  limit: number;
  offset: number;
}

export interface FineTunedModel {
  id: string;
  organization_id: string;
  job_id: string;
  name: string;
  provider: string;
  provider_model_id: string;
  base_model: string;
  status: FineTunedModelStatus;
  deployed: boolean;
  metrics: Record<string, unknown>;
  created_at: string;
}

export interface FineTunedModelListResponse {
  items: FineTunedModel[];
  total: number;
  limit: number;
  offset: number;
}

export interface FineTuningEvaluation {
  id: string;
  model_id: string;
  dataset_id: string;
  evaluation_job_id: string | null;
  metrics: Record<string, unknown>;
  score: number | null;
  created_at: string;
}

export const listDatasets = (orgId: string, limit = 50, offset = 0) =>
  api.get<FineTuningDatasetListResponse>(`/fine-tuning/datasets?org_id=${orgId}&limit=${limit}&offset=${offset}`);

export const createDataset = (orgId: string, data: { name: string; description?: string; dataset_type?: string }, file: File) =>
  api.postMultipart<FineTuningDataset>(
    `/fine-tuning/datasets?org_id=${orgId}`,
    { name: data.name, ...(data.description ? { description: data.description } : {}), dataset_type: data.dataset_type ?? "llm" },
    { file },
  );

export const getDataset = (id: string) => api.get<FineTuningDataset>(`/fine-tuning/datasets/${id}`);
export const deleteDataset = (id: string) => api.delete(`/fine-tuning/datasets/${id}`);
export const validateDataset = (id: string) => api.post<FineTuningDataset>(`/fine-tuning/datasets/${id}/validate`);

export const listJobs = (orgId: string, limit = 50, offset = 0) =>
  api.get<FineTuningJobListResponse>(`/fine-tuning/jobs?org_id=${orgId}&limit=${limit}&offset=${offset}`);

export const createJob = (orgId: string, data: { dataset_id: string; name: string; base_model?: string; provider?: string; hyperparameters?: Record<string, unknown> }) =>
  api.post<FineTuningJob>(`/fine-tuning/jobs?org_id=${orgId}`, data);

export const getJob = (id: string) => api.get<FineTuningJob>(`/fine-tuning/jobs/${id}`);
export const cancelJob = (id: string) => api.post<FineTuningJob>(`/fine-tuning/jobs/${id}/cancel`);
export const getJobMetrics = (id: string) => api.get<Record<string, unknown>>(`/fine-tuning/jobs/${id}/metrics`);

export const listModels = (orgId: string, limit = 50, offset = 0) =>
  api.get<FineTunedModelListResponse>(`/fine-tuning/models?org_id=${orgId}&limit=${limit}&offset=${offset}`);

export const getModel = (id: string) => api.get<FineTunedModel>(`/fine-tuning/models/${id}`);
export const deleteModel = (id: string) => api.delete(`/fine-tuning/models/${id}`);
export const deployModel = (id: string) => api.post<FineTunedModel>(`/fine-tuning/models/${id}/deploy`);
export const undeployModel = (id: string) => api.post<FineTunedModel>(`/fine-tuning/models/${id}/undeploy`);
export const evaluateModel = (id: string, datasetId: string) => api.post<FineTuningEvaluation>(`/fine-tuning/models/${id}/evaluate`, { dataset_id: datasetId });
export const listEvaluations = (id: string) => api.get<FineTuningEvaluation[]>(`/fine-tuning/models/${id}/evaluations`);
