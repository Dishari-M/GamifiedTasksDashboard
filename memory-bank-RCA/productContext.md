# Product Context

## Why This Exists
Multiple related repositories live under one workspace. A shared Memory Bank keeps cross-project context intact between sessions.

## Problems It Solves
- Losing context in a multi-repo workspace
- Unclear current focus when switching projects
- Repeated rediscovery of project structure and tooling

## How It Should Work
- Keep a concise, accurate overview of each project.
- Track current focus and recent changes in `activeContext.md`.
- Record architecture decisions and constraints in `systemPatterns.md` and `techContext.md`.

## User Experience Goals
- Fast orientation to the correct subproject
- Clear next steps without re-reading large parts of the codebase
- Reliable notes on tooling and scripts
