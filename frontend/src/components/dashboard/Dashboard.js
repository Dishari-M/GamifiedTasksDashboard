import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  ArrowClockwise,
  CalendarBlank,
  CheckCircle,
  Clock,
  DotsThreeVertical,
  Flag,
  Lightning,
  ListBullets,
  Play,
  Plus,
  Sparkle,
  Timer,
  TrendDown,
  TrendUp,
  Trophy,
} from "@phosphor-icons/react";

const schedule = [
  { time: "09:00 AM", title: "Daily Standup", duration: "30m", durationMinutes: 30, color: "purple" },
  { time: "10:00 AM", title: "Architecture Review", duration: "1h", durationMinutes: 60, color: "orange" },
  { time: "11:30 AM", title: "Client Sync", duration: "1h", durationMinutes: 60, color: "blue" },
  { time: "01:00 PM", title: "Focus Time Block", duration: "2h 45m available", durationMinutes: 165, color: "green", focus: true },
];

const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

const isSameDay = (isoValue) => {
  if (!isoValue) return false;
  return new Date(isoValue).toLocaleDateString("en-CA") === new Date().toLocaleDateString("en-CA");
};

const formatMinutes = (minutes) => {
  const value = Math.max(0, Number(minutes) || 0);
  const hours = Math.floor(value / 60);
  const mins = value % 60;
  if (!hours) return `${mins}m`;
  if (!mins) return `${hours}h`;
  return `${hours}h ${mins}m`;
};

const formatDateTime = (isoValue) => {
  if (!isoValue) return "Not completed";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(isoValue));
};

const formatTimer = (seconds) => {
  const mins = Math.floor(seconds / 60).toString().padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
};

const completedTodayTasks = (tasks) => tasks.filter((task) => task.status === "Done" && isSameDay(task.completedAt));

const Pill = ({ children, tone = "neutral", testId }) => (
  <span className={`pill pill-${tone}`} data-testid={testId}>
    {children}
  </span>
);

const IconBadge = ({ icon: Icon, tone = "violet", testId }) => (
  <span className={`icon-badge icon-badge-${tone}`} data-testid={testId}>
    <Icon size={26} weight="duotone" aria-hidden="true" />
  </span>
);

export const StatCard = ({ label, value, detail, icon, tone, trend, down, progress, testId }) => (
  <section className="stat-card surface" data-testid={testId}>
    <div className="stat-head"><span>{label}</span><IconBadge icon={icon} tone={tone} testId={`${testId}-icon`} /></div>
    <div className="stat-value" data-testid={`${testId}-value`}>{value}</div>
    {typeof progress === "number" && <div className="progress-track" data-testid={`${testId}-progress-track`} aria-label={`${label} progress`}><span className="progress-fill" style={{ width: `${progress}%` }} data-testid={`${testId}-progress-fill`} /></div>}
    <div className={`stat-detail ${down ? "negative" : "positive"}`} data-testid={`${testId}-detail`}>
      {trend && (down ? <TrendDown size={17} weight="bold" aria-hidden="true" /> : <TrendUp size={17} weight="bold" aria-hidden="true" />)}
      {detail}
    </div>
  </section>
);

export const MissionCard = ({ task, index }) => {
  const Icon = task.icon;
  return (
    <article className={`mission-card mission-${task.accent}`} data-testid={`mission-card-${slug(task.id)}`}>
      <IconBadge icon={Icon} tone={task.accent} testId={`mission-icon-${slug(task.id)}`} />
      <div className="mission-copy">
        <div className="mission-title-row"><h3 data-testid={`mission-title-${slug(task.id)}`}>{task.title}</h3><Pill tone={task.type.toLowerCase()} testId={`mission-type-${slug(task.id)}`}>{task.type}</Pill></div>
        <p className="mission-meta" data-testid={`mission-meta-${slug(task.id)}`}>{task.source} - {task.id}</p>
        <p data-testid={`mission-description-${slug(task.id)}`}>{task.aiInsight || task.description}</p>
      </div>
      <div className="mission-score">
        <Pill tone={task.priority.toLowerCase()} testId={`mission-priority-${slug(task.id)}`}>{task.priority}</Pill>
        <span data-testid={`mission-time-${slug(task.id)}`}><Clock size={16} weight="duotone" aria-hidden="true" /> {task.time} mins</span>
        <strong data-testid={`mission-xp-${slug(task.id)}`}>{task.xp} XP</strong>
        <span className="mission-rank" data-testid={`mission-rank-${slug(task.id)}`}>#{index + 1}</span>
      </div>
    </article>
  );
};

