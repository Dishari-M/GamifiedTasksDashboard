# Tech Context

## Technologies
- Oracle JET 17.1 (`@oracle/oraclejet`, `@oracle/ojet-cli`, tooling)
- TypeScript 5.5-5.6
- Webpack 5.x
- Karma + Mocha + Chai
- ESLint
- Sass
- Puppeteer
- json-server
- jQuery, moment
- Java (multi-module Gradle/Ant builds in `Legacy_ANT` and `myportal`)
- WAR packaging in `myportal`
- CycloneDX SBOM Gradle plugin and Oracle Parfait Gradle plugin (SBOM + static analysis)

## Development Setup
- Workspace root: the codebase folder selected by the user at task creation time.
- Shell: PowerShell
- Node engine (per UI apps): `>=12.21.0`

## Technical Constraints
- Varies by subproject; Oracle JET apps are tied to 17.1 tooling.
- DB scripts must follow formatting and QA correction workflows.
- Internal Maven repositories are referenced in Gradle builds for `Legacy_ANT` and `myportal`.
- People Management page user search and column sorting use the `globalsearch` API endpoint in `ra2/app/administration`.

## Dependencies
- `ra2-*` apps rely on Oracle JET 17.1 packages and associated tooling.
- `Patch_Installer` includes upgrade assets like JDK, Jetty, Apache Drill.
- `myportal` and `Legacy_ANT` share Gradle + Java conventions and internal artifacts.

## Tool Usage Patterns
- Use `rg` for search when possible.
- Run tests via `npx karma start test/karma.conf.js` in JET apps.
- Run SBOM generation via `generateSbom` Gradle task in Java repos when needed.
