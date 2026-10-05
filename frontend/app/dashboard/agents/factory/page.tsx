"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface Blueprint {
  profile: string;
  rationale: string[];
  retrieval_config: Record<string, unknown>;
  agent: { name: string; system_prompt: string; tools: { name: string }[] } & Record<string, unknown>;
}

interface BlueprintResponse {
  blueprint: Blueprint;
  problems: string[];
  deployable: boolean;
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    // 422 bodies from the factory carry a list of problems; show them all.
    if (Array.isArray(err.detail)) return err.detail.map((d) => (typeof d === "string" ? d : JSON.stringify(d))).join(" · ");
    return String(err.detail ?? fallback);
  }
  return fallback;
}

export default function AgentFactoryPage() {
  const router = useRouter();
  const { org, loading: orgLoading } = useCurrentOrg();
  const { t } = useTranslation();
  const [requirement, setRequirement] = useState("");
  const [name, setName] = useState("");
  const [result, setResult] = useState<BlueprintResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const body = { requirement, name: name.trim() || null };

  async function preview(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    setPreviewing(true);
    setError(null);
    try {
      setResult(await api.post<BlueprintResponse>(`/organizations/${org.id}/factory/blueprint`, body));
    } catch (err) {
      setResult(null);
      setError(errorMessage(err, t("agents.factory.error_generic")));
    } finally {
      setPreviewing(false);
    }
  }

  async function deploy() {
    if (!org || !result?.deployable) return;
    setDeploying(true);
    setError(null);
    try {
      await api.post(`/organizations/${org.id}/factory/deploy`, body);
      router.push("/dashboard/agents");
    } catch (err) {
      setError(errorMessage(err, t("agents.factory.error_generic")));
    } finally {
      setDeploying(false);
    }
  }

  if (orgLoading || !org) return <p className="p-6">{t("agents.new.loading")}</p>;

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-2xl font-semibold mb-2">{t("agents.factory.title")}</h1>
      <p className="mb-6 text-sm opacity-80">{t("agents.factory.subtitle")}</p>
      {error && <p role="alert" className="text-danger mb-4">{error}</p>}

      <form onSubmit={preview} className="flex flex-col gap-4">
        <label>{t("agents.factory.requirement")}
          <textarea
            required minLength={10} maxLength={4000} rows={4} value={requirement}
            onChange={(e) => { setRequirement(e.target.value); setResult(null); }}
            placeholder={t("agents.factory.requirement_placeholder")} className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
        <label>{t("agents.factory.name")}
          <input type="text" maxLength={200} value={name} onChange={(e) => { setName(e.target.value); setResult(null); }} className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <button type="submit" disabled={previewing || requirement.trim().length < 10} className="border px-4 py-2 rounded disabled:opacity-50">
          {previewing ? t("agents.factory.previewing") : t("agents.factory.preview")}
        </button>
      </form>

      {result && (
        <section className="mt-8 flex flex-col gap-4" aria-live="polite">
          <p><strong>{t("agents.factory.profile")}:</strong> {result.blueprint.profile} — {result.blueprint.agent.name}</p>

          <div>
            <h2 className="font-semibold mb-1">{t("agents.factory.why")}</h2>
            <ul className="list-disc pl-5 text-sm">{result.blueprint.rationale.map((line) => <li key={line}>{line}</li>)}</ul>
          </div>

          <div>
            <h2 className="font-semibold mb-1">{t("agents.factory.retrieval")}</h2>
            <pre className="text-sm border rounded p-3 overflow-x-auto">{JSON.stringify(result.blueprint.retrieval_config, null, 2)}</pre>
          </div>

          <div>
            <h2 className="font-semibold mb-1">{t("agents.factory.tools")}</h2>
            <p className="text-sm">{result.blueprint.agent.tools.map((tool) => tool.name).join(", ")}</p>
          </div>

          {result.problems.length > 0 && (
            <div role="alert" className="text-danger">
              <h2 className="font-semibold mb-1">{t("agents.factory.problems")}</h2>
              <ul className="list-disc pl-5 text-sm">{result.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}

          <button type="button" onClick={deploy} disabled={!result.deployable || deploying} className="bg-accent text-white px-4 py-2 rounded disabled:opacity-50 self-start">
            {deploying ? t("agents.factory.deploying") : t("agents.factory.deploy")}
          </button>
        </section>
      )}
    </div>
  );
}
