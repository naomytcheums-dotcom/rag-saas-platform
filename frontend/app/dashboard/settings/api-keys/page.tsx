"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
  revoked_at: string | null;
}

interface QuotaStatus {
  quota_limit: number | null;
  quota_period: string | null;
  quota_used: number;
  quota_reset_at: string | null;
}

function KeyStatusBadge({ apiKey }: { apiKey: ApiKey }) {
  if (!apiKey.is_active) return <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs font-medium text-foreground-muted">revoked</span>;
  if (apiKey.expires_at) {
    const daysLeft = (new Date(apiKey.expires_at).getTime() - Date.now()) / 86_400_000;
    if (daysLeft < 0) return <span className="rounded-full bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger">expired</span>;
    if (daysLeft < 7) return <span className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning">expiring soon</span>;
  }
  return <span className="rounded-full bg-success-soft px-2 py-0.5 text-xs font-medium text-success">active</span>;
}

function KeyUsageStats({ keyId }: { keyId: string }) {
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  useEffect(() => {
    void api.get<QuotaStatus>(`/api-keys/${keyId}/quota/status`).then(setQuota).catch(() => setQuota(null));
  }, [keyId]);

  if (!quota || quota.quota_limit === null) return <p className="text-xs text-foreground-muted">No quota configured — unlimited usage.</p>;

  const pct = Math.min(100, Math.round((quota.quota_used / quota.quota_limit) * 100));
  return (
    <div>
      <div className="flex justify-between text-xs text-foreground-muted">
        <span>{quota.quota_used} / {quota.quota_limit} requests ({quota.quota_period})</span>
        <span>{pct}%</span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function ApiKeysPage() {
  const { org } = useCurrentOrg();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [availableScopes, setAvailableScopes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newScopes, setNewScopes] = useState<string[]>([]);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try {
      const [keysData, scopesData] = await Promise.all([
        api.get<ApiKey[]>(`/organizations/${org.id}/api-keys`),
        api.get<{ scopes: string[] }>("/api-keys/scopes"),
      ]);
      setKeys(keysData);
      setAvailableScopes(scopesData.scopes);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load API keys");
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createKey() {
    if (!org || !newName.trim() || newScopes.length === 0) return;
    setCreating(true);
    setError(null);
    try {
      const result = await api.post<{ key: string }>(`/organizations/${org.id}/api-keys`, { name: newName, scopes: newScopes });
      setRevealedKey(result.key);
      setNewName("");
      setNewScopes([]);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to create key");
    } finally {
      setCreating(false);
    }
  }

  async function revokeKey(keyId: string) {
    if (!org) return;
    await api.delete(`/organizations/${org.id}/api-keys/${keyId}`);
    await load();
  }

  async function rotateKey(keyId: string) {
    setError(null);
    try {
      const result = await api.post<{ key: string; id: string }>(`/api-keys/${keyId}/rotate`);
      setRevealedKey(result.key);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to rotate key");
    }
  }

  function toggleScope(scope: string) {
    setNewScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  }

  function copyToClipboard(text: string) {
    void navigator.clipboard.writeText(text);
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-xl font-semibold text-foreground">API keys</h1>
      <p className="mt-1 text-sm text-foreground-muted">
        Real, revocable, organization-scoped keys for the public <code>/v1/*</code> API.
      </p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      {revealedKey && (
        <div className="mt-4 rounded-lg border border-accent bg-accent-soft p-3 text-sm">
          <p className="font-medium text-foreground">Your key (shown once — copy it now):</p>
          <div className="mt-1 flex items-center gap-2">
            <code className="block flex-1 break-all rounded bg-surface px-2 py-1 text-xs">{revealedKey}</code>
            <button type="button" onClick={() => copyToClipboard(revealedKey)} className="shrink-0 rounded-md bg-accent px-2 py-1 text-xs font-medium text-white hover:bg-accent-hover">
              Copy
            </button>
          </div>
          <button type="button" onClick={() => setRevealedKey(null)} className="mt-2 text-xs text-accent hover:underline">Dismiss</button>
        </div>
      )}

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Create a new key</h2>
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Key name (e.g. Production server)"
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {availableScopes.map((scope) => (
            <button
              key={scope}
              type="button"
              onClick={() => toggleScope(scope)}
              className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                newScopes.includes(scope) ? "border-accent bg-accent text-white" : "border-border-strong text-foreground-muted hover:border-accent"
              }`}
            >
              {scope}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => void createKey()}
          disabled={creating || !newName.trim() || newScopes.length === 0}
          className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {creating ? "Creating…" : "Create key"}
        </button>
      </div>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">Existing keys</h2>
        {loading ? (
          <p className="text-sm text-foreground-muted">Loading…</p>
        ) : keys.length === 0 ? (
          <p className="text-sm text-foreground-muted">No API keys yet.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {keys.map((key) => (
              <div key={key.id} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground">{key.name}</p>
                      <KeyStatusBadge apiKey={key} />
                    </div>
                    <p className="text-xs text-foreground-muted">
                      {key.key_prefix}… · {key.scopes.join(", ")}
                      {key.last_used_at && <> · last used {new Date(key.last_used_at).toLocaleDateString()}</>}
                    </p>
                  </div>
                  {key.is_active && (
                    <div className="flex items-center gap-3">
                      <button type="button" onClick={() => setExpanded(expanded === key.id ? null : key.id)} className="text-xs font-medium text-foreground-muted hover:underline">
                        {expanded === key.id ? "Hide usage" : "Usage"}
                      </button>
                      <button type="button" onClick={() => void rotateKey(key.id)} className="text-xs font-medium text-accent hover:underline">
                        Rotate
                      </button>
                      <button type="button" onClick={() => void revokeKey(key.id)} className="text-xs font-medium text-danger hover:underline">
                        Revoke
                      </button>
                    </div>
                  )}
                </div>
                {expanded === key.id && (
                  <div className="mt-3 border-t border-border pt-3">
                    <KeyUsageStats keyId={key.id} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
