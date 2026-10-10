"use client";

import HeroStage from "@/components/figma/HeroStage";
import { AiCreditsSection, ArchitectureSection, CtaSection, FaqSection, FeaturesSection, FooterSection, PricingSection, ProductTourSection, SecuritySection } from "@/components/figma/LandingSections";

// Landing page reproduced from the Figma "AI SaaS Website Design -- Premium Landing Page for AI Tools" reference: one continuous black page
// (#010101) with the same artwork behind every section. The hero, navigation, figures strip and the decorative layers are the exported design
// itself; the texts are the product's own (translated), the plans come from the real billing endpoint.
export default function LandingPage() {
  return (
    <div className="relative overflow-x-clip bg-[#010101] text-white">
      <HeroStage />
      <FeaturesSection />
      <ProductTourSection />
      <ArchitectureSection />
      <AiCreditsSection />
      <SecuritySection />
      <PricingSection />
      <FaqSection />
      <CtaSection />
      <FooterSection />
    </div>
  );
}
