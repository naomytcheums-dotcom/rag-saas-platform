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
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the wall clock) after mount, not a value derivable from props/state.
    setNow(Date.now());
  }, []);

  if (!apiKey.is_active) return <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs font-medium text-foreground-muted">révoquée</span>;
  if (apiKey.expires_at && now !== null) {
    const daysLeft = (new Date(apiKey.expires_at).getTime() - now) / 86_400_000;
    if (daysLeft < 0) return <span className="rounded-full bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger">expirée</span>;
    if (daysLeft < 7) return <span className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning">expire bientôt</span>;
  }
  return <span className="rounded-full bg-success-soft px-2 py-0.5 text-xs font-medium text-success">active</span>;
}

function KeyUsageStats({ keyId }: { keyId: string }) {
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  useEffect(() => {
    void api.get<QuotaStatus>(`/api-keys/${keyId}/quota/status`).then(setQuota).catch(() => setQuota(null));
  }, [keyId]);

  if (!quota || quota.quota_limit === null) return <p className="text-xs text-foreground-muted">Aucun quota configuré — usage illimité.</p>;

  const pct = Math.min(100, Math.round((quota.quota_used / quota.quota_limit) * 100));
  return (
    <p className="text-xs text-foreground-muted">
      {quota.quota_used} / {quota.quota_limit} requêtes ({quota.quota_period}) — {pct}%
    </p>
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec du chargement des clés API");
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec de la création de la clé");
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec de la rotation de la clé");
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
      <h1 className="text-xl font-semibold text-foreground">Clés API</h1>
      <p className="mt-1 text-sm text-foreground-muted">
        Clés réelles, révocables, propres à l&apos;organisation, pour l&apos;API publique <code>/v1/*</code>.
      </p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      {revealedKey && (
        <div className="mt-4 rounded-lg border border-accent bg-accent-soft p-3 text-sm">
          <p className="font-medium text-foreground">Votre clé (affichée une seule fois — copiez-la maintenant) :</p>
          <div className="mt-1 flex items-center gap-2">
            <code className="block flex-1 break-all rounded bg-surface px-2 py-1 text-xs">{revealedKey}</code>
            <button type="button" onClick={() => copyToClipboard(revealedKey)} className="shrink-0 rounded-md bg-accent px-2 py-1 text-xs font-medium text-white hover:bg-accent-hover">
              Copier
            </button>
          </div>
          <button type="button" onClick={() => setRevealedKey(null)} className="mt-2 text-xs text-accent hover:underline">Fermer</button>
        </div>
      )}

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Créer une nouvelle clé</h2>
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nom de la clé (ex. Serveur de production)"
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
          {creating ? "Création…" : "Créer la clé"}
        </button>
      </div>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">Clés existantes</h2>
        {loading ? (
          <p className="text-sm text-foreground-muted">Chargement…</p>
        ) : keys.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucune clé API pour l&apos;instant.</p>
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
                      {key.last_used_at && <> · dernière utilisation {new Date(key.last_used_at).toLocaleDateString()}</>}
                    </p>
                  </div>
                  {key.is_active && (
                    <div className="flex items-center gap-3">
                      <button type="button" onClick={() => setExpanded(expanded === key.id ? null : key.id)} className="text-xs font-medium text-foreground-muted hover:underline">
                        {expanded === key.id ? "Masquer l'usage" : "Usage"}
                      </button>
                      <button type="button" onClick={() => void rotateKey(key.id)} className="text-xs font-medium text-accent hover:underline">
                        Renouveler
                      </button>
                      <button type="button" onClick={() => void revokeKey(key.id)} className="text-xs font-medium text-danger hover:underline">
                        Révoquer
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
