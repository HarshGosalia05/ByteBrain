import { requireRole } from "@/lib/session"
import { getAdminStudentProfile } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { StudentProfileView } from "@/components/admin/students/student-profile-view"

export default async function AdminStudentProfilePage(props: {
  params: Promise<{ studentId: string }>
}) {
  await requireRole("Admin")

  const { studentId } = await props.params
  const decodedId = decodeURIComponent(studentId)

  const res = await getAdminStudentProfile(decodedId)
  if (!res.ok) {
    return (
      <ErrorState
        title="Student profile unavailable"
        description={res.error.message}
      />
    )
  }

  return <StudentProfileView data={res.data} fetchedAt={res.fetchedAt} />
}
