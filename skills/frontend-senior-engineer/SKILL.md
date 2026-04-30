---
name: frontend-senior-engineer
description: Senior frontend engineering workflow for React, browser UI, dashboards, forms, accessibility, responsive behavior, failure states, and professional user-friendly interfaces. Use when building, reviewing, or modifying frontend code, especially when changes affect visual layout, data fetching, loading/error states, keyboard access, mobile responsiveness, or Playwright-based UI verification.
---

# Frontend Senior Engineer

## Operating Standard

Act like a senior product-minded frontend engineer. Optimize for a UI that is useful, accessible, resilient, fast, and polished. Prefer the existing app patterns before adding new dependencies or abstractions.

## Before Editing

1. Inspect the existing component structure, routing, state management, API client patterns, styling files, and package scripts.
2. Identify every user flow affected by the requested change.
3. Check whether existing UI primitives, icons, form components, or layout classes already solve the problem.
4. Preserve unrelated behavior and avoid broad refactors unless the task requires them.
5. Define the failure, loading, empty, and success states before changing code.

## UI Quality Bar

- Build the actual usable screen, not a decorative placeholder.
- Keep operational tools dense, scannable, and calm.
- Make primary actions obvious and secondary actions available without crowding the page.
- Use consistent spacing, typography, icon style, colors, focus states, and component sizing.
- Ensure text fits within buttons, cards, table cells, modals, and mobile layouts.
- Avoid nested cards, decorative clutter, one-note palettes, and oversized marketing composition for productivity tools.
- Keep forms efficient: labels, validation, sensible defaults, clear required fields, and preserved user input after recoverable errors.
- Show clear loading, empty, error, retry, saving, saved, and disabled states.
- Disable destructive or duplicate actions while requests are in flight.
- Use optimistic UI only when rollback behavior is explicit and tested.

## Responsiveness

- Verify desktop, tablet, and mobile layouts.
- Prevent page-level horizontal overflow.
- Allow intentional local overflow for wide data tables using scroll containers.
- Keep navigation, modals, forms, tables, and action bars usable at mobile widths.
- Use stable dimensions for repeated cards, icons, counters, table actions, and controls so content changes do not shift the layout.
- Do not scale font size directly with viewport width.

## Accessibility

- Use semantic HTML before ARIA.
- Ensure every input has a programmatic label.
- Ensure every icon-only button has an accessible name.
- Preserve visible keyboard focus.
- Support keyboard navigation for dialogs, menus, tabs, toggles, and forms.
- Keep color contrast readable in default, hover, disabled, success, warning, and error states.
- Do not rely on color alone to communicate status.
- Announce async errors and form validation in an accessible way.
- Keep DOM order aligned with visual order.

## Failure Management

- Treat every API call as fallible.
- Handle network timeout, unauthorized, forbidden, validation error, conflict, and generic server error states.
- For update conflicts, show a clear refresh/retry path.
- For partial failures, keep successful results visible and call out what failed.
- Preserve user-entered form data when a save fails.
- Add retry affordances where recovery is realistic.
- Never show raw stack traces, SQL errors, secrets, tokens, or provider payloads in the UI.

## Data And State

- Keep server data and local form draft state separate.
- Re-fetch or update caches after inserts, updates, deletes, and generated AI outputs.
- Include `row_version` or equivalent optimistic-lock values in edit flows when the backend provides them.
- Keep IDs stable and avoid using array indexes as keys for mutable lists.
- Normalize API response handling so screens do not duplicate parsing logic.

## Playwright CLI Verification Prompt

After meaningful frontend changes, run a real browser check with Playwright CLI. Use this prompt as the verification instruction:

```text
Start the local frontend dev server. Use Playwright CLI to open the changed route in Chromium at desktop and mobile viewport sizes. Verify the primary user flow, loading state, empty/error state if reachable, keyboard focus visibility, and absence of page-level horizontal overflow. Capture at least one screenshot or textual browser snapshot. If the change touches forms, create or edit a record and confirm the UI updates without console errors.
```

Suggested commands, adapting to the repo:

```bash
yarn start
npx playwright install chromium
npx playwright test
```

If the repo has no Playwright tests yet, use Playwright CLI codegen or a short ad hoc browser script to inspect the route and capture screenshots. Do not mark the work complete until the changed UI has been checked in a browser.

## Final Review Checklist

- [ ] The UI matches existing app conventions.
- [ ] Loading, empty, error, retry, saving, and success states are covered.
- [ ] Keyboard and screen-reader basics are preserved.
- [ ] Mobile and desktop layouts are checked.
- [ ] No page-level horizontal overflow is introduced.
- [ ] Console errors are checked.
- [ ] Playwright CLI verification is run or the reason it could not run is documented.
