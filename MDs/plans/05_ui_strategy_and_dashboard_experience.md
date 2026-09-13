# UI Strategy and Dashboard Experience

## 1. Purpose

This document defines how the product should feel and behave in the browser. It covers screen strategy, dashboard composition, role-specific presentation, and the UI rules that keep the product aligned with the backend-first architecture.

The UI is a consumer of verified backend outputs, not the place where academic or predictive logic should be invented.

## 2. Current UI Position

The current Next.js experience is intentionally minimal. The dashboards exist as placeholders that validate session flow, role routing, and page structure. That is the right foundation, but it is not the finished product.

## 3. UI Principles

- Design for role clarity first, not feature density.
- Keep the experience responsive and mobile-friendly.
- Favor readable, decision-oriented layouts over decorative dashboards.
- Show confidence, freshness, and provenance when data is derived or predictive.
- Avoid surfacing raw machine output without human context.

## 4. Role-Based Experience Model

### 4.1 Student Dashboard

The student view should emphasize personal progress, risk signals, attendance, subject performance, and grounded guidance. It should answer what the student should do next, not just what the numbers are.

### 4.2 Faculty Dashboard

The faculty view should emphasize cohort monitoring, flagged students, comparative views, and intervention context. It should help a faculty member move from signal to action quickly.

### 4.3 Admin Dashboard

The admin view should emphasize operational visibility, data completeness, and platform readiness. It should make the system legible from a governance perspective rather than from a student success perspective.

## 5. Dashboard Composition Rules

- Surface the most important summary first.
- Push detail into drill-down sections or secondary panels.
- Keep explanations adjacent to predictions or warnings.
- Show the last updated time for derived data.
- Separate live status from historical trends.

## 6. Interaction Model

The UI should support a progression from overview to detail:

1. Role landing page.
2. High-level summary cards.
3. Supporting trend or breakdown panels.
4. Drill-down into the underlying student, subject, or cohort context.

This progression works well for both desktop and mobile because it avoids forcing all detail onto the first screen.

## 7. Backend Dependency Rules

- UI routes should call backend APIs for business data.
- The UI should not calculate risk, attendance summaries, or guidance locally.
- Empty and loading states should be designed explicitly, because backend availability is part of the real user experience.
- The interface should remain useful even when some intelligence outputs are still unavailable.

## 8. Visual Direction

The implementation should stay consistent with the current Next.js stack and the project’s shadcn/ui and Tailwind foundation. Visual polish should support clarity, trust, and hierarchy rather than becoming the main story.

## 9. Completion Criteria

A dashboard module is only complete when:

- The backend data contract exists.
- The screen handles loading, empty, and error states.
- The role-specific content is grounded in real data.
- The layout works on small and large screens.
- The page is understandable without requiring source-code knowledge.

## 10. Accessibility and Usability

The platform handles sensitive academic and career data. Accessibility is not a polish step; it is a baseline requirement for a system that students and faculty will use daily.

### 10.1 Accessibility Standards

The UI should meet WCAG 2.1 Level AA as a practical target. This means:

- All interactive elements must be keyboard navigable.
- Color must not be the only means of conveying information (e.g. risk indicators must use icons or text labels alongside color).
- Form inputs must have associated labels.
- Contrast ratios must meet the AA threshold for both light and dark themes.
- Focus indicators must be visible and consistent.

The current implementation already uses `outline-ring/50` as a global focus style in `globals.css`, which provides a starting point. This must be preserved and extended as new components are added.

### 10.2 Screen Reader Support

- All pages should use semantic HTML elements (`main`, `nav`, `header`, `section`, `article`) rather than generic `div` wrappers for layout.
- Data tables should use `<table>`, `<thead>`, `<tbody>`, and `<th>` elements with appropriate `scope` attributes, not CSS grid styled to look like tables.
- Charts and visualizations must include a text alternative, either as an `aria-label` or as an adjacent summary table that conveys the same data.
- Error messages and status changes must be announced to assistive technology using `role="alert"` or `aria-live` regions.

### 10.3 Usability Principles

- Reduce cognitive load. Each screen should have one primary task or one primary insight, not a wall of competing information.
- Provide progressive disclosure. Summary first, detail on interaction.
- Use consistent interaction patterns across all three roles. A student and a faculty member should recognize the same interaction model even though they see different data.
- Avoid requiring technical vocabulary in the UI. Labels, tooltips, and explanations should use institutional language that faculty and students already understand.

### 10.4 Mobile-First Usability

The blueprint requires mobile-first design. This means:

- Layouts must be designed for small screens first, then enhanced for larger viewports.
- Touch targets must be at least 44px in both dimensions.
- Navigation patterns must work without hover interactions.
- Horizontal scrolling must not be required for any primary content on screens 320px and wider.

## 11. Design System Strategy

