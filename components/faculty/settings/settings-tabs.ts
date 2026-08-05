import type { LucideIcon } from "lucide-react"
import {
  Accessibility,
  Bell,
  ChartColumn,
  CircleUserRound,
  FileDown,
  Gauge,
  LayoutDashboard,
  MonitorCog,
  ShieldCheck,
  Sparkles,
} from "lucide-react"

export type SettingsTabId =
  | "profile"
  | "workspace"
  | "dashboard"
  | "analytics"
  | "notifications"
  | "export"
  | "accessibility"
  | "security"
  | "personalization"
  | "readiness"

export type SettingsTab = {
  id: SettingsTabId
  label: string
  icon: LucideIcon
  description: string
}

export const SETTINGS_TABS: SettingsTab[] = [
  {
    id: "profile",
    label: "Profile",
    icon: CircleUserRound,
    description: "Your identity, contact details and profile-extension fields.",
  },
  {
    id: "workspace",
    label: "Workspace",
    icon: MonitorCog,
    description: "Dashboard layout, density, sidebar state and sticky filters.",
  },
  {
    id: "dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    description: "Landing page, term defaults and favourite widgets.",
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: ChartColumn,
    description: "Threshold overrides and chart, table and refresh preferences.",
  },
  {
    id: "notifications",
    label: "Notifications",
    icon: Bell,
    description: "Alert rules, quiet hours, digest and browser channel.",
  },
  {
    id: "export",
    label: "Export",
    icon: FileDown,
    description: "CSV formats, delimiters, precision and file names.",
  },
  {
    id: "accessibility",
    label: "Accessibility",
    icon: Accessibility,
    description: "Contrast, colour palette, fonts, motion and keyboard support.",
  },
  {
    id: "security",
    label: "Security",
    icon: ShieldCheck,
    description: "Your session, recent activity and password.",
  },
  {
    id: "personalization",
    label: "Personalization",
    icon: Sparkles,
    description: "Recent searches, favourites and quick access.",
  },
  {
    id: "readiness",
    label: "Readiness",
    icon: Gauge,
    description: "Your workspace readiness score and guidance.",
  },
]

export const DEFAULT_SETTINGS_TAB: SettingsTabId = "profile"
