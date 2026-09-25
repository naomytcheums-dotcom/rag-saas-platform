"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

const MODELS = [
  { value: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
  { value: "mistral-large", label: "Mistral Large" },
];

const AVAILABLE_TOOLS = [
  "calculator", "word_count", "rag_search", "web_search",
  "http_request", "calendar_list_events", "email_read",
];

export default function NewAgentPage() {
  const router = useRouter();
  const { org, loading: orgLoading } = useCurrentOrg();
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [model, setModel] = useState("claude-3-5-sonnet");
  const [temperature, setTemperature] = useState(0.7);
  const [maxIterations, setMaxIterations] = useState(8);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleTool(tool: string) {
    setSelectedTools((prev) => prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    setLoading(true);
    setError(null);
    try {
      const agent = await api.post<{ id: string }>(`/organizations/${org.id}/agents`, {
        name, description, system_prompt: systemPrompt, model,
        temperature, max_iterations: maxIterations, tools: selectedTools,
      });
      router.push(`/dashboard/agents/${agent.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("agents.new.error_generic"));
    } finally {
      setLoading(false);
    }
  }

  if (orgLoading || !org) return <p className="p-6">{t("agents.new.loading")}</p>;

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-2xl font-semibold mb-6">{t("agents.new.title")}</h1>
      {error && <p className="text-danger mb-4">{error}</p>}
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label>{t("agents.new.name")}
          <input type="text" required value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <label>{t("agents.new.description")}
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <label>{t("agents.new.system_prompt")}
          <textarea required value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={6} className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <label>{t("agents.new.model")}
          <select value={model} onChange={(e) => setModel(e.target.value)} className="mt-1 w-full border rounded px-3 py-2">
            {MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </label>
        <label>{t("agents.new.temperature", { value: temperature })}
          <input type="range" min="0" max="2" step="0.1" value={temperature} onChange={(e) => setTemperature(parseFloat(e.target.value))} className="mt-1 w-full" />
        </label>
        <label>{t("agents.new.max_iterations")}
          <input type="number" min="1" max="20" value={maxIterations} onChange={(e) => setMaxIterations(parseInt(e.target.value))} className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <div>
          <p className="mb-2">{t("agents.new.allowed_tools")}</p>
          <div className="grid grid-cols-2 gap-2">
            {AVAILABLE_TOOLS.map((tool) => (
              <label key={tool} className="flex items-center gap-2">
                <input type="checkbox" checked={selectedTools.includes(tool)} onChange={() => toggleTool(tool)} />
                <span>{tool}</span>
              </label>
            ))}
          </div>
        </div>
        <button type="submit" disabled={loading} className="bg-accent text-white px-4 py-2 rounded disabled:opacity-50">
          {loading ? t("agents.new.submitting") : t("agents.new.submit")}
        </button>
      </form>
    </div>
  );
}
