"use client"

import * as React from "react"
import { Check, Pencil, Plus, Target, Trash2, X } from "lucide-react"

import type { GoalsResponse, StudentGoal, BffResult } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectList,
  SelectIcon,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const GOAL_OPTIONS = [
  { value: "target_sgpa", label: "SGPA", max: 10, step: 0.1, suffix: "" },
  { value: "target_percentage", label: "Overall percentage", max: 100, step: 0.5, suffix: "%" },
  { value: "target_attendance", label: "Attendance", max: 100, step: 1, suffix: "%" },
] as const

const statusBadge = {
  Active: "success",
  Inactive: "muted",
} as const

function goalLabel(goalType: string): string {
  return GOAL_OPTIONS.find((option) => option.value === goalType)?.label ?? goalType
}

function goalSuffix(goalType: string): string {
  return GOAL_OPTIONS.find((option) => option.value === goalType)?.suffix ?? ""
}

function GoalProgress({ goal }: { goal: StudentGoal }) {
  if (goal.current_value === null || goal.target_value <= 0) {
    return null
  }
  const ratio = Math.max(0, Math.min(1, goal.current_value / goal.target_value))
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${ratio * 100}%` }}
          aria-hidden="true"
        />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {goal.current_value.toFixed(1)}
        {goalSuffix(goal.goal_type)} / {goal.target_value.toFixed(1)}
        {goalSuffix(goal.goal_type)}
      </span>
    </div>
  )
}

export function GoalsCard({ initial }: { initial: GoalsResponse }) {
  const [goals, setGoals] = React.useState<StudentGoal[]>(initial.goals)
  const [goalType, setGoalType] = React.useState<string | null>("target_sgpa")
  const [targetValue, setTargetValue] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [editingGoalId, setEditingGoalId] = React.useState<string | null>(null)
  const [editValue, setEditValue] = React.useState("")

  async function refresh() {
    const res = await fetch("/api/student/goals", { cache: "no-store" })
    const result = (await res.json()) as BffResult<GoalsResponse>
    if (result.ok) {
      setGoals(result.data.goals)
    }
  }

  async function addGoal(event: React.FormEvent) {
    event.preventDefault()
    const value = Number(targetValue)
    if (!goalType || !Number.isFinite(value) || value <= 0) {
      setError("Enter a positive target value.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await fetch("/api/student/goals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal_type: goalType, target_value: value }),
      })
      const result = (await res.json()) as BffResult<StudentGoal>
      if (result.ok) {
        setGoals((current) => [...current, result.data])
        setTargetValue("")
      } else {
        setError(result.error.message)
      }
    } catch {
      setError("Could not reach the server. Try again.")
    } finally {
      setBusy(false)
    }
  }

  async function toggleStatus(goal: StudentGoal) {
    const next = goal.status === "Active" ? "Inactive" : "Active"
    setGoals((current) =>
      current.map((item) => (item.goal_id === goal.goal_id ? { ...item, status: next } : item)),
    )
    try {
      const res = await fetch(`/api/student/goals/${goal.goal_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
      })
      const result = (await res.json()) as BffResult<StudentGoal>
      if (result.ok) {
        setGoals((current) =>
          current.map((item) => (item.goal_id === result.data.goal_id ? result.data : item)),
        )
      } else {
        await refresh()
        setError(result.error.message)
      }
    } catch {
      await refresh()
      setError("Could not reach the server. Try again.")
    }
  }

  function startEdit(goal: StudentGoal) {
    setEditingGoalId(goal.goal_id)
    setEditValue(String(goal.target_value))
  }

  function cancelEdit() {
    setEditingGoalId(null)
    setEditValue("")
  }

  async function deleteGoal(goal: StudentGoal) {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/student/goals/${goal.goal_id}`, {
        method: "DELETE",
      })
      const result = (await res.json()) as BffResult<void>
      if (result.ok) {
        setGoals((current) => current.filter((item) => item.goal_id !== goal.goal_id))
      } else {
        await refresh()
        setError(result.error.message)
      }
    } catch {
      await refresh()
      setError("Could not reach the server. Try again.")
    } finally {
      setBusy(false)
    }
  }

  async function saveEdit(goal: StudentGoal) {
    const value = Number(editValue)
    if (!Number.isFinite(value) || value <= 0) {
      setError("Enter a positive target value.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/student/goals/${goal.goal_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_value: value }),
      })
      const result = (await res.json()) as BffResult<StudentGoal>
      if (result.ok) {
        setGoals((current) =>
          current.map((item) => (item.goal_id === result.data.goal_id ? result.data : item)),
        )
        setEditingGoalId(null)
        setEditValue("")
      } else {
        setError(result.error.message)
      }
    } catch {
      setError("Could not reach the server. Try again.")
    } finally {
      setBusy(false)
    }
  }

  // Show only the latest goal per goal type (most recently created)
  const displayGoals = React.useMemo(() => {
    const latestByType = new Map<string, StudentGoal>()
    for (const goal of goals) {
      const existing = latestByType.get(goal.goal_type)
      if (!existing || new Date(goal.created_at) > new Date(existing.created_at)) {
        latestByType.set(goal.goal_type, goal)
      }
    }
    return Array.from(latestByType.values())
  }, [goals])

  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Target className="size-4 text-primary" />
            Personal goals
          </h2>
          <p className="text-xs text-muted-foreground">
            Targets you set for yourself. They never change academic records.
          </p>
        </div>
      </div>

      {displayGoals.length > 0 && (
        <ul className="mt-4 flex flex-col gap-3">
          {displayGoals.map((goal) => (
            <li key={goal.goal_id} className="flex flex-col gap-2 rounded-lg bg-muted/40 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{goalLabel(goal.goal_type)}</p>
                  {goal.achieved === true && (
                    <Badge variant="success">
                      <Check className="size-3" />
                      Achieved
                    </Badge>
                  )}
                </div>
                <Badge variant={statusBadge[goal.status as keyof typeof statusBadge] ?? "muted"}>
                  {goal.status}
                </Badge>
              </div>
              {editingGoalId === goal.goal_id ? (
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={0}
                    max={GOAL_OPTIONS.find((option) => option.value === goal.goal_type)?.max}
                    step={GOAL_OPTIONS.find((option) => option.value === goal.goal_type)?.step}
                    inputMode="decimal"
                    value={editValue}
                    onChange={(event) => setEditValue(event.target.value)}
                    className="h-8 w-24 text-xs"
                    autoFocus
                  />
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => saveEdit(goal)}
                    disabled={busy}
                  >
                    Save
                  </Button>
                  <Button variant="ghost" size="xs" onClick={cancelEdit}>
                    <X className="size-3" />
                  </Button>
                </div>
              ) : (
                <GoalProgress goal={goal} />
              )}
              <div className="flex items-center gap-2">
                <Button variant="outline" size="xs" onClick={() => toggleStatus(goal)}>
                  {goal.status === "Active" ? "Pause goal" : "Activate goal"}
                </Button>
                {editingGoalId !== goal.goal_id && (
                  <Button variant="ghost" size="xs" onClick={() => startEdit(goal)}>
                    <Pencil className="size-3" />
                    Edit goal
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="xs"
                  className="text-destructive hover:text-destructive"
                  onClick={() => deleteGoal(goal)}
                  disabled={busy}
                >
                  <Trash2 className="size-3" />
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={addGoal} className="mt-4 flex flex-col gap-2 border-t border-border/60 pt-4">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="goal-type" className="text-xs font-medium text-muted-foreground">
              Goal type
            </label>
            <Select value={goalType} onValueChange={setGoalType}>
              <SelectTrigger id="goal-type" className="w-full">
                <SelectValue>
                  {(selected: string | null) =>
                    GOAL_OPTIONS.find((option) => option.value === selected)?.label ??
                    "Select goal type"
                  }
                </SelectValue>
                <SelectIcon />
              </SelectTrigger>
              <SelectContent>
                <SelectList>
                  {GOAL_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectList>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="goal-target" className="text-xs font-medium text-muted-foreground">
              Target value
            </label>
            <Input
              id="goal-target"
              type="number"
              min={0}
              max={GOAL_OPTIONS.find((option) => option.value === goalType)?.max}
              step={GOAL_OPTIONS.find((option) => option.value === goalType)?.step}
              inputMode="decimal"
              placeholder="e.g. 75"
              value={targetValue}
              onChange={(event) => setTargetValue(event.target.value)}
            />
          </div>
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button type="submit" size="sm" className="w-fit" disabled={busy}>
          <Plus className="size-3" />
          {busy ? "Adding…" : "Add goal"}
        </Button>
      </form>
    </div>
  )
}
