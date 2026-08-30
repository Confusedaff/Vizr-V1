// Mirrors apps/api/schemas/job_schemas.py and models/db.py. Kept as a
// hand-maintained mirror rather than codegen for this MVP scope — if the
// backend schema drifts, TypeScript's structural typing will catch most
// mismatches at the call site (e.g. an unexpected field) rather than
// silently, since components destructure specific fields.

export type JobStatus =
  | "pending"
  | "classifying"
  | "planning_scene"
  | "validating_scene"
  | "needs_manual_input"
  | "rendering"
  | "validating_render"
  | "repairing"
  | "uploading"
  | "completed"
  | "failed"
  | "quality_failed";

export const VISUALIZATION_TYPES = [
  "array_traversal",
  "two_sum",
  "two_pointers",
  "binary_search",
  "sliding_window",
  "bubble_sort",
  "merge_sort",
  "binary_tree_traversal",
  "graph_bfs_dfs",
  "hashmap_ops",
  "quicksort",
  "linked_list_reversal",
  "valid_parentheses",
  "dynamic_programming_1d",
] as const;

export type VisualizationType = (typeof VISUALIZATION_TYPES)[number];

export interface Job {
  id: string;
  status: JobStatus;
  prompt: string | null;
  visualization_type: string | null;
  video_path: string | null;
  video_url: string | null;
  error_message: string | null;
  repair_attempts: number;
  created_at: string;
  updated_at: string;
}

export interface JobEvent {
  stage: string;
  event_type: string;
  message: string | null;
  created_at: string;
}

export interface StageTiming {
  stage: string;
  started_at: number;
  finished_at: number | null;
  success: boolean | null;
  error: string | null;
  attempt: number;
  duration_seconds: number | null;
}

export interface RenderManifest {
  job_id: string;
  prompt: string | null;
  visualization_type: string | null;
  architecture_path: string | null;
  created_at: number;
  stages: StageTiming[];
  final_status: string | null;
  video_path: string | null;
  video_duration_seconds: number | null;
  quality_passed: boolean | null;
  quality_error_count: number;
  quality_warning_count: number;
  repair_attempts: number;
  cache_hit: boolean;
  renderer_version: string | null;
  notes: string[];
  total_duration_seconds: number;
}

export interface FrameIssue {
  check: string;
  severity: "info" | "warning" | "error";
  message: string;
  bbox: [number, number, number, number] | null;
}

export interface FrameReport {
  frame_index: number;
  timestamp_s: number;
  width: number;
  height: number;
  issues: FrameIssue[];
}

export interface QualityReport {
  valid: boolean;
  video_path: string;
  duration_seconds: number;
  quality_report: {
    video_path: string;
    total_frames_sampled: number;
    passed: boolean;
    error_count: number;
    warning_count: number;
    frames: FrameReport[];
  } | null;
  construction_warnings: string[];
  failure_reasons: string[];
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}
