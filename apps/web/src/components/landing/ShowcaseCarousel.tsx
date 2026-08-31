import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { SHOWCASE_SLIDES } from "./showcaseData";
import { ShowcaseMockup } from "./ShowcaseMockup";
import "./ShowcaseCarousel.css";

export function ShowcaseCarousel() {
  const [index, setIndex] = useState(0);
  const { user } = useAuth();
  const navigate = useNavigate();
  const slide = SHOWCASE_SLIDES[index];

  function tryPrompt(prompt: string) {
    const path = user ? "/app" : "/login";
    navigate(path, { state: { prefillPrompt: prompt } });
  }

  return (
    <section className="showcase" id="showcase" style={{ ["--mockup-accent" as string]: `var(${slide.accent})` }}>
      <div className="showcase__panel">
        <div className="showcase__copy">
          <p className="showcase__eyebrow" style={{ color: `var(${slide.accent})` }}>
            {slide.category}
          </p>
          <h2 className="showcase__title">{slide.title}</h2>
          <p className="showcase__description">{slide.description}</p>

          <p className="showcase__try-label">TRY IT</p>
          <button className="showcase__try-prompt" onClick={() => tryPrompt(slide.tryPrompt)}>
            <span className="showcase__try-glyph">/</span> {slide.tryPrompt}
          </button>

          <div className="showcase__dots">
            {SHOWCASE_SLIDES.map((s, i) => (
              <button
                key={s.id}
                className={`showcase__dot ${i === index ? "showcase__dot--active" : ""}`}
                style={i === index ? { background: `var(${s.accent})` } : undefined}
                onClick={() => setIndex(i)}
                aria-label={`Show ${s.title}`}
              />
            ))}
          </div>
        </div>

        <div className="showcase__stage">
          <span className="showcase__stage-badge" style={{ borderColor: `var(${slide.accent})`, color: `var(${slide.accent})` }}>
            {slide.categoryLabel}
          </span>
          <ShowcaseMockup kind={slide.mockup} />
        </div>
      </div>

      <div className="showcase__pagination">
        {SHOWCASE_SLIDES.map((s, i) => (
          <button
            key={s.id}
            className={`showcase__page-btn ${i === index ? "showcase__page-btn--active" : ""}`}
            style={i === index ? { background: `var(${s.accent})`, color: "#0a0d11", borderColor: `var(${s.accent})` } : undefined}
            onClick={() => setIndex(i)}
          >
            {i + 1}
          </button>
        ))}
      </div>
    </section>
  );
}
