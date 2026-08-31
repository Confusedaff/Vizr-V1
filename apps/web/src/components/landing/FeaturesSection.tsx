import "./FeaturesSection.css";

const FEATURES = [
  {
    title: "Prompt to plan, not prompt to code",
    body: "The LLM only ever writes a structured scene plan — never Manim code. A deterministic renderer takes it from there, so every video is reproducible and every step is inspectable.",
  },
  {
    title: "See exactly what failed, and why",
    body: "Every job leaves a full trail: which stage ran, how long it took, and — if a frame looked wrong — the exact geometric reason. No black box.",
  },
  {
    title: "Bring your own key",
    body: "Groq, Gemini, or Anthropic — pick a provider and paste your own free-tier key. Nothing is shared, nothing is stored beyond your request.",
  },
  {
    title: "Fourteen algorithms, one engine",
    body: "Arrays, trees, graphs, hashmaps, stacks, and dynamic programming all share the same component library, so every video looks and feels consistent.",
  },
];

export function FeaturesSection() {
  return (
    <section className="features" id="features">
      <p className="features__eyebrow">FEATURES</p>
      <h2 className="features__title">
        Everything you need to <span className="features__title-accent">visualize it.</span>
      </h2>
      <div className="features__grid">
        {FEATURES.map((f) => (
          <div className="features__card" key={f.title}>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
