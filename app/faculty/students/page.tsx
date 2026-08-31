import { requireRole } from "@/lib/session"
import { CURRENT_ACADEMIC_YEAR, ACADEMIC_YEAR_ALL } from "@/lib/config"
import { getFacultyClasses, getFacultyMentees } from "@/lib/faculty-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { StudentsView } from "@/components/faculty/students/students-view"

export default async function StudentsPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Faculty")
  
  const searchParams = await props.searchParams
  const tab = typeof searchParams.tab === "string" ? searchParams.tab : "classes"

  const page = typeof searchParams.page === "string" ? parseInt(searchParams.page) : 1
  const search = typeof searchParams.search === "string" ? searchParams.search : undefined
  const semester = typeof searchParams.semester === "string" ? parseInt(searchParams.semester) : undefined
  const sort = typeof searchParams.sort === "string" ? searchParams.sort : undefined
  const order = typeof searchParams.order === "string" ? (searchParams.order as "asc" | "desc") : undefined

  let classesData = null
  let menteesData = null

  if (tab === "classes") {
    const rawAcademicYear =
      typeof searchParams.academic_year === "string" ? searchParams.academic_year : undefined
    const academic_year =
      rawAcademicYear === ACADEMIC_YEAR_ALL
        ? undefined
        : rawAcademicYear ?? CURRENT_ACADEMIC_YEAR
    const subject_id = typeof searchParams.subject_id === "string" ? searchParams.subject_id : undefined
    const attendance_range = typeof searchParams.attendance_range === "string" ? searchParams.attendance_range : undefined
    const sgpa_range = typeof searchParams.sgpa_range === "string" ? searchParams.sgpa_range : undefined
    const grade = typeof searchParams.grade === "string" ? searchParams.grade : undefined
    const result_status = typeof searchParams.result_status === "string" ? searchParams.result_status : undefined
    const student_status = typeof searchParams.student_status === "string" ? searchParams.student_status : undefined
    
    const res = await getFacultyClasses({ 
      page, search, semester, academic_year, subject_id, 
      attendance_range, sgpa_range, grade, result_status, student_status, 
      sort, order 
    })
    if (!res.ok) {
      return <ErrorState title="Failed to load classes" description={res.error.message} />
    }
    classesData = res.data
  } else if (tab === "mentees") {
    const standing = typeof searchParams.standing === "string" ? searchParams.standing : undefined
    const flagged_only = searchParams.flagged_only === "true"
    
    const res = await getFacultyMentees({ page, search, semester, standing, flagged_only, sort, order })
    if (!res.ok) {
      return <ErrorState title="Failed to load mentees" description={res.error.message} />
    }
    menteesData = res.data
  } else {
    return <ErrorState title="Invalid tab" description="The requested tab does not exist." />
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Students</h1>
        <p className="text-muted-foreground mt-2">
          Manage your assigned classes and mentees.
        </p>
      </div>
      <StudentsView 
        activeTab={tab} 
        classesData={classesData} 
        menteesData={menteesData} 
      />
    </div>
  )
}