export const SchedulePanel = ({ events = schedule }) => (
  <section className="surface schedule-panel" data-testid="schedule-panel">
    <div className="section-heading"><h2><CalendarBlank size={26} weight="duotone" aria-hidden="true" /> Today&apos;s Schedule</h2><NavLink to="/calendar" data-testid="view-calendar-link">View Calendar</NavLink></div>
    <div className="timeline" data-testid="schedule-timeline">
      {events.map((event) => (
        <div className="timeline-row" key={event.time} data-testid={`schedule-row-${slug(event.time)}`}>
          <time data-testid={`schedule-time-${slug(event.time)}`}>{event.time}</time>
          <span className={`timeline-dot timeline-${event.color}`} data-testid={`schedule-dot-${slug(event.time)}`} />
          <article className={`event-card event-${event.color}`} data-testid={`schedule-event-${slug(event.title)}`}>
            <strong data-testid={`schedule-title-${slug(event.title)}`}>{event.title}</strong>
            <span data-testid={`schedule-duration-${slug(event.title)}`}>{event.duration}</span>
            {event.focus && <Lightning size={22} weight="fill" aria-hidden="true" />}
          </article>
        </div>
      ))}
    </div>
  </section>
);

export const FocusWidget = ({ compact = false }) => {
  const [isRunning, setIsRunning] = useState(false);
  const [seconds, setSeconds] = useState(25 * 60);

  useEffect(() => {
    if (!isRunning || seconds <= 0) return undefined;
    const id = window.setInterval(() => setSeconds((value) => value - 1), 1000);
    return () => window.clearInterval(id);
  }, [isRunning, seconds]);

  const progress = ((25 * 60 - seconds) / (25 * 60)) * 360;

  return (
    <section className={`surface focus-widget ${compact ? "focus-compact" : ""}`} data-testid="focus-widget">
      <div className="section-heading"><h2><Timer size={26} weight="duotone" aria-hidden="true" /> Focus Mode</h2><NavLink to="/focus" data-testid="focus-sessions-link">Sessions</NavLink></div>
      <div className="timer-ring" style={{ "--timer-progress": `${progress}deg` }} data-testid="focus-timer-ring" aria-label="Pomodoro timer progress"><div><strong data-testid="focus-timer-value">{formatTimer(seconds)}</strong><span data-testid="focus-timer-label">Pomodoro</span></div></div>
      <div className="focus-actions">
        <button className="primary-action" onClick={() => setIsRunning((value) => !value)} data-testid="focus-start-pause-button"><Play size={20} weight="fill" aria-hidden="true" /> {isRunning ? "Pause" : "Start"}</button>
        <button className="icon-button reset-button" onClick={() => { setIsRunning(false); setSeconds(25 * 60); }} aria-label="Reset timer" data-testid="focus-reset-button"><ArrowClockwise size={22} weight="duotone" /></button>
      </div>
    </section>
  );
};

