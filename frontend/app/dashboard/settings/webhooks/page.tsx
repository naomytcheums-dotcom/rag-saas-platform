"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

const WEBHOOK_EVENTS = [
  "message.created", "message.updated", "document.uploaded", "document.processed",
  "agent.run_started", "agent.run_completed", "conversation.created", "conversation.updated",
];

interface Webhook {
  id: string;
  name: string;
  url: string;
  events: string[];
  is_active: boolean;
}

interface Delivery {
  id: string;
  event: string;
  status_code: number | null;
  error: string | null;
  attempt: number;
  delivered_at: string | null;
  created_at: string;
}

function DeliveryStatusBadge({ delivery }: { delivery: Delivery }) {
  if (delivery.status_code && delivery.status_code >= 200 && delivery.status_code < 300) {
    return <span className="rounded-full bg-success-soft px-2 py-0.5 text-xs font-medium text-success">{delivery.status_code}</span>;
  }
  if (delivery.error || delivery.status_code) {
    return <span className="rounded-full bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger">{delivery.status_code ?? "échec"}</span>;
  }
  return <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs font-medium text-foreground-muted">en attente</span>;
}

function WebhookDeliveries({ webhookId }: { webhookId: string }) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDeliveries(await api.get<Delivery[]>(`/webhooks/${webhookId}/deliveries`));
    } finally {
      setLoading(false);
    }
  }, [webhookId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  if (loading) return <p className="text-xs text-foreground-muted">Chargement des livraisons…</p>;
  if (deliveries.length === 0) return <p className="text-xs text-foreground-muted">Aucune livraison pour l&apos;instant.</p>;

  return (
    <div className="flex flex-col gap-1.5">
      {deliveries.map((delivery) => (
        <div key={delivery.id} className="flex items-center justify-between rounded-lg bg-background px-2.5 py-1.5 text-xs">
          <span className="font-medium text-foreground">{delivery.event}</span>
          <span className="text-foreground-muted">tentative {delivery.attempt}</span>
          <DeliveryStatusBadge delivery={delivery} />
          <span className="text-foreground-muted">{new Date(delivery.created_at).toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

export default function WebhooksPage() {
  const { org } = useCurrentOrg();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [testFlash, setTestFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try {
      setWebhooks(await api.get<Webhook[]>(`/organizations/${org.id}/webhooks`));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Échec du chargement des webhooks");
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  async function createWebhook() {
    if (!org || !name.trim() || !url.trim() || events.length === 0) return;
    setCreating(true);
    setError(null);
    try {
      await api.post(`/organizations/${org.id}/webhooks`, { name, url, events });
      setName("");
      setUrl("");
      setEvents([]);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Échec de la création du webhook");
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(webhook: Webhook) {
    await api.patch(`/webhooks/${webhook.id}`, { is_active: !webhook.is_active });
    await load();
  }

  async function deleteWebhook(id: string) {
    await api.delete(`/webhooks/${id}`);
    await load();
  }

  async function testWebhook(id: string) {
    setTestFlash(null);
    try {
      await api.post(`/webhooks/${id}/test`);
      setTestFlash(id);
      setExpanded(id);
      setTimeout(() => setTestFlash(null), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Échec de la livraison de test");
    }
  }

  function toggleEvent(event: string) {
    setEvents((prev) => (prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]));
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-xl font-semibold text-foreground">Webhooks</h1>
      <p className="mt-1 text-sm text-foreground-muted">Recevez un vrai POST HTTP à chaque fois qu&apos;un événement survient dans votre organisation.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <div className="mt-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-foreground">Ajouter un webhook</h2>
        <input
          type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Nom"
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <input
          type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-server.com/webhooks/rag"
          className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {WEBHOOK_EVENTS.map((event) => (
            <button
              key={event} type="button" onClick={() => toggleEvent(event)}
              className={`rounded-full border px-2.5 py-1 text-xs ${
                events.includes(event) ? "border-accent bg-accent text-white" : "border-border-strong text-foreground-muted hover:border-accent"
              }`}
            >
              {event}
            </button>
          ))}
        </div>
        <button
          type="button" onClick={() => void createWebhook()} disabled={creating || !name.trim() || !url.trim() || events.length === 0}
          className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {creating ? "Ajout…" : "Ajouter le webhook"}
        </button>
      </div>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">Webhooks configurés</h2>
        {loading ? (
          <LoadingState fullScreen={false} />
        ) : webhooks.length === 0 ? (
          <p className="text-sm text-foreground-muted">Aucun webhook pour l&apos;instant.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {webhooks.map((webhook) => (
              <div key={webhook.id} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground">{webhook.name}</p>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${webhook.is_active ? "bg-success-soft text-success" : "bg-surface-muted text-foreground-muted"}`}>
                        {webhook.is_active ? "actif" : "inactif"}
                      </span>
                    </div>
                    <p className="text-xs text-foreground-muted">{webhook.url}</p>
                    <p className="text-xs text-foreground-muted">{webhook.events.join(", ")}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button type="button" onClick={() => void testWebhook(webhook.id)} className="text-xs font-medium text-accent hover:underline">
                      {testFlash === webhook.id ? "Envoyé !" : "Tester"}
                    </button>
                    <button type="button" onClick={() => setExpanded(expanded === webhook.id ? null : webhook.id)} className="text-xs font-medium text-foreground-muted hover:underline">
                      {expanded === webhook.id ? "Masquer les livraisons" : "Livraisons"}
                    </button>
                    <button type="button" onClick={() => void toggleActive(webhook)} className="text-xs font-medium text-accent hover:underline">
                      {webhook.is_active ? "Désactiver" : "Activer"}
                    </button>
                    <button type="button" onClick={() => void deleteWebhook(webhook.id)} className="text-xs font-medium text-danger hover:underline">
                      Supprimer
                    </button>
                  </div>
                </div>
                {expanded === webhook.id && (
                  <div className="mt-3 border-t border-border pt-3">
                    <WebhookDeliveries webhookId={webhook.id} />
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
