import * as React from "react"
import {
  Bell,
  Bot,
  BrainCircuit,
  CalendarCheck,
  CheckCircle2,
  Compass,
  FileSpreadsheet,
  Layers,
  LineChart,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const FEATURES = [
  {
    id: "perf-analytics",
    icon: LineChart,
    name: "Academic Performance Analytics",
    tag: "Core Analytics",
    description:
      "Term-over-term CGPA & SGPA tracking, grade distribution curves, and cohort learning-gap diagnostics with automated KPI cards.",
    highlight: "Term-over-term trendlines",
    status: "Active",
    featured: true,
  },
  {
    id: "att-analytics",
    icon: CalendarCheck,
    name: "Attendance Analytics",
    tag: "Governance",
    description:
      "Subject-wise attendance tracking, hourly heatmaps, correlation with exam performance, and automated defaulter review queues.",
    highlight: "75% threshold monitoring",
    status: "Automated",
  },
  {
    id: "subj-insights",
    icon: FileSpreadsheet,
    name: "Subject-Level Insights",
    tag: "Continuous Eval",
    description:
      "Granular C1, C2, and end-semester mark analysis with deep theory vs. lab practical score breakdowns across all enrolled courses.",
    highlight: "C1 & C2 score breakdown",
    status: "Continuous",
  },
  {
    id: "ml-preds",
    icon: BrainCircuit,
    name: "ML-Powered Predictions",
    tag: "Forecasting",
    description:
      "Gradient-boosted machine learning projecting individual student end-semester marks using early continuous evaluation signals.",
    highlight: "End-sem grade projections",
    status: "AI Model",
    featured: true,
  },
  {
    id: "risk-assess",
    icon: ShieldAlert,
    name: "Academic Risk Assessment",
    tag: "Early Warning",
    description:
      "Multi-factor risk classification (Low, Medium, High) that identifies students needing academic intervention well before exam finals.",
    highlight: "Timely student intervention",
    status: "Real-Time",
  },
  {
    id: "next-sem",
    icon: TrendingUp,
    name: "Next-Semester Outlook",
    tag: "Trajectory",
    description:
      "Dual-target predictive models forecasting upcoming semester theory marks and laboratory practical engagement trajectories.",
    highlight: "Dual-target projections",
    status: "Predictive",
  },
  {
    id: "career-guidance",
    icon: Compass,
    name: "Career Direction & Guidance",
    tag: "Career Alignment",
    description:
      "Evaluates student competencies, calculates career readiness scores, and maps personalized learning paths toward target industry roles.",
    highlight: "Industry role readiness",
    status: "Guidance",
    featured: true,
  },
  {
    id: "role-dashboards",
    icon: Layers,
    name: "Role-Based Dashboards",
    tag: "Security",
    description:
      "Isolated portals designed for Students, Faculty, and Administrators with strictly enforced data access rules and audit logging.",
    highlight: "Strict role data isolation",
    status: "RBAC Enforced",
  },
  {
    id: "intel-notifs",
    icon: Bell,
    name: "Intelligent Notifications",
    tag: "Communications",
    description:
      "Proactive alerts for attendance dips below 75%, grade threshold breaches, exam eligibility status, and institutional circulars.",
    highlight: "Multi-channel dispatch",
    status: "Automated",
  },
  {
    id: "ai-copilot",
    icon: Bot,
    name: "AI Chat Assistant",
    tag: "GenAI Copilot",
    description:
      "Role-aware conversational assistant providing grounded answers derived exclusively from verified academic records and zero hallucination.",
    highlight: "Zero-hallucination answers",
    status: "Grounded AI",
    featured: true,
  },
]

export function FeaturesSection() {
  return (
    <section id="features" className="py-20 sm:py-28 relative bg-muted/10 border-t border-border/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
            Platform Capabilities
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            A Unified Academic Intelligence Architecture
          </h2>
          <p className="mt-4 text-base sm:text-lg text-muted-foreground">
            10 production-tested capabilities engineered to replace manual spreadsheets,
            unify fragmented records, and turn academic data into timely intervention.
          </p>
        </div>

        {/* 10-Feature Responsive Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((feature) => {
            const Icon = feature.icon
            return (
              <div
                key={feature.id}
                className={cn(
                  "group relative flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-6 shadow-xs transition-all duration-300 hover:-translate-y-1.5 hover:border-primary/60 hover:shadow-xl ring-1 ring-foreground/5 motion-reduce:hover:translate-y-0",
                  feature.featured && "lg:col-span-1 border-primary/30 bg-card/80"
                )}
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary transition-all duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground group-hover:shadow-md">
                      <Icon className="size-5" />
                    </span>
                    <span className="text-[0.7rem] font-semibold tracking-wider text-muted-foreground uppercase bg-muted/50 px-2.5 py-1 rounded-md border border-border/40 transition-colors group-hover:border-primary/30 group-hover:text-foreground">
                      {feature.tag}
                    </span>
                  </div>

                  <h3 className="text-base sm:text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                    {feature.name}
                  </h3>

                  <p className="mt-2.5 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {feature.description}
                  </p>
                </div>

                {/* Clean, authentic capability footer */}
                <div className="mt-5 pt-3.5 border-t border-border/50 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-muted-foreground text-[0.72rem]">
                    <CheckCircle2 className="size-3.5 text-chart-2 shrink-0" />
                    <span className="font-medium text-foreground/85">{feature.highlight}</span>
                  </div>
                  <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-md">
                    {feature.status}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
