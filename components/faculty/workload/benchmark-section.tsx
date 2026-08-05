import { getFacultyWorkloadBenchmark, type WorkloadSummaryParams } from "@/lib/faculty-api"
import { toSectionResult } from "@/lib/section-result"

import { BenchmarkView } from "./benchmark-view"

export async function BenchmarkSection({ filters }: { filters: WorkloadSummaryParams }) {
  const result = await getFacultyWorkloadBenchmark(filters)
  return <BenchmarkView data={toSectionResult(result)} />
}
