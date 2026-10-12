"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Connector {
  provider: string;
  connected: boolean;
  fields_set: string[];
  required_fields: string[];
  optional_fields: string[];
  works_without_credentials: boolean;
  updated_at: string | null;
}

interface ConnectorList {
  connectors: Connector[];
  platform_credentials_allowed: boolean;
}

const SECRET = /(TOKEN|SECRET|PASSWORD|KEY)$/;

/** "JIRA_BASE_URL" -> "Base URL" (the provider prefix is already in the card title). */
function fieldLabel(provider: string, field: string): string {
  const prefix = provider.toUpperCase().replace(/-/g, "_") + "_";
  const bare = field.startsWith(prefix) ? field.slice(prefix.length) : field;
  return bare.toLowerCase().split("_").map((word, i) => (i === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word)).join(" ");
}

function providerLabel(provider: string): string {
  return provider.split("_").map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}

function ConnectorCard({ orgId, connector, canEdit, onChanged }: { orgId: string; connector: Connector; canEdit: boolean; onChanged: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fields = [...connector.required_fields, ...connector.optional_fields];

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const body: Record<string, string> = {};
    for (const name of fields) if ((values[name] ?? "").trim()) body[name] = values[name].trim();
    try {
      await api.put(`/organizations/${orgId}/connectors/${connector.provider}`, { fields: body });
      setValues({});
      setMessage(t("connectors.saved"));
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("connectors.error"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.delete(`/organizations/${orgId}/connectors/${connector.provider}`);
      setMessage(t("connectors.removed"));
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("connectors.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="rounded-xl border border-border bg-surface p-4" data-provider={connector.provider}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-foreground">{providerLabel(connector.provider)}</h2>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs ${connector.connected ? "bg-success-soft text-success" : "bg-background text-foreground-muted"}`}>
            {connector.connected ? t("connectors.connected") : t("connectors.not_connected")}
          </span>
          {canEdit && (
            <button type="button" onClick={() => setOpen((v) => !v)} className="rounded-lg border border-border px-2 py-1 text-xs" aria-expanded={open}>
              {connector.connected ? t("connectors.replace") : t("connectors.connect")}
            </button>
          )}
        </div>
      </div>
      {connector.works_without_credentials && !connector.connected && <p className="mt-1 text-xs text-foreground-muted">{t("connectors.public_data_note")}</p>}
      {open && canEdit && (
        <form onSubmit={save} className="mt-3 space-y-2" aria-label={providerLabel(connector.provider)}>
          {fields.map((name) => (
            <label key={name} className="block text-xs text-foreground-muted">
              {fieldLabel(connector.provider, name)}
              {connector.optional_fields.includes(name) ? ` (${t("connectors.optional")})` : ""}
              <input
                type={SECRET.test(name) ? "password" : "text"}
                autoComplete="off"
                value={values[name] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [name]: e.target.value }))}
                required={connector.required_fields.includes(name)}
                placeholder={connector.fields_set.includes(name) ? t("connectors.already_set") : ""}
                className="mt-1 block w-full rounded-lg border border-border bg-background px-2 py-1 text-sm text-foreground"
              />
            </label>
          ))}
          <p className="text-xs text-foreground-muted">{t("connectors.stored_encrypted")}</p>
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="rounded-lg bg-accent px-3 py-1 text-sm font-medium text-white disabled:opacity-50">{t("connectors.save")}</button>
            {connector.connected && (
              <button type="button" disabled={busy} onClick={remove} className="rounded-lg border border-border px-3 py-1 text-sm text-danger disabled:opacity-50">{t("connectors.remove")}</button>
            )}
          </div>
        </form>
      )}
      {message && <p role="status" className="mt-2 text-xs text-foreground-muted">{message}</p>}
      {error && <p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
    </li>
  );
}

/** Connected accounts (docs/DECISIONS.md D17): each organization gives the credentials of ITS OWN Jira, Zendesk, Notion... The server's accounts are not used. */
export default function ConnectorsPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [data, setData] = useState<ConnectorList | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const canEdit = org?.my_role === "owner" || org?.my_role === "admin";

  const load = useCallback(() => {
    if (!org) return;
    api.get<ConnectorList>(`/organizations/${org.id}/connectors`).then(setData).catch((err) => setError(err instanceof ApiError ? String(err.detail) : t("connectors.error")));
  }, [org, t]);

  useEffect(load, [load]);

  const shown = useMemo(() => (data?.connectors ?? []).filter((c) => providerLabel(c.provider).toLowerCase().includes(filter.trim().toLowerCase())), [data, filter]);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-foreground">{t("connectors.title")}</h1>
        <p className="mt-1 text-sm text-foreground-muted">{t("connectors.description")}</p>
        {!canEdit && <p className="mt-1 text-xs text-foreground-muted">{t("connectors.read_only")}</p>}
      </header>
      <input
        aria-label={t("connectors.filter")}
        placeholder={t("connectors.filter")}
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
      />
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <ul className="space-y-3">
        {org && shown.map((connector) => <ConnectorCard key={connector.provider} orgId={org.id} connector={connector} canEdit={canEdit} onChanged={load} />)}
      </ul>
    </div>
  );
}
