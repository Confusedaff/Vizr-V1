import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { LLM_PROVIDERS, VISUALIZATION_TYPES } from "../types/api";
import type { LLMProviderOption } from "../types/api";
import "./JobCreateForm.css";

interface Props {
  onSubmitPrompt: (prompt: string, provider?: string, apiKey?: string) => Promise<void>;
  onSubmitManual: (
    type: string,
    input: Record<string, unknown>,
    title: string,
    provider?: string,
    apiKey?: string
  ) => Promise<void>;
  submitting: boolean;
  initialPrompt?: string;
}

const PROVIDER_STORAGE_KEY = "vizr_llm_provider";
const KEY_STORAGE_PREFIX = "vizr_llm_key_";

export function JobCreateForm({ onSubmitPrompt, onSubmitManual, submitting, initialPrompt }: Props) {
  const [mode, setMode] = useState<"prompt" | "manual">("prompt");
  const [prompt, setPrompt] = useState(initialPrompt ?? "");

  const [manualType, setManualType] = useState<string>(VISUALIZATION_TYPES[0]);
  const [manualTitle, setManualTitle] = useState("");
  const [manualArray, setManualArray] = useState("1, 3, 5, 7, 9, 11, 13");
  const [manualTarget, setManualTarget] = useState("9");
  const [error, setError] = useState<string | null>(null);

  const providerState = useProviderKey();

  useEffect(() => {
    if (initialPrompt) setPrompt(initialPrompt);
  }, [initialPrompt]);

  async function handlePromptSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!prompt.trim()) {
      setError("Describe what you want visualized.");
      return;
    }
    try {
      await onSubmitPrompt(prompt.trim(), providerState.provider, providerState.apiKey || undefined);
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
      await onSubmitManual(
        manualType,
        input,
        manualTitle.trim() || manualType,
        providerState.provider,
        providerState.apiKey || undefined
      );
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
          <ProviderKeyField state={providerState} />
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
          <ProviderKeyField state={providerState} />
          {error && <p className="job-form__error">{error}</p>}
          <button type="submit" className="job-form__submit" disabled={submitting}>
            {submitting ? "Starting…" : "Generate video"}
          </button>
        </form>
      )}
    </div>
  );
}

/** Keeps the chosen provider + that provider's key in localStorage, keyed
 * per-provider (vizr_llm_key_groq, vizr_llm_key_gemini, ...) so switching
 * providers doesn't clobber a key you already typed in for another one —
 * genuinely useful when trying more than one free-tier provider locally. */
function useProviderKey() {
  const [provider, setProvider] = useState<string>(
    () => localStorage.getItem(PROVIDER_STORAGE_KEY) || "groq"
  );
  const [apiKey, setApiKeyState] = useState<string>(
    () => localStorage.getItem(KEY_STORAGE_PREFIX + provider) || ""
  );
  const [shown, setShown] = useState(false);

  useEffect(() => {
    localStorage.setItem(PROVIDER_STORAGE_KEY, provider);
    setApiKeyState(localStorage.getItem(KEY_STORAGE_PREFIX + provider) || "");
  }, [provider]);

  function setApiKey(value: string) {
    setApiKeyState(value);
    if (value) {
      localStorage.setItem(KEY_STORAGE_PREFIX + provider, value);
    } else {
      localStorage.removeItem(KEY_STORAGE_PREFIX + provider);
    }
  }

  return { provider, setProvider, apiKey, setApiKey, shown, setShown };
}

type ProviderKeyState = ReturnType<typeof useProviderKey>;

function ProviderKeyField({ state }: { state: ProviderKeyState }) {
  const { provider, setProvider, apiKey, setApiKey, shown, setShown } = state;
  const current: LLMProviderOption =
    LLM_PROVIDERS.find((p) => p.id === provider) ?? LLM_PROVIDERS[0];

  return (
    <div className="job-form__apikey">
      <button type="button" className="job-form__apikey-toggle" onClick={() => setShown(!shown)}>
        {shown ? "▾" : "▸"} LLM provider &amp; API key{" "}
        {apiKey ? `(${current.id} key set)` : "(optional — uses server default if unset)"}
      </button>
      {shown && (
        <div className="job-form__apikey-body">
          <label className="job-form__field">
            <span>Provider</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {LLM_PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={current.keyPlaceholder}
            className="job-form__apikey-input"
          />
          <a href={current.signupUrl} target="_blank" rel="noreferrer" className="job-form__apikey-link">
            Get a free {current.id} API key →
          </a>
        </div>
      )}
    </div>
  );
}
