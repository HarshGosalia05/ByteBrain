import * as React from "react"
import Link from "next/link"
import { ArrowRight, LayoutDashboard, Sparkles } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface CTASectionProps {
  dashboardUrl?: string | null
}

export function CTASection({ dashboardUrl }: CTASectionProps) {
  return (
    <section className="py-20 sm:py-28 relative overflow-hidden">
      {/* Background subtle radial glow */}
      <div
        className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center"
        aria-hidden="true"
      >
        <div className="w-[500px] h-[300px] bg-primary/10 blur-[120px] rounded-full" />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-primary/30 bg-card p-8 sm:p-14 text-center shadow-xl ring-1 ring-primary/20 relative overflow-hidden">
          {/* Subtle decorative elements */}
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground mb-6 shadow-md">
            <Sparkles className="size-6" />
          </div>

          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-foreground max-w-3xl mx-auto leading-tight">
            Build a Smarter Academic Future with CampusX.
          </h2>

          <p className="mt-4 sm:mt-6 text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Turn academic data into meaningful insights, better decisions, and stronger student outcomes.
          </p>

          <div className="mt-8 sm:mt-10 flex flex-col sm:flex-row items-center justify-center gap-3.5">
            {dashboardUrl ? (
              <Link
                href={dashboardUrl}
                className={cn(buttonVariants({ size: "lg" }), "px-8 py-6 text-base font-semibold gap-2 shadow-sm justify-center")}
              >
                <LayoutDashboard className="size-4" />
                <span>Go to Dashboard</span>
              </Link>
            ) : (
              <Link
                href="/login"
                className={cn(buttonVariants({ size: "lg" }), "px-8 py-6 text-base font-semibold gap-2 shadow-sm justify-center")}
              >
                <span>Get Started</span>
                <ArrowRight className="size-4" />
              </Link>
            )}

            <Link
              href="#features"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }), "px-8 py-6 text-base font-semibold text-foreground justify-center")}
            >
              Explore Features
            </Link>
          </div>

          <p className="mt-6 text-xs text-muted-foreground">
            Production-ready academic intelligence platform · Secure institutional sign-in
          </p>
        </div>
      </div>
    </section>
  )
}
