"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Bell,
  BookOpen,
  CalendarCheck,
  GraduationCap,
  LayoutDashboard,
  Settings,
  User,
  type LucideIcon,
} from "lucide-react"

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

export function SideNav() {
  const pathname = usePathname()

  return (
    <nav aria-label="Student navigation" className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <item.icon className="size-4 shrink-0" />
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}
