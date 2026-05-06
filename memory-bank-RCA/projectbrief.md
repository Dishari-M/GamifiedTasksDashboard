# Project Brief

## Overview
This workspace (`c:\Oracle_Repo`) is a multi-project collection of Oracle-related codebases. It includes legacy Java/Ant/Gradle services, Oracle JET UI applications, database script bundles, and a patch installer repository.

## In-Scope Projects (Observed)
- `Legacy_ANT`: legacy multi-module Java codebase with Ant/Gradle build files and numerous subprojects (e.g., Agent, Posting, installer, weatherApp).
- `myportal`: multi-module Java/Gradle portal codebase with WAR packaging; includes `portal` webapp and `PLS` library aggregation (3PL/4PL libs).
- `Patch_Installer`: patch installer repository with `installBuilder`, `patchPackages`, and `patch_pkg_rules.json` for packaging upgrades (JDK, Jetty, Apache Drill, weather).
- `ra2`: database script bundles organized by RA 20.x releases/patches; includes DBCI/QA correction tooling guidance and Apache Drill runtime docs.
- `ra2-devops`: Oracle JET 17.1 UI app (`ebo-devops`) for RA EBO Devops with local mock data.
- `ra2-op`: Oracle JET 17.1 UI app (`UI-OIDC-Provider`) for OIDC Provider UI.
- `ra2-portal`: Oracle JET 17.1 UI app (`ebo-portal`) for RA EBO Portal with shared composites and mock data.
- `skills`: Codex skill definitions (`enterprise-rca`).

## Goals
- Maintain a clear, accurate Memory Bank across sessions.
- Capture per-project context to speed onboarding and reduce rediscovery.
- Identify the active project when work begins.

## Non-Goals
- Detailed feature documentation for every subproject without specific request.

## Open Questions
- Which subproject is the primary focus for current work?
- Are there priority deliverables or active tickets for any project?
