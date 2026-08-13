"use server"

import {
  getPredictionFeedback,
  getStudentPredictionFeedbackContext,
  submitPredictionFeedback,
  type BffResult,
  type FacultyFeedbackAction,
  type FacultyFeedbackItem,
  type FacultyPredictionFeedbackDetail,
  type FacultyStudentFeedbackContext,
} from "@/lib/faculty-api"

export async function fetchPredictionFeedbackContextAction(
  studentId: string
): Promise<BffResult<FacultyStudentFeedbackContext>> {
  return getStudentPredictionFeedbackContext(studentId)
}

export async function fetchPredictionFeedbackAction(
  predictionId: string
): Promise<BffResult<FacultyPredictionFeedbackDetail>> {
  return getPredictionFeedback(predictionId)
}

export async function submitPredictionFeedbackAction(
  predictionId: string,
  payload: { action: FacultyFeedbackAction; note?: string | null },
  studentId: string
): Promise<BffResult<FacultyFeedbackItem>> {
  return submitPredictionFeedback(predictionId, payload, studentId)
}
