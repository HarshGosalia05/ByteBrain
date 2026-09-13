import type { Metadata } from "next"
import { getSessionUser } from "@/lib/auth-jwt"
import { ROLE_DASHBOARDS, type Role } from "@/lib/session"
import { fetchIntelligenceConsoleData } from "@/lib/intelligence-console"

import { Navbar } from "@/components/landing/navbar"
import { HeroSection } from "@/components/landing/hero-section"
import { StatsSection } from "@/components/landing/stats-section"
import { RolesSection } from "@/components/landing/roles-section"
import { FeaturesSection } from "@/components/landing/features-section"
import { IntelligenceSection } from "@/components/landing/intelligence-section"
import { IntelligenceConsole } from "@/components/landing/intelligence-console"
import { HowItWorksSection } from "@/components/landing/how-it-works-section"
import { StudentJourneySection } from "@/components/landing/student-journey-section"
import { CopilotSection } from "@/components/landing/copilot-section"
import { SecuritySection } from "@/components/landing/security-section"
import { ImpactSection } from "@/components/landing/impact-section"
import { CTASection } from "@/components/landing/cta-section"
import { Footer } from "@/components/landing/footer"
import { Reveal } from "@/components/landing/reveal"
import { SplashCursor } from "@/components/landing/splash-cursor"

export const metadata: Metadata = {
  title: "CampusX — AI-Powered Academic Intelligence Platform",
  description:
    "CampusX unifies academic analytics, predictive ML models, career guidance, and role-based portals into one intelligent educational platform.",
  openGraph: {
    title: "CampusX — Smarter Education. Brighter Futures.",
    description:
      "Academic analytics, ML predictions, career guidance, and role-based dashboards in one intelligent platform.",
    type: "website",
  },
}

export default async function HomePage() {
  const user = await getSessionUser()
  const dashboardUrl =
    user?.role && user.role in ROLE_DASHBOARDS
      ? ROLE_DASHBOARDS[user.role as Role]
      : null

  const consoleResult =
    user?.role === "Student" ? await fetchIntelligenceConsoleData() : null

  return (
    <div className="min-h-screen bg-background text-foreground antialiased selection:bg-primary/20 selection:text-primary relative">
      {/* Background Interactive Splash Cursor (CampusX cyan-blue, subtle low animation) */}
      <SplashCursor
        COLOR="#1da1f2"
        RAINBOW_MODE={false}
        SPLAT_FORCE={1800}
        SPLAT_RADIUS={0.14}
        DENSITY_DISSIPATION={4.5}
        VELOCITY_DISSIPATION={2.5}
        CURL={1.5}
      />

      {/* 1. Sticky Navigation Bar */}
      <Navbar userRole={user?.role ?? null} dashboardUrl={dashboardUrl} />

      <main>
        {/* 2. Hero Section with Live Dashboard Preview */}
        <HeroSection dashboardUrl={dashboardUrl} />

        {/* 3. Intelligence Console — logged-in Student only */}
        {consoleResult?.ok && (
          <Reveal>
            <IntelligenceConsole {...consoleResult.data} />
          </Reveal>
        )}

        {/* 4. Platform Statistics */}
        <Reveal>
          <StatsSection />
        </Reveal>

        {/* 5. Built For Every Stakeholder (Students, Faculty, Admins) */}
        <Reveal>
          <RolesSection userRole={user?.role ?? null} />
        </Reveal>

        {/* 6. 10 Core Key Features */}
        <Reveal>
          <FeaturesSection />
        </Reveal>

        {/* 7. CampusX Intelligence Pipeline & Models (M1-M5) */}
        <Reveal>
          <IntelligenceSection />
        </Reveal>

        {/* 8. How It Works (4-Step Flow) */}
        <Reveal>
          <HowItWorksSection />
        </Reveal>

        {/* 9. End-to-End Student Journey */}
        <Reveal>
          <StudentJourneySection />
        </Reveal>

        {/* 10. AI Academic Copilot Preview */}
        <Reveal>
          <CopilotSection />
        </Reveal>

        {/* 11. Security & Trust Architecture */}
        <Reveal>
          <SecuritySection />
        </Reveal>

        {/* 12. Institutional Impact Columns */}
        <Reveal>
          <ImpactSection />
        </Reveal>

        {/* 13. Final Call-to-Action Banner */}
        <Reveal>
          <CTASection dashboardUrl={dashboardUrl} />
        </Reveal>
      </main>

      {/* 14. Professional Footer */}
      <Footer />
    </div>
  )
}
