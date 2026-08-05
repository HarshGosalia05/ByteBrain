# Faculty Module — Settings (Enterprise Faculty Workspace & Preferences Center) Module Plan

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Faculty → Settings

**Architecture:** Reuse-first (shared Preference Engine, existing authentication layer, shared analytics layer)

**Depends On:** Faculty Module V1 (`07_faculty_module_v1_plan.md`), Faculty Profile (`app/faculty/profile`), Performance / Attendance / Teaching Analytics slices (`10`, `11`, `12`)

## 0. Position in the Project

This document expands `07_faculty_module_v1_plan.md` §2.8 (Settings) into an enterprise build-level specification, following the documentation quality and structure established by `10_faculty_performance_analytics_module_plan.md`, `11_faculty_attendance_analytics_module_plan.md`, and `12_faculty_teaching_workload_module_plan.md`. It does not change files 00–06, any faculty slice, or any implementation.

Settings is **not a normal Settings page**. It is designed as the **Enterprise Faculty Workspace & Preferences Center**: a single, versioned, auditable configuration surface that gives faculty complete control over their personal workspace, dashboard, analytics, notifications, export, accessibility, and security preferences. It is simultaneously the first consumer of a **shared Preference Engine** that later serves HOD, Admin, TPO, and Student — with no architecture change, only role-scoped namespaces and defaults.

**Scope discipline:** this module is configuration and preference management, not analytics. Where it surfaces analytical thresholds (Phase 4), it reads them through the **Threshold Engine** and allows override only within **Admin-defined bounds**. Every confirmation message is a rule-based Performance Highlight. No AI, no ML, no prediction, no GenAI narrative.

**Storage decision (locked):** preferences are persisted in a single JSONB `preferences` column on the existing `users` table — a column addition, not a new table. No new database tables are created. Password management uses the existing authentication layer and never recommends plaintext storage.

This module replaces the current placeholder at `app/faculty/settings/page.tsx` (file 07 §2.8 is currently unimplemented).

---

## 1. Canonical Terminology Compliance

Settings follows the master glossary in `plan/00_project_scope_and_principles.md` exactly.

| Rule | Application in this module |
|---|---|
| **Performance Highlights** (not "Insights") | Every rule-based observation or confirmation rendered in this module ("Workspace configured successfully", "Accessibility improved") is a Performance Highlight. The standalone word "Insights" is never used for descriptive output. |
| **Threshold Engine** | Single source of truth for every threshold surfaced in Analytics Preferences; faculty overrides are validated against Admin-defined bounds from the same configuration layer. |
| **Rule-Based Insight Engine** | The deterministic template engine that converts preference state into the Workspace Readiness Score, Recommended Actions, and confirmation highlights. No AI / ML / LLM / prediction. |
| **GenAI Insights** | Reserved exclusively for the future GenAI module. Never refers to rule-based output. |
| **At Risk / Risk language** | Reserved exclusively for future ML modules. Never appears in this module. |
| **Prediction language** | Reserved exclusively for future ML modules. Never appears in this module. |
| **Password storage** | Architecture-neutral only. Password management "uses the existing authentication layer" and "follows the project's authentication architecture"; the document never recommends or implies plaintext storage. |

---

## 2. Module Purpose

A single, self-service configuration surface that answers:

- What is my workspace, and how do I make it mine — layout, density, widgets, filters, page size?
- What should I see first, on every page — default landing page, default term scope, default comparison mode, favourite charts?
- What analytical baselines do I compare against — and can I override them within safe, Admin-defined limits?
- What should I be told, and when — rule-based alerts, quiet hours, digest cadence?
- How should my exports look — format, delimiters, encoding, timezone, filename patterns, templates?
- How accessible is my workspace to me — contrast, fonts, motion, focus, presets?
- Is my account secure — password, current session, and an activity log?

Every answer is a preference persisted in the shared Preference Engine, reusable by Faculty, HOD, Admin, TPO, and Student without duplicating architecture.

---

## 3. Verified Configuration Model (Storage Strategy)

### 3.1 The users table and the JSONB preferences column

The `users` table is the identity anchor for every role (Student, Faculty, Admin) and already carries the role link (`student_id`, `faculty_id`, `department`). Preferences are stored in **one JSONB `preferences` column added to `users`**. This is a single, role-agnostic store — the same column serves Faculty, HOD, Admin, TPO, and Student namespaces, so the Preference Engine has one read/write path for the whole product.

```
users
├─ user_id            (PK)
├─ username / email
├─ password           (managed by the existing authentication layer)
├─ role               (Student | Faculty | Admin)
├─ student_id / faculty_id / department
├─ is_active
├─ created_at
└─ preferences        (JSONB, NEW — single source of preference truth)
     ├─ workspace
     ├─ dashboard
     ├─ analytics
     ├─ notifications
     ├─ export
     ├─ accessibility
     ├─ personalization
     ├─ security
     ├─ activity          (lightweight, capped)
     ├─ versions          (configuration metadata)
     └─ audit             (preference audit trail)
```

### 3.2 Profile-extension fields

Fields the Profile slice does not currently store — `bio`, `office_hours`, `alternate_email`, `profile_picture` — live under the `profile_extra` key of the same JSONB column. No new `faculty` columns are required for V1. The existing `email` and `phone_number` remain governed by the existing `PATCH /api/faculty/profile` endpoint; `profile_extra` is written through the Settings profile section.

