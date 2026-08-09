# KenexAI — Student Module Full Blueprint (KDAC-3)

**Student Academic Success, Subject Performance & Career Readiness Analytics Platform**

> Blueprint only. No code / database changes proposed in this document.

---

## 0. Core Philosophy

> **Don't just tell the student what is happening. Tell them what it means, what they should do, and help them do it.**

| Level | Example |
|---|---|
| ❌ Old ERP | Attendance = 68% |
| 🟡 Analytics Dashboard | Attendance = 68%, below threshold |
| 🟢 **KDAC-3 Student Experience** | Attendance = 68%. You may be at risk for exam eligibility. **5 of your next 6 NLP classes need to be attended to reach the target. Next class: Tomorrow, 2 PM.** `[View Recovery Plan]` |

**Architecture in one line:**
```
UNDERSTAND (dashboards/trends) → IMPROVE (analytics/risk/gaps) → ACT (eligibility/recovery/support)
                                    ↓
                              Student 360
                                    ↓
                          Personal Action Plan
```

### Locked principles
1. Student academic data = **READ ONLY** for the student.
2. Supabase PostgreSQL = source of truth.
3. FastAPI = business logic + authorization.
4. Next.js / BFF = access + screen shaping (no direct browser → DB).
5. No frontend business calculations for authoritative values (attendance %, grades, eligibility, SGPA — always backend-computed).
6. No global CSS changes — existing KenexAI dark design system stays as-is.
7. No duplicate tables if an existing table can serve the purpose.
8. Deterministic logic before ML. ML before GenAI. GenAI never becomes the source of truth.
9. Every prediction must be explainable/auditable (model_version, probability, feature_snapshot).
10. Sensitive lifestyle/wellbeing data gets strict privacy treatment — never auto-exposed to Faculty/Admin/Guardian.
11. Every Student API scopes by **authenticated student identity** (JWT → student_id), never by client-supplied `student_id`.
12. NULL is never treated as 0 (marks, attendance, CT1/CT2, attempt data).

---

## 1. Live Database Schema (17 tables, verified from CSV export)

### Master / Reference
```
departments(dept_code, department_name, department_short_name, degree, total_semesters, status)
subjects(subject_id, subject_code, subject_name, department_code, department_name, semester_no, credits, subject_type, assessment_type, status)
faculty(faculty_id, faculty_code, full_name, gender, department_code, department_name, designation, qualification, specialization, experience_years, email, phone_number, joining_date, employment_type, status)
users(user_id, username, email, password, role, student_id, faculty_id, department, is_active, created_at, preferences)
```

### Student Core
```
students(student_id, enrollment_no, university_roll_no, first_name, last_name, gender, date_of_birth,
         blood_group, category, admission_year, admission_date, admission_type, admission_quota,
         department_code, department_name, current_semester, current_academic_year, domicile_state, city,
         guardian_name, guardian_phone, email, student_phone_number, student_status, created_at, updated_at,
         full_name, latest_sgpa, overall_cgpa, overall_percentage, overall_attendance_percentage,
         total_credits_registered, total_credits_earned, total_backlogs, academic_standing)
```

### Academic Transactional (per subject, per semester)
```
student_subject_enrollment(enrollment_record_id, student_id, enrollment_no, department_code, department_name,
                            semester_no, academic_year, subject_id, subject_code, subject_name, credits,
                            subject_type, faculty_id, enrollment_date, enrollment_status)

student_subject_performance(performance_id, enrollment_record_id, enrollment_no, student_id, subject_id,
                             semester_no, internal_marks, mid_sem_marks, end_sem_marks, total_marks,
                             percentage, grade, grade_point, result_status, attempt_number,
                             performance_category, remarks, ct1_marks, ct2_marks, updated_at, updated_by)

attendance(attendance_id, enrollment_record_id, enrollment_no, student_id, subject_id, semester_no,
           total_classes, attended_classes, attendance_percentage, attendance_status,
           eligibility_status, shortage_flag, remarks)
```

