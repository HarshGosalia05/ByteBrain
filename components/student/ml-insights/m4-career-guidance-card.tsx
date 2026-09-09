import { AlertTriangle, CheckCircle2, Compass, Sparkles, Target, BookOpen, Award, Lightbulb, TrendingUp, Zap } from "lucide-react"

import { ChatMarkdown } from "@/components/shared/chatbot/chat-markdown"
import { Badge } from "@/components/ui/badge"
import type {
  CareerPathRecommendation,
  PrioritySkillGap,
  StudentCareerGuidance,
} from "@/lib/student-api"

import { ModelCard } from "./model-card"

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">
      {children}
    </p>
  )
}

function titleCase(value: string): string {
  return value.replace(/\b\w/g, (char) => char.toUpperCase())
}

function CareerDirectionHeader({ guidance }: { guidance: StudentCareerGuidance }) {
  const { career_direction: direction, career_readiness: readiness } = guidance
  
  if (!direction.available || !direction.domain) {
    return null
  }

  return (
    <div className="rounded-xl border border-primary/20 bg-gradient-to-r from-primary/5 to-transparent p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
            <Compass className="size-5 text-primary" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold">{direction.domain}</h3>
              {direction.source === "declared_preference" ? (
                <Badge variant="success">Your Preference</Badge>
              ) : (
                <Badge variant="secondary">Subject-Based</Badge>
              )}
            </div>
            {direction.note && (
              <p className="mt-0.5 text-sm text-muted-foreground">{direction.note}</p>
            )}
          </div>
        </div>
        
        {readiness.available && readiness.score !== null && (
          <div className="flex items-center gap-2">
            <div className="text-right">
              <p className="text-xs text-muted-foreground">Career Readiness</p>
              <p className="text-lg font-bold">{readiness.score.toFixed(0)}%</p>
            </div>
            <div className={`flex size-10 items-center justify-center rounded-full ${
              readiness.level === "High" ? "bg-chart-2/20 text-chart-2" :
              readiness.level === "Medium" ? "bg-chart-3/20 text-chart-3" :
              "bg-destructive/20 text-destructive"
            }`}>
              <TrendingUp className="size-5" aria-hidden="true" />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function SkillStrengthsSection({ guidance }: { guidance: StudentCareerGuidance }) {
  if (guidance.skill_strengths.length === 0) return null

  return (
    <div className="rounded-lg border border-foreground/10 bg-background/40 p-4">
      <div className="mb-3 flex items-center gap-2">
        <CheckCircle2 className="size-4 text-chart-2" aria-hidden="true" />
        <SectionLabel>Your Strengths</SectionLabel>
      </div>
      <div className="flex flex-wrap gap-2">
        {guidance.skill_strengths.slice(0, 8).map((item) => (
          <Badge key={`${item.source_subject}-${item.skill}`} variant="success" className="text-xs">
            {item.skill}
          </Badge>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Inferred from your strong performance in related subjects.
      </p>
    </div>
  )
}

function SkillGapsSection({ gaps }: { gaps: PrioritySkillGap[] }) {
  if (gaps.length === 0) {
    return (
      <div className="rounded-lg border border-foreground/10 bg-background/40 p-4">
        <div className="mb-3 flex items-center gap-2">
          <AlertTriangle className="size-4 text-chart-3" aria-hidden="true" />
          <SectionLabel>Skill Gap Analysis (ML-Based)</SectionLabel>
        </div>
        <p className="text-sm text-muted-foreground">
          No significant skill gaps identified. Your profile is well-aligned with your career direction.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-foreground/10 bg-background/40 p-4">
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle className="size-4 text-chart-3" aria-hidden="true" />
        <SectionLabel>Skill Gap Analysis (ML-Based)</SectionLabel>
        <Badge variant="outline" className="text-xs">M5 Model</Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {gaps.slice(0, 6).map((gap) => (
          <div
            key={gap.skill_area}
            className="flex items-start gap-3 rounded-md border border-foreground/5 bg-background/60 p-3"
          >
            <div className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full ${
              gap.priority === "High" ? "bg-chart-3/20 text-chart-3" : "bg-muted text-muted-foreground"
            }`}>
              {gap.priority === "High" ? (
                <AlertTriangle className="size-3" aria-hidden="true" />
              ) : (
                <span className="text-xs font-medium">M</span>
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{titleCase(gap.skill_area)}</p>
                {gap.priority === "High" ? (
                  <Badge variant="warning" className="text-[0.625rem]">High</Badge>
                ) : (
                  <Badge variant="muted" className="text-[0.625rem]">Medium</Badge>
                )}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{gap.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function NextStepsSection({ guidance }: { guidance: StudentCareerGuidance }) {
  const nextSteps = guidance.career_path?.personalized_next_steps || []
  
  if (nextSteps.length === 0) {
    return (
      <div className="rounded-lg border border-foreground/10 bg-background/40 p-4">
        <div className="mb-3 flex items-center gap-2">
          <Zap className="size-4 text-primary" aria-hidden="true" />
          <SectionLabel>Recommended Next Steps (ML-Based)</SectionLabel>
        </div>
        <p className="text-sm text-muted-foreground">
          Your personalized next steps will appear here based on ML analysis of your profile.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Zap className="size-4 text-primary" aria-hidden="true" />
        <SectionLabel>Recommended Next Steps (ML-Based)</SectionLabel>
        <Badge variant="outline" className="text-xs">M5 Model</Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {nextSteps.slice(0, 5).map((step, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 rounded-md border border-primary/10 bg-background/60 p-3"
          >
            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              {idx + 1}
            </span>
            <p className="text-sm leading-relaxed">{step}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function AiGuidanceBlock({ guidance }: { guidance: StudentCareerGuidance }) {
  const ai = guidance.ai_guidance
  return (
    <div className="rounded-xl border border-foreground/10 bg-background/40 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Sparkles className="size-4 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-sm font-semibold">AI Career Guidance</p>
      </div>
      {ai.available && ai.content ? (
        <div className="text-sm leading-relaxed [&_ol]:mt-1 [&_ol]:list-decimal [&_ol]:ps-5 [&_strong]:font-semibold [&_ul]:mt-1 [&_ul]:list-disc [&_ul]:ps-5">
          <ChatMarkdown content={ai.content} />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          AI guidance is unavailable right now. Please check back later.
        </p>
      )}
    </div>
  )
}

function RecommendedCareerPathBlock({
  careerPath,
}: {
  careerPath: CareerPathRecommendation
}) {
  return (
    <div className="rounded-xl border border-foreground/10 bg-background/40 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Target className="size-4 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-sm font-semibold">Recommended Career Path</p>
        <Badge variant="secondary">{careerPath.domain}</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Career Roles */}
        {careerPath.roles.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-chart-2" aria-hidden="true" />
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Recommended Roles
              </p>
            </div>
            <ul className="flex flex-wrap gap-1.5">
              {careerPath.roles.map((role) => (
                <Badge key={role} variant="outline" className="text-xs">
                  {role}
                </Badge>
              ))}
            </ul>
          </div>
        )}

        {/* Relevant Skills */}
        {careerPath.skills.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <BookOpen className="size-3.5 text-chart-4" aria-hidden="true" />
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Relevant Technical Skills
              </p>
            </div>
            <ul className="flex flex-wrap gap-1.5">
              {careerPath.skills.map((skill) => (
                <Badge key={skill} variant="outline" className="text-xs">
                  {skill}
                </Badge>
              ))}
            </ul>
          </div>
        )}

        {/* Relevant Subjects */}
        {careerPath.relevant_subjects.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <BookOpen className="size-3.5 text-chart-5" aria-hidden="true" />
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Relevant Subjects to Strengthen
              </p>
            </div>
            <ul className="flex flex-wrap gap-1.5">
              {careerPath.relevant_subjects.map((subj) => (
                <Badge key={subj} variant="success" className="text-xs">
                  {subj}
                </Badge>
              ))}
            </ul>
          </div>
        )}

        {/* Skill Gaps */}
        {careerPath.skill_gaps.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <AlertTriangle className="size-3.5 text-chart-3" aria-hidden="true" />
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Skill Gaps to Address
              </p>
            </div>
            <ul className="flex flex-wrap gap-1.5">
              {careerPath.skill_gaps.map((gap) => (
                <Badge key={gap} variant="warning" className="text-xs">
                  {titleCase(gap)}
                </Badge>
              ))}
            </ul>
          </div>
        )}

        {/* Certifications */}
        {careerPath.certifications.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <Award className="size-3.5 text-primary" aria-hidden="true" />
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Recommended Certifications
              </p>
            </div>
            <ul className="flex flex-col gap-1">
              {careerPath.certifications.map((cert) => (
                <li
                  key={cert}
                  className="rounded-md border border-foreground/10 bg-background/40 px-2.5 py-1.5 text-xs"
                >
                  {cert}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Project Suggestions */}
        {careerPath.project_suggestions.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <Lightbulb className="size-3.5 text-chart-1" aria-hidden="true" />
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Project / Portfolio Ideas
              </p>
            </div>
            <ul className="flex flex-col gap-1">
              {careerPath.project_suggestions.map((proj) => (
                <li
                  key={proj}
                  className="rounded-md border border-foreground/10 bg-background/40 px-2.5 py-1.5 text-xs"
                >
                  {proj}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <p className="mt-3 text-[0.6875rem] text-muted-foreground">
        {careerPath.disclaimer}
      </p>
    </div>
  )
}

export function M4CareerGuidanceCard({
  guidance,
}: {
  guidance: StudentCareerGuidance | null
}) {
  if (!guidance) return null

  if (!guidance.data_available) {
    return (
      <ModelCard
        id="ml-insights-m4-guidance"
        icon={Compass}
        title="Career Direction & Guidance"
        subtitle="Personalized guidance based on your academic performance, interests and current preparation."
      >
        <p className="text-sm text-muted-foreground">
          Your career guidance will appear here once your academic records and
          preferences are available.
        </p>
      </ModelCard>
    )
  }

  return (
    <ModelCard
      id="ml-insights-m4-guidance"
      icon={Compass}
      title="Career Direction & Guidance"
      subtitle="Personalized guidance based on your academic performance, interests and current preparation."
    >
      <div className="flex flex-col gap-4">
        {/* Career Direction Header */}
        <CareerDirectionHeader guidance={guidance} />

        {/* Skill Strengths */}
        <SkillStrengthsSection guidance={guidance} />

        {/* ML-Based Skill Gap Analysis */}
        <SkillGapsSection gaps={guidance.skill_gaps} />

        {/* ML-Based Next Steps */}
        <NextStepsSection guidance={guidance} />

        {/* AI Guidance */}
        <AiGuidanceBlock guidance={guidance} />

        {/* Recommended Career Path */}
        {guidance.career_path && (
          <RecommendedCareerPathBlock careerPath={guidance.career_path} />
        )}
      </div>
    </ModelCard>
  )
}
