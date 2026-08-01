import { User } from "lucide-react"

import { requireRole } from "@/lib/session"
import { getStudentProfile } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { AvatarInitials } from "@/components/shared/data/avatar-initials"

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

export default async function ProfilePage() {
  await requireRole("Student")

  const result = await getStudentProfile()

  if (!result.ok) {
    return <ErrorState title="Profile unavailable" description={result.error.message} />
  }

  const profile = result.data

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <PageHeader title="Profile" description="Your student profile details." fetchedAt={result.fetchedAt} />

      <section className="flex items-center gap-4 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <AvatarInitials
          firstName={profile.first_name}
          lastName={profile.last_name}
          className="size-14 text-lg"
        />
        <div>
          <h2 className="text-lg font-semibold tracking-tight">
            {profile.first_name} {profile.last_name}
          </h2>
          <p className="text-sm text-muted-foreground">{profile.student_id}</p>
        </div>
      </section>

      <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
        <dl>
          <DetailRow label="Student ID" value={profile.student_id} />
          <DetailRow label="Department" value={profile.department_name ?? "Not assigned"} />
          <DetailRow label="Enrollment number" value={String(profile.enrollment_no)} />
          <DetailRow label="Admission year" value={String(profile.admission_year)} />
          <DetailRow label="Current semester" value={`Semester ${profile.current_semester}`} />
        </dl>
      </section>

      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <User className="size-4" />
        Profile editing is not available yet. Settings for account preferences will arrive in a
        future phase.
      </p>
    </div>
  )
}
