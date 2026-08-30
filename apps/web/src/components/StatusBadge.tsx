import type { JobStatus } from "../types/api";
import "./StatusBadge.css";

const STATUS_LABEL: Record<JobStatus, string> = {
  pending: "Queued",
  classifying: "Classifying",
  planning_scene: "Planning scene",
  validating_scene: "Validating scene",
  needs_manual_input: "Needs input",
  rendering: "Rendering",
  validating_render: "Checking quality",
  repairing: "Repairing",
  uploading: "Uploading",
  completed: "Complete",
  failed: "Failed",
  quality_failed: "Quality check failed",
};

const STATUS_TONE: Record<JobStatus, "progress" | "success" | "danger" | "warning"> = {
  pending: "progress",
  classifying: "progress",
  planning_scene: "progress",
  validating_scene: "progress",
  needs_manual_input: "warning",
  rendering: "progress",
  validating_render: "progress",
  repairing: "warning",
  uploading: "progress",
  completed: "success",
  failed: "danger",
  quality_failed: "danger",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  const tone = STATUS_TONE[status] ?? "progress";
  return (
    <span className={`status-badge status-badge--${tone}`}>
      {(tone === "progress") && <span className="status-badge__dot" aria-hidden="true" />}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
