// Partie 22 -- multi-modal media API client, api/routers/media.py's
// real surface.

import { api, fileUrl } from "@/lib/api";

export type MediaType = "image" | "audio" | "video";
export type MediaStatus = "pending" | "processing" | "completed" | "failed";

export interface MediaAsset {
  id: string;
  organization_id: string;
  uploaded_by: string | null;
  media_type: MediaType;
  status: MediaStatus;
  filename: string;
  file_size: number;
  mime_type: string;
  duration_ms: number | null;
  description: string | null;
  ocr_text: string | null;
  objects_json: string[] | null;
  tags_json: string[] | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MediaAssetListResponse {
  items: MediaAsset[];
  total: number;
  limit: number;
  offset: number;
}

export interface MediaTranscript {
  id: string;
  media_asset_id: string;
  text: string;
  segments_json: Record<string, unknown>[] | null;
  language: string | null;
  provider: string | null;
  created_at: string;
}

export interface MediaFrame {
  id: string;
  media_asset_id: string;
  frame_index: number;
  timestamp_ms: number;
  description: string | null;
  objects_json: string[] | null;
  created_at: string;
}

export interface MediaSearchResult {
  media_asset_id: string;
  media_type: MediaType;
  filename: string;
  score: number;
  content: string;
  source: string;
}

export const listMedia = (orgId: string, mediaType?: MediaType, limit = 50, offset = 0) =>
  api.get<MediaAssetListResponse>(`/organizations/${orgId}/media?${mediaType ? `media_type=${mediaType}&` : ""}limit=${limit}&offset=${offset}`);

export const uploadMedia = (orgId: string, file: File) => api.postFile<MediaAsset>(`/organizations/${orgId}/media`, file);

export const getMedia = (id: string) => api.get<MediaAsset>(`/media/${id}`);
export const getMediaStatus = (id: string) => api.get<MediaAsset>(`/media/${id}/status`);
export const deleteMedia = (id: string) => api.delete(`/media/${id}`);
export const reprocessMedia = (id: string) => api.post<MediaAsset>(`/media/${id}/process`);
export const getMediaTranscript = (id: string) => api.get<MediaTranscript>(`/media/${id}/transcript`);
export const listMediaFrames = (id: string) => api.get<MediaFrame[]>(`/media/${id}/frames`);

export const searchMedia = (query: string, mediaType?: MediaType, topK = 10) =>
  api.post<{ results: MediaSearchResult[] }>(`/media/search`, { query, media_type: mediaType, top_k: topK });

export interface VisualSearchResult {
  media_asset_id: string;
  filename: string;
  score: number;
}

// Real CLIP-based search (Partie 22, 3rd finalization) -- compares a
// query directly against real image CONTENT, distinct from
// searchMedia's own text search over LLM-written descriptions.
export const searchVisual = (query: string, topK = 10) =>
  api.post<{ results: VisualSearchResult[] }>(`/media/search/visual`, { query, top_k: topK });

export const searchSimilar = (file: File) => api.postFile<{ results: VisualSearchResult[] }>(`/media/search/similar`, file);

// Real, authenticated fetch-as-blob -- same pattern as
// components/analytics/ExportButton.tsx and VoiceOutput.tsx: this
// endpoint requires a Bearer token, so a plain <img>/<audio>/<video>
// src (no custom headers) can never load it directly.
async function fetchAsBlobUrl(path: string): Promise<string> {
  const token = window.localStorage.getItem("access_token");
  const response = await fetch(fileUrl(path), { headers: token ? { Authorization: `Bearer ${token}` } : undefined, credentials: "include" });
  if (!response.ok) throw new Error(`Failed to load media file (${response.status})`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export const fetchMediaFileBlobUrl = (id: string) => fetchAsBlobUrl(`/media/${id}/file`);
export const fetchMediaFrameFileBlobUrl = (mediaAssetId: string, frameId: string) => fetchAsBlobUrl(`/media/${mediaAssetId}/frames/${frameId}/file`);
