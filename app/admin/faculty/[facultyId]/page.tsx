import { requireRole } from "@/lib/session"
import { getAdminFacultyProfile } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { FacultyProfileView } from "@/components/admin/faculty/faculty-profile-view"

export default async function AdminFacultyProfilePage(props: {
  params: Promise<{ facultyId: string }>
}) {
  await requireRole("Admin")

  const { facultyId } = await props.params
  const decodedId = decodeURIComponent(facultyId)

  const res = await getAdminFacultyProfile(decodedId)
  if (!res.ok) {
    return (
      <ErrorState
        title="Faculty profile unavailable"
        description={res.error.message}
      />
    )
  }

  return <FacultyProfileView data={res.data} fetchedAt={res.fetchedAt} />
}
