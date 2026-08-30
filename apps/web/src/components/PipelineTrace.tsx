import type { LiveEvent } from "../hooks/useJobEvents";
import type { Job } from "../types/api";
import "./PipelineTrace.css";

const STAGE_ORDER = [
  "classify",
  "plan_scene",
  "repair",
  "render",
  "validate_render",
  "upload",
];

const STAGE_LABEL: Record<string, string> = {
  classify: "classify",
  plan_scene: "plan scene",
  repair: "repair",
  render: "render",
  validate_render: "validate render",
  upload: "upload",
};

interface StageState {
  stage: string;
  status: "pending" | "active" | "done" | "failed" | "skipped";
  message?: string | null;
}

function deriveStageStates(events: LiveEvent[], job: Job | null): StageState[] {
  const states: Record<string, StageState> = {};
  for (const stage of STAGE_ORDER) {
    states[stage] = { stage, status: "pending" };
  }

  for (const evt of events) {
    if (!STAGE_ORDER.includes(evt.stage)) continue;
    if (evt.event_type === "started") {
      states[evt.stage] = { stage: evt.stage, status: "active" };
    } else if (evt.event_type === "failed") {
      states[evt.stage] = { stage: evt.stage, status: "failed", message: evt.message };
    } else if (evt.event_type === "completed" || evt.event_type === "needs_manual_input") {
      states[evt.stage] = {
        stage: evt.stage,
        status: evt.event_type === "needs_manual_input" ? "failed" : "done",
        message: evt.message,
      };
    }
  }

  // Repair is conditional — only show it if it actually fired.
  const list = STAGE_ORDER.filter((s) => s !== "repair" || states.repair.status !== "pending").map(
    (s) => states[s]
  );

  // If the job is already terminal per the poller, make sure trailing
  // stages don't hang on "pending" forever after a failure earlier on.
  if (job && ["failed", "quality_failed", "needs_manual_input"].includes(job.status)) {
    const failedIdx = list.findIndex((s) => s.status === "failed");
    if (failedIdx >= 0) {
      for (let i = failedIdx + 1; i < list.length; i++) {
        if (list[i].status === "pending") list[i] = { ...list[i], status: "skipped" };
      }
    }
  }

  return list;
}

const ICON: Record<StageState["status"], string> = {
  pending: "○",
  active: "◐",
  done: "●",
  failed: "✕",
  skipped: "–",
};

export function PipelineTrace({ events, job }: { events: LiveEvent[]; job: Job | null }) {
  const stages = deriveStageStates(events, job);

  return (
    <div className="pipeline-trace" role="list" aria-label="Pipeline progress">
      {stages.map((s) => (
        <div key={s.stage} className={`pipeline-trace__row pipeline-trace__row--${s.status}`} role="listitem">
          <span className="pipeline-trace__icon" aria-hidden="true">{ICON[s.status]}</span>
          <span className="pipeline-trace__label">{STAGE_LABEL[s.stage] ?? s.stage}</span>
          {s.status === "active" && <span className="pipeline-trace__spinner" aria-hidden="true" />}
          {s.message && s.status === "failed" && (
            <span className="pipeline-trace__message">{s.message}</span>
          )}
        </div>
      ))}
    </div>
  );
}