### 3.3 Activity history (architecture-neutral, scalable)

- **Current implementation** may persist lightweight activity history (recent sign-ins, preference changes, export runs) inside the `preferences.activity` namespace, capped to a bounded window.
- **Future enterprise versions** may migrate activity history to a dedicated audit table without changing the Settings architecture — the Settings engine only ever reads/writes a typed activity API, never a storage shape. This keeps the architecture scalable and leaves the migration path open.

### 3.4 Configuration metadata (workspace versioning)

Every preference write increments configuration metadata (see §18): `preferenceVersion`, `configurationVersion`, `lastModified`, `lastSynced`, `schemaVersion`, and `restorePoint`. This makes the workspace restorable and auditable.

---

## 4. Reuse Architecture

### 4.1 Architecture diagram

```
SettingsPage (server)                       app/faculty/settings/page.tsx
  └─ requireRole("Faculty") → parse searchParams → section tab
  └─ getFacultySettings (BFF, bearer token, TTL cache)
       └─ Settings Engine (shared Preference Engine)
            ├─ typed preference namespaces (§3)
            ├─ validation + Admin-defined bounds (Threshold Engine)
            ├─ versioning + audit (§18)
            └─ readiness + highlights (Rule-Based Insight Engine)
                 └─ Repository → asyncpg → users.preferences (JSONB)
Client forms (PATCH) → app/api/faculty/settings/* (BFF) → same Settings Engine
Dashboard page → DashboardView → shared widget registry (renders saved dashboard prefs)
Theme/Accessibility → next-themes + CSS variables (existing mechanism)
Profile section → reuses existing app/faculty/profile + ContactForm
```

### 4.2 Reuse vs. new

| Layer | Reused | New in this module |
|---|---|---|
| Authentication | Existing session + auth architecture; `requireRole`; cookie session | Password change flows through the existing authentication layer; no parallel auth mechanism |
| Profile | Existing `app/faculty/profile` page, `ContactForm`, `PATCH /api/faculty/profile` | Profile-extension fields (`bio`, `office_hours`, `alternate_email`, `profile_picture`) via Settings profile section |
| Dashboard | Existing `DashboardView` sections become **shared widgets** in a widget registry | Dashboard widget registry refactor (renders per saved prefs) |
| Thresholds | Threshold Engine config in `backend/app/core/config.py` | Analytics overrides validated within Admin-defined bounds |
| Export | Existing Export Layer (CSV + print-to-PDF, `lib/csv.ts`) | Export preferences applied at generation time |
| Theme / Accessibility | `next-themes`, CSS variables (`var(--chart-*`, `--destructive`, `--muted`) | Accessibility presets and dependency-aware application (§16) |
| Forms / UI | `components/ui/*` (`Button`, `Input`, `Label`, `Field`, `Badge`, `Card`, `Table`, `Tabs`, `Separator`, `Skeleton`) | Shared UI primitives built once: `Select`, `Switch`, `Textarea`, `Dialog`, `RadioGroup`, `PreferenceSection`, `WorkspaceReadinessCard` |
| Notifications | Rule-Based Insight Engine templates | Notification rule builder, quiet hours, digest engine |
| Loading / Empty / Error | `LoadingSkeleton`, `SectionSuspense`, `EmptyState`, `ErrorState` | Same components, no duplication |
| Freshness | `FreshnessBadge` | Shown for persisted preferences (`lastModified`) |

### 4.3 Component hierarchy

```
SettingsPage (server)                              app/faculty/settings/page.tsx
└─ SettingsView (client shell, Tabs)               components/faculty/settings/settings-view.tsx
    ├─ ProfileSection                              components/faculty/settings/profile-section.tsx
    ├─ WorkspaceSection                            components/faculty/settings/workspace-section.tsx
    │    └─ WorkspaceManagement (backup/restore)   components/faculty/settings/workspace-management.tsx
    ├─ DashboardSection                            components/faculty/settings/dashboard-section.tsx
    ├─ AnalyticsSection                            components/faculty/settings/analytics-section.tsx
    ├─ NotificationsSection                        components/faculty/settings/notifications-section.tsx
    ├─ ExportSection                               components/faculty/settings/export-section.tsx
    ├─ AccessibilitySection                        components/faculty/settings/accessibility-section.tsx
    ├─ SecuritySection                             components/faculty/settings/security-section.tsx
    ├─ PersonalizationSection                      components/faculty/settings/personalization-section.tsx
    ├─ ReadinessCard                               components/faculty/settings/readiness-card.tsx (shared)
    └─ ResetDialog (enterprise reset scopes)       components/faculty/settings/reset-dialog.tsx
Shared widget registry                            components/shared/widgets/ (dashboard refactor)
Shared Preference Engine                          lib/settings-engine.ts (BFF-side) + backend service
```

### 4.4 Analytics Reuse Matrix (extension point)

| Asset | Settings (Faculty) | HOD | Admin | TPO | Student |
|---|---|---|---|---|---|
| Preference Engine (shared) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Threshold Engine (bounds) | ✅ | ✅ | ✅ | ✅ | — |
| Rule-Based Insight Engine (readiness/highlights) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Profile reuse | ✅ | ✅ | ✅ | — | ✅ |
| Widget registry (dashboard) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Export preferences + Layer | ✅ | ✅ | ✅ | ✅ | ✅ |
| Accessibility presets | ✅ | ✅ | ✅ | ✅ | ✅ |
| Notification rules + digest | ✅ | ✅ | ✅ | ✅ | — |
| Workspace backup / restore / versioning | ✅ | ✅ | ✅ | ✅ | — |
| Loading / Empty / Error | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 5. Phase 0 — Configuration Readiness