export const TaskTable = ({ tasks, onComplete, onStatusChange, onEdit, onToggleToday, onUpdateNotes }) => {
  const [openActionId, setOpenActionId] = useState(null);

  const runAction = (action) => {
    action();
    setOpenActionId(null);
  };

  return (
    <div className="task-table-wrap" data-testid="task-table-wrap">
      <table className="task-table enriched-task-table" data-testid="task-table">
        <thead><tr><th>Task</th><th>Today</th><th>Source</th><th>Priority</th><th>AI</th><th>Effort</th><th>XP</th><th>Completed</th><th>Status</th><th>Notes</th><th>Action</th></tr></thead>
        <tbody>
          {tasks.map((task) => {
            const Icon = task.icon;
            const isMenuOpen = openActionId === task.id;
            return (
              <tr key={task.id} data-testid={`task-row-${slug(task.id)}`}>
                <td data-testid={`task-title-cell-${slug(task.id)}`}>
                  <span className={`tiny-task-icon tiny-${task.accent}`}><Icon size={20} weight="duotone" aria-hidden="true" /></span>
                  <span className="task-title-stack"><strong>{task.title}</strong><small>{task.description}</small></span>
                </td>
                <td>
                  <button onClick={() => onToggleToday(task.id)} className={`today-toggle ${task.workingToday ? "active" : ""}`} data-testid={`task-today-button-${slug(task.id)}`}>
                    {task.workingToday ? "Working" : "Add"}
                  </button>
                </td>
                <td data-testid={`task-source-${slug(task.id)}`}>{task.source}</td>
                <td><Pill tone={task.priority.toLowerCase()} testId={`task-priority-${slug(task.id)}`}>{task.priority}</Pill></td>
                <td className="ai-cell" data-testid={`task-ai-${slug(task.id)}`}><span className="ai-score">{Math.round((task.priorityScore || 0) * 100)}%</span><span>{task.difficulty} - impact {task.impact}/10</span></td>
                <td data-testid={`task-time-${slug(task.id)}`}>{task.time} mins</td>
                <td data-testid={`task-xp-${slug(task.id)}`}>{task.xp} XP</td>
                <td data-testid={`task-completed-${slug(task.id)}`}>{formatDateTime(task.completedAt)}</td>
                <td><Pill tone={slug(task.status)} testId={`task-status-${slug(task.id)}`}>{task.status}</Pill></td>
                <td className="notes-cell">
                  <textarea
                    className="inline-notes"
                    value={task.notes || ""}
                    onChange={(event) => onUpdateNotes(task.id, event.target.value)}
                    aria-label={`Notes for ${task.title}`}
                    data-testid={`task-notes-${slug(task.id)}`}
                  />
                </td>
                <td className="task-actions action-menu-cell">
                  <button
                    className="menu-action"
                    aria-label={`Open actions for ${task.title}`}
                    aria-expanded={isMenuOpen}
                    onClick={() => setOpenActionId(isMenuOpen ? null : task.id)}
                    data-testid={`task-menu-button-${slug(task.id)}`}
                  >
                    <DotsThreeVertical size={22} weight="bold" />
                  </button>
                  {isMenuOpen && (
                    <div className="task-action-menu" role="menu" data-testid={`task-action-menu-${slug(task.id)}`}>
                      <button role="menuitem" onClick={() => runAction(() => onEdit(task))} data-testid={`task-edit-button-${slug(task.id)}`}>Edit</button>
                      <button role="menuitem" onClick={() => runAction(() => onStatusChange(task.id))} data-testid={`task-status-button-${slug(task.id)}`}>Advance</button>
                      <button role="menuitem" onClick={() => runAction(() => onComplete(task.id))} data-testid={`task-complete-button-${slug(task.id)}`}>Done</button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const Dashboard = ({ tasks, onComplete, onStatusChange, onEdit, onToggleToday, onUpdateNotes, dashboardStats, dashboardSchedule, dashboardInsight, dashboardStatus }) => {
  const completedCount = dashboardStats?.tasks_completed_today ?? completedTodayTasks(tasks).length;
  const todayTasks = tasks.filter((task) => task.workingToday);
  const totalXp = dashboardStats?.total_xp ?? tasks.filter((task) => task.status === "Done").reduce((sum, task) => sum + task.xp, 2450);
  const focusMinutes = dashboardStats?.focus_minutes;
  const meetingMinutes = dashboardStats?.meeting_minutes;
  const topMissions = [...(todayTasks.length ? todayTasks : tasks.filter((task) => task.status !== "Done"))]
    .sort((a, b) => (b.priorityScore || 0) - (a.priorityScore || 0))
    .slice(0, 3);

  return (
    <main className="dashboard-page" data-testid="dashboard-page">
      <section className="stats-grid" aria-label="Daily productivity metrics">
        <StatCard label="Total XP" value={`${totalXp.toLocaleString()} XP`} detail="Includes completed work" icon={Trophy} tone="violet" trend testId="stat-total-xp" />
        <StatCard label="Tasks Completed" value={`${completedCount} today`} detail="Completion date is captured" icon={CheckCircle} tone="blue" progress={Math.min(100, (completedCount / Math.max(1, todayTasks.length)) * 100)} testId="stat-tasks-completed" />
        <StatCard label="Working Today" value={`${todayTasks.length} tasks`} detail="Feeds the Quests page" icon={Flag} tone="gold" testId="stat-working-today" />
        <StatCard label="Focus Time" value={formatMinutes(focusMinutes ?? 0)} detail={dashboardStatus === "live" ? "From Phase 8 capacity API" : "22% vs yesterday"} icon={Clock} tone="green" trend testId="stat-focus-time" />
        <StatCard label="Meetings" value={formatMinutes(meetingMinutes ?? 0)} detail={dashboardStatus === "live" ? "From Phase 8 calendar data" : "Tracked in overview"} icon={CalendarBlank} tone="orange" trend down testId="stat-meetings" />
      </section>
      <div className="content-grid">
        <section className="surface missions-panel" data-testid="missions-panel"><div className="section-heading"><h2><Flag size={26} weight="duotone" aria-hidden="true" /> Today&apos;s Missions</h2><NavLink to="/quests" data-testid="view-all-missions-link">View quests</NavLink></div><div className="mission-list">{topMissions.map((task, index) => <MissionCard key={task.id} task={task} index={index} />)}</div></section>
        <SchedulePanel events={dashboardSchedule} />
        <section className="surface my-tasks-panel" data-testid="my-tasks-panel"><div className="section-heading task-panel-heading"><h2><ListBullets size={26} weight="duotone" aria-hidden="true" /> My Tasks</h2><NavLink className="add-task-link" to="/tasks" data-testid="dashboard-add-task-link"><Plus size={19} weight="bold" aria-hidden="true" /> Add Task</NavLink></div><div className="tab-row" role="tablist" aria-label="Task filters">{["All", "Working Today", "Done", "Blocked"].map((tab, index) => <button key={tab} className={index === 0 ? "tab active" : "tab"} role="tab" data-testid={`task-filter-${slug(tab)}`}>{tab}</button>)}</div><TaskTable tasks={tasks} onComplete={onComplete} onStatusChange={onStatusChange} onEdit={onEdit} onToggleToday={onToggleToday} onUpdateNotes={onUpdateNotes} /></section>
        <aside className="right-stack" data-testid="right-stack"><FocusWidget compact /><section className="surface insight-card" data-testid="ai-insight-card"><div className="quote-mark" aria-hidden="true">&quot;</div><h2><Sparkle size={25} weight="duotone" aria-hidden="true" /> AI Insight</h2><p data-testid="ai-insight-text">{dashboardInsight?.text || topMissions[0]?.aiInsight || "Select work for today to generate focused insights."}</p><div className="insight-grid"><span data-testid="ai-capacity-value">{formatMinutes(dashboardInsight?.capacity_minutes ?? todayTasks.reduce((sum, task) => sum + task.time, 0))} {dashboardInsight ? "capacity" : "planned"}</span><span data-testid="ai-impact-value">{dashboardInsight?.impact_score ? `${dashboardInsight.impact_score}/10 impact` : `${Math.round((topMissions[0]?.priorityScore || 0) * 100)} priority score`}</span></div></section><section className="surface quote-card" data-testid="quote-card"><div className="quote-mark" aria-hidden="true">&quot;</div><p data-testid="quote-text">Discipline is the bridge between goals and accomplishment.</p><span data-testid="quote-author">- Jim Rohn</span></section></aside>
      </div>
      <p className="footer-note" data-testid="dashboard-footer-note">You&apos;re doing great. Keep the momentum going.</p>
    </main>
  );
};

export default Dashboard;
