"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Bell,
  BookOpen,
  CalendarCheck,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Settings,
  User,
  type LucideIcon,
} from "lucide-react"

import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { Button } from "@/components/ui/button"
import { signOut } from "@/lib/auth-actions"
import type { StudentProfile } from "@/lib/student-api"
import { cn } from "@/lib/utils"

const NAV_ITEMS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/student/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/student/academic", label: "Academic", icon: GraduationCap },
  { href: "/student/subjects", label: "Subjects", icon: BookOpen },
  { href: "/student/attendance", label: "Attendance", icon: CalendarCheck },
  { href: "/student/profile", label: "Profile", icon: User },
  { href: "/student/notifications", label: "Notifications", icon: Bell },
  { href: "/student/settings", label: "Settings", icon: Settings },
]

export function SideNav({ profile }: { profile: StudentProfile | null }) {
  const pathname = usePathname()

  const firstName = profile?.first_name ?? ""
  const lastName = profile?.last_name ?? ""
  const fullName = `${firstName} ${lastName}`.trim() || "Student"
  const department = profile?.department_name ?? "Student"

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

      <div className="mt-auto flex flex-col gap-2 border-t border-sidebar-border pt-4">
        <Link
          href="/student/profile"
          className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors outline-none hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <AvatarInitials firstName={firstName} lastName={lastName} />
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
