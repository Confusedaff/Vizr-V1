import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import type { Job } from "../types/api";

const TERMINAL_STATUSES = new Set([
  "completed",
  "failed",
  "quality_failed",
  "needs_manual_input",
]);

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.has(status);
}

/** Polls GET /jobs/{id} at an interval while the job is in-flight. The
 * WebSocket gives low-latency updates, but this is the actual source of
 * truth (matches the backend's own design: the socket is "a thin bridge,
 * not a source of truth") — so the UI never fully depends on the socket
 * connection surviving. */
export function useJobPolling(jobId: string | null, intervalMs = 3000) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!jobId) return;
    try {
      const j = await api.getJob(jobId);
      setJob(j);
      setError(null);
      if (isTerminal(j.status) && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load job");
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    refresh();
    timerRef.current = setInterval(refresh, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [jobId, intervalMs, refresh]);

  return { job, error, refresh };
}
