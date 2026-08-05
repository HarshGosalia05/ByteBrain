import Link from "next/link"
import { ArrowRight, BookOpen, GraduationCap, Users } from "lucide-react"

import { requireRole } from "@/lib/session"
import { getFacultyDashboard, getFacultyProfile } from "@/lib/faculty-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { StatCard } from "@/components/shared/data/stat-card"
import { ErrorState } from "@/components/shared/state/error-state"
import { ContactForm } from "@/components/faculty/profile/contact-form"
import { Badge } from "@/components/ui/badge"

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/60 py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  )
}

export default async function ProfilePage() {
  await requireRole("Faculty")

  const [profileResult, dashboardResult] = await Promise.all([
    getFacultyProfile(),
    getFacultyDashboard(),
  ])

  if (!profileResult.ok) {
    return <ErrorState title="Profile unavailable" description={profileResult.error.message} />
  }

  const profile = profileResult.data
  const dashboard = dashboardResult.ok ? dashboardResult.data : null

  const fetchedAt = [profileResult, dashboardResult]
    .filter((r) => r.ok)
    .map((r) => r.fetchedAt)
    .sort()
    .pop()

  return (
    <div className="flex max-w-full flex-col gap-6 lg:max-w-[95%]">
      <PageHeader
        title="Profile"
        description="Your faculty identity, contact details and teaching overview."
        fetchedAt={fetchedAt}
      />

      <section className="flex flex-wrap items-center gap-4 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <AvatarInitials
          firstName={profile.full_name.split(" ")[0] ?? ""}
          lastName={profile.full_name.split(" ").slice(1).join(" ") ?? ""}
          size="lg"
        />
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold tracking-tight">{profile.full_name}</h2>
          <p className="text-sm text-muted-foreground">{profile.faculty_id}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {profile.designation && <Badge variant="default">{profile.designation}</Badge>}
            {profile.department_name && <Badge variant="outline">{profile.department_name}</Badge>}
            <Badge variant="muted">Joined {profile.joining_date}</Badge>
          </div>
        </div>
      </section>

      <section
        className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        aria-label="Teaching overview"
      >
        <StatCard
          label="Subjects"
          value={dashboard ? String(dashboard.subjects) : "—"}
          icon={BookOpen}
          hint="Currently assigned"
        />
        <StatCard
          label="Students"
          value={dashboard ? String(dashboard.students) : "—"}
          icon={Users}
          hint="Across your classes"
          tone="success"
        />
        <StatCard
          label="Mentees"
          value={dashboard ? String(dashboard.mentees) : "—"}
          icon={GraduationCap}
          hint="Under mentorship"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Employment and contact details">
        <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <h3 className="mb-2 text-sm font-semibold">Employment details</h3>
          <dl>
            <DetailRow label="Faculty ID" value={profile.faculty_id} />
            <DetailRow label="Faculty code" value={profile.faculty_code} />
            <DetailRow label="Gender" value={profile.gender ?? "—"} />
            <DetailRow label="Qualification" value={profile.qualification ?? "—"} />
            <DetailRow label="Specialization" value={profile.specialization ?? "—"} />
            <DetailRow label="Experience" value={`${profile.experience_years ?? 0} years`} />
            <DetailRow label="Employment type" value={profile.employment_type ?? "—"} />
            <DetailRow label="Status" value={profile.status ?? "—"} />
          </dl>
        </div>

        <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <ContactForm profile={profile} />
          <p className="mt-4 border-t border-border/60 pt-4 text-xs text-muted-foreground">
            Designation and department are managed by the administration and cannot be changed
            here.
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2" aria-label="Quick links">
        <Link
          href="/faculty/subjects"
          className="group flex items-center gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10 transition-colors outline-none hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <BookOpen className="size-5 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Subjects</p>
            <p className="text-xs text-muted-foreground">Subjects you currently teach.</p>
          </div>
          <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
        </Link>
        <Link
          href="/faculty/students"
          className="group flex items-center gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10 transition-colors outline-none hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <Users className="size-5 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Students</p>
            <p className="text-xs text-muted-foreground">Your classes and mentees.</p>
          </div>
          <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
        </Link>
      </section>
    </div>
  )
}
