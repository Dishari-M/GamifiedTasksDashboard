---
name: enterprise-rca
description: Deep root cause analysis for large multi-module enterprise projects like RA2, Legacy_Ant, myportal, ra2-portal, ra2-op, ra2-devops and translation-files projects. Use when asked to find RCA, affected modules/files, or concrete code fixes from bug reports, stack traces, JIRA tickets, or memory-bank/build.gradle dependency context.
---

# Enterprise RCA

## Purpose
Perform deep RCA across multi-module enterprise codebases and produce precise, file-level fixes.

## Mandatory Context Sources
- Use `memory-bank/` as the primary reference. Each subfolder represents a module. Extract code flow, architecture, known issues, and integration points.
- Analyze all relevant `build.gradle` files to determine module dependencies and inter-module relationships. If module A depends on B, include both in analysis.
- Expand the scope to all related modules based on dependencies and code flow; do not stop at the entry module.

## Module Entry Mapping
Use these mappings as a starting point only. Always expand via dependencies and code flow.

- **Versioning note (UI repo split):**
  - If a Jira key is provided, **extract the Affects Version from Jira** and use it to decide UI locations:
    - **Affects Version < 20.2**: UI/frontend code lives inside `ra2/` monorepo. Check these legacy paths for UI issues:
      - `ra2/UI_Devops/`
      - `ra2/UI_Development/`
      - `ra2/UI-OIDC-Provider/`
    - **Affects Version >= 20.2**: UI/frontend code is separated into repos:
      - `ra2-portal/`
      - `ra2-op/`
      - `ra2-devops/`
  - If no Jira key or no Affects Version is available, fall back to the mappings below and expand via dependencies.

- Portal UI -> RA2/UI_Development/, ra2-portal/ 
- Devops UI -> RA2/UI_DevOps/, ra2-devops/
- OP,OIDC UI,login,logout,sign in,sign out -> RA2/UI-OIDC-Provider/, ra2-op/, RA2/app/OIDC-provider/
- Labor,Employment Info -> RA2/app/, myportal/
- ReportMail, scheduler, info delivery -> RA2/app/scheduler/
- BI,BIAPI,CT,CTAPI -> RA2/app/bi-api/, RA2/app/bi-engine/
- PM,POS,FLM,User,People,roles,People Management -> RA2/app/administration/
- reports,report -> RA2/app/reports/
- RTA,posting,AdminServer -> Legacy_Ant/posting/, Legacy_Ant/Agent/
- SelfService,exports -> RA2/app/data-access/, RA2/app/data-access-scheduler/
- provisioning -> devops/
- DB/SQL/ORA -> Database-RA2/
- inmotion -> inmotion/
- iquery -> Legacy_Ant/dotnetsrc/iQuery2/, RA2/app/iquery-engine/,RA2/app/iquery-service/
- Translation -> translation-files/

## Data Model Notes (API Accounts)
- `CORE_USER.APIACCOUNTTYPE` identifies API account type:
  - `BI` = BIAPI accounts
  - `CT` = CTAPI accounts
  - `NULL` = normal portal users

## RCA Workflow
1. If a Jira ticket is provided (eg. HEPRT-123, HRA-123), get the Jira details **and comments** using MCP tools otherwise use the input. Parse the bug description, error messages, stack traces, logs, **and comments**. Extract keywords. If Jira includes **Affects Version**, use it to select UI code locations per the UI repo split rule.
2. Identify the entry module using the mapping rules, then expand using `build.gradle` dependencies.
3. Trace code flow end-to-end: UI -> API -> Service -> DAO Impl -> sql query. Track data transformations, null handling, conditions, and exception flows.
4. Perform cross-module analysis. Identify where data is produced, modified, and consumed.
5. Validate against evidence (logs, stack traces, DB queries). Do not assume.
6. Identify the root cause (the specific reason it failed, not symptoms).
7. Identify all affected files with exact paths and reasons for change.
8. Suggest precise code fixes with before/after snippets and defensive handling as needed.
9. If multiple viable fixes exist, list all options with brief tradeoffs so the user can choose the most suitable fix.

## Output Requirements
- Use the exact output template the user specifies.
- Always include: root cause, affected modules, affected files (paths + reasons), and precise code changes.
- For code suggestions, present changes as removed vs added lines (diff-style or clearly labeled "Removed"/"Added").

## Output Template (when user does not provide one)
## Root Cause
<clear, specific explanation>

## Affected Modules
- Module A
- Module B

## Affected Files
- path/to/file1.java -> reason
- path/to/file2.js -> reason


## Code Fix Suggestion
```language
// improved code here
```
