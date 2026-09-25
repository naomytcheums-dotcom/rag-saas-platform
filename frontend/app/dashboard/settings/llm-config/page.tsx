"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface LLMConfig {
  id: string;
  provider: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const PROVIDERS = [
  { id: "anthropic", name: "Anthropic (Claude)" },
  { id: "openai", name: "OpenAI (GPT)" },
  { id: "gemini", name: "Google (Gemini)" },
  { id: "mistral", name: "Mistral" },
  { id: "openai_compatible", name: "Compatible OpenAI (autre fournisseur)" },
];

export default function LLMConfigPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [provider, setProvider] = useState(PROVIDERS[0].id);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try {
      const data = await api.get<LLMConfig[]>(`/organizations/${org.id}/llm-config`);
      setConfigs(data);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("llmconfig.error_load"));
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function saveKey() {
    if (!org || !apiKey.trim()) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await api.post(`/organizations/${org.id}/llm-config`, { provider, api_key: apiKey });
      setApiKey("");
      setSuccess(t("llmconfig.success"));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("llmconfig.error_save"));
    } finally {
      setSaving(false);
    }
  }

  async function removeKey(p: string) {
    if (!org) return;
    setError(null);
    try {
      await api.delete(`/organizations/${org.id}/llm-config/${p}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("llmconfig.error_delete"));
    }
  }

  function providerName(id: string) {
    return PROVIDERS.find((p) => p.id === id)?.name ?? id;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-xl font-semibold text-foreground">{t("llmconfig.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("llmconfig.subtitle")}</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {success && <p className="mt-4 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">{success}</p>}

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">{t("llmconfig.add_heading")}</h2>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        >
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={t("llmconfig.api_key_placeholder")}
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          type="button"
          onClick={() => void saveKey()}
          disabled={saving || !apiKey.trim()}
          className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {saving ? t("llmconfig.saving") : t("llmconfig.save_button")}
        </button>
      </div>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("llmconfig.configured_heading")}</h2>
        {loading ? (
          <LoadingState fullScreen={false} />
        ) : configs.length === 0 ? (
          <p className="text-sm text-foreground-muted">{t("llmconfig.empty")}</p>
        ) : (
          <div className="flex flex-col gap-2">
            {configs.map((c) => (
              <div key={c.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3">
                <div>
                  <p className="text-sm font-medium text-foreground">{providerName(c.provider)}</p>
                  <p className="text-xs text-foreground-muted">
                    {t("llmconfig.configured_on")} {new Date(c.created_at).toLocaleDateString()}
                  </p>
                </div>
                <button type="button" onClick={() => void removeKey(c.provider)} className="text-xs font-medium text-danger hover:underline">
                  {t("llmconfig.delete")}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
