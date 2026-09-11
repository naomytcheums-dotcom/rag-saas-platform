// Partie 16 (ter) -- plugin marketplace API client, api/routers/plugins.py.
// Org-scoped calls need `orgId` explicitly (this app's real convention --
// see api/routers/plugins.py's own top docstring on why URLs stay
// /organizations/{org_id}/... rather than an implicit "current org").

import { api } from "@/lib/api";
import type {
  Plugin, PluginExecution, PluginInstallation, PluginPermission, PluginRatingSummary, PluginReview, PluginVersion,
} from "@/lib/types";

export interface PluginListFilters {
  search?: string;
  category?: string;
  min_rating?: number;
  sort_by?: "date" | "popularity" | "rating";
  limit?: number;
  offset?: number;
}

function toQuery(filters: PluginListFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export const listPlugins = (filters: PluginListFilters = {}) => api.get<Plugin[]>(`/marketplace/plugins${toQuery(filters)}`);

export const getPlugin = (id: string) => api.get<Plugin>(`/marketplace/plugins/${id}`);

export const listPluginPermissions = () => api.get<PluginPermission[]>("/marketplace/permissions");

export const getPluginRating = (id: string) => api.get<PluginRatingSummary>(`/marketplace/plugins/${id}/rating`);

export const listReviews = (id: string) => api.get<PluginReview[]>(`/marketplace/plugins/${id}/reviews`);

export const deleteReview = (reviewId: string) => api.delete(`/marketplace/reviews/${reviewId}`);

export const listPluginVersions = (id: string) => api.get<PluginVersion[]>(`/marketplace/plugins/${id}/versions`);

export function createPlugin(orgId: string, data: { name: string; description: string; category: string; manifest: Blob; code: Blob }) {
  return api.postMultipart<Plugin>(
    `/organizations/${orgId}/plugins/publish`,
    { name: data.name, description: data.description, category: data.category },
    { manifest: data.manifest, code: data.code },
  );
}

export function publishVersion(orgId: string, id: string, data: { description?: string; changelog?: string; manifest: Blob; code: Blob }) {
  const fields: Record<string, string> = {};
  if (data.description !== undefined) fields.description = data.description;
  if (data.changelog !== undefined) fields.changelog = data.changelog;
  return api.putMultipart<Plugin>(`/organizations/${orgId}/plugins/${id}`, fields, { manifest: data.manifest, code: data.code });
}

export const listPublishedPlugins = (orgId: string) => api.get<Plugin[]>(`/organizations/${orgId}/plugins/published`);

export const deletePlugin = (orgId: string, id: string) => api.delete(`/organizations/${orgId}/plugins/${id}`);

export const installPlugin = (orgId: string, id: string) => api.post<PluginInstallation>(`/organizations/${orgId}/plugins/${id}/install`);

export const uninstallPlugin = (orgId: string, installationId: string) => api.delete(`/organizations/${orgId}/plugins/installed/${installationId}`);

export const listInstalledPlugins = (orgId: string) => api.get<PluginInstallation[]>(`/organizations/${orgId}/plugins/installed`);

export const enablePlugin = (orgId: string, installationId: string) => api.patch<PluginInstallation>(`/organizations/${orgId}/plugins/installed/${installationId}`, { enabled: true });

export const disablePlugin = (orgId: string, installationId: string) => api.patch<PluginInstallation>(`/organizations/${orgId}/plugins/installed/${installationId}`, { enabled: false });

export const updateInstallationConfig = (orgId: string, installationId: string, config: Record<string, unknown>) =>
  api.patch<PluginInstallation>(`/organizations/${orgId}/plugins/installed/${installationId}`, { config });

export const addReview = (orgId: string, id: string, data: { rating: number; comment?: string | null }) =>
  api.post<PluginReview>(`/organizations/${orgId}/plugins/${id}/reviews`, data);

export const executePlugin = (orgId: string, id: string, data: Record<string, unknown> = {}) =>
  api.post<PluginExecution>(`/organizations/${orgId}/plugins/${id}/execute`, { data });

export const listPluginExecutions = (orgId: string, id: string) => api.get<PluginExecution[]>(`/organizations/${orgId}/plugins/${id}/executions`);

// Admin moderation (superadmin) -- kept here rather than a separate
// service file since it's the same real /admin/plugins/... surface,
// not a separate concern for the frontend to import from elsewhere.
export const listPendingPlugins = () => api.get<Plugin[]>("/admin/plugins/pending");
export const approvePlugin = (id: string) => api.post<Plugin>(`/admin/plugins/${id}/approve`);
export const rejectPlugin = (id: string, reason: string) => api.post<Plugin>(`/admin/plugins/${id}/reject`, { reason });
export const suspendPlugin = (id: string, reason: string) => api.post<Plugin>(`/admin/plugins/${id}/suspend`, { reason });
