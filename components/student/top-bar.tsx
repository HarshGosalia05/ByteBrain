"use client"

import * as React from "react"
import { Menu, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"
import { UserMenu } from "@/components/student/user-menu"
import { NotificationBell } from "@/components/student/notification-bell"
import { useTranslation } from "@/lib/i18n"
import type { StudentProfile } from "@/lib/student-api"

export function TopBar({
  menuOpen,
  onMenu,
  profile,
}: {
  menuOpen: boolean
  onMenu: () => void
  profile: StudentProfile | null
}) {
  const { resolvedTheme, setTheme } = useTheme()
  const { t } = useTranslation()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true)
  }, [])

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border/60 bg-background/80 px-4 backdrop-blur lg:px-8 print:hidden">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("Open navigation menu", "Open navigation menu")}
          aria-expanded={menuOpen}
          className="lg:hidden"
          onClick={onMenu}
        >
          <Menu className="size-4" />
        </Button>
        <p className="text-sm font-medium">{t("Student Portal", "Student Portal")}</p>
      </div>
      <div className="flex items-center gap-1">
        <NotificationBell />
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("Toggle theme", "Toggle theme")}
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          {mounted ? (
            resolvedTheme === "dark" ? (
              <Sun className="size-4" />
            ) : (
              <Moon className="size-4" />
            )
          ) : (
            <span className="size-4" aria-hidden="true" />
          )}
        </Button>
        <UserMenu profile={profile} />
      </div>
    </header>
  )
}
