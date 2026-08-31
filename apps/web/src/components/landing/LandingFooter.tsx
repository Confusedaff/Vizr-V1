import { Link } from "react-router-dom";
import "./LandingFooter.css";

export function LandingFooter() {
  return (
    <footer className="landing-footer" id="contact">
      <div className="landing-footer__inner">
        <span className="landing-footer__brand">vizr</span>
        <p>Turn an algorithm into a video you can trust.</p>
        <Link to="/login" className="landing-footer__cta">
          Get Started →
        </Link>
      </div>
    </footer>
  );
}
