import { NextResponse } from "next/server"

import { saveSubjectMarks } from "@/lib/faculty-api"

export async function PATCH(
  request: Request,
  props: { params: Promise<{ subjectId: string; enrollmentRecordId: string }> },
) {
  const { subjectId, enrollmentRecordId } = await props.params
  let body: {
    semester_no?: number
    academic_year?: string
    internal_marks?: number | null
    mid_sem_marks?: number | null
    end_sem_marks?: number | null
    remarks?: string | null
  }
  try {
    body = (await request.json()) as typeof body
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "Invalid request body." },
      },
      { status: 400 },
    )
  }
  if (body.semester_no === undefined || body.academic_year === undefined) {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "semester_no and academic_year are required." },
      },
      { status: 400 },
    )
  }
  const result = await saveSubjectMarks(subjectId, {
    semester_no: body.semester_no,
    academic_year: body.academic_year,
    rows: [
      {
        enrollment_record_id: enrollmentRecordId,
        internal_marks: body.internal_marks ?? null,
        mid_sem_marks: body.mid_sem_marks ?? null,
        end_sem_marks: body.end_sem_marks ?? null,
        remarks: body.remarks ?? null,
      },
    ],
  })
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
