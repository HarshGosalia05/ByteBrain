import Link from "next/link"
import {
  ArrowRight,
  Target,
  Brain,
  Sparkles,
  Shield,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { LiveStatusIndicator } from "@/components/landing/live-status-indicator"
import { m1V3GradeTone, m1V3PredictedSGPA, type M1V3PredictionData } from "@/lib/m1v3-prediction"
import { m3V2RiskTone, riskLevelLabel, formatRiskPercent, type M3V2PredictionData } from "@/lib/m3v2-prediction"
import type { StudentProfile, SemesterSummaryItem, StudentCareerGuidance } from "@/lib/student-api"
import type { SystemHealthStatus } from "@/lib/intelligence-console"

function SectionCard({
  children,
  className = "",
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={`rounded-xl border border-border/60 bg-card/80 p-4 ring-1 ring-foreground/5 backdrop-blur-sm ${className}`}
    >
      {children}
    </div>
  )
}

function MiniLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[0.625rem] font-semibold tracking-widest text-muted-foreground uppercase">
      {children}
    </p>
  )
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className="relative flex size-1.5">
      <span
        className={`absolute inline-flex size-full rounded-full opacity-75 ${ok ? "animate-ping bg-emerald-400" : "bg-red-400"}`}
      />
      <span
        className={`relative inline-flex size-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`}
      />
    </span>
  )
}

