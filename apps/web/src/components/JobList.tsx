import { Link, useParams } from "react-router-dom";
import type { Job } from "../types/api";
import { StatusBadge } from "./StatusBadge";
import "./JobList.css";

export function JobList({ jobs }: { jobs: Job[] }) {
  const { jobId: activeId } = useParams();

  if (jobs.length === 0) {
    return <p className="job-list__empty">No videos yet — describe one above to get started.</p>;
  }

  return (
    <nav className="job-list" aria-label="Job history">
      {jobs.map((job) => (
        <Link
          key={job.id}
          to={`/app/jobs/${job.id}`}
          className={`job-list__item ${job.id === activeId ? "job-list__item--active" : ""}`}
        >
          <div className="job-list__item-top">
            <span className="job-list__title">
              {job.prompt || job.visualization_type || "Untitled"}
            </span>
          </div>
          <div className="job-list__item-bottom">
            <StatusBadge status={job.status} />
            <span className="job-list__time">{formatRelativeTime(job.created_at)}</span>
          </div>
        </Link>
      ))}
    </nav>
  );
}

function formatRelativeTime(iso: string): string {
  const then = new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime();
  const diffMs = Date.now() - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
