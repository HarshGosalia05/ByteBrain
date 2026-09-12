import * as React from "react"
import {
  BookOpen,
  CalendarCheck,
  CheckCircle2,
  Compass,
  GraduationCap,
  Info,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const JOURNEY_NODES = [
  {
    step: "01",
    phase: "Year 1 · Onboarding",
    label: "Academic Foundations",
    icon: GraduationCap,
    desc: "Baseline tracking of SGPA, cumulative CGPA, and historical semester progress from day one.",
    highlight: "SGPA & CGPA baseline setup",
    milestone: "Enrollment",
  },
  {
    step: "02",
    phase: "Years 1–2 · Engagement",
    label: "Attendance & Habits",
    icon: CalendarCheck,
    desc: "Real-time class presence tracking, 75% statutory compliance monitoring, and defaulter prevention.",
    highlight: "75% compliance tracking",
    milestone: "Active Monitoring",
  },
  {
    step: "03",
    phase: "Years 2–3 · Mid-Degree",
    label: "Continuous Evaluation",
    icon: BookOpen,
    desc: "In-depth tracking of internal assessments (C1/C2), lab work, and theory engagement across all subjects.",
    highlight: "C1 & C2 exam analytics",
    milestone: "Coursework",
  },
  {
    step: "04",
    phase: "Years 2–3 · Intervention",
    label: "Risk & Course Correction",
    icon: ShieldAlert,
    desc: "Automated identification of academic distress to trigger proactive faculty mentoring and advisory support.",
    highlight: "Proactive mentor intervention",
    milestone: "Advisory",
  },
  {
    step: "05",
    phase: "Year 3–4 · Advanced Planning",
    label: "Next-Semester Trajectory",
    icon: TrendingUp,
    desc: "Forward-looking AI projections across theory and practical coursework to prepare for final terms.",
    highlight: "Upcoming term forecasting",
    milestone: "Trajectory",
  },
  {
    step: "06",
    phase: "Final Year · Industry",
    label: "Career & Placement",
    icon: Compass,
    desc: "Competency readiness scoring, domain skill-gap mapping, and structured career pathway guidance.",
    highlight: "Job readiness & skill mapping",
    milestone: "Industry Ready",
  },
]

export function StudentJourneySection() {
  return (
    <section className="py-20 sm:py-28 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-14">
          <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
            End-To-End Student Journey
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            Guiding Every Step From Enrollment to Industry
          </h2>
          <p className="mt-4 text-base sm:text-lg text-muted-foreground">
            CampusX supports students throughout their entire university lifecycle, connecting daily
            effort with future academic and professional milestones.
          </p>
        </div>

        {/* Visual Lifecycle Progress Track */}
        <div className="mb-10 hidden md:grid grid-cols-3 gap-4 rounded-xl border border-border/60 bg-muted/20 p-3 text-xs">
          <div className="flex items-center gap-2.5 px-2">
            <span className="flex size-6 items-center justify-center rounded-full bg-primary/15 text-primary text-[0.7rem] font-bold">
              1
            </span>
            <div>
              <p className="font-semibold text-foreground">Foundation Phase</p>
              <p className="text-[0.68rem] text-muted-foreground">Academic onboarding & attendance</p>
            </div>
          </div>
          <div className="flex items-center gap-2.5 px-2 border-l border-border/50">
            <span className="flex size-6 items-center justify-center rounded-full bg-primary/15 text-primary text-[0.7rem] font-bold">
              2
            </span>
            <div>
              <p className="font-semibold text-foreground">Diagnostic & Intervention</p>
              <p className="text-[0.68rem] text-muted-foreground">Continuous assessment & risk alerts</p>
            </div>
          </div>
          <div className="flex items-center gap-2.5 px-2 border-l border-border/50">
            <span className="flex size-6 items-center justify-center rounded-full bg-chart-2/15 text-chart-2 text-[0.7rem] font-bold">
              3
            </span>
            <div>
              <p className="font-semibold text-foreground">Placement & Transition</p>
              <p className="text-[0.68rem] text-muted-foreground">Term outlook & industry readiness</p>
            </div>
          </div>
        </div>

        {/* 6 Journey Step Cards (3x2 Grid for spacious readability) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6 mb-12">
          {JOURNEY_NODES.map((node) => {
            const Icon = node.icon
            return (
              <div
                key={node.step}
                className={cn(
                  "group relative flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-6 shadow-xs transition-all duration-300 hover:-translate-y-1.5 hover:border-primary/60 hover:shadow-xl ring-1 ring-foreground/5 motion-reduce:hover:translate-y-0"
                )}
              >
                <div>
                  {/* Top Header: Step + Phase Tag & Icon */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground text-xs font-bold shadow-xs">
                        {node.step}
                      </span>
                      <span className="text-[0.7rem] font-medium text-muted-foreground uppercase tracking-wider">
                        {node.phase}
                      </span>
                    </div>
                    <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary transition-all duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground">
                      <Icon className="size-4" />
                    </span>
                  </div>

                  {/* Title & Description */}
                  <h3 className="text-base sm:text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                    {node.label}
                  </h3>
                  <p className="mt-2 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    {node.desc}
                  </p>
                </div>

                {/* Proper Capability / Milestone Footer (replaces fake "Next Phase ->") */}
                <div className="mt-5 pt-3.5 border-t border-border/50 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-muted-foreground text-[0.72rem]">
                    <CheckCircle2 className="size-3.5 text-chart-2 shrink-0" />
                    <span className="font-medium text-foreground/85">{node.highlight}</span>
                  </div>
                  <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-md">
                    {node.milestone}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Responsible AI Transparency Disclaimer */}
        <div className="rounded-xl border border-border/60 bg-muted/20 p-4 sm:p-5 flex items-start gap-3.5 max-w-4xl mx-auto">
          <Info className="size-5 text-primary shrink-0 mt-0.5" />
          <div className="text-xs text-muted-foreground leading-relaxed">
            <span className="font-semibold text-foreground">Responsible AI & Transparency: </span>
            Predictive machine learning models in CampusX are designed as decision-support indicators
            to assist students and academic advisors in timely course correction. Models reflect
            statistical probabilities based on validated historical patterns and do not determine or
            guarantee final institutional outcomes.
          </div>
        </div>
      </div>
    </section>
  )
}