Backend-first persistence before any UI (file 10 §13.1 discipline).

- **Configuration validation** — every preference write is validated against its schema (`schemaVersion`); unknown keys are rejected, type-mismatched values are rejected with a mapped error, bounded values are clamped to Admin-defined limits.
- **Preference storage strategy** — single JSONB `preferences` column on `users` (§3.1); one typed write API per namespace; storage shape is an implementation detail of the Preference Engine, never a UI concern.
- **Feature flags** — each namespace can be feature-flagged (e.g. notification digest toggled by flag); flagged-off sections render the shared EmptyState with a why-reason instead of being built into the UI.
- **Version compatibility** — persisted `schemaVersion` is checked on read; a version mismatch triggers a rule-based migration/notice rather than a parse error.
- **Shared configuration layer** — the Preference Engine is the single read/write path for all roles; Admin-defined bounds for analytical thresholds come from the same configuration layer as the Threshold Engine.
- **Data freshness** — persisted preferences surface `lastModified` via the existing `FreshnessBadge`; the Settings page shows when the workspace was last changed and last synced.
- **Preference defaults** — every preference has a documented default (see Preference Matrix §23.2); defaults are role-namespaced so HOD/Admin/TPO inherit sensible baselines.
- **Role validation** — the BFF resolves the role from the session (`requireRole("Faculty")`); the backend resolves `users.user_id` from the token and reads/writes only that row's preferences. No role can read another role's or user's preferences.
- **Later reuse** — this readiness layer (validation, versioning, bounds, defaults, role scoping) is exactly what HOD, Admin, TPO, and Student settings consume later: they add namespaces and defaults, not new storage or validation logic.

---

## 6. Phase 1 — Profile Settings

**Reuses the existing Faculty Profile module — no duplication.** The Profile page remains the canonical identity view; Settings links to it and adds only the profile-extension fields.

### 6.1 Editable (through Settings profile section)

| Field | Persistence | Validation |
|---|---|---|
| Mobile Number | `faculty.phone_number` via existing `PATCH /api/faculty/profile` | Numeric, existing rules |
| Alternate Email | `preferences.profile_extra.alternate_email` | Email format |
| Office Hours | `preferences.profile_extra.office_hours` | Free text / structured schedule |
| Faculty Bio | `preferences.profile_extra.bio` | Length-capped |
| Profile Picture | `preferences.profile_extra.profile_picture` | URL reference / uploaded asset |

### 6.2 Read-only (managed by administration)

Faculty ID, Faculty Code, Department, Designation, Joining Date, Employment Type, Status — rendered read-only, consistent with the existing Profile page ("Designation and department are managed by the administration").

---

## 7. Phase 2 — Workspace Personalization

### 7.1 Layout and density controls

| Preference | Options | Effect |
|---|---|---|
| Dashboard Layout | Single column / two column / grid | Applied via the widget registry (§8) |
| Widget Visibility | Per-widget on/off | Widget registry hides/show sections |
| Widget Order | Reorderable list | Widget registry ordering |
| Compact Mode | On / Off | Applies the dependency chain (§16) |
| Comfortable Mode | On / Off | Inverse of Compact Mode |
| Table Density | Compact / Default / Comfortable | Table paddings |
| Card Density | Compact / Default / Comfortable | Card paddings |
| Sidebar Default State | Expanded / Collapsed | `side-nav` initial state |
| Sticky Filters | On / Off | Filter bars remain visible on scroll |
| Default Page Size | 10 / 20 / 50 | Applied to paginated tables |

### 7.2 Workspace management

| Capability | Behaviour |
|---|---|
| Saved Workspace | Persists the full workspace namespace as a named snapshot |
| Workspace Reset | Reverts workspace to defaults (see Reset Levels, §17) |
| Restore Defaults | Restores default layout/density/page-size |
| Restore Previous Version | Rolls back to the last `restorePoint` (§18) |
| Configuration Backup | Downloads a **preference-only** backup file (JSON) |
| Export Settings | Downloads the workspace configuration as JSON |
| Import Settings | Uploads a JSON configuration backup and validates it |
| Workspace Restore | Re-applies a previously exported configuration |

**Backup scope (locked):** all backup/import/export/restore operations are **preference backups only**. They serialize the `preferences` JSONB content (workspace, dashboard, analytics, notifications, export, accessibility, personalization). **No academic data is affected** — enrollments, marks, attendance, subjects, and identities are never exported, imported, or altered by any workspace operation.

---

## 8. Phase 3 — Dashboard Preferences

**Refactor decision (locked):** the existing static `DashboardView` is refactored into a **shared widget registry** — each dashboard section becomes a typed widget (StatCard grid, Needs Attention, Subject table, and future sections) rendered according to saved preferences. The refactor preserves current rendering and applies to every role's dashboard via the same registry.

### 8.1 Widget controls

| Preference | Behaviour |
|---|---|
| Pinned Widgets | Fixed widgets that stay visible regardless of scroll/state |
| Hidden Widgets | Widgets excluded from the dashboard render |
| Collapsed Widgets | Widgets rendered collapsed (expandable) |
| Widget Ordering | Explicit order across the dashboard |
| Favorite Widgets | Quick-access shortcuts to priority widgets |