The design system is the shared visual and structural vocabulary for every screen in the platform.

### 11.1 Current Design Foundation

The current implementation establishes the following design foundation:

- **Design tokens** are defined in `globals.css` using CSS custom properties in oklch color space, with separate light and dark palettes.
- **Spacing** is controlled by a `--spacing: 0.25rem` base token.
- **Border radius** is governed by a `--radius: 1.3rem` base token with derived `sm`, `md`, `lg`, and `xl` variants.
- **Shadow system** uses CSS custom properties for configurable shadow depth, with hsl-based shadow color tuning.
- **Typography** defaults to Open Sans (sans-serif) for body text, with Geist loaded as a web font in the root layout. The mono font is Menlo.
- **Color system** includes primary, secondary, muted, accent, destructive, and chart color families, plus a full sidebar color set.

### 11.2 Token Discipline

All new components and screens must use the design tokens from `globals.css`. Hardcoded color values, spacing values, or font sizes in component files are not acceptable. If a new token is needed, it should be added to `globals.css` and documented, not embedded in a component.

### 11.3 Dark Mode

The platform supports system-detected and manual dark mode via the `next-themes` provider. The `ThemeProvider` component enables a keyboard shortcut (`D` key) for quick toggling. Every new component must be tested in both light and dark modes. The dark mode palette is independently tuned in `globals.css` and should not be treated as an automatic inversion of light mode.

### 11.4 Design System Growth Rules

- New design tokens must be added to `globals.css`, not scattered across component files.
- New color families should follow the existing pattern: oklch values in `:root` and `.dark`, mapped to Tailwind theme colors in the `@theme inline` block.
- The design system is intentionally minimal at this stage. It should grow by need as new dashboard modules are built, not by speculative token creation.

## 12. tweakcn and shadcn Component Reuse

The UI stack uses shadcn/ui as the component foundation and tweakcn as the theming layer. This section defines how components should be used and extended.

### 12.1 Current Component Inventory

The current codebase includes the following shadcn/ui components in `components/ui/`:

- `button.tsx` — primary interactive element with variant support via `class-variance-authority`.
- `card.tsx` — container with header, content, title, and description slots.
- `field.tsx` — form field composition system with label, error, group, separator, and description subcomponents.
- `input.tsx` — styled text input.
- `label.tsx` — form label with accessibility support.
- `separator.tsx` — visual divider.

### 12.2 Adding New Components

New components should be added using the shadcn CLI:

```
npx shadcn@latest add <component-name>
```

This ensures components are generated with the correct style (`base-nova`), theme tokens, and import paths as configured in `components.json`. Components should not be copied from external sources or written from scratch if an equivalent exists in the shadcn registry.

### 12.3 Component Customization Rules

- Use the `cn()` utility from `lib/utils.ts` for conditional class merging. Do not use string concatenation for class names.
- Override styles through Tailwind classes passed via `className` props, not by modifying the generated component source. If a component needs structural changes, those changes should be minimal and documented.
- Preserve the `data-slot` attributes used by shadcn components for CSS targeting. These are part of the component contract and should not be removed.

### 12.4 tweakcn Theming

tweakcn provides the visual theme layer on top of shadcn/ui. The current configuration in `components.json` specifies:

- Style: `base-nova`.
- Base color: `neutral`.
- CSS variables: enabled.
- Icon library: `lucide`.

Theme changes should be made through tweakcn's configuration and the design tokens in `globals.css`, not through direct component style overrides.

### 12.5 Component Reuse Rules

- Prefer composition over duplication. If two screens need similar layouts, extract a shared component rather than copying markup.
- Every component should receive its data through props or server component data fetching. Components must not contain hardcoded data or make direct database calls.
- Components that need client-side interactivity must be marked with `"use client"` and should be as small as possible. The default should be server components, with client components used only for interactive elements.

## 13. BFF Response Shaping Rules

The BFF (Backend-for-Frontend) layer in Next.js shapes FastAPI responses for specific screens. This section defines the rules that keep the BFF thin and prevent it from drifting into business logic.

### 13.1 What the BFF May Do

The BFF layer may:

- Aggregate multiple FastAPI responses into a single payload for a screen that needs data from several endpoints.
- Rename or restructure fields for screen-specific convenience (e.g. flattening a nested response for a card component).
- Add presentation-only metadata such as display labels, formatting hints, or sort defaults.
- Apply short-TTL caching for frequently viewed aggregates to reduce latency from the Next.js → FastAPI → PostgreSQL round trip.

### 13.2 What the BFF Must Not Do

The BFF must not:

- Compute analytics, summaries, or aggregations from raw data. If a screen needs a cohort average, that average must come from a FastAPI analytics endpoint, not from a BFF route summing rows.
- Apply business rules such as risk classification, performance categorization, or career recommendation logic.
- Generate narrative insights or interact with LLM providers.
- Re-derive data that FastAPI has already computed. If the response shape from FastAPI is wrong for the screen, the preferred fix is to add a FastAPI endpoint variant, not to restructure data in the BFF.

