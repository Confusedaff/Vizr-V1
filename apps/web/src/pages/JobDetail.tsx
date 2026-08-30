import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import * as api from "../api/client";
import { DebugPanel } from "../components/DebugPanel";
import { ManualSceneForm } from "../components/ManualSceneForm";
import { PipelineTrace } from "../components/PipelineTrace";
import { StatusBadge } from "../components/StatusBadge";
import { VideoPlayer } from "../components/VideoPlayer";
import type { LiveEvent } from "../hooks/useJobEvents";
import { useJobEvents } from "../hooks/useJobEvents";
import { isTerminal, useJobPolling } from "../hooks/useJobPolling";
import "./JobDetail.css";

export function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const { job, error, refresh } = useJobPolling(jobId ?? null);
  const active = job ? !isTerminal(job.status) : true;
  const liveEvents = useJobEvents(jobId ?? null, active);
  const [historicalEvents, setHistoricalEvents] = useState<LiveEvent[]>([]);

  // The WebSocket only ever has events from the moment the socket
  // connects — if the page is loaded (or reloaded) after a job has
  // already progressed or finished, PipelineTrace would otherwise show
  // every stage stuck at "pending" despite real history existing in
  // Postgres. Seed from GET /jobs/{id}/events once per job so the trace
  // reflects the truth immediately, then live events layer on top for
  // anything still in flight.
  useEffect(() => {
    if (!jobId) return;
    api
      .getJobEvents(jobId)
      .then((events) =>
        setHistoricalEvents(
          events.map((e) => ({ stage: e.stage, event_type: e.event_type, message: e.message }))
        )
      )
      .catch(() => setHistoricalEvents([]));
  }, [jobId]);

  const allEvents = [...historicalEvents, ...liveEvents];

  if (error) {
    return (
      <div className="job-detail job-detail--empty">
        <p className="job-detail__error">{error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="job-detail job-detail--empty">
        <p className="job-detail__loading">Loading…</p>
      </div>
    );
  }

  async function handleManualScene(steps: Record<string, unknown>[], narration: string[]) {
    if (!jobId) return;
    await api.submitManualScene(jobId, steps, narration);
    await refresh();
  }

  return (
    <div className="job-detail">
      <header className="job-detail__header">
        <div>
          <h1 className="job-detail__title">{job.prompt || job.visualization_type || "Visualization"}</h1>
          <div className="job-detail__meta">
            <StatusBadge status={job.status} />
            {job.visualization_type && <span className="job-detail__type mono">{job.visualization_type}</span>}
          </div>
        </div>
      </header>

      {job.status === "needs_manual_input" && <ManualSceneForm onSubmit={handleManualScene} />}

      {job.error_message && job.status !== "needs_manual_input" && (
        <div className="job-detail__error-box">
          <strong>Something went wrong.</strong>
          <p>{job.error_message}</p>
        </div>
      )}

      {job.video_url && job.status === "completed" ? (
        <VideoPlayer jobId={job.id} videoUrl={job.video_url} />
      ) : (
        <PipelineTrace events={allEvents} job={job} />
      )}

      <DebugPanel jobId={job.id} />
    </div>
  );
}