### Granular / Semester-level
```
daily_attendance_07(attendance_id, student_id, enrollment_no, subject_id, subject_name, faculty_id,
                     lecture_date, lecture_number, day_name, department_code, semester_no, academic_year,
                     attendance_status, created_at, updated_at)

student_semester_summary(semester_summary_id, student_id, enrollment_no, semester_no, academic_year,
                          subjects_registered, credits_registered, credits_earned, semester_total_marks,
                          semester_percentage, semester_sgpa, semester_grade, semester_attendance_percentage,
                          backlog_count, semester_result, academic_standing)

weekly_timetable_07(timetable_id, department_code, semester_no, academic_year, day_name, slot_no,
                     start_time, end_time, subject_id, subject_name, faculty_id, lecture_type,
                     created_at, updated_at)
```

### Context Data (data-stitching goldmine)
```
lifestyle_survey(lifestyle_id, student_id, enrollment_no, average_sleep_hours, daily_study_hours,
                  screen_time_hours, physical_activity, stress_level, mental_wellbeing,
                  attendance_commitment, part_time_job, internet_access, preferred_learning_mode, survey_date)

career_preferences(career_preference_id, student_id, enrollment_no, preferred_domain, dream_job_role,
                    preferred_industry, preferred_work_mode, target_package_lpa, higher_studies_interest,
                    entrepreneurship_interest, certification_interest, internship_completed,
                    placement_readiness_level, survey_date)

faculty_student_map(faculty_student_map_id, faculty_id, student_id, enrollment_no, department,
                     mentor_role, allocation_reason, mentor_since, status)
```

### Intelligence Output
```
risk_predictions(risk_prediction_id, student_id, enrollment_no, prediction_status,
                  prediction_timestamp, created_at, updated_at)
```
⚠️ Currently placeholder-shaped — no `model_version`, `probability`, `feature_snapshot`, or `prediction_reason` columns. Must be extended before serving as real auditable ML output.

### Audit Trail
```
attendance_change_log(change_id, lecture_date, slot_no, student_id, subject_id, field_name,
                       old_value, new_value, operation_type, changed_by, changed_at)

performance_change_log(change_id, performance_id, enrollment_record_id, student_id, subject_id,
                        field_name, old_value, new_value, operation_type, changed_by, changed_at)
```

### Notifications (exists, currently empty)
```
student_messages   — 0 rows currently. Inspect exact columns before building Notification Center;
                      reuse if it can represent (student_id, message, type, read/unread, created_at),
                      extend minimally if not. Do not create a parallel notifications table.
```

**Canonical keys:**
- `student_id` — the person/stitching key across almost every table.
- `enrollment_record_id` — the academic-grain key connecting enrollment → performance → attendance (important because of repeat attempts / `attempt_number`).

---

## 2. Table → Join → Feature Map

| Tables | Join Key | Feature | Output |
|---|---|---|---|
| `students` + `student_semester_summary` | `student_id` | Academic overview | SGPA / credits / backlogs |
| `students` + `student_subject_enrollment` | `student_id` | My Subjects | current-term subject list |
| Enrollment + Performance | `enrollment_record_id` | Marks | internal/mid/end/total/%/grade |
| Enrollment + Attendance | `enrollment_record_id` | Attendance | %/eligibility/shortage |
| Student + `daily_attendance_07` | `student_id + subject_id` | Attendance history/calendar | P/A log by date |
| Attendance + `weekly_timetable_07` | subject/semester/year + current_date | Recovery Plan | classes needed / can-miss |
| Performance components (`ct1/ct2/mid/end`) | `enrollment_record_id` | Weak-area detector | assessment trend, gap |
| `student_semester_summary` sequence | `student_id + semester_no` | Performance trend | SGPA over semesters |
| `student_semester_summary` + cohort | department + admission cohort + semester | Cross-cohort trend | batch benchmark |
| Enrollment + Performance + `subjects.credits` | subject | Credit-load vs performance | workload heatmap |
| `career_preferences` + Performance + `subjects` | `student_id`, subject | Career readiness / gap | alignment score |
| `career_preferences` + `subjects.subject_type` | domain/role | Elective advisor | recommended electives + why |
| `risk_predictions` + `students` | `student_id` | Risk badge | status/probability |
| `risk_predictions` + `faculty_student_map` | `student_id` | Mentor early-warning loop | intervention alert |
| `performance_change_log` + Performance | `performance_id` | Marks-updated notification | event |
| `attendance_change_log` + Attendance | student/subject | Attendance-alert notification | event |
| `lifestyle_survey` + `career_preferences` | `student_id` | Lifestyle-performance/career insight | correlation (not causation) |

