import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "./LandingNav.css";

const LINKS = [
  { href: "#home", label: "Home" },
  { href: "#features", label: "Features" },
  { href: "#showcase", label: "Showcase" },
  { href: "#create", label: "Create" },
];

export function LandingNav() {
  const [menuOpen, setMenuOpen] = useState(false);

  // Close the mobile menu automatically if the viewport is resized back
  // up past the breakpoint (e.g. rotating a tablet, or a resized
  // desktop window) so it can never get stuck open where it no longer
  // makes sense.
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 861px)");
    const handler = () => {
      if (mq.matches) setMenuOpen(false);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Lock body scroll while the mobile menu is open so the page behind
  // the overlay doesn't scroll with it.
  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = "";
      };
    }
  }, [menuOpen]);

  return (
    <header className="landing-nav">
      <div className="landing-nav__inner">
        <Link to="/" className="landing-nav__brand" onClick={() => setMenuOpen(false)}>
          vizr
        </Link>
        <nav className="landing-nav__links" aria-label="Primary">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href}>
              {l.label}
            </a>
          ))}
        </nav>
        <Link to="/login" className="landing-nav__cta">
          Get Started
        </Link>
        <button
          type="button"
          className="landing-nav__menu-btn"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="landing-nav-mobile-menu"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span className={`landing-nav__burger ${menuOpen ? "landing-nav__burger--open" : ""}`} />
        </button>
      </div>

      <nav
        id="landing-nav-mobile-menu"
        className={`landing-nav__mobile ${menuOpen ? "landing-nav__mobile--open" : ""}`}
        aria-label="Primary mobile"
        aria-hidden={!menuOpen}
      >
        {LINKS.map((l) => (
          <a key={l.href} href={l.href} onClick={() => setMenuOpen(false)}>
            {l.label}
          </a>
        ))}
        <Link to="/login" className="landing-nav__mobile-cta" onClick={() => setMenuOpen(false)}>
          Get Started
        </Link>
      </nav>
    </header>
  );
}
