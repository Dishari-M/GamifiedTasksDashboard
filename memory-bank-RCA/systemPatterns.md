# System Patterns

## Architecture Overview
- Multi-repo workspace with independent projects.
- Three Oracle JET-based SPAs: `ra2-portal`, `ra2-devops`, `ra2-op`.
- Two legacy Java multi-module repos using Gradle/Ant: `Legacy_ANT`, `myportal`.
- Database script bundles in `ra2\DB Scripts` organized by release/patch.
- Patch installer with packaged upgrade components in `Patch_Installer\patchPackages`.

## Key Technical Decisions
- Oracle JET 17.1 toolchain used across `ra2-*` UI apps.
- TypeScript-based front-end builds with Karma-based test suites.
- Java repos standardize SBOM generation and Parfait analysis via Gradle plugins.

## Design Patterns
- Oracle JET composables under `src/ts/jet-composites` (portal/devops).
- Mock data directories (`mock-database-directory`) for local/test data.
- `ra2` DB scripts follow a fixed patch folder structure including `Formatted_Production_Scripts`, `QA_Support_Scripts`, `DBCI_Tool`, and `QA_Correction_Tool`.

## Component Relationships
- UI apps are independent but share similar tooling and structure.
- Patch installer aggregates upgrade packages including Apache Drill, JDK, and Jetty.
- `ra2` DB scripts include QA support and formatting tools (DBCI).
- `myportal` uses `PLS` as a shared library drop for 3PL/4PL dependencies.

## Critical Implementation Paths
- UI apps: build and test via `package.json` scripts (lint/test).
- DB scripts: follow patch folder structure and formatting/QA guidelines.
- Java repos: Gradle builds with `generateSbom` task for SBOM output.
