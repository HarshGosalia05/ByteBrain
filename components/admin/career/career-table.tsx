import { GraduationCap, BarChart, TrendingUp, DollarSign, Award } from "lucide-react"

import type { AdminStudentRow } from "@/lib/admin-api"

import { ChartCard } from "@/components/shared/data/chart-card"
import { StatCard } from "@/components/shared/data/stat-card"

export function CareerTable({ data }: { data: { students: AdminStudentRow[] } }) {
  const students = data.students

  const totalInternships = students.filter(
    (s) => s.internship_completed === "Yes",
  ).length

  const internshipRateStr =
    students.length > 0
      ? `${((totalInternships / students.length) * 100).toFixed(1)}%`
      : "—"

  const packages = students
    .map((s) => s.target_package_lpa)
    .filter((p): p is number => typeof p === "number" && !isNaN(p))

  const avgPackageStr =
    packages.length > 0
      ? `${(packages.reduce((a, b) => a + b, 0) / packages.length).toFixed(2)} LPA`
      : "—"

  const sortedPackages = [...packages].sort((a, b) => a - b)
  const medianPackageStr =
    sortedPackages.length > 0
      ? `${sortedPackages[Math.floor(sortedPackages.length / 2)].toFixed(2)} LPA`
      : "—"

  return (
    <ChartCard
      title="Career Outcomes & Preferences"
      subtitle="Aggregated directly from stored student career survey & preference records"
      status={students.length > 0 ? "ready" : "empty"}
      emptyIcon={GraduationCap}
      emptyTitle="No career data"
      emptyDescription="No students match the current filters."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Total Students"
          value={students.length > 0 ? students.length.toString() : "0"}
          icon={GraduationCap}
          tone="primary"
        />
        <StatCard
          label="Internships Done"
          value={students.length > 0 ? totalInternships.toString() : "—"}
          icon={BarChart}
          tone="success"
        />
        <StatCard
          label="Internship Rate"
          value={internshipRateStr}
          icon={TrendingUp}
          tone="warning"
        />
        <StatCard
          label="Avg Target LPA"
          value={avgPackageStr}
          icon={DollarSign}
          tone="primary"
        />
        <StatCard
          label="Median Target LPA"
          value={medianPackageStr}
          icon={Award}
          tone="primary"
        />
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-190 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Student</th>
              <th className="py-2 pr-4 font-medium">Department</th>
              <th className="py-2 pr-4 font-medium">Preferred Domain</th>
              <th className="py-2 pr-4 font-medium">Dream Role</th>
              <th className="py-2 pr-4 font-center font-medium">Internship</th>
              <th className="py-2 pr-4 text-right font-medium">Target Package</th>
              <th className="py-2 pr-4 font-medium">Readiness / Status</th>
            </tr>
          </thead>
          <tbody>
            {students.map((row) => (
              <tr key={row.student_id} className="border-b last:border-0">
                <td className="py-2.5 pr-4">
                  <p className="max-w-52 truncate font-medium">{row.student_name}</p>
                  <p className="text-xs text-muted-foreground">{row.student_id}</p>
                </td>
                <td className="py-2.5 pr-4 text-xs">{row.department_name || "—"}</td>
                <td className="py-2.5 pr-4 text-xs font-medium">{row.preferred_domain || "—"}</td>
                <td className="py-2.5 pr-4 text-xs text-muted-foreground">{row.dream_job_role || "—"}</td>
                <td className="py-2.5 pr-4">
                  {row.internship_completed ? (
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                        row.internship_completed === "Yes"
                          ? "bg-success/10 text-success"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {row.internship_completed === "Yes" ? "Completed" : "No"}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-xs font-semibold">
                  {row.target_package_lpa != null ? `${row.target_package_lpa.toFixed(2)} LPA` : "—"}
                </td>
                <td className="py-2.5 flex items-center gap-1.5 flex-wrap">
                  {row.placement_readiness_level ? (
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                        row.placement_readiness_level === "High"
                          ? "bg-success/10 text-success"
                          : row.placement_readiness_level === "Medium"
                            ? "bg-chart-3/20 text-chart-3"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {row.placement_readiness_level}
                    </span>
                  ) : null}
                  {row.academic_standing && row.academic_standing !== "At Risk" ? (
                    <span className="bg-success/10 text-success rounded-md px-2 py-0.5 text-xs font-medium">
                      Supported
                    </span>
                  ) : (
                    <span className="bg-destructive/10 text-destructive rounded-md px-2 py-0.5 text-xs font-medium">
                      At Risk
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Showing {students.length} student{students.length === 1 ? "" : "s"} in the selected scope
      </p>
    </ChartCard>
  )
}