---

## 3. Live-Update Flow (Faculty → Student)

### Option A — Refetch on demand (baseline, use everywhere)
```
Faculty saves marks/attendance
        ↓
UPDATE canonical table (student_subject_performance / attendance)
        ↓
INSERT into change_log (audit trail)
        ↓
Student dashboard/subject page → fresh API call on load/focus → latest data
```
No websockets needed. "Live" = *immediately correct in DB, fresh on next fetch.* Use React Query/SWR with short TTL, or refetch on `window.onfocus`.

### Option B — True real-time (use selectively, for demo impact)
Supabase Realtime (built into Postgres, no extra infra) on `student_subject_performance` / `attendance`, filtered by `student_id`. Faculty saves → student's screen updates without refresh.

**Recommendation:** Option A everywhere (reliable, simple), Option B on **one showcase flow** (e.g. live marks update) for demo impact. Realtime must never bypass FastAPI/BFF authorization — it's a UI enhancement, not a new access path.

### Notification generation (free, from existing audit tables)
```
performance_change_log / attendance_change_log new row
        ↓
Notification event derived (no new source table needed)
        ↓
student_messages
        ↓
Student Notification Center
```

---

## 4. Complete Feature Catalog

Grouped into **8 student experiences**. Each feature tagged with priority, data source, and whether a new table is required.

### 🏠 4.1 Home / Today
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 1 | Student Academic Command Center (dashboard) | students, semester_summary, enrollment, performance, attendance | No | P0 |
| 2 | Today's Classes | weekly_timetable_07 | No | P0 |
| 3 | Needs Your Attention | attendance + performance thresholds | No | P0 |
| 4 | "What Should I Focus On?" (rule-based top-3 priorities) | attendance + performance + backlog | No | P1 |
| 5 | "What Changed Since Yesterday?" | performance_change_log + attendance_change_log | No | P1 |
| 6 | Today's Student Brief (single compact daily card) | timetable + attendance + performance | No | P1 |
| 7 | Personal Academic Action Plan (checklist) | derived from focus areas | No | P2 |
| 8 | Deadline + Attendance + Exam "Conflict Detector" | timetable + eligibility + assignments | Yes (assignments) | P2 |
| 9 | Student Academic Timeline (all events, one feed) | change logs + notifications | No | P2 |

### 📚 4.2 Academics
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 10 | Subject Overview / My Subjects (ALL subjects, no hardcoding) | enrollment + performance + attendance | No | P0 |
| 11 | Marks display with NULL-safe handling (Not entered / Not calculated) | student_subject_performance | No | P0 |
| 12 | Performance Trend (semester-wise SGPA/%) | student_semester_summary | No | P1 |
| 13 | Component-Level Weak-Area Detector (CT1→CT2→Mid→End trend) | ct1_marks, ct2_marks, mid_sem_marks, end_sem_marks | No | **P0** ⭐ |
| 14 | Cohort/class-average benchmark (privacy-safe aggregate) | GROUP BY subject_id | No | P1 |
| 15 | Learning Gap Detection (declining-assessment pattern, not diagnosis) | performance components | No | P1 |
| 16 | Marks Simulator / What-if (client-side, never persisted) | performance formulas | No | P1 |
| 17 | Repeat-Attempt Support (attempt_number-aware, non-punitive framing) | performance history by attempt_number | No | P1 |
| 18 | Backlog Clearance Roadmap | result_status='Fail' + attempt_number | No | P1 |
| 19 | Academic Health Score (deterministic composite: attendance+performance+consistency+progress) | multiple | No | P1 |
| 20 | Strengths & Weaknesses summary | subject percentage ranking | No | P1 |
| 21 | Personal Academic Goals (target SGPA/%/attendance, student-set) | student input + backend progress calc | Small (goals) | P2 |
| 22 | Personal Improvement Tracker (↑↓ over time, not just current score) | semester_summary sequence | No | P2 |

