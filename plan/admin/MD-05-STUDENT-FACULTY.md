TASK: Implement MD-05 — Admin Student and Faculty Overview.

PRECONDITION
MD-01 through MD-04 complete.

OBJECTIVE
Give Admin read-only institution-level visibility into students and faculty without duplicating Student or Faculty modules.

PART A — STUDENTS

Route:
 /admin/students

READ ONLY.

Table:
Student
Enrollment No
Department
Semester
SGPA
CGPA
Percentage
Attendance
Backlogs
Risk
Academic Standing

SEARCH:
- Name
- Enrollment
- Email

FILTERS:
- Department
- Semester
- Academic Year
- Risk

SORT:
- SGPA
- Percentage
- Attendance
- Backlogs
- Risk

Do not create student editing/deletion.

Do not recreate Student Profile page.

Optional:
clicking a student may open a compact read-only academic snapshot using existing Student data, but do not duplicate the complete Student Module.

PART B — FACULTY

Route:
 /admin/faculty

KPIs:
- Total Faculty
- Active Faculty if actual status exists
- Department count

Charts:
- Faculty by Department
- Faculty by Designation

Table:
Faculty
Department
Designation
Subject count
Student count
Workload if existing workload analytics is available

Reuse existing Faculty workload/subject allocation data.

Do not create:
- Faculty CRUD
- Faculty settings
- Faculty profile editor

SECURITY:
Admin-only.

TEST:
- student search
- filters
- sorting
- faculty aggregation
- authorization
- empty states
- pagination if needed

DO NOT implement Career/Lifestyle/Institution Health/Notifications/ML.