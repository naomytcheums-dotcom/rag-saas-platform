import LandingNavbar from "@/components/landing/LandingNavbar";
import LandingHero from "@/components/landing/LandingHero";
import LandingLogos from "@/components/landing/LandingLogos";
import LandingBento from "@/components/landing/LandingBento";
import LandingItems from "@/components/landing/LandingItems";
import LandingFeatureRising from "@/components/landing/LandingFeatureRising";
import LandingTabs from "@/components/landing/LandingTabs";

// Reproduction a l'identique de la maquette Figma "Launch UI" --
// https://www.figma.com/design/eAxoVdXfGpnPmhfpWYX5hB -- texte, logos et
// branding d'origine conserves tels quels. 7 des 12 sections desktop sont
// couvertes ici (Navbar, Hero, Logos, Bento Grid, Items, Feature/Rising,
// Tabs) -- Testimonials, Pricing, FAQ, CTA et Footer restent a recuperer
// une fois la limite d'appels de l'API Figma MCP reinitialisee. Les
// versions Tablet et Mobile de la maquette n'ont pas encore ete
// recuperees non plus (meme blocage).
export default function MaquettePage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-white">
      <LandingNavbar />
      <LandingHero />
      <LandingLogos />
      <LandingBento />
      <LandingItems />
      <LandingFeatureRising />
      <LandingTabs />
    </div>
  );
}
