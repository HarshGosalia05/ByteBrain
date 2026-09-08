import { AlertTriangle, CheckCircle2, Compass, Sparkles, Target, BookOpen, Award, Lightbulb } from "lucide-react"

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

function DirectionBlock({ guidance }: { guidance: StudentCareerGuidance }) {
  const { career_direction: direction } = guidance
  return (
    <div className="flex flex-col gap-2">
      <SectionLabel>Career Direction</SectionLabel>
      {direction.available && direction.domain ? (
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <p className="text-xl font-semibold">{direction.domain}</p>
            {direction.source === "declared_preference" ? (
              <Badge variant="success">Based on your preference</Badge>
            ) : (
              <Badge variant="secondary">Based on your subjects</Badge>
            )}
          </div>
          {direction.note && (
            <p className="text-sm text-muted-foreground">{direction.note}</p>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {direction.note ?? "Career direction needs more preference information."}
        </p>
      )}
    </div>
  )
}

function SkillEvidenceChips({
  guidance,
  className,
}: {
  guidance: StudentCareerGuidance
  className?: string
}) {
  if (guidance.skill_strengths.length === 0) return null
  return (
    <div
      className={`min-w-0 rounded-lg border border-foreground/10 bg-background/40 p-3.5 ${className ?? ""}`}
    >
      <SectionLabel>Skill Evidence</SectionLabel>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {guidance.skill_strengths.slice(0, 8).map((item) => (
          <Badge key={`${item.source_subject}-${item.skill}`} variant="outline">
            <CheckCircle2 className="text-chart-2" aria-hidden="true" />
            {item.skill}
          </Badge>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Suggested by your strong performance in related subjects.
      </p>
    </div>
  )
}

function SkillGapList({
  gaps,
  className,
}: {
  gaps: PrioritySkillGap[]
  className?: string
}) {
  return (
    <div className={`flex min-w-0 flex-col gap-2.5 ${className ?? ""}`}>
      <SectionLabel>Skill Gaps</SectionLabel>
      {gaps.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No skill gaps identified for this direction yet.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {gaps.slice(0, 6).map((gap) => (
            <li
              key={gap.skill_area}
              className="flex items-center justify-between gap-2 text-sm"
            >
              <span className="flex min-w-0 items-center gap-2">
                <AlertTriangle
                  className={`size-4 shrink-0 ${
                    gap.priority === "High" ? "text-chart-3" : "text-muted-foreground"
                  }`}
                  aria-hidden="true"
                />
                <span className="truncate font-medium">{titleCase(gap.skill_area)}</span>
              </span>
              {gap.priority === "High" ? (
                <Badge variant="warning">High priority</Badge>
              ) : (
                <Badge variant="muted">Medium</Badge>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AiGuidanceBlock({ guidance }: { guidance: StudentCareerGuidance }) {
  const ai = guidance.ai_guidance
  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
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

function NextStepsBlock({ guidance }: { guidance: StudentCareerGuidance }) {
  return (
    <div className="flex flex-col gap-2.5">
      <SectionLabel>Your Next Steps</SectionLabel>
      {guidance.roadmap.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Your next steps will appear here as your career plan takes shape.
        </p>
      ) : (
        <ol className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {guidance.roadmap.slice(0, 6).map((step) => (
            <li
              key={step.sequence}
              className="rounded-lg border border-foreground/10 bg-background/40 p-3.5"
            >
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                  {step.sequence}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium leading-snug">
                    {titleCase(step.focus_area)}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {step.next_action}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ol>
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

      {/* Personalized Next Steps */}
      {careerPath.personalized_next_steps.length > 0 && (
        <div className="mt-4 rounded-lg border border-primary/20 bg-primary/5 p-3">
          <p className="mb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            Personalized Next Steps
          </p>
          <ul className="flex flex-col gap-1">
            {careerPath.personalized_next_steps.map((step, idx) => (
              <li key={idx} className="flex items-start gap-2 text-xs leading-relaxed">
                <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[0.625rem] font-semibold text-primary">
                  {idx + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

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
      <div className="flex flex-col gap-5">
        <DirectionBlock guidance={guidance} />

        {(guidance.skill_strengths.length > 0 || guidance.skill_gaps.length > 0) && (
          <div className="grid gap-3 lg:grid-cols-2">
            <SkillEvidenceChips
              guidance={guidance}
              className={guidance.skill_gaps.length === 0 ? "lg:col-span-2" : ""}
            />
            <SkillGapList
              gaps={guidance.skill_gaps}
              className={
                guidance.skill_strengths.length === 0 ? "lg:col-span-2" : ""
              }
            />
          </div>
        )}

        <AiGuidanceBlock guidance={guidance} />

        <NextStepsBlock guidance={guidance} />

        {guidance.career_path && (
          <RecommendedCareerPathBlock careerPath={guidance.career_path} />
        )}
      </div>
    </ModelCard>
  )
}
