import pg from "pg"

const pool = new pg.Pool({
  host: "aws-1-ap-south-1.pooler.supabase.com",
  port: 5432,
  database: "postgres",
  user: "postgres.rtaqkxqdejelxsamnesm",
  password: "KenexAI@*195",
  ssl: { rejectUnauthorized: false },
  connectionTimeoutMillis: 15000,
})

const sid = "STU000001"

// 1. Profile (as repository does)
const profile = await pool.query(
  "SELECT student_id, first_name, last_name, enrollment_no, admission_year, current_semester, department_name, department_code, current_academic_year, latest_sgpa, overall_cgpa, overall_percentage, total_credits_registered, total_credits_earned, total_backlogs, academic_standing FROM students WHERE student_id = $1",
  [sid],
)
console.log("PROFILE:", JSON.stringify(profile.rows[0], null, 1))

// 2. Semester summaries (as repository does)
const summaries = await pool.query(
  "SELECT semester_no AS semester, semester_sgpa AS sgpa, credits_earned AS total_credits_earned, semester_attendance_percentage AS attendance_percentage, backlog_count AS active_backlogs, academic_year, subjects_registered, credits_registered, semester_percentage, semester_grade, semester_result, academic_standing FROM student_semester_summary WHERE student_id = $1 ORDER BY semester_no ASC",
  [sid],
)
console.log("SUMMARIES count:", summaries.rows.length)
console.log("SUMMARIES:", JSON.stringify(summaries.rows, null, 1))

// 3. Subject performance (no semester) as repository does
const perf = await pool.query(
  `SELECT
     sse.semester_no AS semester, sse.subject_id, sse.subject_code, sse.subject_name,
     sse.credits, sse.academic_year,
     sp.internal_marks, sp.mid_sem_marks, sp.end_sem_marks, sp.total_marks,
     sp.percentage, sp.grade, sp.grade_point, sp.result_status, sp.attempt_number,
     sp.performance_category, sp.remarks, sp.updated_at,
     a.attendance_percentage
   FROM student_subject_enrollment sse
   LEFT JOIN subjects subj ON subj.subject_id = sse.subject_id
   LEFT JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
   LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
   WHERE sse.student_id = $1
     AND (sp.student_id = $1 OR sp.student_id IS NULL)
     AND (a.student_id = $1 OR a.student_id IS NULL)
   ORDER BY sse.semester_no ASC, sse.subject_name ASC`,
  [sid],
)
console.log("PERFORMANCE count:", perf.rows.length)
console.log("PERFORMANCE semesters:", JSON.stringify(perf.rows.map((r) => r.semester)))
console.log(
  "S7 rows:",
  JSON.stringify(
    perf.rows
      .filter((r) => r.semester === 7)
      .map((r) => ({
        code: r.subject_code,
        internal: r.internal_marks,
        mid: r.mid_sem_marks,
        end: r.end_sem_marks,
        total: r.total_marks,
        pct: r.percentage,
        result: r.result_status,
      })),
    null,
    1,
  ),
)

await pool.end()
