import * as React from "react"
import { CheckCircle2, GraduationCap, School, UserCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"

const IMPACT_COLS = [
  {
    role: "For Students",
    headline: "Know where you stand.",
    icon: GraduationCap,
    description:
      "Instant clarity on academic standing, attendance compliance warnings, and early predicted grades so you can correct your trajectory before final examinations.",
    bullets: [
      "Track continuous assessments across all enrolled subjects",
      "Eliminate surprise attendance shortfalls before hall tickets",
      "Receive personalized career readiness guidance and skill gaps",
    ],
  },
  {
    role: "For Faculty",
    headline: "Know who needs attention.",
    icon: UserCheck,
    description:
      "Actionable learning-gap alerts, mentee cohort management, and automated workload governance metrics that replace tedious manual spreadsheet tabulation.",
    bullets: [
      "Instantly spot students slipping below the 75% attendance line",
      "Inspect grade curve distributions across test C1 and C2",
      "Access weekly timetable and teaching capacity metrics",
    ],
    featured: true,
  },
  {
    role: "For Administrators",
    headline: "Know what is happening across the institution.",
    icon: School,
    description:
      "Centralized departmental performance indicators, cohort retention trajectories, and teaching capacity analytics for data-informed academic leadership.",
    bullets: [
      "Compare pass rates and average SGPAs across departments",
      "Track multi-year academic progression and backlog volumes",
      "Export 30+ chart-level reports for compliance and accreditation",
    ],
  },
]

export function ImpactSection() {
  return (
    <section className="py-20 sm:py-28 relative bg-muted/10 border-t border-border/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
            Institutional Impact
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            Clarity For Every Academic Decision
          </h2>
          <p className="mt-4 text-base sm:text-lg text-muted-foreground">
            Transforming reactive guesswork into structured, timely, and data-backed academic action.
          </p>
        </div>

        {/* 3 Impact Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {IMPACT_COLS.map((col) => {
            const Icon = col.icon
            return (
              <div
                key={col.role}
                className="flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-6 sm:p-8 shadow-xs ring-1 ring-foreground/5 hover:border-primary/40 transition-colors"
              >
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Icon className="size-5" />
                    </span>
                    <span className="text-xs font-bold uppercase tracking-wider text-primary">
                      {col.role}
                    </span>
                  </div>

                  <h3 className="text-xl sm:text-2xl font-bold text-foreground leading-snug">
                    &ldquo;{col.headline}&rdquo;
                  </h3>

                  <p className="mt-3 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {col.description}
                  </p>

                  <div className="mt-6 pt-6 border-t border-border/40 space-y-2.5">
                    {col.bullets.map((b) => (
                      <div key={b} className="flex items-start gap-2 text-xs text-muted-foreground">
                        <CheckCircle2 className="size-4 text-chart-2 shrink-0 mt-0.5" />
                        <span>{b}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