### 🟢 4.3 Attendance
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 23 | All-subjects Attendance Overview | attendance + enrollment | No | P0 |
| 24 | Exam Eligibility Checker (backend-authoritative, no frontend guessing) | attendance.eligibility_status, shortage_flag | No | **P0** ⭐ |
| 25 | Attendance Calculator (miss/attend-N formula) | attendance.total/attended_classes | No | P0 |
| 26 | Attendance Recovery Plan (date-wise, using upcoming timetable) | attendance + daily_attendance_07 + weekly_timetable_07 | No | **P0** ⭐ |
| 27 | Attendance Calendar (day-by-day P/A grid) | daily_attendance_07 | No | P1 |
| 28 | Attendance Forecast (trend-based projection, not just current %) | daily_attendance_07 pattern | No | P1 |
| 29 | Attendance Streak / Consistency (professional tone, not gamified) | daily_attendance_07 | No | P2 |
| 30 | Attendance Dispute / Discrepancy Report (self-service correction request) | attendance_change_log as audit reference | **Yes** (`attendance_disputes`) | **P0** ⭐ |

### 🎯 4.4 Success / Risk
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 31 | Risk Status Badge (LOW/MODERATE/HIGH/CRITICAL, direct from table) | risk_predictions | No | P0 |
| 32 | "Why am I at risk?" explainable reasons | risk_predictions + rule engine (later SHAP) | Extend risk table | P1 |
| 33 | Early-Warning Loop to Mentor (auto-alert on CRITICAL) | risk_predictions + faculty_student_map | No | P1 |

### 💼 4.5 Career
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 34 | Career Readiness Dashboard (composite score) | career_preferences + performance | No | P1 |
| 35 | Career Gap Analysis (skills held vs needed for dream role) | career_preferences + subject mapping | Maybe (skills config) | P1 |
| 36 | Next-Semester Elective Advisor (career + performance aligned) | career_preferences + subjects + performance | No | **P1** ⭐ |
| 37 | Achievement / Document Vault (certificates, internship proof) | career_preferences.certification_interest | Yes | P2 |
| 38 | Personal Achievement Timeline | manual + derived milestones | Yes | P2 |
| 39 | One-click Resume/LinkedIn-ready Academic Snapshot | career_preferences + academic summary | No | P2 |

### 🧑‍🏫 4.6 Support
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 40 | Ask Faculty / Doubt Box (per-subject Q&A) | student_subject_enrollment.faculty_id | **Yes** (`student_faculty_queries`) | P1 |
| 41 | Grievance Center — Marks Recheck Request (workflow, not direct edit) | performance_change_log as audit reference | **Yes** (`marks_recheck_requests`) | **P0** ⭐ |
| 42 | Advisor / Mentor Connect card | faculty_student_map (mentor_role) | No | P1 |
| 43 | Gentle Wellbeing Check-in (soft nudge, connect-to-human only, no diagnosis) | lifestyle_survey.stress_level/mental_wellbeing | No (careful privacy handling) | P1 |
| 44 | Scholarship / Financial Opportunity Finder ("may qualify", not "eligible") | students.category, admission_quota | No | P2 |

