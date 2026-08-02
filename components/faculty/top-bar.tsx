"use client"

import * as React from "react"
import { Menu, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"
import { UserMenu } from "@/components/faculty/user-menu"
import type { FacultyProfile } from "@/lib/faculty-api"

export function TopBar({
  menuOpen,
  onMenu,
  profile,
}: {
  menuOpen: boolean
  onMenu: () => void
  profile: FacultyProfile | null
}) {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true)
  }, [])

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border/60 bg-background/80 px-4 backdrop-blur lg:px-8">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open navigation menu"
          aria-expanded={menuOpen}
          className="lg:hidden"
          onClick={onMenu}
        >
          <Menu className="size-4" />
        </Button>
        <p className="text-sm font-medium">Faculty Portal</p>
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle theme"
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
