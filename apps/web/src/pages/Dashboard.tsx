import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import * as api from "../api/client";
import { JobCreateForm } from "../components/JobCreateForm";
import { JobList } from "../components/JobList";
import { useAuth } from "../hooks/useAuth";
import type { Job } from "../types/api";
import "./Dashboard.css";

export function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const prefillPrompt = (location.state as { prefillPrompt?: string } | null)?.prefillPrompt;

  const refreshJobs = useCallback(async () => {
    try {
      const list = await api.listJobs();
      setJobs(list);
    } catch {
      // Sidebar list failing silently is acceptable — the active job's
      // own page still polls itself independently.
    }
  }, []);

  useEffect(() => {
    refreshJobs();
    const interval = setInterval(refreshJobs, 5000);
    return () => clearInterval(interval);
  }, [refreshJobs]);

  async function handlePromptSubmit(prompt: string, provider?: string, apiKey?: string) {
    setSubmitting(true);
    try {
      const job = await api.createJobFromPrompt(prompt, provider, apiKey);
      await refreshJobs();
      navigate(`/app/jobs/${job.id}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleManualSubmit(
    type: string,
    input: Record<string, unknown>,
    title: string,
    provider?: string,
    apiKey?: string
  ) {
    setSubmitting(true);
    try {
      const job = await api.createJobFromManual(type, input, title, provider, apiKey);
      await refreshJobs();
      navigate(`/app/jobs/${job.id}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="dashboard">
      <aside className="dashboard__sidebar">
        <div className="dashboard__brand">
          <span className="dashboard__brand-glyph">▸</span>
          <span>aiviz</span>
        </div>
        <JobList jobs={jobs} />
        <div className="dashboard__account">
          <span className="dashboard__email">{user?.email}</span>
          <button className="dashboard__logout" onClick={logout}>
            Log out
          </button>
        </div>
      </aside>

      <main className="dashboard__main">
        <JobCreateForm
          onSubmitPrompt={handlePromptSubmit}
          onSubmitManual={handleManualSubmit}
          submitting={submitting}
          initialPrompt={prefillPrompt}
        />
        <div className="dashboard__content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