### 8.2 Defaults and navigation

| Preference | Options |
|---|---|
| Default Landing Page | Dashboard / Performance / Attendance / Teaching |
| Default Semester | Semester filter default (or All) |
| Default Academic Year | Year filter default (or All) |
| Default Compare Mode | On / Off for SoS comparison |
| Default Chart | Preferred chart per analytics page |
| Favourite Analytics | Pinned analytics pages/views |
| Recent Analytics | Auto-tracked recently viewed analytics |
| Quick Launch | Shortcut panel content (§15) |
| Dashboard Reset | Reverts dashboard preferences to defaults (§17) |

---

## 9. Phase 4 — Analytics Preferences

**Reuses the Threshold Engine.** Faculty may override analytical thresholds **within Admin-defined bounds** — the bounds are configuration, not hardcoded, and are enforced by the Preference Engine on write.

| Preference | Behaviour | Bound source |
|---|---|---|
| Attendance Threshold | Override within `[admin_min, admin_max]` | Threshold Engine |
| Performance Threshold | Override within `[admin_min, admin_max]` | Threshold Engine |
| Teaching Threshold | Override within `[admin_min, admin_max]` | Threshold Engine |
| Default Comparison Mode | On / Off | Dashboard default |
| Chart Behaviour | Tooltips on/off, legend position, aggregation labels | Chart registry |
| Auto Refresh Preference | Manual / 30s / 60s / 5m | BFF refresh cadence |
| Sorting Preference | Default sort + order per table | Table preferences |
| Table Preference | Default page size, density | Workspace defaults |

Every override stores both the user value and the Admin bound used for validation, so the UI can explain why a value was clamped.

---

## 10. Phase 5 — Notification Center

**Rule-based only** — alerts are generated by the shared Rule-Based Insight Engine from the same aggregates the analytics pages compute. No AI, no ML, no prediction.

### 10.1 Alert types

| Type | Trigger (rule-based) |
|---|---|
| Attendance Alerts | Attendance below threshold, exam ineligible, shortage flag |
| Performance Alerts | Below-baseline performance, pass-rate movement |
| Teaching Alerts | Capacity utilization / workload status changes |
| Export Completion | Export job finished / failed |
| System Notifications | Configuration, maintenance, feature updates |

### 10.2 Rule controls

| Control | Behaviour |
|---|---|
| Notification Rule Builder | Create/edit/disable per-alert-type rules with threshold + subject/scope |
| Notification History | Bounded, per §3.3 activity persistence |
| Notification Rules | Per-type on/off and threshold overrides |
| Quiet Hours | Time window during which non-critical alerts are suppressed |
| Do Not Disturb | Full suppression until disabled or a timer expires |
| Digest Frequency | Instant / Daily / Weekly / Monthly |
| Notification Digest | Aggregated digest of suppressed or low-priority alerts |

### 10.3 Channels

| Channel | Status |
|---|---|
| Browser (in-app) | **V1** — in-app banner/toast with the shared alert component |
| Email | **Future-ready** — placeholder contract, no V1 implementation |
| Mobile | **Future-ready** — placeholder contract, no V1 implementation |

---

## 11. Phase 6 — Export Preferences

**Reuses the existing Export Layer** (CSV builder + print-to-PDF) and applies preferences at generation time — no new export engine.

| Preference | Options / behaviour |
|---|---|
| CSV Delimiter | `,` / `;` / tab |
| UTF Encoding | UTF-8 (default) with BOM option for spreadsheet compatibility |
| Date Format | `YYYY-MM-DD` / `DD/MM/YYYY` / `MM/DD/YYYY` |
| Time Format | 12h / 24h |
| Decimal Precision | 0 / 1 / 2 / 3 places |
| Filename Pattern | Pattern with scope + timestamp tokens |
| Timezone | User-selected timezone for timestamps |
| Default Export Scope | Current View / Complete Dataset |
| Export Templates | Saved named export configurations |

---

## 12. Phase 7 — Accessibility Center

Reuses `next-themes` and the existing CSS-variable theme system; no new theming architecture.

### 12.1 V1 controls

| Control | Behaviour |
|---|---|
| Compact Mode | Compact density preset (shares the dependency chain, §16) |
| Comfortable Mode | Comfortable density preset |
| High Contrast | High-contrast theme class applied to charts, tables, badges, sidebar, cards (§16) |
| Color Blind Safe Palette | Palette swap to a color-blind-safe chart palette |
| Font Scaling | 100% / 115% / 130% root font scale |
| Reduced Motion | Disables non-essential animations/transitions |
| Focus Ring Size | Small / Medium / Large focus indicators |
| Keyboard Navigation | Full keyboard reachability (already the standard; surfaced here) |
| Screen Reader Labels | Enhanced `aria-label` verbosity |
| Accessibility Presets | One-click named presets (e.g. "High Visibility", "Low Motion") |

### 12.2 Future (roadmap V2/V3)

Cursor Size, Screen Magnifier — explicitly **not** V1.

---

## 13. Phase 8 — Security Center

### 13.1 Password management (V1)

- **Password Change** — verified against the current credential, then updated through the **existing authentication layer**. Password management follows the project's authentication architecture. Future credential hardening can be introduced without changing the Settings architecture.
- No password is ever handled, displayed, or stored by the Settings module itself.

