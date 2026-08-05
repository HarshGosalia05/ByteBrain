"use client"

import { Suspense } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

import { SettingsSection } from "./settings-section"
import { SettingsSectionSkeleton } from "./settings-skeleton"
import { SETTINGS_TABS } from "./settings-tabs"
import type { FacultyProfile, FacultySettingsResponse } from "@/lib/faculty-api"

export function SettingsView({
  activeTab,
  settings,
  profile,
}: {
  activeTab: string
  settings: FacultySettingsResponse
  profile: FacultyProfile | null
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleTabChange = (value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", value)
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
      <div className="overflow-x-auto pb-1">
        <TabsList className="h-auto w-full justify-start sm:w-auto">
          {SETTINGS_TABS.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="gap-1.5">
              <tab.icon className="size-4" />
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      <div className="mt-4">
        <Suspense key={activeTab} fallback={<SettingsSectionSkeleton />}>
          <SettingsSection activeTab={activeTab} settings={settings} profile={profile} />
        </Suspense>
      </div>
    </Tabs>
  )
}
