"use client";

import { useRef, useState } from "react";
import { useEvalQuestions } from "@/lib/hooks/useEvalQuestions";

export function QuestionList({ datasetId }: { datasetId: string }) {
  const { questions, total, loading, error, create, remove, importFile } = useEvalQuestions(datasetId);
  const [question, setQuestion] = useState("");
  const [expectedAnswer, setExpectedAnswer] = useState("");
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    await create({ question: question.trim(), expected_answer: expectedAnswer.trim() || undefined });
    setQuestion("");
    setExpectedAnswer("");
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const format = file.name.endsWith(".csv") ? "csv" : "json";
    try {
      const result = await importFile(file, format);
      setImportMessage(`Imported ${result.imported} test case(s)${result.errors.length ? `, ${result.errors.length} error(s)` : ""}.`);
    } catch (err) {
      setImportMessage(err instanceof Error ? err.message : "Import failed");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Test cases ({total})</h2>
        <label className="cursor-pointer rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-hover">
          Import CSV/JSON
          <input ref={fileInputRef} type="file" accept=".csv,.json" onChange={handleImport} className="hidden" />
        </label>
      </div>
      {importMessage && <p className="text-xs text-foreground-muted">{importMessage}</p>}

      <form onSubmit={handleAdd} className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-3">
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Question" required className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
        <input value={expectedAnswer} onChange={(e) => setExpectedAnswer(e.target.value)} placeholder="Expected answer (optional)" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
        <button type="submit" disabled={!question.trim()} className="self-start rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">Add test case</button>
      </form>

      {loading ? (
        <p className="text-sm text-foreground-muted">Loading…</p>
      ) : error ? (
        <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      ) : questions.length === 0 ? (
        <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No test cases yet.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-xs text-foreground-muted">
              <th className="pb-2">Question</th>
              <th className="pb-2">Expected answer</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody>
            {questions.map((q) => (
              <tr key={q.id} className="border-t border-border">
                <td className="py-2 pr-4 text-foreground">{q.question}</td>
                <td className="py-2 pr-4 text-foreground-muted">{q.expected_answer ?? "—"}</td>
                <td className="py-2 text-right">
                  <button type="button" onClick={() => void remove(q.id)} className="text-xs font-medium text-danger hover:underline">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
