import { useEffect, useState } from "react";
import * as api from "../api/client";
import type { QualityReport, RenderManifest } from "../types/api";
import "./DebugPanel.css";

export function DebugPanel({ jobId }: { jobId: string }) {
  const [manifest, setManifest] = useState<RenderManifest | null>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    (async () => {
      try {
        const m = await api.getJobManifest(jobId);
        setManifest(m);
      } catch {
        // manifest may not exist yet (job still running) — not an error state worth surfacing loudly
      }
      try {
        const q = await api.getQualityReport(jobId);
        setQuality(q);
      } catch {
        // no quality report yet either — same reasoning
      }
    })();
  }, [jobId, expanded]);

  return (
    <div className="debug-panel">
      <button
        className="debug-panel__toggle"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="debug-panel__toggle-icon">{expanded ? "▾" : "▸"}</span>
        Debug details
      </button>

      {expanded && (
        <div className="debug-panel__body">
          {manifest && (
            <section className="debug-panel__section">
              <h4>Stage timings</h4>
              <table className="debug-panel__table">
                <thead>
                  <tr>
                    <th>stage</th>
                    <th>attempt</th>
                    <th>duration</th>
                    <th>result</th>
                  </tr>
                </thead>
                <tbody>
                  {manifest.stages.map((s, i) => (
                    <tr key={`${s.stage}-${i}`}>
                      <td>{s.stage}</td>
                      <td>{s.attempt}</td>
                      <td>{s.duration_seconds != null ? `${s.duration_seconds.toFixed(2)}s` : "—"}</td>
                      <td className={s.success ? "debug-panel__ok" : s.success === false ? "debug-panel__fail" : ""}>
                        {s.success === true ? "ok" : s.success === false ? "failed" : "…"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {manifest.notes.length > 0 && (
                <ul className="debug-panel__notes">
                  {manifest.notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {quality?.quality_report && (
            <section className="debug-panel__section">
              <h4>
                Frame quality — {quality.quality_report.passed ? "passed" : "failed"} (
                {quality.quality_report.total_frames_sampled} frames sampled,{" "}
                {quality.quality_report.error_count} errors, {quality.quality_report.warning_count}{" "}
                warnings)
              </h4>
              {quality.quality_report.frames
                .filter((f) => f.issues.length > 0)
                .slice(0, 8)
                .map((f) => (
                  <div key={f.frame_index} className="debug-panel__frame-issue">
                    <span className="mono">t={f.timestamp_s.toFixed(2)}s</span>
                    {f.issues.map((issue, i) => (
                      <span key={i} className={`debug-panel__issue debug-panel__issue--${issue.severity}`}>
                        {issue.check}: {issue.message}
                      </span>
                    ))}
                  </div>
                ))}
            </section>
          )}

          {!manifest && !quality && (
            <p className="debug-panel__empty">No debug data available for this job yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
