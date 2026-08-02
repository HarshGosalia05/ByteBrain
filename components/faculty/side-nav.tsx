"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BarChart3,
  BookOpen,
  Briefcase,
  CalendarCheck,
  LayoutDashboard,
  LogOut,
  Settings,
  User,
  Users,
  type LucideIcon,
} from "lucide-react"

import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { Button } from "@/components/ui/button"
import { signOut } from "@/lib/auth-actions"
import { splitFullName } from "@/lib/faculty-name"
import type { FacultyProfile } from "@/lib/faculty-api"
import { cn } from "@/lib/utils"

const NAV_ITEMS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/faculty/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/faculty/profile", label: "Profile", icon: User },
  { href: "/faculty/students", label: "Students", icon: Users },
  { href: "/faculty/subjects", label: "Subjects", icon: BookOpen },
  { href: "/faculty/performance", label: "Performance Analytics", icon: BarChart3 },
  { href: "/faculty/attendance", label: "Attendance Analytics", icon: CalendarCheck },
  { href: "/faculty/workload", label: "Teaching Workload", icon: Briefcase },
  { href: "/faculty/settings", label: "Settings", icon: Settings },
]

export function SideNav({ profile }: { profile: FacultyProfile | null }) {
  const pathname = usePathname()

  const fullName = profile?.full_name ?? "Faculty"
  const department = profile?.department_name ?? "Faculty"

  return (
    <nav aria-label="Faculty navigation" className="flex min-h-0 flex-1 flex-col gap-6">
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

      <div className="mt-auto flex flex-col gap-2 border-t border-sidebar-border pt-4">
        <Link
          href="/faculty/profile"
          className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors outline-none hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <AvatarInitials
            firstName={splitFullName(profile?.full_name).first}
            lastName={splitFullName(profile?.full_name).last}
          />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{fullName}</span>
            <span className="block truncate text-xs text-muted-foreground">{department}</span>
          </span>
        </Link>
        <form action={signOut}>
          <Button
            variant="ghost"
            size="sm"
            type="submit"
            className="w-full justify-start gap-2.5 text-muted-foreground hover:text-foreground"
          >
            <LogOut className="size-4" />
            Log out
          </Button>
        </form>
      </div>
    </nav>
  )
}
