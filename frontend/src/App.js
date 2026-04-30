import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes, useLocation } from "react-router-dom";
import {
  ArrowClockwise,
  Bell,
  Bug,
  CalendarBlank,
  CaretDown,
  CheckCircle,
  CheckSquare,
  Clock,
  CloudArrowDown,
  Database,
  DotsThreeVertical,
  FileText,
  Fire,
  Flag,
  FunnelSimple,
  GearSix,
  GitPullRequest,
  House,
  Hourglass,
  Lightning,
  ListBullets,
  ListChecks,
  MagnifyingGlass,
  Moon,
  Play,
  Plus,
  RocketLaunch,
  ShieldStar,
  SidebarSimple,
  Sparkle,
  SquaresFour,
  SunDim,
  Timer,
  TrendDown,
  TrendUp,
  Trophy,
  UsersThree,
} from "@phosphor-icons/react";
import "./App.css";
import "./responsive-fixes.css";
import "./feature-additions.css";

const navItems = [
  { label: "Dashboard", path: "/", icon: House },
  { label: "My Tasks", path: "/tasks", icon: ListChecks },
  { label: "Quests", path: "/quests", icon: Flag },
  { label: "Overview", path: "/overview", icon: SquaresFour },
  { label: "Calendar", path: "/calendar", icon: CalendarBlank },
  { label: "Focus Mode", path: "/focus", icon: Timer },
  { label: "AI Insights", path: "/insights", icon: Sparkle },
  { label: "Sync", path: "/sync", icon: CloudArrowDown },
  { label: "Settings", path: "/settings", icon: GearSix },
];

const taskTypes = ["Task", "Bug", "Epic", "Review", "Meeting"];
const priorities = ["Critical", "High", "Medium", "Low"];
const statuses = ["To Do", "In Progress", "Blocked", "Done", "Upcoming"];
const sources = ["Custom", "Jira", "Outlook", "Microsoft To Do"];

const todayKey = () => new Date().toLocaleDateString("en-CA");
const nowIso = () => new Date().toISOString();

const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

const parseNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const isSameDay = (isoValue, day = todayKey()) => {
  if (!isoValue) return false;
  return new Date(isoValue).toLocaleDateString("en-CA") === day;
};

const startOfWeekKey = (date = new Date()) => {
  const copy = new Date(date);
  const day = copy.getDay() || 7;
  copy.setDate(copy.getDate() - day + 1);
  return copy.toLocaleDateString("en-CA");
};

