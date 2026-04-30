# DevQuest - AI-Powered Gamified Developer Productivity Dashboard

DevQuest is a developer productivity dashboard that brings tasks, meetings, focus time, AI prioritization, and gamified progress into one workspace. It is designed to help developers cut through fragmented tools like Jira, Outlook Calendar, and Microsoft To Do, then turn the day's work into clear, actionable missions and quests.

The product uses a React frontend with a Python backend plan targeting Oracle Autonomous Database for persistence and OCI Generative AI/Agents for task intelligence. The intended backend will enrich work items with AI-generated difficulty, effort, impact, XP, prioritization, insights, standup notes, and daily or weekly productivity summaries.

## Key Capabilities

- Unified task management across custom tasks, Jira issues, Outlook meetings, and Microsoft To Do items.
- AI-assisted task enrichment for priority, effort, XP, category, impact, and suggested next actions.
- Daily missions and quests that translate tasks into a focused work plan.
- Capacity analysis based on working hours, meeting load, and available focus windows.
- Standup note generation based on tasks completed today, blockers, notes, and current work.
- Daily and weekly overviews covering accomplishments, meeting time, learnings, and progress.
- Gamified productivity elements such as XP, streaks, levels, focus mode, and quest-style task cards.

## Current Status

The frontend currently implements the DevQuest dashboard experience with in-memory demo data. Backend integration work is documented in:

- `docs/backend-api-integration-plan.md`
- `docs/backend-todo-list.md`

Leaderboard can be ignored for the current backend scope.