### 13.2 Session and activity (V1)

| Item | Behaviour |
|---|---|
| Current Session | Active cookie-session card: browser/device metadata, sign-in time, current role |
| Recent Activity | Lightweight activity history (sign-ins, preference changes, export runs) — current implementation may persist this inside the preferences namespace; future enterprise versions may migrate it to a dedicated audit table (§3.3) |

### 13.3 Future-ready (roadmap V2/V3)

Login History, Device History, 2FA, Passkeys, Trusted Devices — placeholders with contracts, no V1 implementation.

---

## 14. Phase 9 — Performance Highlights

Deterministic, rule-based confirmations and observations rendered in a compact panel. Canonical terminology only.

| Template |
|---|
| "Workspace configured successfully." |
| "Dashboard preferences updated." |
| "Accessibility improved (High Contrast + Reduced Motion enabled)." |
| "Notification rules changed (Quiet Hours set to 21:00–07:00)." |
| "Export preferences updated (CSV delimiter set to semicolon)." |
| "Profile completion improved to 80%." |
| "Reset performed: Dashboard restored to defaults." |

Quiet state: when no rule fires, show "All settings are at their recommended defaults." Never fabricate a highlight.

---

## 15. Personalization

A dedicated subsection capturing usage-shaped preferences, reusable across Faculty, HOD, Admin, TPO, and Student through the same Preference Engine namespaces.

| Preference | Behaviour | Reused by |
|---|---|---|
| Recent Searches | Auto-tracked recent searches per page | Faculty / HOD / Admin / TPO |
| Favorite Filters | Saved filter combinations | Faculty / HOD / Admin / TPO |
| Favorite Subjects | Pinned subjects | Faculty / HOD / Admin |
| Pinned Students | Pinned students for quick access | Faculty / HOD / Admin |
| Recent Pages | Recently visited pages | All roles |
| Quick Launch Shortcuts | Editable quick-launch panel items | Faculty / HOD / Admin / TPO |

---

## 16. Preference Dependency Matrix

One preference automatically affects all dependent UI components through the shared widget registry and theme system — a single toggle propagates through the dependency chain, never hand-wired per component.

### 16.1 Compact Mode chain

```
Compact Mode
  ↓
Dense Tables
  ↓
Smaller Cards
  ↓
Reduced Padding
  ↓
Compact Charts
```

### 16.2 High Contrast chain

```
High Contrast
  ↓
Charts
  ↓
Tables
  ↓
Badges
  ↓
Sidebar
  ↓
Cards
```

### 16.3 Dependency rules

- Dependencies are declared once in the Preference Engine (a preference → affected components map) and applied by the widget registry / CSS-variable theme.
- A preference change re-renders only affected components; unaffected sections keep their state.
- Each dependency is deterministic and documented; enabling Compact Mode while Comfortable Mode is on resolves by explicit precedence (last-saved wins, with a rule-based highlight explaining the resolution).

---

## 17. Reset Levels (enterprise reset scopes)

The generic Reset option is replaced by scoped resets. Each resets only its namespace and records the action in the activity/audit trail.

| Reset scope | What it resets | What it does NOT touch |
|---|---|---|
| Reset Dashboard | Landing page, term/compare/chart defaults, favourites, widget configuration (pins/hidden/collapsed/order) | Profile, analytics thresholds, notifications, accessibility, export |
| Reset Analytics | Threshold overrides, comparison mode, chart/table/auto-refresh preferences | Dashboard, notifications, accessibility, export, workspace |
| Reset Notifications | Alert rules, quiet hours, Do Not Disturb, digest frequency | All other namespaces |
| Reset Accessibility | Contrast, palette, fonts, motion, focus, presets | All other namespaces |
| Reset Workspace | Layout, density, sidebar, sticky filters, page size, saved workspace | All other namespaces |
| Factory Reset Preferences | All preference namespaces back to role defaults; creates a restore point before applying | Profile-extension fields (`profile_extra`) are retained unless explicitly confirmed |

Every reset creates a `restorePoint` (§18) before applying, so it is always reversible via Restore Previous Version.

---

## 18. Workspace Versioning

Configuration metadata stored with every preference namespace, surfaced in the Settings header and the readiness card.

| Metadata | Meaning |
|---|---|
| Preference Version | Version of the user preference payload (increments per save) |
| Configuration Version | Version of the whole configuration object |
| Last Modified | Timestamp of the most recent preference write |
| Last Synced | Timestamp of the most recent sync (V1: server write; V2: cross-device) |
| Schema Version | `schemaVersion` of the persisted shape (migration gate, §5) |
| Restore Point | A named/timestamped snapshot created before any reset or restore |

---

## 19. Workspace Readiness Score

A deterministic readiness score for the faculty workspace, computed by the Rule-Based Insight Engine. No AI, no ML.

### 19.1 Components

| Component | Weight | Satisfied when |
|---|---|---|
| Profile Completed | 25% | `profile_extra` filled + primary contact present |
| Dashboard Configured | 20% | Landing page + term scope + widget config set |
| Notifications Enabled | 15% | At least one alert rule enabled |
| Accessibility Configured | 10% | At least one accessibility preference non-default |
| Security Updated | 10% | Password verified/updated + activity log present |
| Export Preferences Configured | 10% | Export preferences set to non-default values |
| Workspace Personalized | 10% | Any personalization preference used |

