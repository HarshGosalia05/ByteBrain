import { AlertTriangle, TrendingUp } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { MlExplanationFactor } from "@/lib/student-api"

const sourceLabels: Record<MlExplanationFactor["source"], string> = {
  input: "Input",
  business_rule: "Rule",
  model_metadata: "Model",
}

export function FactorList({ factors }: { factors: MlExplanationFactor[] }) {
  if (factors.length === 0) return null
  return (
    <ul className="flex flex-col gap-2" aria-label="Reasons">
      {factors.map((factor, index) => {
        const positive = factor.kind === "positive"
        const Icon = positive ? TrendingUp : AlertTriangle
        return (
          <li key={index} className="flex items-start gap-2 text-sm">
            <Icon
              className={`mt-0.5 size-4 shrink-0 ${positive ? "text-chart-2" : "text-chart-3"}`}
              aria-hidden="true"
            />
            <span className="min-w-0 flex-1">{factor.detail}</span>
            <Badge variant={positive ? "success" : "warning"}>{sourceLabels[factor.source]}</Badge>
          </li>
        )
      })}
    </ul>
  )
}
