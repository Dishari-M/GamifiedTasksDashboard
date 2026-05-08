# AI Insights And Missions Demo Talking Points

## AI Insights

- AI Insights are generated from the user's actual Gamified Tasks Dashboard context, not from a generic prompt.
- The backend sends structured evidence to OCI GenAI: today's tasks, Working Today items, completed work, due dates, priority, XP, RCA T-shirt size, effort, notes, blockers, calendar meetings, and available focus time.
- The AI is instructed to use only this supplied evidence, so it should not invent tasks, meetings, or blockers.
- The output gives a daily insight, risks, recommendations, themes, and task-level insight.
- Due dates are part of the decision logic, so overdue or due-today work can be surfaced more strongly.
- The AI button lets the user regenerate insights on demand.

## Missions

- Missions are the recommended work items for today.
- They are decided using task priority, due date urgency, XP, RCA complexity, file-change count, estimated effort, impact score, task status, notes, and available focus time.
- Done tasks are excluded from Today's Missions.
- A blocked task can be surfaced if unblocking it is the most important next step.
- A high-impact due-today task can be ranked higher than a lower-risk task.
- The goal is to answer: "What should I focus on next, and why?"

## Quests

- Quests convert Working Today tasks into an execution path.
- The AI ranks the quest path using today's task list, meetings, focus blocks, effort, priority, due date, XP, and complexity.
- The result is a practical route for the day: active quest, queued quests, reasons, and XP context.
- This makes the app move from a task tracker to a guided work planner.

## Business Impact

- Reduces daily planning time.
- Helps avoid missing urgent or blocked work.
- Makes standup preparation faster.
- Gives users an explainable reason behind recommendations.
- Improves focus by matching work to available capacity.

## Simple Demo Flow

1. Open Dashboard and show today's capacity, tasks, and mission cards.
2. Explain that completed tasks are excluded from active missions.
3. Go to Quests and click Generate/Regenerate Quests.
4. Show the ranked quest path and reasons.
5. Go to AI Insights and click AI.
6. Show daily insight, risks, recommendations, and task-level insights.
7. Mention that due date, priority, XP, RCA complexity, effort, notes, and calendar capacity are all part of the AI context.
