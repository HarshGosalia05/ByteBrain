import * as React from "react"
import Link from "next/link"
import { ArrowRight } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { DashboardPreview } from "./dashboard-preview"

interface HeroSectionProps {
  dashboardUrl?: string | null
}

export function HeroSection({ dashboardUrl }: HeroSectionProps) {
  return (
    <section
      id="top"
      className="relative overflow-hidden pt-12 pb-16 md:pt-20 md:pb-24 lg:pt-24 lg:pb-32"
    >
      {/* Ambient subtle glow background */}
      <div
        className="pointer-events-none absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-primary/10 blur-[130px] rounded-full -z-10"
        aria-hidden="true"
      />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Copy & Actions */}
          <div className="lg:col-span-6 flex flex-col items-start text-left">
            {/* Tagline / Pill */}
            <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card px-3 py-1 text-xs font-medium text-muted-foreground mb-6 shadow-xs ring-1 ring-foreground/5">
              <span className="flex size-2 rounded-full bg-primary animate-pulse" />
              <span className="text-foreground font-semibold">CampusX KDAC-3</span>
              <span className="text-muted-foreground/60">|</span>
              <span>Next-Gen Academic Intelligence</span>
            </div>

            {/* Main Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-foreground leading-[1.1]">
              Smarter Education.
              <br />
              <span className="bg-gradient-to-r from-foreground via-foreground to-primary bg-clip-text text-transparent">
                Brighter Futures.
              </span>
            </h1>

            {/* Supporting Paragraph */}
            <p className="mt-6 text-base sm:text-lg text-muted-foreground max-w-xl leading-relaxed">
              CampusX brings academic analytics, AI-powered insights, career
              guidance, and intelligent decision-making together in one platform.
            </p>

            {/* CTAs */}
            <div className="mt-8 flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto">
              {dashboardUrl ? (
                <Link
                  href={dashboardUrl}
                  className={cn(
                    buttonVariants({ size: "lg" }),
                    "group gap-2 font-medium px-7 py-5 text-base shadow-sm justify-center transition-all duration-200 hover:shadow-md hover:scale-[1.02] active:scale-[0.98]"
                  )}
                >
                  <span>Go to Dashboard</span>
                  <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-1" />
                </Link>
              ) : (
                <Link
                  href="/login"
                  className={cn(
                    buttonVariants({ size: "lg" }),
                    "group gap-2 font-medium px-7 py-5 text-base shadow-sm justify-center transition-all duration-200 hover:shadow-md hover:scale-[1.02] active:scale-[0.98]"
                  )}
                >
                  <span>Get Started</span>
                  <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-1" />
                </Link>
              )}

              <Link
                href="#features"
                className={cn(
                  buttonVariants({ variant: "outline", size: "lg" }),
                  "px-7 py-5 text-base text-foreground font-medium justify-center transition-all duration-200 hover:border-primary/60 hover:bg-accent/40 active:scale-[0.98]"
                )}
              >
                Explore CampusX
              </Link>
            </div>
          </div>

          {/* Right Column: Interactive High-Fidelity Dashboard Preview */}
          <div className="lg:col-span-6 w-full relative">
            <DashboardPreview />
          </div>
        </div>
      </div>
    </section>
  )
}
