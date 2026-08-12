import { GraduationCap, BarChart, TrendingUp } from "lucide-react"

import type { AdminStudentRow } from "@/lib/admin-api"

import { StatCard } from "@/components/shared/data/stat-card"

export function CareerHeader({ data }: { data: { students: AdminStudentRow[] } }) {
  const students = data.students

  const totalInternships = students.filter(
    (s) => s.internship_completed === "Yes",
  ).length

  const placementRate =
    students.length > 0
      ? `${((totalInternships / students.length) * 100).toFixed(1)}%`
      : "—"

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Career</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Career path and placement intelligence from stored student data.
          </p>
        </div>

        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <StatCard
            label="Total Students"
            value={students.length > 0 ? students.length.toString() : "0"}
            icon={GraduationCap}
            tone="primary"
          />
          <StatCard
            label="Total Internships"
            value={totalInternships.toString()}
            icon={BarChart}
            tone="success"
          />
          <StatCard
            label="Placement Rate"
            value={placementRate}
            icon={TrendingUp}
            tone="warning"
          />
        </div>
      </div>
    </div>
  )
}