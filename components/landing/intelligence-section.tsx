import * as React from "react"
import {
  ArrowDown,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Database,
  LineChart,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"

const PIPELINE_STEPS = [
  { label: "CampusX Data", sub: "21 Tables · 7 Domains", icon: Database },
  { label: "Analytics", sub: "KPIs · Distributions", icon: LineChart },
  { label: "ML Predictions", sub: "M1_v3 & M2-TP Models", icon: BrainCircuit },
  { label: "Verified Insights", sub: "M3 Risk & M4 Readiness", icon: Target },
  { label: "Actionable Guidance", sub: "M5 GenAI Roadmap", icon: Sparkles },
]

const MODELS = [
  {
    code: "M1_v3",
    name: "Subject End-Semester Marks Prediction",
    type: "Predictive ML Model",
    typeBadge: "Gradient Boosting",
    description:
      "Predicts continuous end-semester marks on the /70 scale per enrolled subject using continuous evaluation signals (C1, C2, attendance rate, assignment submissions).",
    inputs: ["Continuous Assessments (C1/C2)", "Attendance Rate", "Historical Subject Performance"],
    output: "Predicted End-Sem Marks & Expected Grade Band",
  },
  {
    code: "M2-TP",
    name: "Next-Semester Theory & Practical Outlook",
    type: "Predictive ML Model",
    typeBadge: "Dual-Target Ensemble",
    description:
      "Projects expected performance across upcoming semester curriculum, separating theory mastery from laboratory/practical aptitude to highlight specific preparation gaps.",
    inputs: ["Cumulative SGPA History", "Prior Lab Performance", "Course Prerequisite Grades"],
    output: "Dual Projection: Theory % & Practical Engagement",
  },
  {
    code: "M3",
    name: "Academic Risk Prediction",
    type: "Early-Warning Classifier",
    typeBadge: "Supervised Classifier",
    description:
      "Categorizes students into Low, Medium, or High academic risk categories well before final examinations, surfacing key risk contributors for faculty mentor intervention.",
    inputs: ["Attendance Deficits", "Down-trending Marks", "Historical Backlog Record"],
    output: "Risk Tier Classification & Primary Contributing Factors",
  },
  {
    code: "M4",
    name: "Career Readiness Assessment",
    type: "Evaluation Engine",
    typeBadge: "Multi-Factor Scoring",
    description:
      "Evaluates a student's holistic preparation for industry roles by combining academic consistency, declared skills, project history, and career preferences.",
    inputs: ["Verified Course Grades", "Skill Inventory", "Project & Internship Signals"],
    output: "Overall Readiness Score (0-100%) & Competency Breakdown",
  },
  {
    code: "M5",
    name: "Career Domain Mapping & Grounded GenAI",
    type: "Intelligence & Guidance Layer",
    typeBadge: "Grounded LLM + Mapping",
    description:
      "Maps student profiles to high-fit industry tracks (AI/ML, Cloud, Full-Stack, Data) and produces role-scoped, grounded advice strictly within verified student boundaries.",
    inputs: ["M4 Readiness Output", "Domain Market Alignment", "Academic Specialization"],
    output: "Personalized Action Roadmap & Grounded AI Guidance",
  },
]

export function IntelligenceSection() {
  return (
    <section id="intelligence" className="py-20 sm:py-28 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
            CampusX Intelligence
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            From Raw Academic Data to Grounded Action
          </h2>
          <p className="mt-4 text-base sm:text-lg text-muted-foreground">
            CampusX connects verified institutional datasets to specialized machine learning models
            and rule-based evaluators, ensuring every insight is explainable and strictly bounded.
          </p>
        </div>

        {/* Visual Pipeline Flow Diagram */}
        <div className="mb-16 rounded-2xl border border-border/80 bg-card p-6 sm:p-8 shadow-sm ring-1 ring-foreground/5">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground text-center mb-6">
            The CampusX Verified Data Pipeline
          </p>

          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            {PIPELINE_STEPS.map((step, idx) => {
              const Icon = step.icon
              const isLast = idx === PIPELINE_STEPS.length - 1
              return (
                <React.Fragment key={step.label}>
                  <div className="flex flex-col items-center text-center w-full md:w-auto">
                    <span className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 mb-2">
                      <Icon className="size-5" />
                    </span>
                    <span className="text-sm font-bold text-foreground">
                      {step.label}
                    </span>
                    <span className="text-[0.7rem] text-muted-foreground">
                      {step.sub}
                    </span>
                  </div>

                  {!isLast && (
                    <div className="hidden md:flex items-center text-primary/40 shrink-0">
                      <ArrowRight className="size-5" />
                    </div>
                  )}
                  {!isLast && (
                    <div className="flex md:hidden items-center text-primary/40 my-1">
                      <ArrowDown className="size-4" />
                    </div>
                  )}
                </React.Fragment>
              )
            })}
          </div>

          <div className="mt-6 pt-4 border-t border-border/60 text-center text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Zero Synthetic Leaks: </span>
            Predictions are generated only from pre-exam features. CSE Sem 7 and current incomplete terms never use fabricated future results.
          </div>
        </div>

        {/* Detailed Model Architecture Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {MODELS.map((model) => (
            <div
              key={model.code}
              className="flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-6 shadow-xs transition-all duration-200 hover:border-primary/40 ring-1 ring-foreground/5"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono text-sm font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-lg border border-primary/20">
                    {model.code}
                  </span>
                  <Badge variant="outline" className="text-[0.65rem] border-border/80 text-muted-foreground">
                    {model.typeBadge}
                  </Badge>
                </div>

                <h3 className="text-base font-bold text-foreground">
                  {model.name}
                </h3>
                <p className="text-[0.7rem] font-medium text-primary mt-0.5">
                  {model.type}
                </p>

                <p className="mt-3 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                  {model.description}
                </p>

                <div className="mt-4 pt-3 border-t border-border/40 space-y-2">
                  <div>
                    <span className="text-[0.65rem] font-semibold tracking-wider text-muted-foreground uppercase">
                      Inputs:
                    </span>
                    <ul className="mt-1 space-y-0.5">
                      {model.inputs.map((inp) => (
                        <li key={inp} className="text-[0.75rem] text-muted-foreground flex items-center gap-1.5">
                          <CheckCircle2 className="size-3 text-primary shrink-0" />
                          <span>{inp}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="pt-2">
                    <span className="text-[0.65rem] font-semibold tracking-wider text-muted-foreground uppercase">
                      Output Contract:
                    </span>
                    <p className="mt-0.5 text-xs font-medium text-foreground">
                      {model.output}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Model Integrity Summary Card */}
          <div className="flex flex-col justify-between rounded-2xl border border-primary/30 bg-primary/5 p-6 shadow-xs ring-1 ring-primary/20">
            <div>
              <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground mb-4">
                <ShieldCheck className="size-5" />
              </div>

              <h3 className="text-base font-bold text-foreground">
                Responsible AI & Model Governance
              </h3>
              <p className="text-[0.7rem] font-medium text-primary mt-0.5">
                Validated Scikit-Learn Pipelines
              </p>

              <p className="mt-3 text-xs text-muted-foreground leading-relaxed">
                Every ML model in CampusX is bundled as a self-contained, reload-tested pipeline (`.joblib`). Models undergo student-isolated and temporal validation to prevent data leakage and guarantee honest generalization.
              </p>

              <div className="mt-4 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-foreground font-medium">
                  <CheckCircle2 className="size-3.5 text-chart-2" />
                  <span>Strict Temporal Ordering</span>
                </div>
                <div className="flex items-center gap-2 text-foreground font-medium">
                  <CheckCircle2 className="size-3.5 text-chart-2" />
                  <span>Student-Level Isolation</span>
                </div>
                <div className="flex items-center gap-2 text-foreground font-medium">
                  <CheckCircle2 className="size-3.5 text-chart-2" />
                  <span>Mandatory Model Reload Tests</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
