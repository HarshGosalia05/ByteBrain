"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  AlertTriangle,
  Bell,
  BookOpen,
  Brain,
  Building2,
  CalendarCheck,
  LayoutDashboard,
  Library,
  LineChart,
  Rocket,
  Smile,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"


function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-3 pt-1 text-xs font-semibold tracking-wider text-muted-foreground/70 uppercase">
      {children}
    </p>
  )
}

function NavLink({
  href,
  icon: Icon,
  label,
}: {
  href: string
  icon: LucideIcon
  label: string
}) {
  const pathname = usePathname()
  const active =
    pathname === href ||
    (pathname.startsWith(href) &&
      !pathname.slice(href.length).startsWith("/"))
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex min-h-8 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      <Icon
        className={cn(
          "size-4 shrink-0 transition-colors",
          active
            ? "text-primary"
            : "text-muted-foreground group-hover:text-foreground"
        )}
      />
      {label}
      {active && (
        <span
          className="ml-auto size-1.5 rounded-full bg-primary"
          aria-hidden="true"
        />
      )}
    </Link>
  )
}

export function SideNav() {
  const pathname = usePathname()
  const dashboardActive =
    pathname === "/admin/dashboard" || pathname === "/admin"

  return (
    <nav
      aria-label="Admin navigation"
      className="flex min-h-0 flex-1 flex-col gap-6"
    >
      <div className="flex flex-col gap-1">
        <Link
          href="/admin/dashboard"
          aria-current={dashboardActive ? "page" : undefined}
          className={cn(
            "group flex min-h-8 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
            dashboardActive
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          )}
        >
          <LayoutDashboard
            className={cn(
              "size-4 shrink-0 transition-colors",
              dashboardActive
                ? "text-primary"
                : "text-muted-foreground group-hover:text-foreground"
            )}
          />
          Dashboard
          {dashboardActive && (
            <span
              className="ml-auto size-1.5 rounded-full bg-primary"
              aria-hidden="true"
            />
          )}
        </Link>
      </div>

      <div className="flex flex-col gap-1">
        <GroupLabel>Academic</GroupLabel>
        <div className="flex flex-col gap-1 pl-4">
          <NavLink href="/admin/academic" icon={Library} label="Overview" />
          <NavLink href="/admin/academic/subjects" icon={BookOpen} label="Subjects" />
          <NavLink href="/admin/academic/departments" icon={Building2} label="Departments" />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <GroupLabel>Analytics</GroupLabel>
        <div className="flex flex-col gap-1 pl-4">
          <NavLink href="/admin/analytics" icon={LineChart} label="Overview" />
          <NavLink href="/admin/analytics/departments" icon={Building2} label="Departments" />
          <NavLink href="/admin/analytics/at-risk" icon={AlertTriangle} label="At-Risk" />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <NavLink href="/admin/attendance" icon={CalendarCheck} label="Attendance" />
        <NavLink href="/admin/risk" icon={AlertTriangle} label="Risk & Early Warning" />
        <NavLink href="/admin/ml-intelligence" icon={Brain} label="ML Intelligence" />
        <NavLink href="/admin/students" icon={Users} label="Students" />
        <NavLink href="/admin/faculty" icon={UserCog} label="Faculty" />
        <NavLink href="/admin/career" icon={Rocket} label="Career Readiness" />
        <NavLink href="/admin/health" icon={Smile} label="Lifestyle Insights" />
        <NavLink href="/admin/notifications" icon={Bell} label="Notifications & Insights" />
      </div>
    </nav>
  )
}