export function IntelligenceConsole({
  profile,
  latestSummary,
  m1v3,
  m3v2,
  m4Score,
  careerGuidance,
  systemHealth,
}: {
  profile: StudentProfile
  latestSummary: SemesterSummaryItem | null
  m1v3: M1V3PredictionData | null
  m3v2: M3V2PredictionData | null
  m4Score: { score: number | null; level: string | null } | null
  careerGuidance: StudentCareerGuidance | null
  systemHealth: SystemHealthStatus
}) {
  const department = profile.department_name ?? "Department"
  const predictedSGPA = m1v3?.subjects ? m1V3PredictedSGPA(m1v3.subjects) : null
  const topSubjects = m1v3?.subjects?.slice(0, 4) ?? []
  const riskReady = m3v2 && m3v2.readiness_status === "READY" && m3v2.probability_at_risk !== null
  const careerDomain = careerGuidance?.career_direction?.domain ?? null
  const aiGuidance = careerGuidance?.ai_guidance?.content ?? null

  return (
    <section className="py-8 sm:py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Console Header */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 border border-primary/20">
              <Brain className="size-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight text-foreground">
                CampusX Intelligence Console
              </h2>
              <p className="text-xs text-muted-foreground">
                Real-time academic intelligence for {profile.first_name} {profile.last_name}
              </p>
            </div>
          </div>
          <LiveStatusIndicator health={systemHealth} />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* ─── Student Identity ─── */}
          <SectionCard className="sm:col-span-2 lg:col-span-1">
            <div className="flex flex-col gap-3">
              <MiniLabel>Student Identity</MiniLabel>
              <div className="flex items-center gap-3">
                <div className="flex size-11 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary border border-primary/20">
                  {profile.first_name?.[0]}
                  {profile.last_name?.[0]}
                </div>
                <div>
                  <p className="text-sm font-semibold">
                    {profile.first_name} {profile.last_name}
                  </p>
                  <p className="text-[0.6875rem] text-muted-foreground">
                    {department} · Sem {profile.current_semester}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/30">
                <div>
                  <p className="text-[0.6rem] text-muted-foreground">Enrollment</p>
                  <p className="text-xs font-medium tabular-nums">{profile.enrollment_no}</p>
                </div>
                <div>
                  <p className="text-[0.6rem] text-muted-foreground">Backlogs</p>
                  <p className="text-xs font-medium tabular-nums">
                    {profile.total_backlogs ?? 0}
                  </p>
                </div>
              </div>
            </div>
          </SectionCard>

          {/* ─── Academic Standing ─── */}
          <Link href="/student/academic">
            <SectionCard className="group flex h-full flex-col gap-3 transition-colors hover:bg-muted/40">
              <MiniLabel>Academic Standing</MiniLabel>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold tabular-nums">
                  {profile.overall_cgpa?.toFixed(2) ?? "—"}
                </span>
                <span className="text-xs text-muted-foreground">CGPA</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary">Sem {profile.current_semester}</Badge>
                {profile.academic_standing && (
                  <Badge
                    variant={
                      profile.academic_standing === "Good"
                        ? "success"
                        : profile.academic_standing === "Probation"
                          ? "destructive"
                          : "warning"
                    }
                  >
                    {profile.academic_standing}
                  </Badge>
                )}
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-border/30">
                <span className="text-[0.6rem] text-muted-foreground">
                  SGPA {profile.latest_sgpa?.toFixed(2) ?? "—"}
                </span>
                <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
              </div>
            </SectionCard>
          </Link>

          {/* ─── Attendance ─── */}
          <Link href="/student/attendance">
            <SectionCard className="group flex h-full flex-col gap-3 transition-colors hover:bg-muted/40">
              <MiniLabel>Attendance</MiniLabel>
              {latestSummary ? (
                <>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold tabular-nums">
                      {latestSummary.attendance_percentage.toFixed(1)}
                    </span>
                    <span className="text-xs text-muted-foreground">%</span>
                  </div>
                  <Badge
                    variant={
                      latestSummary.attendance_percentage >= 85
                        ? "success"
                        : latestSummary.attendance_percentage >= 75
                          ? "warning"
                          : "destructive"
                    }
                  >
                    {latestSummary.attendance_percentage >= 85
                      ? "Excellent"
                      : latestSummary.attendance_percentage >= 75
                        ? "Good"
                        : "Low"}
                  </Badge>
                  <div className="flex items-center justify-between pt-1 border-t border-border/30">
                    <span className="text-[0.6rem] text-muted-foreground">
                      Sem {latestSummary.semester}
                    </span>
                    <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </>
              ) : (
                <div className="flex flex-1 items-center justify-center">
                  <p className="text-xs text-muted-foreground">No data yet</p>
                </div>
              )}
            </SectionCard>
          </Link>

          {/* ─── Performance Predictions (M1 V3) ─── */}
          <Link href="/student/ml-insights">
            <SectionCard className="group flex h-full flex-col gap-3 transition-colors hover:bg-muted/40 sm:col-span-2 lg:col-span-1">
              <MiniLabel>Performance Predictions</MiniLabel>
              {m1v3 && m1v3.readiness_status === "READY" && m1v3.subjects.length > 0 ? (
                <>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[0.6rem]">
                      M1 V3
                    </Badge>
                    <span className="text-[0.6rem] text-muted-foreground">
                      {m1v3.subjects.length} subjects
                    </span>
                  </div>
                  {predictedSGPA !== null && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-bold tabular-nums">
                        {predictedSGPA.toFixed(2)}
                      </span>
                      <span className="text-xs text-muted-foreground">Pred. SGPA</span>
                    </div>
                  )}
                  <div className="space-y-1.5">
                    {topSubjects.map((s) => {
                      const tone = m1V3GradeTone(s.grade_band)
                      return (
                        <div
                          key={s.subject_id}
                          className="flex items-center justify-between text-[0.7rem]"
                        >
                          <span className="truncate text-muted-foreground">
                            {s.subject_name || s.subject_id}
                          </span>
                          <Badge variant={tone} className="ml-2 shrink-0 text-[0.6rem]">
                            {s.grade_band}
                          </Badge>
                        </div>
                      )
                    })}
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-border/30">
                    <span className="text-[0.6rem] text-muted-foreground">End-sem predictions</span>
                    <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-1">
                  <p className="text-xs text-muted-foreground">Predictions unavailable</p>
                  {m1v3?.reason && (
                    <p className="text-[0.6rem] text-muted-foreground/70">{m1v3.reason}</p>
                  )}
                </div>
              )}
            </SectionCard>
          </Link>

          {/* ─── Academic Risk (M3 V2) ─── */}
          <Link href="/student/ml-insights">
            <SectionCard className="group flex h-full flex-col gap-3 transition-colors hover:bg-muted/40">
              <MiniLabel>Academic Risk</MiniLabel>
              {riskReady ? (
                <>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold tabular-nums">
                      {formatRiskPercent(m3v2.probability_at_risk)}
                    </span>
                  </div>
                  <Badge variant={m3V2RiskTone(m3v2.probability_at_risk)}>
                    {riskLevelLabel(m3v2.probability_at_risk)} Risk
                  </Badge>
                  {m3v2.signals.length > 0 && (
                    <div className="space-y-1">
                      {m3v2.signals.slice(0, 2).map((sig, i) => (
                        <p key={i} className="text-[0.6rem] text-muted-foreground truncate">
                          {sig.feature.replace(/_/g, " ")}
                        </p>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center justify-between pt-1 border-t border-border/30">
                    <span className="text-[0.6rem] text-muted-foreground">M3 V2 estimate</span>
                    <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-1">
                  <Shield className="size-5 text-muted-foreground/50" />
                  <p className="text-xs text-muted-foreground">No risk data</p>
                  {m3v2?.reason && (
                    <p className="text-[0.6rem] text-muted-foreground/70 text-center">{m3v2.reason}</p>
                  )}
                </div>
              )}
            </SectionCard>
          </Link>

          {/* ─── Career Readiness (M4) ─── */}
          <Link href="/student/ml-insights">
            <SectionCard className="group flex h-full flex-col gap-3 transition-colors hover:bg-muted/40">
              <MiniLabel>Career Readiness</MiniLabel>
              {m4Score && m4Score.score !== null ? (
                <>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold tabular-nums">
                      {m4Score.score.toFixed(0)}
                    </span>
                    <span className="text-xs text-muted-foreground">%</span>
                  </div>
                  <Badge
                    variant={
                      m4Score.level === "High"
                        ? "success"
                        : m4Score.level === "Medium"
                          ? "warning"
                          : "destructive"
                    }
                  >
                    {m4Score.level ?? "—"} Readiness
                  </Badge>
                  <div className="flex items-center justify-between pt-1 border-t border-border/30">
                    <span className="text-[0.6rem] text-muted-foreground">M4 assessment</span>
                    <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-1">
                  <Target className="size-5 text-muted-foreground/50" />
                  <p className="text-xs text-muted-foreground">Not available</p>
                </div>
              )}
            </SectionCard>
          </Link>

          {/* ─── Career Domain (M5) ─── */}
          <Link href="/student/ml-insights">
            <SectionCard className="group flex h-full flex-col gap-3 transition-colors hover:bg-muted/40 sm:col-span-2 lg:col-span-1">
              <MiniLabel>Career Domain</MiniLabel>
              {careerDomain ? (
                <>
                  <div className="flex items-center gap-2">
                    <Sparkles className="size-4 text-primary" />
                    <span className="text-sm font-semibold">{careerDomain}</span>
                  </div>
                  {careerGuidance?.career_direction?.source && (
                    <Badge variant="outline" className="w-fit text-[0.6rem]">
                      {careerGuidance.career_direction.source === "declared_preference"
                        ? "Your Preference"
                        : "Subject-Based Mapping"}
                    </Badge>
                  )}
                  {careerGuidance?.skill_gaps && careerGuidance.skill_gaps.length > 0 && (
                    <div className="space-y-1">
                      {careerGuidance.skill_gaps.slice(0, 2).map((gap, i) => (
                        <p key={i} className="text-[0.6rem] text-muted-foreground truncate">
                          Gap: {gap.skill_area}
                        </p>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center justify-between pt-1 border-t border-border/30">
                    <span className="text-[0.6rem] text-muted-foreground">M5 domain mapping</span>
                    <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-1">
                  <Sparkles className="size-5 text-muted-foreground/50" />
                  <p className="text-xs text-muted-foreground">No domain mapped</p>
                </div>
              )}
            </SectionCard>
          </Link>

          {/* ─── AI Guidance Preview ─── */}
          <Link href="/student/ml-insights">
            <SectionCard className="group flex h-full flex-col gap-3 transition-colors hover:bg-muted/40 sm:col-span-2 lg:col-span-2">
              <MiniLabel>AI Guidance</MiniLabel>
              {aiGuidance ? (
                <>
                  <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                    {aiGuidance.slice(0, 200)}
                    {aiGuidance.length > 200 ? "..." : ""}
                  </p>
                  <div className="flex items-center justify-between pt-1 border-t border-border/30">
                    <span className="text-[0.6rem] text-muted-foreground">Grounded GenAI</span>
                    <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </>
              ) : (
                <div className="flex flex-1 items-center justify-center">
                  <p className="text-xs text-muted-foreground">
                    AI guidance will appear once career data is available
                  </p>
                </div>
              )}
            </SectionCard>
          </Link>
        </div>
      </div>
    </section>
  )
}
