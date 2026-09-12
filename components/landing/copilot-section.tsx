import * as React from "react"
import {
  Bot,
  CheckCircle2,
  Lock,
  Send,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"

const COPILOT_PILLARS = [
  {
    title: "Grounded Responses",
    desc: "Every answer is strictly synthesized from verified student database records, preventing hallucination.",
  },
  {
    title: "Role-Aware Boundaries",
    desc: "Students only query their own records. Faculty query enrolled cohorts. Admins access institution aggregates.",
  },
  {
    title: "Personalized Action Guidance",
    desc: "Provides clear, explainable steps to improve grades, meet attendance thresholds, and prepare for placements.",
  },
  {
    title: "Zero Unauthorized Exposure",
    desc: "Internal database connection strings, credentials, and sensitive audit logs are isolated from AI prompts.",
  },
]

export function CopilotSection() {
  return (
    <section className="py-20 sm:py-28 relative bg-muted/10 border-t border-border/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Column: Copilot Description */}
          <div className="lg:col-span-6 flex flex-col items-start">
            <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
              Academic Copilot
            </Badge>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground leading-tight">
              An AI Academic Advisor Grounded in Truth
            </h2>
            <p className="mt-4 text-base sm:text-lg text-muted-foreground leading-relaxed">
              CampusX includes an embedded conversational intelligence copilot that helps students
              navigate coursework, understand risk drivers, and prepare for career goals without
              speculation.
            </p>

            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
              {COPILOT_PILLARS.map((pillar) => (
                <div
                  key={pillar.title}
                  className="rounded-xl border border-border/70 bg-card p-4 ring-1 ring-foreground/5"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <CheckCircle2 className="size-4 text-chart-2 shrink-0" />
                    <h4 className="text-xs font-bold text-foreground">
                      {pillar.title}
                    </h4>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {pillar.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Right Column: Realistic Chat Mockup */}
          <div className="lg:col-span-6 w-full">
            <div className="rounded-2xl border border-border/80 bg-card shadow-xl ring-1 ring-foreground/10 overflow-hidden backdrop-blur-sm">
              {/* Chat Header */}
              <div className="flex items-center justify-between border-b border-border/60 bg-muted/30 px-5 py-3.5">
                <div className="flex items-center gap-2.5">
                  <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                    <Bot className="size-4" />
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-foreground">CampusX Copilot</span>
                      <Badge variant="outline" className="text-[0.65rem] border-chart-2/40 text-chart-2 py-0">
                        Grounded
                      </Badge>
                    </div>
                    <p className="text-[0.7rem] text-muted-foreground">Session: Aarav Patel (Student)</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Lock className="size-3 text-primary" />
                  <span className="text-[0.7rem]">Protected Context</span>
                </div>
              </div>

              {/* Chat Message Stream */}
              <div className="p-4 sm:p-5 space-y-4 max-h-[460px] overflow-y-auto">
                {/* User Message 1 */}
                <div className="flex items-start gap-3 justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-none bg-primary px-4 py-2.5 text-xs sm:text-sm text-primary-foreground">
                    Which subject should I focus on this semester?
                  </div>
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-foreground text-xs font-semibold">
                    AP
                  </span>
                </div>

                {/* Copilot Response 1 */}
                <div className="flex items-start gap-3 justify-start">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Bot className="size-3.5" />
                  </span>
                  <div className="max-w-[88%] rounded-2xl rounded-tl-none border border-border/60 bg-muted/40 p-4 text-xs sm:text-sm text-foreground space-y-2 leading-relaxed">
                    <p>
                      Based on your verified continuous evaluation records,{" "}
                      <span className="font-semibold text-primary">Distributed Systems (CS603)</span>{" "}
                      currently needs the most attention.
                    </p>
                    <div className="rounded-lg bg-background/60 p-2.5 border border-border/40 text-xs space-y-1">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">C1 Mid-Sem:</span>
                        <span className="font-medium text-foreground">22 / 30</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">C2 Continuous:</span>
                        <span className="font-medium text-destructive">16 / 30 (-27%)</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">M1_v3 Projection:</span>
                        <span className="font-medium text-chart-3">48 / 70 (BC Grade Band)</span>
                      </div>
                    </div>
                    <p className="text-muted-foreground text-xs">
                      Recommendation: Scoring ≥24 in the upcoming quiz will lift your projected grade into the AB band.
                    </p>
                  </div>
                </div>

                {/* User Message 2 */}
                <div className="flex items-start gap-3 justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-none bg-primary px-4 py-2.5 text-xs sm:text-sm text-primary-foreground">
                    Why is my academic risk flagged?
                  </div>
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-foreground text-xs font-semibold">
                    AP
                  </span>
                </div>

                {/* Copilot Response 2 */}
                <div className="flex items-start gap-3 justify-start">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Bot className="size-3.5" />
                  </span>
                  <div className="max-w-[88%] rounded-2xl rounded-tl-none border border-border/60 bg-muted/40 p-4 text-xs sm:text-sm text-foreground space-y-2 leading-relaxed">
                    <p>
                      Your overall status remains <span className="font-semibold text-chart-2">Low Risk (M3: 0.12)</span>, but a single subject watch flag was triggered:
                    </p>
                    <ul className="list-disc pl-4 text-xs text-muted-foreground space-y-1">
                      <li>
                        <span className="text-foreground font-medium">CS603 Attendance: </span>
                        Currently at 71.4%, which is below the 75% institutional exam eligibility threshold.
                      </li>
                      <li>
                        Attending the next 3 consecutive lecture hours will elevate your attendance to 76.2%.
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Chat Input Bar (Display only) */}
              <div className="p-3 border-t border-border/60 bg-muted/20 flex items-center gap-2">
                <div className="flex-1 rounded-lg border border-border/80 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
                  Ask about your subjects, attendance, or career readiness...
                </div>
                <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <Send className="size-3.5" />
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
