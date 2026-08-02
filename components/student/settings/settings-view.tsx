"use client"

import { useTheme } from "next-themes"
import {
  Bell,
  Check,
  Lock,
  Monitor,
  Moon,
  Palette,
  ShieldCheck,
  Sun,
  UserRound,
  type LucideIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const THEME_OPTIONS: { value: string; label: string; icon: LucideIcon }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
]

function SectionCard({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-xl bg-card ring-1 ring-foreground/10">
      <div className="flex items-start gap-3 border-b border-border/60 p-5">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Icon className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function ComingSoonRow({ label, description }: { label: string; description: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border/60 py-3 last:border-0">
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <Badge variant="muted" className="shrink-0">
        Coming soon
      </Badge>
    </div>
  )
}

export function SettingsView({
  session,
}: {
  session: {
    username: string | null
    role: string | null
    studentId: string | null
    department: string | null
  } | null
}) {
  const { theme, setTheme } = useTheme()

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <SectionCard
        icon={Palette}
        title="Theme preference"
        description="Choose how the portal looks across this device."
      >
        <div className="grid grid-cols-3 gap-2 sm:max-w-md">
          {THEME_OPTIONS.map((option) => {
            const selected = theme === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setTheme(option.value)}
                aria-pressed={selected}
                className={cn(
                  "flex flex-col items-center gap-2 rounded-xl border px-3 py-3 text-sm font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                  selected
                    ? "border-primary bg-primary/5 text-foreground"
                    : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <option.icon className="size-4" />
                {option.label}
                {selected && <Check className="size-3 text-primary" />}
              </button>
            )
          })}
        </div>
      </SectionCard>

      <SectionCard
        icon={UserRound}
        title="Account preferences"
        description="Personalise your account and how information is displayed."
      >
        <ComingSoonRow
          label="Display language"
          description="Select the language used across the portal."
        />
        <ComingSoonRow
          label="Name display"
          description="Choose how your name is shown in the header and reports."
        />
      </SectionCard>

      <SectionCard
        icon={Bell}
        title="Notification preferences"
        description="Control what notifications you receive and how."
      >
        <ComingSoonRow
          label="Grade alerts"
          description="Get notified when new grades or results are published."
        />
        <ComingSoonRow
          label="Attendance warnings"
          description="Alerts when attendance drops below the required threshold."
        />
        <ComingSoonRow
          label="Semester results"
          description="Be notified when semester summaries are updated."
        />
      </SectionCard>

      <SectionCard
        icon={Lock}
        title="Security"
        description="Protect your account and manage sign-in options."
      >
        <ComingSoonRow
          label="Change password"
          description="Update the password used to sign in to your account."
        />
        <ComingSoonRow
          label="Two-factor authentication"
          description="Add an extra layer of security to your account."
        />
        <ComingSoonRow
          label="Sign out all devices"
          description="End all active sessions across other browsers and devices."
        />
      </SectionCard>

      <SectionCard
        icon={ShieldCheck}
        title="Session information"
        description="Details about your current signed-in session."
      >
        {session ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium">Signed in as {session.username}</p>
                <p className="text-xs text-muted-foreground">
                  {session.department ?? "No department"} · Student
                </p>
              </div>
              <Badge variant="success">Active session</Badge>
            </div>
            <div className="grid gap-x-6 gap-y-1 border-t border-border/60 pt-3 text-sm sm:grid-cols-2">
              <p className="text-muted-foreground">
                Role: <span className="font-medium text-foreground">Student</span>
              </p>
              {session.studentId && (
                <p className="text-muted-foreground">
                  Student ID: <span className="font-medium text-foreground">{session.studentId}</span>
                </p>
              )}
              {session.department && (
                <p className="text-muted-foreground">
                  Department:{" "}
                  <span className="font-medium text-foreground">{session.department}</span>
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Session details are unavailable right now.
          </p>
        )}
      </SectionCard>

      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <ShieldCheck className="size-4" />
        You can sign out from the sidebar or the account menu in the header.
      </div>
    </div>
  )
}
