import { requireRole } from "@/lib/session"
import { getReportCard } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { ReportCardView } from "@/components/student/report-card/report-card-view"

export default async function ReportCardPage() {
  await requireRole("Student")

  const result = await getReportCard()

  if (!result.ok) {
    return (
      <ErrorState
        title="Report card unavailable"
        description={result.error.message}
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="print:hidden">
        <PageHeader
          title="Report Card"
          description="Consolidated academic report card across all semesters."
          fetchedAt={result.fetchedAt}
        />
      </div>
      <ReportCardView data={result.data} />
    </div>
  )
}
