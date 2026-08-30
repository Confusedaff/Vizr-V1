import { useState } from "react";
import "./ManualSceneForm.css";

interface Props {
  onSubmit: (steps: Record<string, unknown>[], narration: string[]) => Promise<void>;
}

const EXAMPLE_STEPS = `[
  {"action": "show_array", "data": [1, 3, 5, 7, 9]},
  {"action": "set_pointer", "name": "mid", "index": 2},
  {"action": "highlight_pair", "indices": [2, 2], "color": "highlight"},
  {"action": "show_result", "indices": [2], "message": "Found it"}
]`;

export function ManualSceneForm({ onSubmit }: Props) {
  const [stepsJson, setStepsJson] = useState(EXAMPLE_STEPS);
  const [narrationText, setNarrationText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    let steps: Record<string, unknown>[];
    try {
      steps = JSON.parse(stepsJson);
      if (!Array.isArray(steps)) throw new Error("Steps must be a JSON array");
    } catch (err) {
      setError(err instanceof Error ? `Invalid steps JSON: ${err.message}` : "Invalid steps JSON");
      return;
    }
    const narration = narrationText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      await onSubmit(steps, narration);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit scene.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="manual-scene">
      <p className="manual-scene__explainer">
        No LLM key was available to plan this scene automatically. Write the steps yourself as
        JSON — each step is one action from the schema (<code>set_pointer</code>,{" "}
        <code>highlight_range</code>, <code>swap</code>, and so on).
      </p>
      <label className="manual-scene__field">
        <span>Steps (JSON array)</span>
        <textarea
          value={stepsJson}
          onChange={(e) => setStepsJson(e.target.value)}
          rows={10}
          className="mono"
        />
      </label>
      <label className="manual-scene__field">
        <span>Narration (one line per caption, optional)</span>
        <textarea
          value={narrationText}
          onChange={(e) => setNarrationText(e.target.value)}
          rows={3}
        />
      </label>
      {error && <p className="manual-scene__error">{error}</p>}
      <button className="manual-scene__submit" onClick={handleSubmit} disabled={submitting}>
        {submitting ? "Rendering…" : "Render this scene"}
      </button>
    </div>
  );
}