### 📅 4.7 Planning
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 45 | Weekly Timetable + Today's Classes | weekly_timetable_07 | No | P0 |
| 46 | Smart Free-Slot Study Suggestions (gap slot → weakest subject) | timetable + performance + attendance | No | P1 |
| 47 | Assignment & Deadline Tracker | — | **Yes** (`assignments`) | **P0/P1** ⭐ |
| 48 | Student Academic Calendar (exam/deadline dates) | — | Yes (admin-maintained) | P2 |
| 49 | Study Session Mode (client-side focus timer) | none (local state) | No | P2 |
| 50 | Regional Study Buddy (opt-in, anonymized until join) | students.city/domicile_state | Yes (opt-in groups) | P2 |
| 51 | Peer Study Group Matcher (same-weak-subject, anonymous) | performance + opt-in | Yes | P2 |

### ⚙️ 4.8 Student Control (Responsible AI / Inclusive Design)
| # | Feature | Data Source | New Table? | Priority |
|---|---|---|---|---|
| 52 | Consent & Data Privacy Dashboard (download/delete my data, usage toggles) | lifestyle_survey, career_preferences | Yes (`student_data_consents`) | **P1** ⭐ |
| 53 | Student-Controlled Guardian Sharing (opt-in, preview before enable) | students.guardian_name/phone | Yes (consent flags) | P1 |
| 54 | Language & Accessibility Mode (English/Hindi/Gujarati) | i18n only, no schema change | No | P2 |
| 55 | Data Saver / Lightweight Mode (same data, lighter presentation layer) | presentation layer only | No | P2 |
| 56 | Smart Notification Center (only meaningful events, categorized) | change logs + risk + timetable diffs | Reuse `student_messages` | P1 |
| 57 | Emergency Info Card (masked by default, `[Reveal]`, role-gated visibility) | students.blood_group/guardian_* | No | P1 |
| 58 | Digital Student ID + QR (opaque verification token, not raw PII in QR) | students.university_roll_no/enrollment_no | No | P1 |

---

## 5. "Definitely Add" — Highest-Value Cluster

These form one connected loop and are the strongest differentiator vs a normal college ERP:

```
Problem detected (Weak-Area Detector / Eligibility Checker)
        ↓
Student understands problem (Recovery Plan / Learning Gap explanation)
        ↓
System gives exact action (dates, class counts, targets)
        ↓
Student can request help (Grievance Center / Ask Faculty)
        ↓
Faculty/mentor responds (workflow, audited)
        ↓
Student tracks resolution
```

**P0 build order:**
1. Component-Level Weak-Area Detector
2. Exam Eligibility Checker
3. Attendance Recovery Plan
4. Attendance Dispute (Grievance Center)
5. Marks Recheck Request (Grievance Center)
6. Assignment/Deadline Tracker
7. Today's Academic Brief
8. Smart Notifications

> Verify `ct1_marks` / `ct2_marks` / `attempt_number` population in the live DB before building UI around them. If mostly NULL, show "Not entered" — never fabricate values just because the column exists.

---

## 6. Grievance / Workflow Architecture (important — read before building)

Student-initiated corrections **never** write directly to canonical tables.

```
Student Request (attendance_disputes / marks_recheck_requests)
        ↓
Faculty/Admin Review
        ↓
Approved
        ↓
Existing canonical write flow (Faculty Marks/Attendance Entry)
        ↓
performance_change_log / attendance_change_log (audit)
```

`attendance_change_log` and `performance_change_log` are **audit trails**, not workflow tables — they record what happened after a canonical write, they don't hold pending requests. New workflow tables are required:

```
attendance_disputes(dispute_id, student_id, subject_id, attendance_id, lecture_date, reason,
                     student_comment, status, faculty_id, faculty_response, created_at, reviewed_at)

marks_recheck_requests(request_id, student_id, performance_id, subject_id, reason,
                        status, faculty_id, faculty_response, created_at, reviewed_at)

student_faculty_queries(query_id, student_id, faculty_id, subject_id, question, answer,
                         status, created_at, answered_at)
```

