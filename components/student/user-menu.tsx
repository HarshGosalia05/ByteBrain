"use client"

import { useRouter } from "next/navigation"
import { ChevronDown, LogOut, Settings, UserRound } from "lucide-react"
import { Menu } from "@base-ui/react/menu"

import { AvatarInitials } from "@/components/shared/data/avatar-initials"
import { Button } from "@/components/ui/button"
import { signOut } from "@/lib/auth-actions"
import type { StudentProfile } from "@/lib/student-api"
import { cn } from "@/lib/utils"

export function UserMenu({ profile }: { profile: StudentProfile | null }) {
  const router = useRouter()

  const firstName = profile?.first_name ?? ""
  const lastName = profile?.last_name ?? ""
  const fullName = `${firstName} ${lastName}`.trim() || "Student"
  const department = profile?.department_name ?? null
  const semester = profile?.current_semester ?? null
  const enrollment = profile?.enrollment_no ?? null
  const studentId = profile?.student_id ?? null

  const meta = [
    semester ? `Sem ${semester}` : null,
    enrollment !== null ? `ENR ${enrollment}` : null,
    department ?? null,
  ]
    .filter(Boolean)
    .join(" • ")

  return (
    <Menu.Root>
      <Menu.Trigger
        render={
          <Button variant="ghost" className="h-10 gap-2 rounded-full px-2 sm:px-2.5" />
        }
        aria-label="Account menu"
      >
        <AvatarInitials firstName={firstName} lastName={lastName} />
        <span className="hidden min-w-0 flex-col text-left leading-tight sm:flex">
          <span className="max-w-40 truncate text-sm font-medium">{fullName}</span>
          {meta && (
            <span className="max-w-56 truncate text-xs text-muted-foreground">{meta}</span>
          )}
        </span>
        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
      </Menu.Trigger>

      <Menu.Portal>
        <Menu.Positioner align="end" sideOffset={8} className="z-50">
          <Menu.Popup className="min-w-60 overflow-hidden rounded-xl border border-border bg-popover p-1.5 text-sm text-popover-foreground shadow-xl outline-none">
            <div className="flex items-center gap-3 rounded-lg px-2.5 py-2.5">
              <AvatarInitials firstName={firstName} lastName={lastName} />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{fullName}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {studentId ?? (department ?? "Student")}
                </p>
              </div>
            </div>
            {meta && (
              <p className="truncate px-2.5 pb-1 text-xs text-muted-foreground">{meta}</p>
            )}
            <Menu.Separator className="my-1 h-px bg-border" />
            <Menu.Item
              className={cn(
                "flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-muted data-[highlighted]:text-foreground",
              )}
              onClick={() => router.push("/student/profile")}
            >
              <UserRound className="size-4 text-muted-foreground" />
              View Profile
            </Menu.Item>
            <Menu.Item
              className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-muted data-[highlighted]:text-foreground"
              onClick={() => router.push("/student/settings")}
            >
              <Settings className="size-4 text-muted-foreground" />
              Settings
            </Menu.Item>
            <Menu.Separator className="my-1 h-px bg-border" />
            <Menu.Item
              className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-destructive outline-none data-[highlighted]:bg-destructive/10"
              onClick={() => signOut()}
            >
              <LogOut className="size-4" />
              Sign Out
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  )
}
