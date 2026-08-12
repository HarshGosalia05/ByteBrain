import { requireRole } from "@/lib/session"
import { getAdminFaculty } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { FacultyView } from "@/components/admin/faculty/faculty-view"

export default async function AdminFacultyPage() {
  await requireRole("Admin")

  const res = await getAdminFaculty()
  if (!res.ok) {
    return (
      <ErrorState
        title="Failed to load faculty"
        description={res.error.message}
      />
    )
  }

  return <FacultyView data={res.data} fetchedAt={res.fetchedAt} />
}
