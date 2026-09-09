"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import {
  BookOpen,
  CalendarCheck,
  Clock,
  GraduationCap,
  History,
  Layers,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { StatCard } from "@/components/shared/data/stat-card"
import { SubjectCard } from "@/components/shared/data/subject-card"
import { EmptyState } from "@/components/shared/state/empty-state"
import { SubjectsView } from "./subjects-view"
import type {
  FacultySubjectsResponse,
  FacultyCurrentSubjectsResponse,
  FacultyPreviousBatchResponse,
  FacultyTeachingHistoryResponse,
  FacultyClassCard,
} from "@/lib/faculty-api"

function formatPercent(value: number | null, digits = 1): string {
  return value !== null ? `${value.toFixed(digits)}%` : "—"
}

function subjectHref(card: FacultyClassCard): string {
  return `/faculty/subjects/${card.subject_id}?semester=${card.semester_no}&academic_year=${encodeURIComponent(card.academic_year)}`
}

function SubjectGrid({ cards }: { cards: FacultyClassCard[] }) {
  if (cards.length === 0) {
    return (
      <EmptyState
        icon={GraduationCap}
        title="No subjects"
        description="No teaching assignments found for this term."
      />
    )
  }
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((card) => (
        <SubjectCard key={`${card.subject_id}-${card.semester_no}-${card.academic_year}`} card={card} href={subjectHref(card)} />
      ))}
    </div>
  )
}

function TermStats({ data }: { data: { subjects: number; students: number; average_attendance: number | null; average_performance: number | null } }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <StatCard label="Subjects" value={data.subjects.toString()} icon={BookOpen} />
      <StatCard label="Students" value={data.students.toString()} icon={Users} tone="success" />
      <StatCard label="Avg attendance" value={formatPercent(data.average_attendance)} icon={CalendarCheck} />
      <StatCard label="Avg performance" value={formatPercent(data.average_performance)} icon={TrendingUp} />
    </div>
  )
}

function CurrentTab({ data }: { data: FacultyCurrentSubjectsResponse }) {
  if (!data.semester_no || !data.academic_year) {
    return (
      <EmptyState
        icon={Layers}
        title="No subjects assigned yet"
        description="Subjects you teach in the current semester will appear here once teaching assignments are recorded."
      />
    )
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">
            Current Semester
          </h2>
          <p className="text-xs text-muted-foreground">
            Semester {data.semester_no} · {data.academic_year}
          </p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
          <Sparkles className="size-3.5" />
          Teaching now
        </span>
      </div>
      <TermStats
        data={{
          subjects: data.subjects.length,
          students: data.subjects.reduce((sum, c) => sum + c.class_strength, 0),
          average_attendance: averageCard(data.subjects, "average_attendance"),
          average_performance: averageCard(data.subjects, "average_percentage"),
        }}
      />
      <SubjectGrid cards={data.subjects} />
    </div>
  )
}

function PreviousTab({ data }: { data: FacultyPreviousBatchResponse }) {
  if (!data.has_previous || !data.semester_no || !data.academic_year) {
    return (
      <EmptyState
        icon={History}
        title="No previous batch"
        description="You have no teaching history from the term before the current semester. This is expected for your first year of teaching."
      />
    )
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">
            Previous Batch
          </h2>
          <p className="text-xs text-muted-foreground">
            Semester {data.semester_no} · {data.academic_year}
          </p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
          <Clock className="size-3.5" />
          Previous term
        </span>
      </div>
      <TermStats
        data={{
          subjects: data.subjects.length,
          students: data.subjects.reduce((sum, c) => sum + c.class_strength, 0),
          average_attendance: averageCard(data.subjects, "average_attendance"),
          average_performance: averageCard(data.subjects, "average_percentage"),
        }}
      />
      <SubjectGrid cards={data.subjects} />
    </div>
  )
}

function HistoryTab({ data }: { data: FacultyTeachingHistoryResponse }) {
  if (data.terms.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No teaching history"
        description="Once you teach across semesters, your full teaching record will appear here."
      />
    )
  }
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-sm font-semibold">Teaching History</h2>
        <p className="text-xs text-muted-foreground">
          Every term you have taught, oldest first. Current term is marked.
        </p>
      </div>
      {data.terms.map((term) => {
        const isCurrent =
          term.semester_no === data.current_semester &&
          term.academic_year === data.current_academic_year
        return (
          <section
            key={`${term.semester_no}-${term.academic_year}`}
            className="rounded-xl bg-card p-4 ring-1 ring-foreground/10"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold">
                  Semester {term.semester_no} · {term.academic_year}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {term.subjects} subject{term.subjects === 1 ? "" : "s"} · {term.students} students
                </p>
              </div>
              {isCurrent && (
                <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                  <Sparkles className="size-3.5" />
                  Current
                </span>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Chip label="Attendance" value={formatPercent(term.average_attendance)} />
              <Chip label="Performance" value={formatPercent(term.average_performance)} />
              <Chip label="Pass rate" value={formatPercent(term.pass_percentage, 0)} />
            </div>
            <div className="mt-4">
              <SubjectGrid cards={term.subject_cards} />
            </div>
          </section>
        )
      })}
    </div>
  )
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground">
      {label}:
      <span className="font-semibold tabular-nums">{value}</span>
    </span>
  )
}

function averageCard(
  cards: FacultyClassCard[],
  key: "average_attendance" | "average_percentage",
): number | null {
  const present = cards.map((c) => c[key]).filter((v): v is number => v !== null)
  if (present.length === 0) return null
  return Math.round((present.reduce((a, b) => a + b, 0) / present.length) * 10) / 10
}

export function SubjectsTabsView({
  allData,
  currentData,
  previousData,
  historyData,
  initialTab,
}: {
  allData: FacultySubjectsResponse
  currentData: FacultyCurrentSubjectsResponse | null
  previousData: FacultyPreviousBatchResponse | null
  historyData: FacultyTeachingHistoryResponse | null
  initialTab: string
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const activeTabRaw = searchParams.get("tab") || initialTab
  const tabs = ["current", "previous", "history", "all"] as const
  const activeTab = tabs.includes(activeTabRaw as (typeof tabs)[number])
    ? (activeTabRaw as (typeof tabs)[number])
    : "current"

  const handleTabChange = (val: string) => {
    const params = new URLSearchParams()
    params.set("tab", val)
    // Switching terms should not carry over all-subjects filters.
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
      <TabsList>
        <TabsTrigger value="current">Current Semester</TabsTrigger>
        <TabsTrigger value="previous">Previous Batch</TabsTrigger>
        <TabsTrigger value="history">Teaching History</TabsTrigger>
        <TabsTrigger value="all">All Subjects</TabsTrigger>
      </TabsList>
      <div className="mt-4">
        {activeTab === "current" &&
          (currentData ? (
            <CurrentTab data={currentData} />
          ) : (
            <EmptyState
              icon={Layers}
              title="Data unavailable"
              description="Could not load current-semester subjects. Please try again."
            />
          ))}
        {activeTab === "previous" &&
          (previousData ? (
            <PreviousTab data={previousData} />
          ) : (
            <EmptyState
              icon={History}
              title="Data unavailable"
              description="Could not load the previous batch. Please try again."
            />
          ))}
        {activeTab === "history" &&
          (historyData ? (
            <HistoryTab data={historyData} />
          ) : (
            <EmptyState
              icon={History}
              title="Data unavailable"
              description="Could not load your teaching history. Please try again."
            />
          ))}
        {activeTab === "all" && <SubjectsView data={allData} />}
      </div>
    </Tabs>
  )
}