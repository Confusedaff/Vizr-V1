import { useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../api/client";
import "./AuthPage.css";

export function AuthPage() {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login, signup } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const prefillPrompt = (location.state as { prefillPrompt?: string } | null)?.prefillPrompt;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await signup(email, password);
      }
      navigate("/app", { state: prefillPrompt ? { prefillPrompt } : undefined });
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Something went wrong. Try again.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-page__card">
        <div className="auth-page__mark">
          <span className="auth-page__mark-glyph">▸</span>
          <span className="auth-page__mark-text">aiviz</span>
        </div>
        <p className="auth-page__tagline">Turn an algorithm into a video you can trust.</p>

        {prefillPrompt && (
          <p className="auth-page__prefill-note">
            Sign in to generate: <span className="mono">&ldquo;{prefillPrompt}&rdquo;</span>
          </p>
        )}

        <div className="auth-page__tabs">
          <button
            className={mode === "login" ? "auth-page__tab auth-page__tab--active" : "auth-page__tab"}
            onClick={() => setMode("login")}
            type="button"
          >
            Log in
          </button>
          <button
            className={mode === "signup" ? "auth-page__tab auth-page__tab--active" : "auth-page__tab"}
            onClick={() => setMode("signup")}
            type="button"
          >
            Sign up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-page__form">
          <label className="auth-page__field">
            <span>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
            />
          </label>
          <label className="auth-page__field">
            <span>Password</span>
            <input
              type="password"
              required
              minLength={8}
              maxLength={72}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder="At least 8 characters"
            />
          </label>

          {error && <p className="auth-page__error">{error}</p>}

          <button type="submit" className="auth-page__submit" disabled={submitting}>
            {submitting ? "Working…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