---

## 7. ML & GenAI Layer (build only after deterministic core is solid)

### Rule: if deterministic calculation can answer it, don't use ML
Attendance %, classes needed/can-miss, total marks, grade, eligibility, SGPA from existing summary — **all deterministic, server-side, no model needed.**

### ML Model A — At-Risk Prediction
- **Tables:** students + enrollment + performance + attendance + semester_summary (+ optional lifestyle_survey, with governance approval)
- **Join:** student_id + enrollment_record_id + semester_no + academic_year
- **Target:** at_risk_next_period (define precisely from historical outcomes)
- **Models:** Logistic Regression → XGBoost (compare, don't jump to deep learning)
- **Validation:** temporal split (past semesters → train, later semester → test); never randomly split rows from the same student across train/test (leakage)

### ML Model B — Performance Prediction
- **Inputs:** past semester performance + current components + attendance + credits
- **Target:** next semester % or final subject %
- **Models:** ElasticNet baseline → Random Forest / XGBoost, selected by validation metric

### Trend Prediction (two levels)
- **Student-level:** student_id + semester_no + SGPA/%
- **Cohort-level:** department + admission cohort + semester (fulfils "predict trends" from the problem statement)
- Always present forecasts with uncertainty, never as certainty.

### Explainability
XGBoost → SHAP → top contributing factors, translated into plain language for the student. Raw SHAP vectors are never shown directly.

### ML Storage (extend `risk_predictions`)
```
prediction_id, student_id, prediction_type, prediction_status, probability,
model_version, feature_snapshot_id, prediction_timestamp, prediction_horizon, prediction_reason
```
Plus a `model_registry` (or MLflow) for model versioning.

### GenAI — comes after verified analytics/ML
```
Verified DB → Structured analytics → ML outputs → Grounded context object → GenAI → Validated response → Student UI
```
GenAI receives structured numbers (`attendance=68, threshold=75, required_classes=5`), never raw unrestricted DB access.

| GenAI Feature | Needs ML? |
|---|---|
| AI Academic Coach (explain metrics, answer "why") | No |
| Explain risk (with SHAP) | Yes |
| Personalized study plan | No |
| Career-gap explanation | No |
| Academic Q&A | No |
| Faculty/mentor summary | Maybe |

**GenAI must never:** calculate marks/attendance, decide eligibility, invent timetable data, invent career requirements, or override ML output.

---

## 8. Security & Privacy Rules

**Student can read:** own profile, marks, attendance, semester history, timetable, career preferences, risk result, notifications.

**Student cannot read:** other students' data, faculty-only analytics, other students' lifestyle/risk/career data, internal audit beyond approved transparency.

**Student cannot write:** marks, attendance, grades, SGPA/CGPA, semester summary, risk prediction — enforced **server-side**, not just hidden in UI.

**API pattern:**
```
Authenticated User → user.student_id (from JWT) → Student Service → WHERE student_id = authenticated_student_id
```
Never `GET /student?student_id=STU000002` trusting a client-supplied ID.

**Sensitive data (`lifestyle_survey.stress_level`, `mental_wellbeing`) rules:**
- Never auto-exposed to Faculty/Admin/Guardian dashboards.
- Wellbeing check-in language: never diagnostic ("You are depressed" ❌); always a soft nudge toward a real person ("Consider talking to your counselor or mentor" ✅).
- Guardian sharing is opt-in, default OFF, with a preview of exactly what will be shared before enabling.

---

## 9. Frontend / API Notes

**Preserve existing APIs** (`/me/profile`, `/me/academic-summary`, `/me/performance`) — no breaking changes.

**Prefer domain-oriented endpoints over one-endpoint-per-card:**
```
GET /me/dashboard        → identity + summary + today + alerts + attendance + performance
GET /me/attendance        GET /me/attendance/history        GET /me/attendance/recovery
GET /me/timetable
GET /me/notifications     GET /me/notifications/unread-count
GET /me/analytics/health  GET /me/analytics/focus  GET /me/analytics/learning-gaps
GET /me/career
GET /me/risk
```

**Reuse existing shared components** before creating new ones: `StatCard`, `ChartCard`, `SubjectCard`, `FreshnessBadge`, `LoadingSkeleton`, `EmptyState`, `ErrorState`, `TrendChart`, `BarChart`, `GradeBadge`, `DataTable`, `AvatarInitials`.

**Caching:** short TTL by default; bypass/revalidate after a known faculty update or manual refresh. Critical values (eligibility, attendance, marks) must always show a **freshness indicator** rather than presenting stale data as current — this matters especially because `student_semester_summary` is ETL-derived and can lag behind live subject-level updates.

---

## 10. Implementation Phases (locked order)

```
PHASE 0  Verification — inspect existing APIs/schema/BFF/components before writing any code
PHASE 1  Student Data Foundation — profile, all subjects, marks, attendance, timetable, freshness/error/empty states
PHASE 2  Attendance Intelligence — eligibility, calculator, recovery plan, calendar
PHASE 3  Academic Analytics — health score, focus areas, needs-attention, learning gaps, trends, what-if
PHASE 4  Notifications — student_messages integration, unread count, event generation
PHASE 5  Career Intelligence — readiness, gap analysis, elective advisor
PHASE 6  ML Foundation — ETL/data quality → feature dataset → baseline model → evaluation → registry
PHASE 7  ML UI — risk, probability, explanation, trend prediction (only after verified predictions)
PHASE 8  GenAI — Academic Coach, personalized plans, career explanation (grounded on verified context only)
```

Each phase acceptance criteria include: student sees only own data, no academic write endpoint for students, NULL handled correctly (never shown as 0), loading/error/empty states present, mobile responsive, typecheck/lint/build passing.

---

## 11. Edge Cases Checklist

**Marks:** End-sem NULL, CT1/CT2 NULL, partial marks, multiple attempts, no performance row yet.
**Attendance:** zero classes, no daily records, exactly at 75%, recovery mathematically impossible, no future timetable sessions to recover with, duplicate daily records.
**Semester:** current semester has no summary yet, summary stale vs latest subject data, student changed department.
**Career:** no career_preferences row, missing dream role, incomplete survey.
**Notifications:** duplicate events, stale notification, deactivated student.
**ML:** insufficient historical data (~80 students is small — do not overclaim), class imbalance, missing features, data leakage, stale prediction.
**GenAI:** unsupported question, missing grounding data, hallucination risk, stale context.

---

## 12. Priority Snapshot

| Priority | Features |
|---|---|
| 🔴 P0 | Component-Level Weak Area Detector · Exam Eligibility Checker · Attendance Recovery Plan · Attendance Dispute · Marks Recheck Request · Assignment/Deadline Tracker · Today's Academic Brief · Student Notifications · All-Subjects Attendance/Marks/Timetable (foundation) |
| 🟠 P1 | Repeat-Attempt Support · Elective Advisor · Digital ID+QR · Emergency Info Card · Backlog Roadmap · Free-Slot Suggestions · Academic Timeline · Career Readiness/Gap · Ask Faculty · Mentor Connect · Consent Dashboard · Guardian Sharing · Wellbeing Check-in |
| 🟡 P2 | Regional Study Buddy · Study Session Mode · Achievement Timeline/Vault · Scholarship Finder · Language/Data-Saver modes · Advanced ML · GenAI Coach |

---

*This document consolidates all Student Module discussions to date: live schema, join maps, live-update flow, 58 catalogued features across 8 experiences, grievance workflow architecture, ML/GenAI dependency rules, and security/privacy requirements. Treat as the architecture baseline — implement in isolated slices, one component/API at a time, per the phase order above.*
