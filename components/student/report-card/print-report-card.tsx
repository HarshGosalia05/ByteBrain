import type { ReportCardResponse } from "@/lib/student-api"
import { buildPrintReport } from "@/lib/student/print-report-card"

import "./print-report-card.css"

export function PrintReportCard({ data }: { data: ReportCardResponse }) {
  const report = buildPrintReport(data)

  const headerFields: Array<[string, string]> = [
    ["Student Name", report.name],
    ["Department", report.department],
    ["Enrollment No.", report.enrollmentNo],
    ["Admission Year", report.admissionYear],
    ["Current Semester", report.currentSemester],
    ["Academic Year", report.academicYear],
    ["Generated On", report.generatedAt],
    ["Academic Standing", report.standing],
  ]

  return (
    <div className="print-report-card">
      <article className="prc-document">
        <header className="prc-header">
          <div className="prc-title-row">
            <span className="prc-brand">KENEXAI</span>
            <span className="prc-document-title">Academic Report Card</span>
          </div>
          <dl className="prc-student-grid">
            {headerFields.map(([label, value]) => (
              <div className="prc-student-field" key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </header>

        <section className="prc-summary">
          <h2>Summary</h2>
          <dl className="prc-summary-grid">
            {report.summary.map((item) => (
              <div className="prc-summary-field" key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        {report.semesters.map((sem) => (
          <section className="prc-semester" key={sem.semester}>
            <div className="prc-semester-head">
              <div className="prc-semester-title">
                <h2>Semester {sem.semester}</h2>
                {sem.academicYear ? (
                  <span className="prc-semester-year">{sem.academicYear}</span>
                ) : null}
              </div>
              <dl className="prc-semester-meta">
                {sem.meta.map((item) => (
                  <div className="prc-semester-field" key={item.label}>
                    <dt>{item.label}</dt>
                    <dd>{item.value}</dd>
                  </div>
                ))}
              </dl>
            </div>

            {sem.rows.length === 0 ? (
              <p className="prc-empty">No subject records for this semester.</p>
            ) : (
              <table className="prc-table">
                <colgroup>
                  <col className="prc-col-subject" />
                  <col className="prc-col-credits" />
                  <col className="prc-col-marks" />
                  <col className="prc-col-marks" />
                  <col className="prc-col-marks" />
                  <col className="prc-col-marks" />
                  <col className="prc-col-percent" />
                  <col className="prc-col-grade" />
                  <col className="prc-col-result" />
                  <col className="prc-col-attendance" />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">Subject</th>
                    <th scope="col">Credits</th>
                    <th scope="col">Internal</th>
                    <th scope="col">Mid-Sem</th>
                    <th scope="col">End-Sem</th>
                    <th scope="col">Total</th>
                    <th scope="col">%</th>
                    <th scope="col">Grade</th>
                    <th scope="col">Result</th>
                    <th scope="col">Attendance</th>
                  </tr>
                </thead>
                <tbody>
                  {sem.rows.map((row) => (
                    <tr key={row.code}>
                      <td className="prc-subject-cell">
                        <span className="prc-subject-name">{row.subject}</span>
                        <span className="prc-subject-code">{row.code}</span>
                      </td>
                      <td className="prc-num">{row.credits}</td>
                      <td className="prc-num">{row.internal}</td>
                      <td className="prc-num">{row.midSem}</td>
                      <td className="prc-num">{row.endSem}</td>
                      <td className="prc-num">{row.total}</td>
                      <td className="prc-num">{row.percentage}</td>
                      <td className="prc-grade">{row.grade}</td>
                      <td className="prc-result">{row.result}</td>
                      <td className="prc-num">{row.attendance}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        ))}
      </article>
    </div>
  )
}
