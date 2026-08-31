import { Link } from "react-router-dom";
import "./LandingNav.css";

export function LandingNav() {
  return (
    <header className="landing-nav">
      <div className="landing-nav__inner">
        <Link to="/" className="landing-nav__brand">
          aiviz
        </Link>
        <nav className="landing-nav__links" aria-label="Primary">
          <a href="#home">Home</a>
          <a href="#features">Features</a>
          <a href="#showcase">Showcase</a>
          <a href="#create">Create</a>
        </nav>
        <Link to="/login" className="landing-nav__cta">
          Get Started
        </Link>
      </div>
    </header>
  );
}
