import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import "./LandingHero.css";

const EXAMPLE_CHIPS = [
  "Binary search",
  "Two sum",
  "Merge sort",
  "BFS on a graph",
  "Reverse a linked list",
];

export function LandingHero() {
  const [prompt, setPrompt] = useState("");
  const { user } = useAuth();
  const navigate = useNavigate();

  function goCreate(withPrompt: string) {
    const trimmed = withPrompt.trim();
    if (user) {
      navigate("/app", { state: trimmed ? { prefillPrompt: trimmed } : undefined });
    } else {
      navigate("/login", { state: trimmed ? { prefillPrompt: trimmed } : undefined });
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    goCreate(prompt);
  }

  return (
    <section className="hero" id="home">
      <div className="hero__glow" aria-hidden="true" />
      <p className="hero__eyebrow">math-theme-left</p>
      <h1 className="hero__title">
        Need to <span className="hero__title-muted">Visualize?</span>
      </h1>
      <p className="hero__subtitle">
        Turn any algorithm into a narrated video. Just describe it, aiviz animates it.
      </p>

      <button type="button" className="hero__cta" onClick={() => goCreate(prompt)}>
        Start Creating Today <span aria-hidden="true">→</span>
      </button>

      <form className="hero__promptbar" onSubmit={handleSubmit} id="create">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Try: Explain Binary Search."
          aria-label="Describe the algorithm you want visualized"
        />
        <button type="submit" aria-label="Generate">
          →
        </button>
      </form>

      <div className="hero__chips">
        {EXAMPLE_CHIPS.map((chip) => (
          <button key={chip} type="button" className="hero__chip" onClick={() => goCreate(chip)}>
            {chip} <span aria-hidden="true">↗</span>
          </button>
        ))}
      </div>
    </section>
  );
}