### 19.2 Output

- **Overall Readiness %** — weighted sum, deterministic.
- **Recommended Actions** — the Rule-Based Insight Engine lists the uncompleted components ("Add your bio and office hours to reach 85% readiness.").
- No AI, no ML, no prediction language. The score is a descriptive configuration-completeness measure.

---

## 20. Advanced Enterprise Features

| Feature | Where | V1 / Future |
|---|---|---|
| Workspace Readiness Score | §19 | V1 |
| Profile Completion Score | §19 component | V1 |
| Dashboard Personalization | §8 | V1 |
| Saved Workspace Views | §7.2 | V1 |
| Favourite Analytics | §8.2 | V1 |
| Recent Activity Timeline | §13.2 | V1 |
| Preference Audit Trail | §18 / `preferences.audit` | V1 (lightweight) |
| Quick Launch Panel | §15 | V1 |
| Notification Rule Builder | §10 | V1 |
| Export Templates | §11 | V1 |
| Workspace Backup / Restore / Import / Export | §7.2 | V1 (preference-only) |
| Keyboard Shortcuts | Accessibility | V1 |
| Workspace Health Score | Readiness derivative | V1 |
| Faculty Productivity Score | Readiness + usage derivative | V2 (rule-based) |
| Workspace Analytics | Usage analytics | V2 (rule-based) |
| Cross Device Sync | — | V2/V3 (§27) |
| Feature Flags | §5 | V1 |
| Privacy Controls | Preferences access | V1 |
| Preference Synchronization | — | V2/V3 |
| Activity Timeline | §13.2 | V1 |
| Configuration Audit | §18 | V1 (lightweight) |
| Workspace Recovery | Restore Previous Version | V1 |
| Preference Version History | §18 | V1 |

---

## 21. Reuse Matrix (shared Preference Engine)

The Settings module is the first consumer of the **shared Preference Engine** — the architecture is designed so that every role consumes the same engine, namespaces, validation, versioning, and audit without duplicating architecture.

| Consumer | Reuses (unchanged) | Adds (scoped) |
|---|---|---|
| **Faculty** | Preference Engine, profile reuse, widget registry, Threshold Engine bounds, export prefs, accessibility presets, notification rules, backup/versioning, readiness | Faculty namespaces + defaults |
| **HOD** | Same engine + widgets + rules + export + accessibility + versioning | HOD namespaces, department-wide defaults, visibility of department preference templates |
| **Admin** | Same engine + widgets + rules + export + accessibility + versioning | Admin namespaces, Admin-defined bounds for threshold overrides, feature flags |
| **TPO** | Same engine + widgets + rules + export + accessibility + versioning | TPO namespaces, career-oriented defaults |
| **Student** | Same engine, profile reuse, widget registry, accessibility presets, export prefs | Student namespaces + defaults; no analytics-threshold overrides |

Each consumer layers role-scoped namespaces and defaults on top of the shared engine; none re-implements storage, validation, versioning, or components.

---

## 22. API Recommendations

Endpoints only — no implementation. All under the existing BFF pattern with the session user resolved server-side.

| Endpoint | Purpose |
|---|---|
| `GET /faculty/settings` | Read the full preference document + metadata + readiness |
| `PATCH /faculty/settings/profile` | Profile-extension fields (bio, office hours, alternate email, picture) |
| `PATCH /faculty/settings/workspace` | Workspace namespace + saved workspaces |
| `PATCH /faculty/settings/dashboard` | Dashboard namespace + widget configuration |
| `PATCH /faculty/settings/analytics` | Analytics namespace (threshold overrides within bounds) |
| `PATCH /faculty/settings/notifications` | Notification rules, quiet hours, digest |
| `PATCH /faculty/settings/export` | Export preferences + templates |
| `PATCH /faculty/settings/accessibility` | Accessibility namespace |
| `PATCH /faculty/settings/security` | Password change (through the authentication layer) |
| `PATCH /faculty/settings/personalization` | Personalization namespace |
| `POST /faculty/settings/reset` | Scoped reset (body: reset level) |
| `GET /faculty/settings/workspace/backup` | Preference-only configuration backup (JSON) |
| `POST /faculty/settings/workspace/import` | Import and validate a configuration backup |
| `POST /faculty/settings/workspace/restore` | Restore a previous version / restore point |
| `GET /faculty/settings/activity` | Lightweight activity history (bounded) |
| `GET /faculty/settings/readiness` | Readiness score + recommended actions |

Password change, where it requires a credential check, delegates to the existing authentication layer rather than implementing a parallel auth path.

---

## 23. Matrices

### 23.1 Feature matrix

| Phase | Deliverables |
|---|---|
| 0 Configuration Readiness | Validation, versioning, feature flags, bounds, defaults, role validation |
| 1 Profile Settings | Profile-extension fields; read-only identity; profile reuse |
| 2 Workspace Personalization | Layout/density, widgets, sidebar, sticky filters, page size, backup/restore/import/export |
| 3 Dashboard Preferences | Landing/term/compare/chart defaults, favourites, recents, quick launch, widget registry |
| 4 Analytics Preferences | Bounded threshold overrides, chart/table/refresh prefs |
| 5 Notification Center | Rule-based alerts, rules, quiet hours, Do Not Disturb, digest, browser channel |
| 6 Export Preferences | CSV/PDF, delimiter, encoding, formats, precision, filenames, timezone, scope, templates |
| 7 Accessibility Center | Contrast, palette, fonts, motion, focus, keyboard, presets |
| 8 Security Center | Password (auth layer), current session, activity log |
| 9 Performance Highlights | Confirmation highlights + quiet state |

