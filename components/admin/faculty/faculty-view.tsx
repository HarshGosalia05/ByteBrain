import {
  Building2,
  BriefcaseBusiness,
  Clock3,
  UserCog,
  Users,
} from "lucide-react"

import type {
  AdminFacultyData,
  AdminFacultyRow,
} from "@/lib/admin-api"

import { StatCard } from "@/components/shared/data/stat-card"
import { ChartCard } from "@/components/shared/data/chart-card"
import { DonutChart } from "@/components/shared/charts/donut-chart"
import { SubjectBarChart } from "@/components/shared/charts/bar-chart"

const PALETTE = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

function toFixed(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function FacultyByDepartmentCard({
  data,
}: {
  data: AdminFacultyData["by_department"]
}) {
  const chartData = data.map((item) => ({
    department: item.department_name,
    count: item.count,
  }))

  return (
    <ChartCard
      title="Faculty by Department"
      subtitle="Faculty headcount per department"
      status={chartData.length > 0 ? "ready" : "empty"}
      emptyIcon={Building2}
      emptyTitle="No department data"
      emptyDescription="There are no faculty records in the current data."
    >
      <SubjectBarChart
        data={chartData}
        xKey="department"
        dataKey="count"
        color="var(--chart-1)"
        height={240}
      />
    </ChartCard>
  )
}

function FacultyByDesignationCard({
  data,
}: {
  data: AdminFacultyData["by_designation"]
}) {
  const total = data.reduce((sum, item) => sum + item.count, 0)
  const slices = data.map((item, index) => ({
    name: item.designation,
    value: item.count,
    color: PALETTE[index % PALETTE.length],
  }))

  return (
    <ChartCard
      title="Faculty by Designation"
      subtitle="Faculty headcount by designation"
      status={slices.length > 0 ? "ready" : "empty"}
      emptyIcon={BriefcaseBusiness}
      emptyTitle="No designation data"
      emptyDescription="There are no designations in the current data."
    >
      <DonutChart
        data={slices}
        height={210}
        centerValue={String(total)}
        centerLabel="Faculty"
      />
    </ChartCard>
  )
}

function FacultyTable({ rows }: { rows: AdminFacultyRow[] }) {
  return (
    <ChartCard
      title="Faculty"
      subtitle="Faculty allocation and weekly workload from existing teaching data"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={Users}
      emptyTitle="No faculty"
      emptyDescription="There are no faculty records in the current data."
      exportFileName="admin_faculty.csv"
      exportColumns={[
        { key: "faculty_id", label: "Faculty ID" },
        { key: "faculty_code", label: "Faculty Code" },
        { key: "full_name", label: "Faculty" },
        { key: "department_name", label: "Department" },
        { key: "designation", label: "Designation" },
        { key: "subject_count", label: "Subject Count" },
        { key: "student_count", label: "Student Count" },
        { key: "workload_hours", label: "Workload Hours" },
      ]}
      exportRows={rows as unknown as Array<Record<string, unknown>>}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-200 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Faculty</th>
              <th className="py-2 pr-4 font-medium">Department</th>
              <th className="py-2 pr-4 font-medium">Designation</th>
              <th className="py-2 pr-4 text-right font-medium">Subjects</th>
              <th className="py-2 pr-4 text-right font-medium">Students</th>
              <th className="py-2 text-right font-medium">Workload</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.faculty_id} className="border-b last:border-0">
                <td className="py-2.5 pr-4">
                  <p className="max-w-52 truncate font-medium" title={row.full_name}>
                    {row.full_name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {row.faculty_code || row.faculty_id}
                  </p>
                </td>
                <td className="py-2.5 pr-4 text-xs">{row.department_name || "—"}</td>
                <td className="py-2.5 pr-4 text-xs">{row.designation || "—"}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{row.subject_count}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{row.student_count}</td>
                <td className="py-2.5 text-right tabular-nums">
                  {row.workload_hours === null ? "—" : `${toFixed(row.workload_hours)} h/wk`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  )
}

export function FacultyView({
  data,
  fetchedAt,
}: {
  data: AdminFacultyData
  fetchedAt: string
}) {
  const { kpis } = data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Faculty</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Read-only institution overview of faculty allocation and teaching workload.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
          <UserCog className="size-3.5" />
          {kpis.total_faculty} faculty
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard
          label="Total Faculty"
          value={String(kpis.total_faculty)}
          icon={Users}
          tone="primary"
        />
        <StatCard
          label="Active Faculty"
          value={String(kpis.active_faculty)}
          icon={UserCog}
          tone="success"
          hint="Faculty with an Active status"
        />
        <StatCard
          label="Departments"
          value={String(kpis.department_count)}
          icon={Building2}
          tone="warning"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <FacultyByDepartmentCard data={data.by_department} />
        <FacultyByDesignationCard data={data.by_designation} />
      </div>

      <FacultyTable rows={data.faculty} />

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Clock3 className="size-3.5" />
        Workload is the existing faculty derivation (weekly teaching hours from
        class totals). Data refreshed{" "}
        {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}
