"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ClassesTab } from "./classes-tab"
import { MenteesTab } from "./mentees-tab"
import type { FacultyClassesResponse, FacultyMenteesResponse } from "@/lib/faculty-api"

export function StudentsView({
  activeTab,
  classesData,
  menteesData,
}: {
  activeTab: string
  classesData: FacultyClassesResponse | null
  menteesData: FacultyMenteesResponse | null
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleTabChange = (val: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", val)
    // reset pagination/filters when switching tabs to avoid carrying over invalid filters
    params.delete("page")
    params.delete("search")
    params.delete("semester")
    params.delete("academic_year")
    params.delete("subject_id")
    params.delete("standing")
    params.delete("flagged_only")
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
      <TabsList>
        <TabsTrigger value="classes">My Classes</TabsTrigger>
        <TabsTrigger value="mentees">My Mentees</TabsTrigger>
      </TabsList>
      <div className="mt-4">
        {activeTab === "classes" && classesData && (
          <ClassesTab data={classesData} />
        )}
        {activeTab === "mentees" && menteesData && (
          <MenteesTab data={menteesData} />
        )}
      </div>
    </Tabs>
  )
}
