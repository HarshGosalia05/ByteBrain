"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Bell,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  FileText,
  GraduationCap,
  LayoutDashboard,
  Settings,
  Sparkles,
  User,
  type LucideIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"

const NAV_ITEMS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/student/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/student/academic", label: "Academic", icon: GraduationCap },
  { href: "/student/report-card", label: "Report Card", icon: FileText },
  { href: "/student/subjects", label: "Subjects", icon: BookOpen },
  { href: "/student/attendance", label: "Attendance", icon: CalendarCheck },
  { href: "/student/timetable", label: "Timetable", icon: CalendarDays },
  { href: "/student/ml-insights", label: "ML Insights", icon: Sparkles },
  { href: "/student/profile", label: "Profile", icon: User },
  { href: "/student/notifications", label: "Notifications", icon: Bell },
  { href: "/student/settings", label: "Settings", icon: Settings },
]

export function SideNav() {
  const pathname = usePathname()

  return (
    <nav aria-label="Student navigation" className="flex min-h-0 flex-1 flex-col gap-6">
      <div className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex min-h-8 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <item.icon
                className={cn(
                  "size-4 shrink-0 transition-colors",
                  active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
                )}
              />
              {item.label}
              {active && (
                <span className="ml-auto size-1.5 rounded-full bg-primary" aria-hidden="true" />
              )}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
