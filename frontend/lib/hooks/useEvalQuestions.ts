"use client";

import { useCallback, useEffect, useState } from "react";
import * as evalService from "@/lib/services/eval";
import type { EvalQuestion } from "@/lib/services/eval";

export function useEvalQuestions(datasetId: string) {
  const [questions, setQuestions] = useState<EvalQuestion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await evalService.listQuestions(datasetId);
      setQuestions(response.items);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load test cases");
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with the backend after mount/dataset change
    void reload();
  }, [reload]);

  const create = useCallback(async (data: { question: string; expected_answer?: string }) => {
    await evalService.createQuestion(datasetId, data);
    await reload();
  }, [datasetId, reload]);

  const remove = useCallback(async (id: string) => {
    await evalService.deleteQuestion(id);
    await reload();
  }, [reload]);

  const importFile = useCallback(async (file: File, format: "json" | "csv") => {
    const result = await evalService.importQuestions(datasetId, file, format);
    await reload();
    return result;
  }, [datasetId, reload]);

  return { questions, total, loading, error, reload, create, remove, importFile };
}