### 23.2 Preference matrix (defaults)

| Preference | Default |
|---|---|
| Dashboard Layout | Grid |
| Compact Mode | Off |
| Comfortable Mode | Off |
| Table / Card Density | Default |
| Sidebar Default State | Expanded |
| Sticky Filters | Off |
| Default Page Size | 20 |
| Default Landing Page | Dashboard |
| Default Semester / Year | All / All |
| Default Compare Mode | Off |
| Digest Frequency | Daily |
| Quiet Hours | Off |
| CSV Delimiter | Comma |
| UTF Encoding | UTF-8 |
| Date / Time Format | YYYY-MM-DD / 24h |
| Decimal Precision | 2 |
| Default Export Scope | Current View |
| Font Scaling | 100% |
| Reduced Motion | Off |
| High Contrast | Off |
| Focus Ring Size | Medium |

### 23.3 Security matrix

| Item | V1 | Future-ready |
|---|---|---|
| Password Change (auth layer) | ✅ | — |
| Current Session | ✅ | — |
| Recent Activity | ✅ (lightweight, migratable) | ✅ (dedicated audit table) |
| Login History | — | ✅ |
| Device History | — | ✅ |
| 2FA | — | ✅ |
| Passkeys | — | ✅ |
| Trusted Devices | — | ✅ |

### 23.4 Accessibility matrix

| Control | V1 | Future |
|---|---|---|
| Compact / Comfortable Mode | ✅ | — |
| High Contrast | ✅ | — |
| Color Blind Safe Palette | ✅ | — |
| Font Scaling | ✅ | — |
| Reduced Motion | ✅ | — |
| Focus Ring Size | ✅ | — |
| Keyboard Navigation | ✅ | — |
| Screen Reader Labels | ✅ | — |
| Accessibility Presets | ✅ | — |
| Cursor Size | — | ✅ |
| Screen Magnifier | — | ✅ |

### 23.5 Workspace matrix

| Capability | V1 |
|---|---|
| Saved Workspace | ✅ |
| Reset / Restore Defaults | ✅ |
| Restore Previous Version | ✅ |
| Configuration Backup | ✅ |
| Export / Import Settings | ✅ |
| Workspace Restore | ✅ |
| Preference-only guarantee (no academic data) | ✅ |
| Cross Device Sync | V2/V3 |

### 23.6 Data source mapping

| Data | Source |
|---|---|
| Preference document | `users.preferences` (JSONB) |
| Profile-extension fields | `users.preferences.profile_extra` |
| Primary contact fields | `faculty.email` / `faculty.phone_number` via existing endpoint |
| Read-only identity | `faculty` (existing profile API) |
| Threshold bounds | `backend/app/core/config.py` (Threshold Engine) |
| Activity / audit | `users.preferences.activity` / `.audit` (lightweight, migratable) |
| Theme / accessibility | `next-themes` + CSS variables |
| Dashboard widgets | Shared widget registry (refactor of `DashboardView`) |

---

## 24. Implementation Order

1. Backend: add JSONB `preferences` column to `users` (migration), preference read/write service + validation + versioning + audit methods.
2. BFF: `GET/PATCH /api/faculty/settings/*` routes + `lib/settings-engine.ts` + types in `lib/faculty-api.ts`.
3. Dashboard refactor: extract shared widget registry from `DashboardView`.
4. Settings page shell + Phase 0 readiness + Profile section (reuse).
5. Workspace → Dashboard → Analytics sections.
6. Export → Accessibility → Personalization sections.
7. Notification Center (rules, quiet hours, digest, browser channel).
8. Security Center (password via auth layer, current session, activity log).
9. Readiness score + Performance Highlights.
10. Reset levels + workspace backup/restore/import/export.
11. Verification (§26).

---

## 25. Production Checklist

- No new database tables; single JSONB `preferences` column on `users` is the only schema touch.
- Preferences validated, versioned, and audited on every write; Admin bounds enforced for threshold overrides.
- Password management uses the existing authentication layer; no password logic lives in Settings.
- Preference backups are preference-only; verified that no academic data is ever included.
- Activity history is lightweight and capped; migration to a dedicated audit table documented, not required in V1.
- Every reset creates a restore point before applying; every reset is reversible.
- All queries parameterized; preference reads/writes scoped to the session user.
- Accessibility and Compact Mode propagate through the dependency matrix, never hand-wired per component.
- No new npm dependencies beyond shared UI primitives built once (`Select`, `Switch`, `Textarea`, `Dialog`, `RadioGroup`).
- Loading / Empty / Error states on every section independently (a notification-section failure never breaks workspace).
- Freshness (`lastModified` / `lastSynced`) surfaced via `FreshnessBadge`.

---

## 26. Definition of Done