### 13.3 BFF Implementation Pattern

BFF routes should follow this pattern:

1. Receive the request from the dashboard page or component.
2. Forward the user's session token to the relevant FastAPI endpoint(s).
3. Await the FastAPI response(s).
4. Shape the response for the specific screen's needs.
5. Return the shaped response to the component.

### 13.4 BFF Error Handling

- If FastAPI returns an error, the BFF should translate it into a screen-appropriate error state, not expose raw backend error messages to the user.
- If FastAPI is unreachable, the BFF should return a structured error response that the UI can handle with a designed empty or error state.
- Timeouts should be configured at the BFF level. A slow FastAPI response should not hang the entire dashboard page.

### 13.5 BFF Typing Discipline

BFF routes should use types generated from or aligned with the FastAPI OpenAPI schema. Hand-typed response interfaces that drift from the actual backend contract will cause silent integration failures. When the FastAPI contract changes, the BFF types must be updated before the corresponding UI work begins.

## 14. UI Standards and Component Guidelines

This section provides the practical rules for building dashboard screens consistently.

### 14.1 Page Structure

Every dashboard page should follow this structure:

1. A page-level server component that handles data fetching and role verification.
2. A layout section that provides navigation, breadcrumbs, and role context.
3. One or more content sections built from reusable components.
4. Appropriate Next.js loading, error, and not-found boundaries.

### 14.2 Loading States

Every data-dependent section must define an explicit loading state. The loading state should:

- Use skeleton components or subtle loading indicators, not blank screens or full-page spinners.
- Be visually consistent with the loaded state so the layout does not shift when data arrives.
- Be implemented using Next.js `loading.tsx` files or React Suspense boundaries.

### 14.3 Empty States

Every section that can have no data must define an explicit empty state. The empty state should:

- Clearly communicate that no data is available, not that the system is broken.
- Suggest a reason when possible (e.g. "No risk predictions have been generated yet" rather than "No data").
- Be visually distinct from loading states.

### 14.4 Error States

Every section that depends on backend data must handle errors gracefully. The error state should:

- Provide a user-understandable message, not a stack trace or HTTP status code.
- Offer a retry action where appropriate.
- Be implemented using Next.js `error.tsx` boundaries or component-level error handling.

### 14.5 Data Freshness Indicators

Derived, predicted, or generated data must show when it was last updated. The freshness indicator should:

- Display a human-readable relative timestamp (e.g. "Updated 3 hours ago").
- Be visually subtle but always present for derived data sections.
- Use a warning treatment if the data is older than the expected refresh cadence.

### 14.6 Chart and Visualization Standards

The project includes `recharts` as the charting library. When building visualizations:

- Use the chart color tokens (`--chart-1` through `--chart-5`) defined in `globals.css`. Do not use arbitrary colors.
- Every chart must include axis labels, a legend where multiple series are shown, and a text summary for accessibility.
- Charts should be responsive and must not require horizontal scrolling on mobile.
- Prefer clear, simple chart types (bar, line, area) over complex or decorative visualizations.

### 14.7 Table Standards

The project includes `@tanstack/react-table` for data tables. When building tables:

- Use semantic HTML table elements, not div-based grid layouts.
- Support sorting and filtering where the data set is large enough to benefit.
- Paginate results when the row count exceeds a reasonable screen height.
- Tables must remain usable on mobile, either through horizontal scroll with a fixed first column or through a card-based alternative layout.

### 14.8 Notification and Feedback Standards

The project includes `sonner` for toast notifications. When providing user feedback:

- Use toast notifications for transient success or info messages (e.g. "Feedback submitted").
- Use inline error messages for form validation, not toasts.
- Use persistent alert banners for system-level warnings (e.g. "Data is stale — last updated 24 hours ago").

### 14.9 Form and Input Standards

The project includes `zod` for validation schemas. When building forms:

- Define validation schemas using Zod and apply them in server actions or API routes.
- Use the `Field`, `FieldLabel`, `FieldError`, and `FieldGroup` components from `components/ui/field.tsx` for consistent form layout.
- Display validation errors inline, adjacent to the field they relate to.
- Use `useActionState` for server action forms, consistent with the existing login form pattern.

### 14.10 Naming and File Organization

- Dashboard page components go in `app/<role>/dashboard/` or `app/<role>/<feature>/`.
- Shared dashboard components go in `components/` organized by domain (e.g. `components/student/`, `components/faculty/`, `components/admin/`).
- Components that are reused across roles go in `components/shared/`.
- UI primitives remain in `components/ui/` and should only contain shadcn-generated or shadcn-compatible components.
