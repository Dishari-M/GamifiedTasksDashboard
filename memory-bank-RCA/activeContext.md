# Active Context

## Current Focus
- Updating the Memory Bank with context from each project under the runtime-selected codebase workspace.

## Recent Changes
- Added per-project context based on root structure, Gradle build files, and UI `package.json` metadata.

## Next Steps
- Confirm the primary project for ongoing work.
- Perform deeper scans for architecture details once the focus is chosen.

## Decisions & Considerations
- Treat the workspace as multi-project until a primary target is specified.
- Resolve project paths relative to the codebase folder selected by the user at task creation time; do not assume a fixed local root path.
- Keep project summaries lightweight unless a specific repo is active.

## Patterns & Preferences
- Document Oracle JET app structure consistently across `ra2-*` apps.
- Prefer `rg` for searches and PowerShell for scripts.

## Learnings
- `ra2`, `Patch_Installer` include Apache Drill runtime instructions.
- `ra2-*` UI apps share Oracle JET 17.1 tooling and similar dev stacks.
