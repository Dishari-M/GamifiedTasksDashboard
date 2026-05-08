# AI Usage And Impact Summary

## Overview

Gamified Tasks Dashboard uses AI to help developers plan the day, choose the right work, understand risks, generate mission and quest recommendations, and prepare daily updates.

The AI is grounded in the app's own task, calendar, capacity, XP, RCA complexity, due-date, and notes data.

The goal is to reduce manual planning effort and help users move from "what should I do?" to "here is the best next path."

## Before

Developers had to manually inspect multiple signals before deciding what to work on:

| Signal | Why It Matters |
| --- | --- |
| Task priority | Identifies business or engineering urgency |
| Due dates | Highlights overdue or due-today work |
| Estimated effort | Helps decide what fits available time |
| XP value | Supports gamified progress and reward planning |
| RCA T-shirt size / complexity | Adds engineering complexity context |
| File-change count | Indicates likely implementation or review risk |
| Calendar meetings | Reduces available focus time |
| Available focus time | Determines what can realistically be completed |
| Working Today status | Marks committed daily work |
| Notes and blockers | Captures risk and context |
| Completed work | Supports summaries, XP, and standup updates |

### Key Pain Points

- Daily planning took time and was inconsistent.
- High-priority or due-today work could be missed.
- Developers had to manually compare task effort with available focus windows.
- Standup notes required manual summarization.
- Blockers and risks were easy to overlook.
- Task ordering depended on individual judgment rather than a consistent evidence-based approach.

## After

Gamified Tasks Dashboard now uses AI to convert task and schedule context into practical guidance.

Users can:

- See dashboard insight based on today's work and available capacity.
- Generate missions that recommend what to focus on.
- Generate quests that turn Working Today tasks into a ranked execution path.
- Generate AI insights with risks, recommendations, and task-specific guidance.
- Generate standup notes from completed, in-progress, and blocked work.

This improves the experience by giving users a clearer daily flow:

1. Review today's capacity and task signals.
2. Generate or review recommended missions.
3. Generate quests for the day's execution path.
4. Use AI Insights to understand risks and next actions.
5. Use standup output as a starting point for team updates.

## How AI Insights Are Decided

AI Insights are generated from the user's current work context. The backend prepares structured evidence and sends it to OCI GenAI.

### Input Evidence

- Tasks marked Working Today
- Completed tasks
- Task priority
- Task status
- Due date and start date
- XP value
- Estimated effort
- RCA T-shirt size
- RCA file-change count
- Impact score
- Priority score
- Task notes
- Labels
- Calendar meetings
- Focus blocks
- Available focus minutes
- Previous-day comparison metrics

### AI Instructions

The AI is instructed to:

- Use only supplied evidence.
- Avoid inventing task names, blockers, meetings, or accomplishments.
- Identify practical risks.
- Recommend concrete next actions.
- Consider due-date urgency.
- Consider available focus capacity.
- Use XP and RCA complexity as supporting signals.

### Output

The generated result includes:

- Daily insight
- Risks
- Recommendations
- Themes
- Task-level insights

## How Missions Are Decided

Missions are recommended tasks for the user to focus on. They are decided using both deterministic backend ranking and AI reasoning.

### Signals Used

- Due date urgency
- Priority
- Impact score
- Priority score
- XP value
- RCA T-shirt size
- RCA file-change count
- Estimated effort
- Task status
- Notes and blockers
- Available focus time
- Calendar constraints

The backend first prepares eligible candidate tasks. Done tasks are excluded. Working Today tasks are prioritized when relevant.

AI then ranks missions and explains why each task matters.

### Example Mission Reasoning

- A blocked task may be recommended first if unblocking it is urgent.
- A high-impact due-today task may be recommended before lower-impact work.
- A smaller task may be recommended if it fits available focus time.
- A task with high RCA complexity may be treated as higher effort or higher risk.

## How Quests Are Decided

Quests are the execution path generated from Working Today tasks.

Quest generation considers:

- Which tasks are selected for today
- Available focus windows
- Meeting load
- Task effort
- Priority
- Impact
- Due dates
- XP
- RCA complexity
- Notes and risk signals

The output is a ranked quest plan with:

- Quest order
- Reason for each quest
- Suggested timing where available
- XP snapshot
- Active or queued quest state

The Quests page then shows the route for the day.

## Explainability

The AI is not making decisions from hidden or external data. It uses only the structured context supplied by the backend.

This makes the output explainable because recommendations can be traced back to:

- Task fields
- Due dates
- Notes
- Calendar capacity
- XP values
- RCA complexity
- Status and blocker data

The implementation also stores AI runs, so request and response history can be reviewed later for debugging, demos, or audit-style analysis.

## Impact Metrics

### Time Saved

Expected daily savings per developer:

| Activity | Before | After |
| --- | --- | --- |
| Daily planning | Around 10-15 minutes | Around 1-3 minutes |
| Standup preparation | Around 5-10 minutes | Under 1 minute of review/editing |
| Quest planning | Manual sorting | One generate action |

Estimated saving:

- 10-20 minutes per developer per day
- For a 5-person team: 50-100 minutes per day
- Around 4-8 hours per week across the team

### Error Reduction

Expected improvements:

- Fewer missed due-today or overdue tasks
- Fewer missed blockers
- Fewer completed tasks appearing in active mission planning
- More consistent task prioritization across users
- Better awareness of work that exceeds available focus time

### Productivity Gains

Expected gains:

- Faster start to the workday
- Less manual context gathering
- Better alignment between priority, due dates, and focus time
- More consistent daily execution
- Easier standup preparation
- Reduced context switching between tasks, calendar, and notes

### Throughput Or Delivery Improvements

Expected improvements:

- High-priority work starts earlier.
- Blocked work is surfaced sooner.
- Working Today tasks become a clearer execution path.
- Developers spend more time executing and less time deciding.
- Team updates become more consistent and evidence-based.

## Summary

Gamified Tasks Dashboard uses AI as a planning assistant for developer productivity. It does not replace the user's judgment; it organizes the available evidence and highlights the most practical next steps.

The main value is faster planning, fewer missed priorities, better focus, and clearer daily execution.
