// Partie 19 -- white-label API client, api/routers/white_label.py's
// full /organizations/{org_id}/whitelabel/* surface.

import { api } from "@/lib/api";

export interface WhiteLabelConfig {
  organization_id: string;
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_family: string;
  brand_name: string | null;
  custom_css: string | null;
  custom_js: string | null;
  hide_platform_branding: boolean;
  company_email: string | null;
  support_email: string | null;
  email_sender_name: string | null;
  email_sender_email: string | null;
  is_active: boolean;
  domain: string | null;
  domain_verified: boolean;
}

export type WhiteLabelConfigUpdate = Partial<
  Pick<
    WhiteLabelConfig,
    "primary_color" | "secondary_color" | "accent_color" | "font_family" | "brand_name" | "custom_css" | "custom_js" |
    "hide_platform_branding" | "company_email" | "support_email" | "is_active"
  >
>;

export const getWhiteLabelConfig = (orgId: string) => api.get<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/config`);

export const updateWhiteLabelConfig = (orgId: string, data: WhiteLabelConfigUpdate) =>
  api.patch<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/config`, data);

export const uploadLogo = (orgId: string, file: File) => api.postFile<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/logo`, file);

export const removeLogo = (orgId: string) => api.delete<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/logo`);

export const uploadFavicon = (orgId: string, file: File) => api.postFile<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/favicon`, file);

export const setCustomDomain = (orgId: string, domain: string) => api.post<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/domain`, { domain });

export const removeCustomDomain = (orgId: string) => api.delete<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/domain`);

export const verifyDomain = (orgId: string) => api.post<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/domain/verify`);

export const configureEmail = (orgId: string, data: { sender_name: string; sender_email: string }) =>
  api.post<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/email`, data);

export const removeEmailConfig = (orgId: string) => api.delete<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/email`);

export const getPreview = (orgId: string) => api.get<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/preview`);

export const resetWhiteLabel = (orgId: string) => api.post<WhiteLabelConfig>(`/organizations/${orgId}/whitelabel/reset`);
