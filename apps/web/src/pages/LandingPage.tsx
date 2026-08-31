import { FeaturesSection } from "../components/landing/FeaturesSection";
import { LandingFooter } from "../components/landing/LandingFooter";
import { LandingHero } from "../components/landing/LandingHero";
import { LandingNav } from "../components/landing/LandingNav";
import { ShowcaseCarousel } from "../components/landing/ShowcaseCarousel";
import "./LandingPage.css";

export function LandingPage() {
  return (
    <div className="landing-page">
      <LandingNav />
      <LandingHero />
      <FeaturesSection />
      <ShowcaseCarousel />
      <LandingFooter />
    </div>
  );
}
