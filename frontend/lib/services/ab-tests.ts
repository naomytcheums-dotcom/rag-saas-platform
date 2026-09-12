// Partie 21 -- A/B testing API client, api/routers/ab_tests.py's real
// surface (Partie 7.3.10's original endpoints + Partie 21's new ones).

import { api, fileUrl } from "@/lib/api";

export interface ABTest {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  variant_a: Record<string, unknown>;
  variant_b: Record<string, unknown>;
  traffic_split: number;
  status: "draft" | "running" | "paused" | "completed";
  metrics: Record<string, unknown> | null;
  start_date: string | null;
  end_date: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  test_type: "agent" | "prompt" | "model" | null;
  target_metric: string | null;
  min_sample_size: number;
  confidence_level: number;
  winner: "a" | "b" | "none" | null;
}

export interface ABTestListResponse {
  items: ABTest[];
  total: number;
  limit: number;
  offset: number;
}

export interface ABTestMetricResult {
  variant_a: { count: number; mean: number; std_dev: number };
  variant_b: { count: number; mean: number; std_dev: number };
  lift: number | null;
  p_value: number | null;
  significant: boolean | null;
  confidence_interval_lower: number | null;
  confidence_interval_upper: number | null;
  effect_size_cohens_d: number | null;
  statistical_power: number | null;
  min_sample_size_reached: boolean | null;
}

export interface ABTestResultsResponse {
  test_id: string;
  status: string;
  metrics: Record<string, ABTestMetricResult>;
}

export interface ABTestAssignment {
  id: string;
  ab_test_id: string;
  request_id: string;
  variant: string;
  assigned_at: string;
}

export interface ABTestAssignmentListResponse {
  items: ABTestAssignment[];
  total: number;
  limit: number;
  offset: number;
}

export const listABTests = (orgId: string, limit = 50, offset = 0) =>
  api.get<ABTestListResponse>(`/organizations/${orgId}/ab-tests?limit=${limit}&offset=${offset}`);

export const createABTest = (orgId: string, data: {
  name: string; description?: string; variant_a: Record<string, unknown>; variant_b: Record<string, unknown>;
  traffic_split?: number; test_type?: string; target_metric?: string; min_sample_size?: number; confidence_level?: number;
}) => api.post<ABTest>(`/organizations/${orgId}/ab-tests`, data);

export const getABTest = (id: string) => api.get<ABTest>(`/ab-tests/${id}`);

export const updateABTest = (id: string, data: Partial<Pick<ABTest, "name" | "description" | "traffic_split" | "test_type" | "target_metric" | "min_sample_size" | "confidence_level">>) =>
  api.patch<ABTest>(`/ab-tests/${id}`, data);

export const deleteABTest = (id: string) => api.delete(`/ab-tests/${id}`);

export const startABTest = (id: string) => api.post<ABTest>(`/ab-tests/${id}/start`);
export const pauseABTest = (id: string) => api.post<ABTest>(`/ab-tests/${id}/pause`);
export const resumeABTest = (id: string) => api.post<ABTest>(`/ab-tests/${id}/resume`);
export const completeABTest = (id: string) => api.post<ABTest>(`/ab-tests/${id}/complete`);

export const chooseABTestWinner = (id: string, variant: "a" | "b") => api.post<ABTest>(`/ab-tests/${id}/variants/choose`, { variant });
export const decideABTest = (id: string) => api.post<ABTest>(`/ab-tests/${id}/decide`);

export const getABTestResults = (id: string) => api.get<ABTestResultsResponse>(`/ab-tests/${id}/results`);
export const getABTestStatistics = (id: string) => api.get<ABTestResultsResponse>(`/ab-tests/${id}/statistics`);
export const listABTestAssignments = (id: string, limit = 100, offset = 0) =>
  api.get<ABTestAssignmentListResponse>(`/ab-tests/${id}/assignments?limit=${limit}&offset=${offset}`);

export function exportABTestUrl(id: string, format: "csv" | "json"): string {
  return fileUrl(`/ab-tests/${id}/export?format=${format}`);
}

export const trackABTestMetric = (id: string, variant: "a" | "b", metric: string, value: number) =>
  api.post<ABTest>(`/ab-tests/${id}/track`, { variant, metric, value });