- [ ] Settings page renders from real persisted preferences (no placeholder, no localStorage-only state).
- [ ] All Phases 0–9 sections render with independent loading/empty/error states.
- [ ] Profile section reuses the existing Profile module; no duplicated profile view.
- [ ] Dashboard refactor preserves current rendering while enabling pinned/hidden/collapsed/ordered/favourite widgets.
- [ ] Threshold overrides are clamped to Admin-defined bounds with an explained reason.
- [ ] Notification Center is rule-based (Rule-Based Insight Engine) with quiet hours, Do Not Disturb, and digest frequencies; browser is the only V1 channel.
- [ ] Export preferences (delimiter, encoding, formats, precision, filenames, timezone, scope) apply at generation time.
- [ ] Accessibility controls (contrast, palette, fonts, motion, focus, presets) apply via the dependency matrix.
- [ ] Security Center: password change via the authentication layer, current session, lightweight activity log; 2FA/passkeys/device history are future-ready placeholders only.
- [ ] Workspace backup/import/export/restore are preference-only — verified no academic data is touched.
- [ ] Reset levels reset exactly their namespace and are reversible via restore point.
- [ ] Readiness score + Recommended Actions render deterministically with no AI wording.
- [ ] Canonical terminology only; no "Insights", prediction, risk, or plaintext-password language anywhere.
- [ ] Typecheck, lint, build, and live-render checks pass.

---

## 27. Future Roadmap (V2 / V3)

Strictly V2/V3 — **not** V1 implementation:

- Voice Assistant
- AI Assistant
- Theme Marketplace
- Passkeys
- Enterprise SSO
- Google / Outlook Calendar Sync
- Cloud Backup
- Cross Device Live Sync
- Mobile Push Notifications
- Email-notification delivery (browser remains the V1 channel)
- Cursor Size and Screen Magnifier accessibility controls
- Login History / Device History / 2FA / Trusted Devices
- Dedicated activity / audit table (migration of lightweight history)
- Workspace Analytics and Faculty Productivity Score (rule-based)
- Preference Recommendations (rule-based)

None of these change the V1 architecture; they layer onto the same Preference Engine, authentication layer, and widget registry (file 00 §6 terminology applies).

---

## 28. Locked Decisions

1. **Storage** — preferences live in a single JSONB `preferences` column on `users`; profile-extension fields under `profile_extra`. No new tables.
2. **Password management** — uses the existing authentication layer; architecture-neutral language; future credential hardening is a non-architectural change.
3. **Activity history** — lightweight and capped in V1; future versions may migrate to a dedicated audit table (§3.3).
4. **Dashboard** — refactored into a shared widget registry to support pinned/hidden/collapsed/ordered/favourite widgets.
5. **Analytics overrides** — allowed only within Admin-defined bounds from the Threshold Engine.
6. **Notification channel** — browser only in V1; email/mobile future-ready.
7. **Workspace backup/import/export/restore** — preference-only; no academic data affected.
8. **Resets** — scoped reset levels (Dashboard / Analytics / Notifications / Accessibility / Workspace / Factory), each reversible via restore point.
9. **Accessibility** — V1 set per §12.1; cursor size and magnifier are future.
10. **Dependency matrix** — one preference propagates to all dependent UI components (§16).
11. **Readiness Score** — deterministic weighted completeness; Recommended Actions from the Rule-Based Insight Engine; no AI.
12. **Canonical terminology** — Performance Highlights only; "Insights", prediction, and risk language reserved per file 00.
13. **No schema assumptions** — the single JSONB column is the only schema touch; everything else reuses existing tables and APIs.

---

## 29. Self-Review & Open Questions

**Assumptions made**
- `users` carries `faculty_id`, `student_id`, `role`, and `department`, making it the correct role-agnostic anchor for a shared Preference Engine.
- Profile-extension fields can live under `preferences.profile_extra` rather than new `faculty` columns (smaller schema footprint; revisitable if profile search/indexing needs arise).
- The existing dashboard sections can be extracted into a widget registry without behavioral change (verified: `DashboardView` is a composed, self-contained view).
- Lightweight activity history in JSONB is acceptable for V1; a dedicated audit table is the documented V2 migration path.
- The current auth flow's credential comparison is the "existing authentication layer"; Settings calls it and never re-implements credential handling.

**Schema fields / contracts to confirm before building**
- Exact shape and maximum size of the JSONB `preferences` document (cap per namespace to bound writes).
- Whether `next-themes` needs a high-contrast/color-blind variant registered, or whether CSS-variable overrides alone suffice.
- Whether uploaded profile pictures are stored as URLs (existing asset strategy) or require an upload endpoint.

**Potential naming conflicts**
- "Performance Highlights" is shared with analytics modules — Settings confirmations reuse the same term and same template pattern; they are not a second insights concept.
- "Workspace Reset" (Phase 2) vs "Reset Workspace" (Reset Levels) vs "Factory Reset Preferences" — the Reset Levels matrix (§17) defines the precise scope of each; the UI must use the §17 labels verbatim.
- The `preferences.activity` namespace must not be confused with the future dedicated audit table; §3.3 documents the migration explicitly.
- Accessibility "Compact Mode" is the same preference surfaced in Workspace (§7) — one stored value, two entry points; the dependency matrix (§16) guarantees they cannot drift.

**Further reuse opportunities**
- The Preference Engine and widget registry are the natural foundation for Admin-configured default templates pushed to role namespaces.
- The readiness score can later be composed with the Health Scores from the analytics modules (files 11 §9.3, 12 §9.3) into a combined "workspace + domain health" card without new architecture.
- The reset/restore-point mechanism can be reused by any future settings surface (HOD, Admin, TPO) unchanged.
