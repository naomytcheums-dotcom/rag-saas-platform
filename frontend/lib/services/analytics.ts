// Partie 20 -- advanced analytics API client, api/routers/analytics.py's
// full /organizations/{org_id}/analytics/* surface, plus the
// platform-wide, superadmin-only /analytics/business/* endpoints.

import { api } from "@/lib/api";

export interface MetricPoint {
  metric_name: string;
  metric_value: number;
  period: string;
  period_start: string;
}

export interface AnalyticsEventRow {
  id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  user_id: string | null;
  created_at: string;
}

export interface Dashboard {
  id: string;
  organization_id: string;
  name: string;
  widgets: unknown[];
  is_default: boolean;
  created_at: string;
}

function toQuery(params: Record<string, string | undefined>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") usp.set(key, value);
  }
  const query = usp.toString();
  return query ? `?${query}` : "";
}

// -- Generic metrics -----------------------------------------------------

export const trackEvent = (orgId: string, eventType: string, eventData: Record<string, unknown> = {}) =>
  api.post<{ id: string }>(`/organizations/${orgId}/analytics/events`, { event_type: eventType, event_data: eventData });

export const getMetrics = (orgId: string, filters: { metric_name?: string; period?: string; date_range?: string } = {}) =>
  api.get<MetricPoint[]>(`/organizations/${orgId}/analytics/metrics${toQuery(filters)}`);

export const queryMetrics = (orgId: string, filters: { event_type?: string; date_range?: string } = {}) =>
  api.get<AnalyticsEventRow[]>(`/organizations/${orgId}/analytics/metrics/query${toQuery(filters)}`);

export function exportMetricsUrl(orgId: string, dateRange: string, format: "csv" | "json"): string {
  return `/organizations/${orgId}/analytics/metrics/export?date_range=${dateRange}&format=${format}`;
}

// -- Business (platform-wide) ---------------------------------------------

export const getBusinessRevenue = (dateRange = "30d") => api.get(`/analytics/business/revenue${toQuery({ date_range: dateRange })}`);
export const getBusinessCustomers = () => api.get(`/analytics/business/customers`);
export const getBusinessRetention = (dateRange = "30d") => api.get(`/analytics/business/retention${toQuery({ date_range: dateRange })}`);
export const getBusinessChurn = (dateRange = "30d") => api.get(`/analytics/business/churn${toQuery({ date_range: dateRange })}`);
export const getBusinessLtv = (dateRange = "30d") => api.get(`/analytics/business/ltv${toQuery({ date_range: dateRange })}`);
export const getBusinessRevenueTrend = (dateRange = "30d") => api.get<{ date: string; mrr_cents: number }[]>(`/analytics/business/revenue/trend${toQuery({ date_range: dateRange })}`);

export async function getBusinessMetrics(dateRange = "30d") {
  const [revenue, customers, retention, churn, ltv] = await Promise.all([
    getBusinessRevenue(dateRange), getBusinessCustomers(), getBusinessRetention(dateRange), getBusinessChurn(dateRange), getBusinessLtv(dateRange),
  ]);
  return { revenue, customers, retention, churn, ltv };
}

// -- Product (per-organization) --------------------------------------------

export const getProductUsage = (orgId: string, dateRange = "30d") => api.get(`/organizations/${orgId}/analytics/product/usage${toQuery({ date_range: dateRange })}`);
export const getProductAdoption = (orgId: string, dateRange = "30d") => api.get(`/organizations/${orgId}/analytics/product/adoption${toQuery({ date_range: dateRange })}`);
export const getProductEngagement = (orgId: string, dateRange = "30d") => api.get(`/organizations/${orgId}/analytics/product/engagement${toQuery({ date_range: dateRange })}`);
export const getProductFunnel = (orgId: string, steps: string[], dateRange = "30d") =>
  api.get(`/organizations/${orgId}/analytics/product/funnels${toQuery({ steps: steps.join(","), date_range: dateRange })}`);

export async function getProductMetrics(orgId: string, dateRange = "30d") {
  const [usage, adoption, engagement] = await Promise.all([
    getProductUsage(orgId, dateRange), getProductAdoption(orgId, dateRange), getProductEngagement(orgId, dateRange),
  ]);
  return { usage, adoption, engagement };
}

// -- Technical (per-organization) -------------------------------------------

export const getTechnicalPerformance = (orgId: string) => api.get(`/organizations/${orgId}/analytics/technical/performance`);
export const getTechnicalErrors = (orgId: string) => api.get(`/organizations/${orgId}/analytics/technical/errors`);
export const getTechnicalApiUsage = (orgId: string, dateRange = "30d") => api.get(`/organizations/${orgId}/analytics/technical/api-usage${toQuery({ date_range: dateRange })}`);
export const getTechnicalLlmUsage = (orgId: string, dateRange = "30d") => api.get(`/organizations/${orgId}/analytics/technical/llm-usage${toQuery({ date_range: dateRange })}`);

export async function getTechnicalMetrics(orgId: string, dateRange = "30d") {
  const [performance, errors, apiUsage, llmUsage] = await Promise.all([
    getTechnicalPerformance(orgId), getTechnicalErrors(orgId), getTechnicalApiUsage(orgId, dateRange), getTechnicalLlmUsage(orgId, dateRange),
  ]);
  return { performance, errors, apiUsage, llmUsage };
}

// -- Dashboards ---------------------------------------------------------

export const listDashboards = (orgId: string) => api.get<Dashboard[]>(`/organizations/${orgId}/analytics/dashboards`);
export const getDashboard = (orgId: string, dashboardId: string) => api.get<Dashboard>(`/organizations/${orgId}/analytics/dashboards/${dashboardId}`);
export const createDashboard = (orgId: string, data: { name: string; widgets?: unknown[]; is_default?: boolean }) =>
  api.post<Dashboard>(`/organizations/${orgId}/analytics/dashboards`, data);
export const updateDashboard = (orgId: string, dashboardId: string, data: Partial<{ name: string; widgets: unknown[]; is_default: boolean }>) =>
  api.patch<Dashboard>(`/organizations/${orgId}/analytics/dashboards/${dashboardId}`, data);
export const deleteDashboard = (orgId: string, dashboardId: string) => api.delete(`/organizations/${orgId}/analytics/dashboards/${dashboardId}`);
