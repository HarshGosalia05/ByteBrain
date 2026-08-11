"use client"

import { ChevronDown, LogOut } from "lucide-react"
import { Menu } from "@base-ui/react/menu"

import { Button } from "@/components/ui/button"
import { signOut } from "@/lib/auth-actions"
import { cn } from "@/lib/utils"

export function AdminUserMenu({ username }: { username: string | null }) {
  const displayName = username && username.trim() ? username.trim() : "Admin"
  const initial = displayName.charAt(0).toUpperCase() || "A"

  return (
    <Menu.Root>
      <Menu.Trigger
        render={
          <Button
            variant="ghost"
            className="h-10 gap-2 rounded-full px-2 sm:px-2.5"
          />
        }
        aria-label="Account menu"
      >
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary select-none"
          aria-hidden="true"
        >
          {initial}
        </span>
        <span className="hidden min-w-0 flex-col text-left leading-tight sm:flex">
          <span className="max-w-40 truncate text-sm font-medium">
            {displayName}
          </span>
          <span className="text-xs text-muted-foreground">Administrator</span>
        </span>
        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
      </Menu.Trigger>

      <Menu.Portal>
        <Menu.Positioner align="end" sideOffset={8} className="z-50">
          <Menu.Popup className="min-w-60 overflow-hidden rounded-xl border border-border bg-popover p-1.5 text-sm text-popover-foreground shadow-xl outline-none">
            <div className="flex items-center gap-3 rounded-lg px-2.5 py-2.5">
              <span
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary select-none"
                aria-hidden="true"
              >
                {initial}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{displayName}</p>
                <p className="truncate text-xs text-muted-foreground">
                  Administrator
                </p>
              </div>
            </div>
            <Menu.Separator className="my-1 h-px bg-border" />
            <Menu.Item
              className={cn(
                "flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-destructive outline-none data-[highlighted]:bg-destructive/10"
              )}
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