const addDaysKey = (dateKey, days) => {
  const date = new Date(`${dateKey}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toLocaleDateString("en-CA");
};

const isWithinWeek = (isoValue, weekStart = startOfWeekKey()) => {
  if (!isoValue) return false;
  const day = new Date(isoValue).toLocaleDateString("en-CA");
  return day >= weekStart && day <= addDaysKey(weekStart, 6);
};

const formatMinutes = (minutes) => {
  const value = Math.max(0, parseNumber(minutes, 0));
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

const iconForType = (type) => {
  if (type === "Bug") return Bug;
  if (type === "Epic") return RocketLaunch;
  if (type === "Review") return GitPullRequest;
  if (type === "Meeting") return UsersThree;
  return FileText;
};

const accentForPriority = (priority) => {
  if (priority === "Critical" || priority === "High") return "red";
  if (priority === "Medium") return "gold";
  if (priority === "Low") return "green";
  return "blue";
};

const buildAiFields = (task) => {
  const priorityWeight = { Critical: 10, High: 8, Medium: 5, Low: 3 }[task.priority] || 5;
  const effort = Math.max(15, parseNumber(task.time ?? task.estimatedMinutes, 60));
  const notesBoost = task.notes ? 0.4 : 0;
  const impact = Math.min(10, Math.max(1, parseNumber(task.impact, priorityWeight + notesBoost)));
  const priorityScore = Math.min(0.99, Math.round(((priorityWeight * 0.58 + impact * 0.32 + Math.min(effort / 60, 4) * 0.1) / 10) * 100) / 100);
  const xp = Math.max(10, parseNumber(task.xp, Math.round((effort * 0.75 + impact * 9 + priorityWeight * 5) / 10) * 10));
  const difficulty = effort >= 105 || priorityWeight >= 9 ? "Hard" : effort <= 35 && priorityWeight <= 5 ? "Easy" : "Medium";
  return {
    difficulty,
    impact,
    priorityScore,
    effort,
    xp,
    aiInsight: task.aiInsight || `${task.priority} priority ${task.type || "Task"} with ${formatMinutes(effort)} expected effort. ${task.notes ? "Use the notes as context for standup and overview summaries." : "Add notes as you learn more to improve the summary."}`,
  };
};

const normalizeTask = (task) => {
  const ai = buildAiFields(task);
  return {
    ...task,
    source: task.source || "Custom",
    type: task.type || "Task",
    priority: task.priority || "Medium",
    status: task.status || "To Do",
    time: ai.effort,
    xp: ai.xp,
    difficulty: ai.difficulty,
    impact: ai.impact,
    priorityScore: ai.priorityScore,
    aiInsight: ai.aiInsight,
    notes: task.notes || "",
    labels: Array.isArray(task.labels) ? task.labels : String(task.labels || "").split(",").map((label) => label.trim()).filter(Boolean),
    workingToday: Boolean(task.workingToday),
    icon: iconForType(task.type || "Task"),
    accent: task.accent || accentForPriority(task.priority || "Medium"),
  };
};

const makeTaskId = (source, externalId) => {
  if (externalId?.trim()) return externalId.trim();
  const prefix = source === "Jira" ? "JRA" : source === "Outlook" ? "OUT" : source === "Microsoft To Do" ? "TODO" : "CUS";
  return `${prefix}-${Math.floor(Math.random() * 9000 + 1000)}`;
};

const initialTasks = [
  normalizeTask({
    id: "PAY-2301",
    externalId: "PAY-2301",
    projectKey: "PAY",
    title: "Fix payment gateway timeout issue",
    description: "Users face timeout while making payments on the checkout page.",
    source: "Jira",
    type: "Bug",
    priority: "High",
    status: "In Progress",
    impact: 9,
    time: 120,
    actualMinutes: 45,
    xp: 120,
    workingToday: true,
    dueDate: todayKey(),
    notes: "Retry policy may be too generous for the gateway sandbox. Validate timeout cap and add regression coverage.",
    labels: ["payments", "backend"],
  }),
  normalizeTask({
    id: "ORD-1587",
    externalId: "ORD-1587",
    projectKey: "ORD",
    title: "Implement order tracking API",
    description: "Create a REST API to fetch real-time order status.",
    source: "Jira",
    type: "Epic",
    priority: "Medium",
    status: "To Do",
    impact: 8,
    time: 90,
    xp: 90,
    workingToday: true,
    dueDate: addDaysKey(todayKey(), 1),
    notes: "Contract is clear; biggest risk is mapping courier status states cleanly.",
    labels: ["api"],
  }),
  normalizeTask({
    id: "DOC-047",
    externalId: "DOC-047",
    title: "Update deployment documentation",
    description: "Update deployment steps for the v2.3.0 release.",
    source: "Microsoft To Do",
    type: "Task",
    priority: "Low",
    status: "To Do",
    impact: 5,
    time: 30,
    xp: 30,
    workingToday: false,
    notes: "Add rollback screenshots and note the environment variable rename.",
    labels: ["docs"],
  }),
  normalizeTask({
    id: "PR-468",
    externalId: "PR-468",
    title: "Review PR #468",
    description: "Review caching updates and leave concise feedback.",
    source: "Jira",
    type: "Review",
    priority: "Low",
    status: "Done",
    impact: 4,
    time: 20,
    actualMinutes: 25,
    xp: 30,
    workingToday: false,
    completedAt: nowIso(),
    notes: "Cache invalidation looked good. Suggested a smaller TTL for the checkout path.",
    labels: ["review"],
  }),
  normalizeTask({
    id: "OUT-902",
    externalId: "OUT-902",
    title: "Team retrospective",
    description: "Capture action items from the sprint retrospective.",
    source: "Outlook",
    type: "Meeting",
    priority: "Medium",
    status: "Upcoming",
    impact: 6,
    time: 60,
    xp: 60,
    workingToday: true,
    startDate: todayKey(),
    notes: "Bring release readiness and CI stability as discussion topics.",
    labels: ["meeting"],
  }),
];

const schedule = [
  { time: "09:00 AM", title: "Daily Standup", duration: "30m", durationMinutes: 30, color: "purple" },
  { time: "10:00 AM", title: "Architecture Review", duration: "1h", durationMinutes: 60, color: "orange" },
  { time: "11:30 AM", title: "Client Sync", duration: "1h", durationMinutes: 60, color: "blue" },
  { time: "01:00 PM", title: "Focus Time Block", duration: "2h 45m available", durationMinutes: 165, color: "green", focus: true },
];

const defaultOverview = {
  meetingMinutes: 190,
  focusMinutes: 155,
  newLearnings: "Gateway sandbox timeout thresholds differ from production.",
  wentWell: "Review feedback was concise and actionable.",
  wentWrong: "Timeout details were split across a few systems.",
};

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

const Sidebar = ({ open, onClose }) => (
  <aside className={`sidebar ${open ? "sidebar-open" : ""}`} data-testid="app-sidebar">
    <div className="brand" data-testid="app-brand">
      <span className="brand-mark" data-testid="app-brand-mark">
        <RocketLaunch size={34} weight="fill" aria-hidden="true" />
      </span>
      <span className="brand-name">DevQuest</span>
    </div>

    <nav className="nav-list" aria-label="Primary navigation">
      {navItems.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink key={item.path} to={item.path} end={item.path === "/"} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} data-testid={`nav-link-${slug(item.label)}`} onClick={onClose}>
            <Icon size={23} weight="duotone" aria-hidden="true" />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
    </nav>

    <div className="sidebar-card streak-card" data-testid="sidebar-streak-card">
      <div className="mini-title"><Fire size={20} weight="fill" aria-hidden="true" /> Streak</div>
      <strong data-testid="streak-days-value">12 days</strong>
      <p>Keep it up!</p>
    </div>

    <div className="sidebar-card level-card" data-testid="sidebar-level-card">
      <div className="level-row">
        <ShieldStar size={34} weight="duotone" aria-hidden="true" />
        <div>
          <strong data-testid="level-value">Level 7</strong>
          <span data-testid="level-progress-label">450 / 700 XP</span>
        </div>
      </div>
      <div className="progress-track" data-testid="level-progress-track" aria-label="Level progress">
        <span className="progress-fill level-fill" style={{ width: "64%" }} data-testid="level-progress-fill" />
      </div>
    </div>
  </aside>
);

const Topbar = ({ onMenuClick }) => {
  const location = useLocation();
  const title = location.pathname === "/" ? "Good morning, Dishari" : navItems.find((item) => item.path === location.pathname)?.label || "DevQuest";

  return (
    <header className="topbar" data-testid="topbar">
      <button className="icon-button mobile-menu" onClick={onMenuClick} aria-label="Open navigation" data-testid="mobile-menu-button"><SidebarSimple size={24} weight="duotone" /></button>
      <div className="topbar-title">
        <h1 data-testid="page-title">{title}</h1>
        <p data-testid="page-subtitle">Plan the work, capture the learning, and keep momentum visible.</p>
      </div>
      <label className="search-box" data-testid="search-label">
        <MagnifyingGlass size={22} weight="duotone" aria-hidden="true" />
        <input data-testid="global-search-input" aria-label="Search tasks" placeholder="Search tasks..." />
      </label>
      <button className="theme-toggle" aria-label="Dark mode enabled" data-testid="theme-toggle-button">
        <SunDim size={22} weight="duotone" aria-hidden="true" />
        <span className="toggle-knob"><Moon size={18} weight="fill" aria-hidden="true" /></span>
      </button>
      <button className="bell-button" aria-label="View notifications" data-testid="notifications-button">
        <Bell size={28} weight="duotone" />
        <span data-testid="notification-count">3</span>
      </button>
      <button className="profile-button" aria-label="Open profile menu" data-testid="profile-menu-button">
        <span className="avatar" data-testid="profile-avatar">DM</span>
        <span data-testid="profile-name">Dishari Mukherjee</span>
        <CaretDown size={16} weight="bold" aria-hidden="true" />
      </button>
    </header>
  );
};

const StatCard = ({ label, value, detail, icon, tone, trend, down, progress, testId }) => (
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

const MissionCard = ({ task, index }) => {
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

const SchedulePanel = () => (
  <section className="surface schedule-panel" data-testid="schedule-panel">
    <div className="section-heading"><h2><CalendarBlank size={26} weight="duotone" aria-hidden="true" /> Today&apos;s Schedule</h2><NavLink to="/calendar" data-testid="view-calendar-link">View Calendar</NavLink></div>
    <div className="timeline" data-testid="schedule-timeline">
      {schedule.map((event) => (
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

const FocusWidget = ({ compact = false }) => {
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

const TaskTable = ({ tasks, onComplete, onStatusChange, onEdit, onToggleToday, onUpdateNotes }) => {
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

const emptyTaskForm = {
  title: "",
  description: "",
  source: "Custom",
  externalId: "",
  projectKey: "",
  type: "Task",
  priority: "Medium",
  status: "To Do",
  dueDate: "",
  startDate: "",
  estimatedMinutes: 60,
  actualMinutes: 0,
  xp: 60,
  labels: "",
  notes: "",
  workingToday: true,
  runAiEnrichment: true,
};

const formFromTask = (task) => ({
  title: task.title || "",
  description: task.description || "",
  source: task.source || "Custom",
  externalId: task.externalId || task.id || "",
  projectKey: task.projectKey || "",
  type: task.type || "Task",
  priority: task.priority || "Medium",
  status: task.status || "To Do",
  dueDate: task.dueDate || "",
  startDate: task.startDate || "",
  estimatedMinutes: task.time || 60,
  actualMinutes: task.actualMinutes || 0,
  xp: task.xp || 60,
  labels: (task.labels || []).join(", "),
  notes: task.notes || "",
  workingToday: Boolean(task.workingToday),
  runAiEnrichment: true,
});

const TaskEditor = ({ mode = "create", task, onSubmit, onCancel }) => {
  const [form, setForm] = useState(task ? formFromTask(task) : emptyTaskForm);

  useEffect(() => {
    setForm(task ? formFromTask(task) : emptyTaskForm);
  }, [task]);

  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const submit = (event) => {
    event.preventDefault();
    if (!form.title.trim()) return;
    onSubmit(form);
    if (mode === "create") setForm(emptyTaskForm);
  };

  return (
    <form className="task-editor-form" onSubmit={submit} data-testid={`${mode}-task-form`}>
      <label>Title<input value={form.title} onChange={(event) => update("title", event.target.value)} placeholder="Investigate CI failure" data-testid={`${mode}-task-title-input`} /></label>
      <label>Description<textarea value={form.description} onChange={(event) => update("description", event.target.value)} placeholder="What needs to happen?" data-testid={`${mode}-task-description-input`} /></label>
      <label>Type<select value={form.type} onChange={(event) => update("type", event.target.value)}>{taskTypes.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Source<select value={form.source} onChange={(event) => update("source", event.target.value)}>{sources.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>External ID<input value={form.externalId} onChange={(event) => update("externalId", event.target.value)} placeholder="PAY-2301" /></label>
      <label>Project key<input value={form.projectKey} onChange={(event) => update("projectKey", event.target.value)} placeholder="PAY" /></label>
      <label>Priority<select value={form.priority} onChange={(event) => update("priority", event.target.value)}>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Status<select value={form.status} onChange={(event) => update("status", event.target.value)}>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Due date<input type="date" value={form.dueDate} onChange={(event) => update("dueDate", event.target.value)} /></label>
      <label>Start date<input type="date" value={form.startDate} onChange={(event) => update("startDate", event.target.value)} /></label>
      <label>Estimated minutes<input type="number" min="0" value={form.estimatedMinutes} onChange={(event) => update("estimatedMinutes", event.target.value)} /></label>
      <label>Actual minutes<input type="number" min="0" value={form.actualMinutes} onChange={(event) => update("actualMinutes", event.target.value)} /></label>
      <label>XP<input type="number" min="0" value={form.xp} onChange={(event) => update("xp", event.target.value)} /></label>
      <label>Labels<input value={form.labels} onChange={(event) => update("labels", event.target.value)} placeholder="api, backend" /></label>
      <label className="wide-field">Notes<textarea value={form.notes} onChange={(event) => update("notes", event.target.value)} placeholder="Learnings, what went right, what went wrong, blockers..." data-testid={`${mode}-task-notes-input`} /></label>
      <label className="checkbox-field"><input type="checkbox" checked={form.workingToday} onChange={(event) => update("workingToday", event.target.checked)} /> Working on this today</label>
      <label className="checkbox-field"><input type="checkbox" checked={form.runAiEnrichment} onChange={(event) => update("runAiEnrichment", event.target.checked)} /> Run AI enrichment</label>
      <div className="editor-actions">
        {onCancel && <button type="button" className="ghost-button" onClick={onCancel} data-testid={`${mode}-task-cancel-button`}>Cancel</button>}
        <button className="primary-action" type="submit" data-testid={`${mode}-task-submit-button`}><Plus size={19} weight="bold" aria-hidden="true" /> {mode === "edit" ? "Save Task" : "Add Task"}</button>
      </div>
    </form>
  );
};

const taskFromForm = (form, existingTask) => {
  const status = form.status || "To Do";
  const completedAt = status === "Done" ? existingTask?.completedAt || nowIso() : existingTask?.completedAt && existingTask.status === "Done" ? undefined : existingTask?.completedAt;
  return normalizeTask({
    ...(existingTask || {}),
    id: existingTask?.id || makeTaskId(form.source, form.externalId),
    externalId: form.externalId || existingTask?.externalId || "",
    projectKey: form.projectKey,
    title: form.title.trim(),
    description: form.description,
    source: form.source,
    type: form.type,
    priority: form.priority,
    status,
    dueDate: form.dueDate,
    startDate: form.startDate,
    time: parseNumber(form.estimatedMinutes, 60),
    actualMinutes: parseNumber(form.actualMinutes, 0),
    xp: parseNumber(form.xp, 60),
    labels: form.labels,
    notes: form.notes,
    workingToday: form.workingToday,
    completedAt,
    aiInsight: form.runAiEnrichment ? "" : existingTask?.aiInsight,
  });
};

const completedTodayTasks = (tasks) => tasks.filter((task) => task.status === "Done" && isSameDay(task.completedAt));

const generateStandupNote = (tasks) => {
  const accomplished = completedTodayTasks(tasks);
  const inProgress = tasks.filter((task) => task.workingToday && task.status !== "Done" && task.status !== "Blocked");
  const blockers = tasks.filter((task) => task.status === "Blocked");
  const accomplishedText = accomplished.length ? accomplished.map((task) => task.title).join("; ") : "No completed tasks logged yet.";
  const inProgressText = inProgress.length ? inProgress.map((task) => task.title).join("; ") : "No active in-progress tasks selected.";
  const blockerText = blockers.length ? blockers.map((task) => `${task.title}${task.notes ? ` (${task.notes})` : ""}`).join("; ") : "No blockers captured.";
  return {
    accomplished: accomplishedText,
    inProgress: inProgressText,
    blockers: blockerText,
    nextSteps: inProgress.slice(0, 3).map((task) => task.aiInsight || `Continue ${task.title}`),
    fullNote: `Accomplished: ${accomplishedText}\nIn progress: ${inProgressText}\nBlockers: ${blockerText}`,
  };
};

const Dashboard = ({ tasks, onComplete, onStatusChange, onEdit, onToggleToday, onUpdateNotes }) => {
  const completedCount = completedTodayTasks(tasks).length;
  const todayTasks = tasks.filter((task) => task.workingToday);
  const totalXp = tasks.filter((task) => task.status === "Done").reduce((sum, task) => sum + task.xp, 2450);
  const topMissions = [...(todayTasks.length ? todayTasks : tasks.filter((task) => task.status !== "Done"))]
    .sort((a, b) => (b.priorityScore || 0) - (a.priorityScore || 0))
    .slice(0, 3);

  return (
    <main className="dashboard-page" data-testid="dashboard-page">
      <section className="stats-grid" aria-label="Daily productivity metrics">
        <StatCard label="Total XP" value={`${totalXp.toLocaleString()} XP`} detail="Includes completed work" icon={Trophy} tone="violet" trend testId="stat-total-xp" />
        <StatCard label="Tasks Completed" value={`${completedCount} today`} detail="Completion date is captured" icon={CheckCircle} tone="blue" progress={Math.min(100, (completedCount / Math.max(1, todayTasks.length)) * 100)} testId="stat-tasks-completed" />
        <StatCard label="Working Today" value={`${todayTasks.length} tasks`} detail="Feeds the Quests page" icon={Flag} tone="gold" testId="stat-working-today" />
        <StatCard label="Focus Time" value="2h 35m" detail="22% vs yesterday" icon={Clock} tone="green" trend testId="stat-focus-time" />
        <StatCard label="Meetings" value="3h 10m" detail="Tracked in overview" icon={CalendarBlank} tone="orange" trend down testId="stat-meetings" />
      </section>
      <div className="content-grid">
        <section className="surface missions-panel" data-testid="missions-panel"><div className="section-heading"><h2><Flag size={26} weight="duotone" aria-hidden="true" /> Today&apos;s Missions</h2><NavLink to="/quests" data-testid="view-all-missions-link">View quests</NavLink></div><div className="mission-list">{topMissions.map((task, index) => <MissionCard key={task.id} task={task} index={index} />)}</div></section>
        <SchedulePanel />
        <section className="surface my-tasks-panel" data-testid="my-tasks-panel"><div className="section-heading task-panel-heading"><h2><ListBullets size={26} weight="duotone" aria-hidden="true" /> My Tasks</h2><NavLink className="add-task-link" to="/tasks" data-testid="dashboard-add-task-link"><Plus size={19} weight="bold" aria-hidden="true" /> Add Task</NavLink></div><div className="tab-row" role="tablist" aria-label="Task filters">{["All", "Working Today", "Done", "Blocked"].map((tab, index) => <button key={tab} className={index === 0 ? "tab active" : "tab"} role="tab" data-testid={`task-filter-${slug(tab)}`}>{tab}</button>)}</div><TaskTable tasks={tasks} onComplete={onComplete} onStatusChange={onStatusChange} onEdit={onEdit} onToggleToday={onToggleToday} onUpdateNotes={onUpdateNotes} /></section>
        <aside className="right-stack" data-testid="right-stack"><FocusWidget compact /><section className="surface insight-card" data-testid="ai-insight-card"><div className="quote-mark" aria-hidden="true">&quot;</div><h2><Sparkle size={25} weight="duotone" aria-hidden="true" /> AI Insight</h2><p data-testid="ai-insight-text">{topMissions[0]?.aiInsight || "Select work for today to generate focused insights."}</p><div className="insight-grid"><span data-testid="ai-capacity-value">{formatMinutes(todayTasks.reduce((sum, task) => sum + task.time, 0))} planned</span><span data-testid="ai-impact-value">{Math.round((topMissions[0]?.priorityScore || 0) * 100)} priority score</span></div></section><section className="surface quote-card" data-testid="quote-card"><div className="quote-mark" aria-hidden="true">&quot;</div><p data-testid="quote-text">Discipline is the bridge between goals and accomplishment.</p><span data-testid="quote-author">- Jim Rohn</span></section></aside>
      </div>
      <p className="footer-note" data-testid="dashboard-footer-note">You&apos;re doing great. Keep the momentum going.</p>
    </main>
  );
};

const TasksPage = ({ tasks, onAddTask, onComplete, onStatusChange, onEdit, onToggleToday, onUpdateNotes }) => {
  const [editingTask, setEditingTask] = useState(null);

  return (
    <main className="page-stack" data-testid="tasks-page">
      <section className="surface form-card" data-testid="add-task-card">
        <div className="section-heading"><h2><Plus size={26} weight="duotone" aria-hidden="true" /> Add Task With Full Details</h2><span data-testid="task-count-label">{tasks.length} tasks loaded</span></div>
        <TaskEditor mode="create" onSubmit={(form) => onAddTask(taskFromForm(form))} />
      </section>
      {editingTask && (
        <section className="surface form-card" data-testid="edit-task-card">
          <div className="section-heading"><h2><FileText size={26} weight="duotone" aria-hidden="true" /> Edit Task</h2><span>{editingTask.id}</span></div>
          <TaskEditor mode="edit" task={editingTask} onSubmit={(form) => { onEdit(taskFromForm(form, editingTask)); setEditingTask(null); }} onCancel={() => setEditingTask(null)} />
        </section>
      )}
      <section className="surface" data-testid="unified-task-list-card">
        <div className="section-heading"><h2><Database size={26} weight="duotone" aria-hidden="true" /> Unified Task List</h2><button className="ghost-button" data-testid="task-filter-button"><FunnelSimple size={18} weight="duotone" aria-hidden="true" /> Filter</button></div>
        <TaskTable tasks={tasks} onComplete={onComplete} onStatusChange={onStatusChange} onEdit={setEditingTask} onToggleToday={onToggleToday} onUpdateNotes={onUpdateNotes} />
      </section>
    </main>
  );
};

const CalendarPage = ({ overview }) => <main className="page-stack" data-testid="calendar-page"><SchedulePanel /><section className="surface weekly-panel" data-testid="weekly-overview-card"><div className="section-heading"><h2><SquaresFour size={26} weight="duotone" aria-hidden="true" /> Weekly Overview</h2><NavLink to="/overview">Open overview</NavLink></div><div className="weekly-grid"><StatCard label="Completed" value="24 tasks" detail="6 more than last week" icon={CheckSquare} tone="green" trend testId="weekly-completed-stat" /><StatCard label="XP Earned" value="740 XP" detail="Level 8 is within reach" icon={Trophy} tone="violet" testId="weekly-xp-stat" /><StatCard label="Meeting Time" value={formatMinutes(overview.meetingMinutes)} detail="Tracked from calendar" icon={Clock} tone="blue" trend testId="weekly-time-stat" /></div></section></main>;

const FocusPage = () => <main className="focus-page" data-testid="focus-page"><FocusWidget /><section className="surface focus-guidance" data-testid="focus-guidance-card"><h2><Lightning size={26} weight="duotone" aria-hidden="true" /> Deep Work Protocol</h2><ul><li data-testid="focus-guidance-item-1">Start with the highest-impact mission.</li><li data-testid="focus-guidance-item-2">Mute distractions until the timer ends.</li><li data-testid="focus-guidance-item-3">Complete one status update after each session.</li></ul></section></main>;

const QuestsPage = ({ tasks }) => {
  const todayTasks = tasks.filter((task) => task.workingToday).sort((a, b) => (b.priorityScore || 0) - (a.priorityScore || 0));
  return (
    <main className="page-stack" data-testid="quests-page">
      <section className="surface missions-panel" data-testid="all-quests-panel">
        <div className="section-heading"><h2><Flag size={26} weight="duotone" aria-hidden="true" /> Daily Quest Board</h2><button className="primary-action" data-testid="generate-quests-button"><Sparkle size={19} weight="duotone" aria-hidden="true" /> Generate Quests</button></div>
        <div className="mission-list">{todayTasks.length ? todayTasks.map((task, index) => <MissionCard key={task.id} task={task} index={index} />) : <p className="empty-state">No tasks are marked as working today yet.</p>}</div>
      </section>
      <section className="surface" data-testid="daily-work-source-card">
        <div className="section-heading"><h2><Database size={26} weight="duotone" aria-hidden="true" /> Daily Work Source</h2><span>{todayKey()}</span></div>
        <div className="source-truth-grid">
          {todayTasks.map((task, index) => (
            <article className="source-row" key={task.id}>
              <strong>{index + 1}. {task.title}</strong>
              <span>{task.id} - {task.priority} - {task.time} mins planned - {task.xp} XP</span>
              <p>{task.notes || task.aiInsight}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
};

const InsightsPage = ({ tasks, onRefreshInsights }) => {
  const [standupNote, setStandupNote] = useState(() => generateStandupNote(tasks));
  const todayTasks = tasks.filter((task) => task.workingToday);
  const completed = completedTodayTasks(tasks);
  const topPriority = [...todayTasks].sort((a, b) => (b.priorityScore || 0) - (a.priorityScore || 0))[0];

  const refresh = () => {
    onRefreshInsights();
    setStandupNote(generateStandupNote(tasks));
  };

  return (
    <main className="page-stack" data-testid="insights-page">
      <section className="surface insight-detail-card" data-testid="capacity-analysis-card">
        <div className="section-heading"><h2><Sparkle size={26} weight="duotone" aria-hidden="true" /> AI Task Insights</h2><button className="ghost-button" onClick={refresh} data-testid="refresh-insights-button"><ArrowClockwise size={18} weight="duotone" aria-hidden="true" /> Refresh</button></div>
        <div className="capacity-grid">
          <StatCard label="Top Priority" value={topPriority?.priority || "None"} detail={topPriority?.title || "Mark a task for today"} icon={Flag} tone="red" testId="capacity-top-priority-stat" />
          <StatCard label="Planned Effort" value={formatMinutes(todayTasks.reduce((sum, task) => sum + task.time, 0))} detail="Working-today tasks" icon={Clock} tone="blue" testId="capacity-working-hours-stat" />
          <StatCard label="Today XP" value={`${completed.reduce((sum, task) => sum + task.xp, 0)} XP`} detail="Completed today" icon={Trophy} tone="green" testId="capacity-xp-stat" />
        </div>
        <div className="insight-list">
          {todayTasks.map((task) => <article key={task.id}><strong>{task.title}</strong><span>{Math.round((task.priorityScore || 0) * 100)} priority - {task.xp} XP - {task.time} min effort</span><p>{task.aiInsight}</p></article>)}
        </div>
      </section>
      <section className="surface standup-card" data-testid="standup-generator-card">
        <div className="section-heading"><h2><FileText size={26} weight="duotone" aria-hidden="true" /> Standup Note Generator</h2><button className="primary-action" onClick={() => setStandupNote(generateStandupNote(tasks))} data-testid="generate-standup-button"><Sparkle size={19} weight="duotone" aria-hidden="true" /> Generate</button></div>
        <pre className="standup-note" data-testid="standup-summary-text">{standupNote.fullNote}</pre>
        <div className="insight-grid">
          <span><strong>Accomplished</strong>{standupNote.accomplished}</span>
          <span><strong>In Progress</strong>{standupNote.inProgress}</span>
          <span><strong>Blockers</strong>{standupNote.blockers}</span>
        </div>
      </section>
    </main>
  );
};

const OverviewPage = ({ tasks, overview, onOverviewChange }) => {
  const completedToday = completedTodayTasks(tasks);
  const weekStart = startOfWeekKey();
  const completedWeek = tasks.filter((task) => task.status === "Done" && isWithinWeek(task.completedAt, weekStart));
  const dailyXp = completedToday.reduce((sum, task) => sum + task.xp, 0);
  const weeklyXp = completedWeek.reduce((sum, task) => sum + task.xp, 0);
  const notes = completedToday.map((task) => task.notes).filter(Boolean);
  const update = (field, value) => onOverviewChange({ ...overview, [field]: value });

  return (
    <main className="page-stack" data-testid="overview-page">
      <section className="surface" data-testid="daily-overview-card">
        <div className="section-heading"><h2><CalendarBlank size={26} weight="duotone" aria-hidden="true" /> Daily Overview</h2><span>{todayKey()}</span></div>
        <div className="overview-stats">
          <StatCard label="Tasks Accomplished" value={completedToday.length} detail={`${dailyXp} XP earned`} icon={CheckCircle} tone="green" testId="daily-completed-stat" />
          <StatCard label="Meetings" value={formatMinutes(overview.meetingMinutes)} detail="Editable daily tracker" icon={UsersThree} tone="orange" testId="daily-meetings-stat" />
          <StatCard label="Focus Time" value={formatMinutes(overview.focusMinutes)} detail="Deep-work estimate" icon={Timer} tone="blue" testId="daily-focus-stat" />
        </div>
        <div className="overview-editor">
          <label>Meeting minutes<input type="number" min="0" value={overview.meetingMinutes} onChange={(event) => update("meetingMinutes", parseNumber(event.target.value, 0))} /></label>
          <label>Focus minutes<input type="number" min="0" value={overview.focusMinutes} onChange={(event) => update("focusMinutes", parseNumber(event.target.value, 0))} /></label>
          <label>New learnings<textarea value={overview.newLearnings} onChange={(event) => update("newLearnings", event.target.value)} /></label>
          <label>Went well<textarea value={overview.wentWell} onChange={(event) => update("wentWell", event.target.value)} /></label>
          <label>Went wrong<textarea value={overview.wentWrong} onChange={(event) => update("wentWrong", event.target.value)} /></label>
        </div>
        <div className="accomplished-list">
          {completedToday.map((task) => <article key={task.id}><strong>{task.title}</strong><span>{formatDateTime(task.completedAt)} - {task.actualMinutes || task.time} mins - {task.xp} XP</span><p>{task.notes}</p></article>)}
        </div>
        <p className="insight-copy" data-testid="daily-overview-summary">Summary: {completedToday.length ? `Completed ${completedToday.length} task(s), earned ${dailyXp} XP, and captured ${notes.length} task note(s) for AI review.` : "No completions logged for today yet."}</p>
      </section>
      <section className="surface" data-testid="weekly-overview-card">
        <div className="section-heading"><h2><SquaresFour size={26} weight="duotone" aria-hidden="true" /> Weekly Overview</h2><span>{weekStart} to {addDaysKey(weekStart, 6)}</span></div>
        <div className="weekly-grid">
          <StatCard label="Completed" value={`${completedWeek.length} tasks`} detail={`${weeklyXp} XP earned`} icon={CheckSquare} tone="green" testId="overview-weekly-completed-stat" />
          <StatCard label="Meeting Time" value={formatMinutes(overview.meetingMinutes * 5)} detail="Projected from daily tracker" icon={CalendarBlank} tone="orange" testId="overview-weekly-meetings-stat" />
          <StatCard label="Focus Time" value={formatMinutes(overview.focusMinutes * 5)} detail="Projected from daily tracker" icon={Clock} tone="blue" testId="overview-weekly-focus-stat" />
        </div>
        <div className="theme-list">
          {[...new Set(completedWeek.flatMap((task) => task.labels || []))].slice(0, 5).map((theme) => <Pill key={theme} tone="task">{theme}</Pill>)}
        </div>
        <p className="insight-copy">Weekly summary: {completedWeek.length ? `The week is trending around ${completedWeek.slice(0, 3).map((task) => task.title).join(", ")}.` : "Complete tasks to build the weekly summary."}</p>
      </section>
    </main>
  );
};

const SyncPage = () => <main className="page-stack" data-testid="sync-page"><section className="surface sync-card" data-testid="sync-management-card"><div className="section-heading"><h2><CloudArrowDown size={26} weight="duotone" aria-hidden="true" /> Sync Center</h2><button className="primary-action" data-testid="run-sync-button"><CloudArrowDown size={19} weight="duotone" aria-hidden="true" /> Sync Now</button></div><div className="sync-grid">{["Jira", "Outlook Calendar", "Microsoft To Do"].map((source) => <article className="sync-source" key={source} data-testid={`sync-source-${slug(source)}`}><CheckCircle size={26} weight="duotone" aria-hidden="true" /><strong data-testid={`sync-source-title-${slug(source)}`}>{source}</strong><span data-testid={`sync-source-status-${slug(source)}`}>Ready to sync</span></article>)}</div></section></main>;

const SettingsPage = () => <main className="page-stack" data-testid="settings-page"><section className="surface settings-card" data-testid="settings-card"><div className="section-heading"><h2><GearSix size={26} weight="duotone" aria-hidden="true" /> Productivity Settings</h2></div><label className="settings-row" data-testid="working-hours-setting-label">Working hours<input value="09:00 - 17:00" readOnly data-testid="working-hours-setting-input" /></label><label className="settings-row" data-testid="xp-multiplier-setting-label">Focus XP multiplier<input value="1.5x" readOnly data-testid="xp-multiplier-setting-input" /></label></section></main>;

const AppShell = () => {
  const [tasks, setTasks] = useState(initialTasks);
  const [overview, setOverview] = useState(defaultOverview);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const statusCycle = useMemo(() => ["To Do", "In Progress", "Blocked", "Done"], []);

  const handleComplete = (id) => setTasks((items) => items.map((task) => (task.id === id ? normalizeTask({ ...task, status: "Done", completedAt: task.completedAt || nowIso() }) : task)));
  const handleStatusChange = (id) => setTasks((items) => items.map((task) => {
    if (task.id !== id) return task;
    const currentIndex = statusCycle.indexOf(task.status);
    const nextStatus = statusCycle[(currentIndex + 1) % statusCycle.length] || "To Do";
    return normalizeTask({ ...task, status: nextStatus, completedAt: nextStatus === "Done" ? task.completedAt || nowIso() : task.completedAt });
  }));
  const handleToggleToday = (id) => setTasks((items) => items.map((task) => (task.id === id ? normalizeTask({ ...task, workingToday: !task.workingToday }) : task)));
  const handleUpdateNotes = (id, notes) => setTasks((items) => items.map((task) => (task.id === id ? normalizeTask({ ...task, notes, aiInsight: "" }) : task)));
  const handleEditTask = (updatedTask) => setTasks((items) => items.map((task) => (task.id === updatedTask.id ? normalizeTask(updatedTask) : task)));
  const handleRefreshInsights = () => setTasks((items) => items.map((task) => normalizeTask({ ...task, aiInsight: "" })));

  return (
    <div className="app-shell" data-testid="app-shell">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <button className={`sidebar-scrim ${sidebarOpen ? "sidebar-scrim-active" : ""}`} aria-label="Close navigation" onClick={() => setSidebarOpen(false)} data-testid="sidebar-scrim-button" aria-hidden={!sidebarOpen} tabIndex={sidebarOpen ? 0 : -1} />
      <div className="workspace" data-testid="workspace">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <Routes>
          <Route path="/" element={<Dashboard tasks={tasks} onComplete={handleComplete} onStatusChange={handleStatusChange} onEdit={handleEditTask} onToggleToday={handleToggleToday} onUpdateNotes={handleUpdateNotes} />} />
          <Route path="/tasks" element={<TasksPage tasks={tasks} onAddTask={(task) => setTasks((items) => [task, ...items])} onComplete={handleComplete} onStatusChange={handleStatusChange} onEdit={handleEditTask} onToggleToday={handleToggleToday} onUpdateNotes={handleUpdateNotes} />} />
          <Route path="/calendar" element={<CalendarPage overview={overview} />} />
          <Route path="/focus" element={<FocusPage />} />
          <Route path="/quests" element={<QuestsPage tasks={tasks} />} />
          <Route path="/insights" element={<InsightsPage tasks={tasks} onRefreshInsights={handleRefreshInsights} />} />
          <Route path="/overview" element={<OverviewPage tasks={tasks} overview={overview} onOverviewChange={setOverview} />} />
          <Route path="/sync" element={<SyncPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
};

function App() {
  return <BrowserRouter><AppShell /></BrowserRouter>;
}

export default App;
