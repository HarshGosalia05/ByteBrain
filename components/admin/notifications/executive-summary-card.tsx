import { Sparkles, Building2, BookOpen, AlertTriangle, GraduationCap, CheckCircle2 } from "lucide-react"

import type { ExecutiveSummaryData } from "@/lib/admin-api"
import { ChartCard } from "@/components/shared/data/chart-card"
import { StatCard } from "@/components/shared/data/stat-card"

export function ExecutiveSummaryCard({ data }: { data: ExecutiveSummaryData }) {
  return (
    <ChartCard
      title="Executive Academic Summary & Insights"
      subtitle="Structured institution analytics and grounded administrative insights"
      status={data ? "ready" : "empty"}
      emptyIcon={Sparkles}
      emptyTitle="No executive insights available"
      emptyDescription="Analytics are currently being compiled."
    >
      {/* Top Grounded Insights Bullet Points */}
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 flex flex-col gap-2.5">
        <div className="flex items-center gap-2 font-medium text-sm text-primary">
          <Sparkles className="size-4 shrink-0" />
          <span>Grounded Key Insights</span>
        </div>
        <ul className="grid gap-2 text-xs text-foreground sm:grid-cols-1 md:grid-cols-2">
          {data.insights.map((insight, idx) => (
            <li key={idx} className="flex items-start gap-2 bg-background/60 rounded-md p-2 border border-border/50">
              <CheckCircle2 className="size-3.5 shrink-0 text-primary mt-0.5" />
              <span>{insight}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* KPI Cards Grid */}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Strongest Dept"
          value={data.strongest_department ? `${data.strongest_department.department_name} (${data.strongest_department.avg_cgpa ?? "—"} CGPA)` : "—"}
          icon={Building2}
          tone="success"
        />
        <StatCard
          label="Weakest Subject"
          value={data.weakest_subject ? `${data.weakest_subject.subject_code} (${data.weakest_subject.avg_percentage ?? "—"}%)` : "—"}
          icon={BookOpen}
          tone="warning"
        />
        <StatCard
          label="At-Risk Students"
          value={data.total_at_risk_students.toString()}
          icon={AlertTriangle}
          tone={data.total_at_risk_students > 0 ? "destructive" : "success"}
        />
        <StatCard
          label="Institution Health"
          value={data.overall_avg_cgpa != null ? `${data.overall_avg_cgpa} CGPA | ${data.overall_attendance_pct ?? "—"}% Att.` : "—"}
          icon={GraduationCap}
          tone="primary"
        />
      </div>
    </ChartCard>
  )
}
