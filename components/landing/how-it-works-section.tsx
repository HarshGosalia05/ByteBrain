import * as React from "react"
import { CheckCircle2, Cpu, Eye, FileText, Send } from "lucide-react"

import { Badge } from "@/components/ui/badge"

const STEPS = [
  {
    step: "01",
    label: "Collect",
    title: "Unify Academic Records",
    icon: FileText,
    description:
      "Academic results, subject marks, continuous attendance, and verified student profiles are stitched from institutional databases into structured domain schemas.",
    details: ["21+ database tables", "Direct PostgreSQL ingest", "Zero manual spreadsheets"],
  },
  {
    step: "02",
    label: "Analyze",
    title: "Process Analytics & Models",
    icon: Cpu,
    description:
      "Backend computation engines calculate term KPIs, attendance patterns, and execute M1_v3 to M3 predictive machine learning models in batch workflows.",
    details: ["Leakage-safe training", "Scikit-learn pipelines", "Real-time KPI aggregation"],
  },
  {
    step: "03",
    label: "Understand",
    title: "Synthesize Grounded Insights",
    icon: Eye,
    description:
      "CampusX translates raw probabilities into interpretable academic risk indicators, subject mark projections, and personalized career readiness assessments.",
    details: ["Explainable factors", "Career skill alignment", "Early warning detection"],
  },
  {
    step: "04",
    label: "Act",
    title: "Execute Timely Interventions",
    icon: Send,
    description:
      "Students optimize study schedules, faculty mentors trigger targeted learning interventions, and administrators steer institutional resources with confidence.",
    details: ["Role-scoped portals", "30+ CSV data exports", "Intelligent notification alerts"],
  },
]

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="py-20 sm:py-28 relative bg-muted/10 border-t border-border/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
            Execution Flow
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            How CampusX Works
          </h2>
          <p className="mt-4 text-base sm:text-lg text-muted-foreground">
            A reliable 4-step workflow that transforms fragmented campus records into early,
            actionable academic interventions.
          </p>
        </div>

        {/* 4-Step Grid (Horizontal on Desktop, Vertical on Mobile) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative">
          {STEPS.map((step) => {
            const Icon = step.icon
            return (
              <div
                key={step.step}
                className="relative flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-6 shadow-xs ring-1 ring-foreground/5 hover:border-primary/40 transition-colors"
              >
                <div>
                  {/* Step badge & Icon */}
                  <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-lg">
                      STEP {step.step}
                    </span>
                    <span className="flex size-9 items-center justify-center rounded-xl bg-muted text-foreground">
                      <Icon className="size-4 text-primary" />
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-foreground">
                    {step.title}
                  </h3>
                  <p className="text-xs font-semibold text-primary uppercase tracking-wider mt-0.5">
                    {step.label}
                  </p>

                  <p className="mt-3 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {step.description}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-border/40 space-y-1.5">
                  {step.details.map((detail) => (
                    <div key={detail} className="flex items-center gap-2 text-xs text-muted-foreground">
                      <CheckCircle2 className="size-3 text-chart-2 shrink-0" />
                      <span>{detail}</span>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
