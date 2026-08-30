import { useState } from "react";
import type { FormEvent } from "react";
import { VISUALIZATION_TYPES } from "../types/api";
import "./JobCreateForm.css";

interface Props {
  onSubmitPrompt: (prompt: string, apiKey?: string) => Promise<void>;
  onSubmitManual: (type: string, input: Record<string, unknown>, title: string, apiKey?: string) => Promise<void>;
  submitting: boolean;
}

export function JobCreateForm({ onSubmitPrompt, onSubmitManual, submitting }: Props) {
  const [mode, setMode] = useState<"prompt" | "manual">("prompt");
  const [prompt, setPrompt] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  const [manualType, setManualType] = useState<string>(VISUALIZATION_TYPES[0]);
  const [manualTitle, setManualTitle] = useState("");
  const [manualArray, setManualArray] = useState("1, 3, 5, 7, 9, 11, 13");
  const [manualTarget, setManualTarget] = useState("9");
  const [error, setError] = useState<string | null>(null);

  async function handlePromptSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!prompt.trim()) {
      setError("Describe what you want visualized.");
      return;
    }
    try {
      await onSubmitPrompt(prompt.trim(), apiKey.trim() || undefined);
      setPrompt("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create job.");
    }
  }

  async function handleManualSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    let array: number[] = [];
    try {
      array = manualArray
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => {
          const n = Number(s);
          if (Number.isNaN(n)) throw new Error(`"${s}" is not a number`);
          return n;
        });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid array input.");
      return;
    }

    const input: Record<string, unknown> = { array };
    if (manualTarget.trim()) input.target = Number(manualTarget);

    try {
      await onSubmitManual(manualType, input, manualTitle.trim() || manualType, apiKey.trim() || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create job.");
    }
  }

  return (
    <div className="job-form">
      <div className="job-form__tabs">
        <button
          type="button"
          className={mode === "prompt" ? "job-form__tab job-form__tab--active" : "job-form__tab"}
          onClick={() => setMode("prompt")}
        >
          Describe it
        </button>
        <button
          type="button"
          className={mode === "manual" ? "job-form__tab job-form__tab--active" : "job-form__tab"}
          onClick={() => setMode("manual")}
        >
          Pick exactly
        </button>
      </div>

      {mode === "prompt" ? (
        <form onSubmit={handlePromptSubmit} className="job-form__body">
          <textarea
            className="job-form__prompt"
            placeholder="e.g. Binary search for 42 in a sorted array of 10 numbers"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
          />
          <ApiKeyField value={apiKey} onChange={setApiKey} shown={showApiKey} setShown={setShowApiKey} />
          {error && <p className="job-form__error">{error}</p>}
          <button type="submit" className="job-form__submit" disabled={submitting}>
            {submitting ? "Starting…" : "Generate video"}
          </button>
        </form>
      ) : (
        <form onSubmit={handleManualSubmit} className="job-form__body">
          <label className="job-form__field">
            <span>Algorithm</span>
            <select value={manualType} onChange={(e) => setManualType(e.target.value)}>
              {VISUALIZATION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="job-form__field">
            <span>Title</span>
            <input value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} placeholder="Optional" />
          </label>
          <label className="job-form__field">
            <span>Array (comma-separated)</span>
            <input value={manualArray} onChange={(e) => setManualArray(e.target.value)} />
          </label>
          <label className="job-form__field">
            <span>Target (optional)</span>
            <input value={manualTarget} onChange={(e) => setManualTarget(e.target.value)} />
          </label>
          <ApiKeyField value={apiKey} onChange={setApiKey} shown={showApiKey} setShown={setShowApiKey} />
          {error && <p className="job-form__error">{error}</p>}
          <button type="submit" className="job-form__submit" disabled={submitting}>
            {submitting ? "Starting…" : "Generate video"}
          </button>
        </form>
      )}
    </div>
  );
}

function ApiKeyField({
  value,
  onChange,
  shown,
  setShown,
}: {
  value: string;
  onChange: (v: string) => void;
  shown: boolean;
  setShown: (v: boolean) => void;
}) {
  return (
    <div className="job-form__apikey">
      <button type="button" className="job-form__apikey-toggle" onClick={() => setShown(!shown)}>
        {shown ? "▾" : "▸"} Anthropic API key {value ? "(set)" : "(optional — uses server default if unset)"}
      </button>
      {shown && (
        <input
          type="password"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="sk-ant-…"
          className="job-form__apikey-input"
        />
      )}
    </div>
  );
}
