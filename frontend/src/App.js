import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowClockwise,
  Bell,
  Bug,
  CalendarBlank,
  CaretDown,
  CaretLeft,
  CaretRight,
  CheckCircle,
  CheckSquare,
  Clock,
  CloudArrowDown,
  Database,
  FileText,
  Fire,
  Flag,
  FloppyDisk,
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
  PencilSimple,
  Play,
  Plus,
  RocketLaunch,
  ShieldStar,
  SignOut,
  SidebarSimple,
  Sparkle,
  SquaresFour,
  SunDim,
  Timer,
  TrendDown,
  TrendUp,
  Trophy,
  UsersThree,
  X,
} from "@phosphor-icons/react";
import "./App.css";
import "./responsive-fixes.css";
import "./feature-additions.css";
import { authApi, CURRENT_USER_STORAGE_KEY, dashboardApi, overviewApi, tasksApi } from "./api/client";
import { activeFocusSeconds, ACTIVE_FOCUS_STORAGE_KEY, createFocusId, FOCUS_SESSIONS_STORAGE_KEY, focusMinutesForSessions, focusOutcomes, orderedFocusTasks, sessionsForDay, sessionMinutes, topFocusedTask } from "./features/focus/focusSessions";
import { applyActiveQuest, clearQuestRun, compareQuestTasks, deriveQuestProgress, generateQuestRun, getNextQuest, getOpenQuestForTask, getQuestById, getQuestOrderedTasks, getQuestTask, isCurrentQuestRun, isUsableQuestRun, questActionLabel, questGeneratedLabel, questProgressSummary, questRationale, readQuestRun, saveQuestRun, skipReasons } from "./features/quests/questRun";
import { readStoredJson, removeStoredJson, writeStoredJson } from "./utils/storage";

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
const statuses = ["To Do", "In Progress", "Blocked", "Done"];
const tableStatuses = ["To Do", "In Progress", "Blocked", "Done"];
const sources = ["Custom", "Jira", "Outlook", "Microsoft To Do"];

const todayKey = () => new Date().toLocaleDateString("en-CA");
const nowIso = () => new Date().toISOString();

const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

const profileFirstName = (user) => user?.first_name || user?.firstName || "User";
const profileLastName = (user) => user?.last_name || user?.lastName || "";
const profileFullName = (user) => [profileFirstName(user), profileLastName(user)].filter(Boolean).join(" ");
const profileInitials = (user) => {
  const first = profileFirstName(user).charAt(0);
  const last = profileLastName(user).charAt(0);
  return `${first}${last || ""}`.toUpperCase();
};

const readCurrentUser = () => {
  try {
    return JSON.parse(window.localStorage.getItem(CURRENT_USER_STORAGE_KEY) || "null");
  } catch {
    return null;
  }
};

const authErrorMessage = (error, fallback) => error?.response?.data?.detail?.message || error?.message || fallback;

const truncateText = (value, maxLength = 46) => {
  const text = String(value || "");
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}...` : text;
};

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

const formatTime = (isoValue) => {
  if (!isoValue) return "";
  return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date(isoValue));
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
  const calculatedPriorityScore = Math.min(0.99, Math.round(((priorityWeight * 0.58 + impact * 0.32 + Math.min(effort / 60, 4) * 0.1) / 10) * 100) / 100);
  const xp = Math.max(10, parseNumber(task.xp, Math.round((effort * 0.75 + impact * 9 + priorityWeight * 5) / 10) * 10));
  const difficulty = effort >= 105 || priorityWeight >= 9 ? "Hard" : effort <= 35 && priorityWeight <= 5 ? "Easy" : "Medium";
  return {
    difficulty: task.difficulty || difficulty,
    impact,
    priorityScore: Number.isFinite(Number(task.priorityScore)) ? Number(task.priorityScore) : calculatedPriorityScore,
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

const TASKS_STORAGE_KEY = "devquest.tasks.v1";

const readStoredTasks = () => {
  const storedTasks = readStoredJson(TASKS_STORAGE_KEY, null);
  return Array.isArray(storedTasks) ? storedTasks.map(normalizeTask) : initialTasks;
};

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

const normalizeApiTask = (task) =>
  normalizeTask({
    id: String(task.external_id || task.task_id),
    taskId: task.task_id,
    externalId: task.external_id || "",
    title: task.title,
    description: task.description,
    source: task.external_source || "Custom",
    type: task.task_type || "Task",
    priority: task.priority || "Medium",
    status: task.status || "To Do",
    time: task.estimated_minutes || task.ai?.effort_minutes || 60,
    actualMinutes: task.actual_minutes || 0,
    xp: task.xp_value || 0,
    workingToday: Boolean(task.working_today),
    completedAt: task.completed_at,
    impact: task.ai?.impact_score || 5,
    priorityScore: task.ai?.priority_score,
    difficulty: task.ai?.difficulty,
    aiInsight: task.ai?.insight,
    notes: task.notes || "",
    labels: [],
  });

const normalizeApiSchedule = (events = []) =>
  events.map((event) => ({
    time: formatTime(event.start_at),
    title: event.title,
    duration: event.is_focus_block ? `${formatMinutes(event.duration_minutes)} available` : formatMinutes(event.duration_minutes),
    durationMinutes: event.duration_minutes,
    color: event.is_focus_block ? "green" : "blue",
    focus: Boolean(event.is_focus_block),
  }));

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

const AuthPage = ({ onAuthenticated }) => {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    username: "",
    email: "",
    identifier: "",
    password: "",
    confirmPassword: "",
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [authError, setAuthError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const update = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: "" }));
    setAuthError("");
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setFieldErrors({});
    setAuthError("");
  };

  const validate = () => {
    const errors = {};
    if (mode === "login") {
      if (!form.identifier.trim()) errors.identifier = "Enter your username or email.";
      if (!form.password) errors.password = "Enter your password.";
    } else {
      if (!form.firstName.trim()) errors.firstName = "First name is required.";
      if (!form.lastName.trim()) errors.lastName = "Last name is required.";
      if (!form.username.trim()) errors.username = "Username is required.";
      if (!form.email.trim()) errors.email = "Email is required.";
      else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) errors.email = "Enter a valid email address.";
      if (!form.password) errors.password = "Password is required.";
      if (!form.confirmPassword) errors.confirmPassword = "Confirm your password.";
      else if (form.password !== form.confirmPassword) errors.confirmPassword = "Passwords must match.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const completeAuth = async (profileIdentifier) => {
    const profile = await authApi.getProfile(profileIdentifier);
    window.localStorage.setItem(CURRENT_USER_STORAGE_KEY, JSON.stringify(profile));
    onAuthenticated(profile);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!validate()) return;
    setIsSubmitting(true);
    setAuthError("");
    try {
      if (mode === "login") {
        const loginResult = await authApi.login({ identifier: form.identifier.trim(), password: form.password });
        await completeAuth(loginResult.username || loginResult.email || form.identifier.trim());
      } else {
        const created = await authApi.register({
          first_name: form.firstName.trim(),
          last_name: form.lastName.trim(),
          username: form.username.trim(),
          email: form.email.trim(),
          password: form.password,
          confirm_password: form.confirmPassword,
        });
        await completeAuth(created.username || form.username.trim());
      }
    } catch (error) {
      setAuthError(authErrorMessage(error, mode === "login" ? "Unable to log in." : "Unable to create account."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="auth-page" data-testid="auth-page">
      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-brand">
          <span className="brand-mark"><RocketLaunch size={34} weight="fill" aria-hidden="true" /></span>
          <span className="brand-name">DevQuest</span>
        </div>
        <div className="auth-heading">
          <h1 id="auth-title">{mode === "login" ? "Welcome back" : "Create your profile"}</h1>
          <p>{mode === "login" ? "Log in to continue your task dashboard." : "Set up your local profile to personalize DevQuest."}</p>
        </div>
        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")} data-testid="login-mode-button">Login</button>
          <button type="button" role="tab" aria-selected={mode === "create"} className={mode === "create" ? "active" : ""} onClick={() => switchMode("create")} data-testid="create-mode-button">Create Account</button>
        </div>
        <form className="auth-form" onSubmit={submit} noValidate data-testid={`${mode}-auth-form`}>
          {mode === "create" && (
            <>
              <label>First Name<input value={form.firstName} onChange={(event) => update("firstName", event.target.value)} autoComplete="given-name" data-testid="first-name-input" /></label>
              {fieldErrors.firstName && <span className="field-error">{fieldErrors.firstName}</span>}
              <label>Last Name<input value={form.lastName} onChange={(event) => update("lastName", event.target.value)} autoComplete="family-name" data-testid="last-name-input" /></label>
              {fieldErrors.lastName && <span className="field-error">{fieldErrors.lastName}</span>}
              <label>User Name<input value={form.username} onChange={(event) => update("username", event.target.value)} autoComplete="username" data-testid="username-input" /></label>
              {fieldErrors.username && <span className="field-error">{fieldErrors.username}</span>}
              <label>Email address<input type="email" value={form.email} onChange={(event) => update("email", event.target.value)} autoComplete="email" data-testid="email-input" /></label>
              {fieldErrors.email && <span className="field-error">{fieldErrors.email}</span>}
            </>
          )}
          {mode === "login" && (
            <>
              <label>Username or email<input value={form.identifier} onChange={(event) => update("identifier", event.target.value)} autoComplete="username" data-testid="login-identifier-input" /></label>
              {fieldErrors.identifier && <span className="field-error">{fieldErrors.identifier}</span>}
            </>
          )}
          <label>Password<input type="password" value={form.password} onChange={(event) => update("password", event.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} data-testid="password-input" /></label>
          {fieldErrors.password && <span className="field-error">{fieldErrors.password}</span>}
          {mode === "create" && (
            <>
              <label>Confirm Password<input type="password" value={form.confirmPassword} onChange={(event) => update("confirmPassword", event.target.value)} autoComplete="new-password" data-testid="confirm-password-input" /></label>
              {fieldErrors.confirmPassword && <span className="field-error">{fieldErrors.confirmPassword}</span>}
            </>
          )}
          {authError && <p className="form-error auth-error" role="alert" data-testid="auth-error">{authError}</p>}
          <button className="primary-action auth-submit" type="submit" disabled={isSubmitting} data-testid="auth-submit-button">
            <ShieldStar size={19} weight="duotone" aria-hidden="true" />
            {isSubmitting ? "Please wait..." : mode === "login" ? "Login" : "Create Account"}
          </button>
        </form>
      </section>
    </main>
  );
};

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

const Topbar = ({ currentUser, isLoggingOut, onLogout, onMenuClick }) => {
  const location = useLocation();
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const title = location.pathname === "/" ? `Good morning, ${profileFirstName(currentUser)}` : navItems.find((item) => item.path === location.pathname)?.label || "DevQuest";
  const subtitle = location.pathname === "/focus" ? "Track deep work against a task." : "Plan the work, capture the learning, and keep momentum visible.";

  return (
    <header className="topbar" data-testid="topbar">
      <button className="icon-button mobile-menu" onClick={onMenuClick} aria-label="Open navigation" data-testid="mobile-menu-button"><SidebarSimple size={24} weight="duotone" /></button>
      <div className="topbar-title">
        <h1 data-testid="page-title">{title}</h1>
        <p data-testid="page-subtitle">{subtitle}</p>
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
      <div className="profile-cluster">
        <button
          className="profile-button"
          aria-label={`Profile for ${profileFullName(currentUser)}`}
          aria-haspopup="menu"
          aria-expanded={isProfileMenuOpen}
          onClick={() => setIsProfileMenuOpen((value) => !value)}
          data-testid="profile-menu-button"
        >
          <span className="avatar" data-testid="profile-avatar">{profileInitials(currentUser)}</span>
          <span data-testid="profile-name">{profileFullName(currentUser)}</span>
          <CaretDown size={16} weight="bold" aria-hidden="true" />
        </button>
        {isProfileMenuOpen && (
          <div className="profile-menu" role="menu" data-testid="profile-dropdown-menu">
            <button
              type="button"
              role="menuitem"
              onClick={onLogout}
              disabled={isLoggingOut}
              data-testid="logout-button"
            >
              <SignOut size={20} weight="duotone" aria-hidden="true" />
              <span>{isLoggingOut ? "Logging out..." : "Logout"}</span>
            </button>
          </div>
        )}
      </div>
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

const CompletionUndoNotice = ({ undo, onUndo }) => {
  if (!undo) return null;
  return (
    <div className="completion-undo-notice" data-testid="completion-undo-notice" role="status">
      <span><strong>{undo.taskTitle}</strong> was marked Done.</span>
      <button className="ghost-button" type="button" onClick={onUndo} data-testid="completion-undo-button">Undo</button>
    </div>
  );
};

const MissionCard = ({ task, index, questMeta }) => {
  const Icon = task.icon;
  return (
    <article className={`mission-card mission-${task.accent}`} data-testid={`mission-card-${slug(task.id)}`}>
      <IconBadge icon={Icon} tone={task.accent} testId={`mission-icon-${slug(task.id)}`} />
      <div className="mission-copy">
        <div className="mission-title-row">
          <h3 data-testid={`mission-title-${slug(task.id)}`}>{task.title}</h3>
          <Pill tone={task.type.toLowerCase()} testId={`mission-type-${slug(task.id)}`}>{task.type}</Pill>
          <Pill tone={slug(task.status)} testId={`mission-status-${slug(task.id)}`}>{task.status}</Pill>
        </div>
        <p className="mission-meta" data-testid={`mission-meta-${slug(task.id)}`}>{task.source} - {task.id}</p>
        <p data-testid={`mission-description-${slug(task.id)}`}>{task.aiInsight || task.description}</p>
        {questMeta && <p className="quest-rationale" data-testid={`quest-rationale-${slug(task.id)}`}>{questMeta.rationale}</p>}
      </div>
      <div className="mission-score">
        {questMeta && <span className={`quest-action quest-action-${slug(task.status)}`} data-testid={`quest-action-${slug(task.id)}`}>{questMeta.action}</span>}
        <Pill tone={task.priority.toLowerCase()} testId={`mission-priority-${slug(task.id)}`}>{task.priority}</Pill>
        <span data-testid={`mission-time-${slug(task.id)}`}><Clock size={16} weight="duotone" aria-hidden="true" /> {task.time} mins</span>
        <strong data-testid={`mission-xp-${slug(task.id)}`}>{task.xp} XP</strong>
        <span className="mission-rank" data-testid={`mission-rank-${slug(task.id)}`}>#{index + 1}</span>
      </div>
    </article>
  );
};

const SchedulePanel = ({ events = schedule }) => (
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

const FocusWidget = ({ tasks = [], focusSessions = [], activeSession, questContext, onStartFocus, onPauseFocus, onResumeFocus, onStopFocus, onCompleteQuest, compact = false }) => {
  const taskOptions = useMemo(() => orderedFocusTasks(tasks), [tasks]);
  const [selectedTaskId, setSelectedTaskId] = useState(() => activeSession?.task_id || taskOptions[0]?.id || "");
  const [outcomeType, setOutcomeType] = useState("Progress made");
  const [outcomeNote, setOutcomeNote] = useState("");
  const [, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!selectedTaskId && taskOptions[0]?.id) setSelectedTaskId(taskOptions[0].id);
  }, [selectedTaskId, taskOptions]);

  useEffect(() => {
    if (activeSession?.task_id) setSelectedTaskId(activeSession.task_id);
  }, [activeSession?.task_id]);

  useEffect(() => {
    if (!activeSession?.isRunning) return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [activeSession?.isRunning]);

  const elapsedSeconds = activeFocusSeconds(activeSession);
  const todaySessions = sessionsForDay(focusSessions);
  const focusedToday = focusMinutesForSessions(todaySessions);
  const selectedTask = tasks.find((task) => task.id === selectedTaskId);
  const selectedTaskSessions = selectedTask ? todaySessions.filter((session) => session.task_id === selectedTask.id) : [];
  const selectedTaskFocusedToday = focusMinutesForSessions(selectedTaskSessions);
  const selectedQuest = questContext && selectedTask && questContext.task?.id === selectedTask.id ? questContext.quest : null;
  const selectedQuestFocusMinutes = selectedQuest ? selectedQuest.focusMinutes : selectedTaskFocusedToday;
  const selectedQuestTargetMinutes = selectedQuest?.focusTargetMinutes || selectedTask?.time || 0;
  const progress = Math.min(360, (elapsedSeconds / (25 * 60)) * 360);
  const statusLabel = activeSession?.isRunning ? "In focus" : activeSession ? "Paused" : "Ready to start";
  const plannedMinutes = selectedTask ? formatMinutes(selectedTask.time) : "No task";
  const hasTasks = taskOptions.length > 0;

  const startFocus = () => {
    if (!selectedTask) return;
    onStartFocus(selectedTask);
  };

  const stopFocus = () => {
    if (elapsedSeconds > 0 && elapsedSeconds < 120 && !window.confirm("This session was under 2 minutes. Save it anyway?")) return;
    onStopFocus({ outcomeType, outcomeNote });
    setOutcomeNote("");
    setOutcomeType("Progress made");
  };

  return (
    <section className={`surface focus-widget ${compact ? "focus-compact" : ""}`} data-testid="focus-widget">
      <div className="section-heading focus-heading">
        <h2><Timer size={26} weight="duotone" aria-hidden="true" /> Current session</h2>
        <span data-testid="focus-today-pill">{formatMinutes(focusedToday)} today</span>
      </div>
      <div className="focus-hero-grid">
        <div className="timer-ring focus-session-ring" style={{ "--timer-progress": `${progress}deg` }} data-testid="focus-timer-ring" aria-label="Focus session progress">
          <div><strong data-testid="focus-timer-value">{formatTimer(elapsedSeconds)}</strong><span data-testid="focus-timer-label">{statusLabel}</span></div>
        </div>
      </div>
      <label className="focus-task-picker">
        Focus task
        <select value={selectedTaskId} onChange={(event) => setSelectedTaskId(event.target.value)} disabled={Boolean(activeSession) || !hasTasks} data-testid="focus-task-select">
          {taskOptions.map((task) => <option key={task.id} value={task.id}>{task.workingToday ? "Today - " : ""}{truncateText(task.title, 24)}</option>)}
          {!taskOptions.length && <option value="">No open tasks</option>}
        </select>
      </label>
      {!compact && selectedTask && (
        <article className="focus-selected-task" data-testid="focus-selected-task">
          <div>
            <span>{selectedTask.source}</span>
            <strong>{selectedTask.title}</strong>
            <p>{selectedTask.description}</p>
          </div>
          <div className="focus-selected-meta" aria-label="Selected task details">
            <Pill tone={selectedTask.priority.toLowerCase()}>{selectedTask.priority}</Pill>
            <span>{plannedMinutes}</span>
            <span>{formatMinutes(selectedTaskFocusedToday)} today</span>
            {selectedQuest && <span data-testid="focus-quest-target">{formatMinutes(selectedQuestFocusMinutes)} / {formatMinutes(selectedQuestTargetMinutes)} quest</span>}
          </div>
        </article>
      )}
      {!compact && !selectedTask && <p className="focus-helper-text" data-testid="focus-helper-text">Choose a task to start a session.</p>}
      {!compact && activeSession && (
        <div className="focus-outcome-panel" data-testid="focus-outcome-panel">
          <span>Wrap up session</span>
          <div className="focus-chip-row">
            {focusOutcomes.map((outcome) => <button key={outcome} className={`focus-chip ${outcomeType === outcome ? "active" : ""}`} onClick={() => setOutcomeType(outcome)} type="button">{outcome}</button>)}
          </div>
          <textarea value={outcomeNote} onChange={(event) => setOutcomeNote(event.target.value)} placeholder="What changed during this session?" data-testid="focus-outcome-note" />
        </div>
      )}
      <div className="focus-actions">
        {!activeSession && <button className="primary-action" onClick={startFocus} disabled={!selectedTask} data-testid="focus-start-pause-button"><Play size={20} weight="fill" aria-hidden="true" /> Start session</button>}
        {activeSession?.isRunning && <button className="primary-action" onClick={onPauseFocus} data-testid="focus-pause-button"><Hourglass size={20} weight="duotone" aria-hidden="true" /> Pause</button>}
        {activeSession && !activeSession.isRunning && <button className="primary-action" onClick={onResumeFocus} data-testid="focus-resume-button"><Play size={20} weight="fill" aria-hidden="true" /> Resume</button>}
        {activeSession && <button className="ghost-button focus-save-action" onClick={stopFocus} data-testid="focus-stop-button"><CheckCircle size={20} weight="duotone" aria-hidden="true" /> Stop &amp; save</button>}
        {!compact && selectedQuest && !activeSession && onCompleteQuest && <button className="ghost-button success-action" onClick={() => onCompleteQuest(selectedQuest.id)} data-testid="focus-complete-quest-button"><CheckCircle size={20} weight="duotone" aria-hidden="true" /> Complete Quest</button>}
      </div>
      {activeSession && <p className="focus-active-copy" data-testid="focus-active-copy">Focusing on <strong>{activeSession.task_title}</strong>.</p>}
    </section>
  );
};

const TaskTable = ({ tasks, onStatusChange, onEdit, onToggleToday, onUpdateNotes, editable = true }) => {
  const [noteDrafts, setNoteDrafts] = useState({});
  const [dirtyNotes, setDirtyNotes] = useState({});
  const [savingNoteId, setSavingNoteId] = useState(null);

  useEffect(() => {
    setNoteDrafts((current) => tasks.reduce((drafts, task) => {
      drafts[task.id] = Object.prototype.hasOwnProperty.call(current, task.id) ? current[task.id] : task.notes || "";
      return drafts;
    }, {}));
    setDirtyNotes((current) => tasks.reduce((dirty, task) => {
      if (current[task.id]) dirty[task.id] = true;
      return dirty;
    }, {}));
  }, [tasks]);

  const updateNoteDraft = (task, value) => {
    setNoteDrafts((current) => ({ ...current, [task.id]: value }));
    setDirtyNotes((current) => ({ ...current, [task.id]: value !== (task.notes || "") }));
  };

  const saveNoteDraft = async (task) => {
    const notes = noteDrafts[task.id] ?? "";
    setSavingNoteId(task.id);
    try {
      await onUpdateNotes(task.id, notes, true);
      setNoteDrafts((current) => ({ ...current, [task.id]: notes }));
      setDirtyNotes((current) => ({ ...current, [task.id]: false }));
    } finally {
      setSavingNoteId(null);
    }
  };

  const cancelNoteDraft = (task) => {
    setNoteDrafts((current) => ({ ...current, [task.id]: task.notes || "" }));
    setDirtyNotes((current) => ({ ...current, [task.id]: false }));
  };

  return (
    <div className="task-table-wrap" data-testid="task-table-wrap">
      <table className="task-table enriched-task-table" data-testid="task-table">
        <thead><tr><th>Task</th><th>Today</th><th>Source</th><th>Priority</th><th>AI</th><th>Effort</th><th>XP</th><th>Completed</th><th>Status</th><th>Notes</th>{editable && <th>Action</th>}</tr></thead>
        <tbody>
          {tasks.map((task) => {
            const Icon = task.icon;
            const hasUnsavedNote = Boolean(dirtyNotes[task.id]);
            const isSavingNote = savingNoteId === task.id;
            return (
              <tr key={task.id} data-testid={`task-row-${slug(task.id)}`}>
                <td data-testid={`task-title-cell-${slug(task.id)}`}>
                  <span className={`tiny-task-icon tiny-${task.accent}`}><Icon size={20} weight="duotone" aria-hidden="true" /></span>
                  <span className="task-title-stack"><strong>{task.title}</strong><small>{task.description}</small></span>
                </td>
                <td>
                  <button
                    onClick={() => onToggleToday(task.id)}
                    className={`today-toggle ${task.status !== "Done" && task.workingToday ? "active" : ""}`}
                    disabled={task.status === "Done"}
                    data-testid={`task-today-button-${slug(task.id)}`}
                  >
                    {task.status === "Done" ? "Done" : task.workingToday ? "Working" : "Add"}
                  </button>
                </td>
                <td data-testid={`task-source-${slug(task.id)}`}>{task.source}</td>
                <td><Pill tone={task.priority.toLowerCase()} testId={`task-priority-${slug(task.id)}`}>{task.priority}</Pill></td>
                <td className="ai-cell" data-testid={`task-ai-${slug(task.id)}`}><span className="ai-score">{Math.round((task.priorityScore || 0) * 100)}%</span><span>{task.difficulty} - impact {task.impact}/10</span></td>
                <td data-testid={`task-time-${slug(task.id)}`}>{task.time} mins</td>
                <td data-testid={`task-xp-${slug(task.id)}`}>{task.xp} XP</td>
                <td data-testid={`task-completed-${slug(task.id)}`}>{formatDateTime(task.completedAt)}</td>
                <td>
                  <select
                    className={`status-select status-select-${slug(task.status)}`}
                    value={task.status}
                    onChange={(event) => onStatusChange(task.id, event.target.value)}
                    data-testid={`task-status-${slug(task.id)}`}
                    aria-label={`Status for ${task.title}`}
                  >
                    {tableStatuses.map((status) => <option key={status} value={status}>{status}</option>)}
                  </select>
                </td>
                <td className="notes-cell">
                  <textarea
                    className={`inline-notes ${editable ? "" : "inline-notes-readonly"}`}
                    value={noteDrafts[task.id] ?? task.notes ?? ""}
                    onChange={(event) => updateNoteDraft(task, event.target.value)}
                    readOnly={!editable}
                    aria-label={`Notes for ${task.title}`}
                    data-testid={`task-notes-${slug(task.id)}`}
                  />
                </td>
                {editable && (
                  <td className="action-menu-cell">
                    {hasUnsavedNote ? (
                      <span className="row-action-group">
                        <button
                          className="row-icon-action row-icon-save"
                          aria-label={`Save notes for ${task.title}`}
                          title="Save notes"
                          onClick={() => saveNoteDraft(task)}
                          disabled={isSavingNote}
                          data-testid={`task-save-notes-button-${slug(task.id)}`}
                        >
                          <FloppyDisk size={19} weight="duotone" />
                        </button>
                        <button
                          className="row-icon-action row-icon-cancel"
                          aria-label={`Discard note changes for ${task.title}`}
                          title="Discard changes"
                          onClick={() => cancelNoteDraft(task)}
                          disabled={isSavingNote}
                          data-testid={`task-cancel-notes-button-${slug(task.id)}`}
                        >
                          <X size={18} weight="bold" />
                        </button>
                      </span>
                    ) : (
                      <button
                        className="row-icon-action"
                        aria-label={`Edit ${task.title}`}
                        title="Edit task"
                        onClick={() => onEdit(task)}
                        data-testid={`task-edit-button-${slug(task.id)}`}
                      >
                        <PencilSimple size={19} weight="duotone" />
                      </button>
                    )}
                  </td>
                )}
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
  labels: (task.labels || []).join(", "),
  notes: task.notes || "",
  workingToday: Boolean(task.workingToday),
  runAiEnrichment: true,
});

const TaskEditor = ({ mode = "create", task, onSubmit, onCancel }) => {
  const [form, setForm] = useState(task ? formFromTask(task) : emptyTaskForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    setForm(task ? formFromTask(task) : emptyTaskForm);
  }, [task]);

  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const submit = async (event) => {
    event.preventDefault();
    if (!form.title.trim()) return;
    setIsSubmitting(true);
    setSubmitError("");
    try {
      await onSubmit(form);
      if (mode === "create") setForm(emptyTaskForm);
    } catch (error) {
      setSubmitError(error?.response?.data?.detail?.message || error?.message || "Unable to save task.");
    } finally {
      setIsSubmitting(false);
    }
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
      <label>Labels<input value={form.labels} onChange={(event) => update("labels", event.target.value)} placeholder="api, backend" /></label>
      <label className="wide-field">Notes<textarea value={form.notes} onChange={(event) => update("notes", event.target.value)} placeholder="Learnings, what went right, what went wrong, blockers..." data-testid={`${mode}-task-notes-input`} /></label>
      <label className="checkbox-field"><input type="checkbox" checked={form.workingToday} onChange={(event) => update("workingToday", event.target.checked)} /> Working on this today</label>
      <label className="checkbox-field"><input type="checkbox" checked={form.runAiEnrichment} onChange={(event) => update("runAiEnrichment", event.target.checked)} /> Run AI enrichment</label>
      {submitError && <p className="form-error" role="alert">{submitError}</p>}
      <div className="editor-actions">
        {onCancel && <button type="button" className="ghost-button" onClick={onCancel} disabled={isSubmitting} data-testid={`${mode}-task-cancel-button`}>Cancel</button>}
        <button className="primary-action" type="submit" disabled={isSubmitting} data-testid={`${mode}-task-submit-button`}>
          {mode === "create" && <Plus size={19} weight="bold" aria-hidden="true" />}
          {isSubmitting ? "Saving..." : mode === "edit" ? "Save Task" : "Add Task"}
        </button>
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
    time: existingTask?.time,
    actualMinutes: existingTask?.actualMinutes,
    xp: existingTask?.xp,
    labels: form.labels,
    notes: form.notes,
    workingToday: form.workingToday,
    completedAt,
    aiInsight: form.runAiEnrichment ? "" : existingTask?.aiInsight,
  });
};

const completedTodayTasks = (tasks) => tasks.filter((task) => task.status === "Done" && isSameDay(task.completedAt));

const uniqueTasksById = (tasks) => [...new Map(tasks.filter(Boolean).map((task) => [task.id, task])).values()];

const dashboardTaskFilters = ["All", "Working Today", "Done"];

const filterDashboardTasks = (tasks, filter) => {
  if (filter === "Working Today") return tasks.filter((task) => task.workingToday);
  if (filter === "Done") return tasks.filter((task) => task.status === "Done");
  return tasks;
};

const emptyTaskFilters = {
  search: "",
  status: "All",
  source: "All",
  priority: "All",
  today: "All",
};

const filterUnifiedTasks = (tasks, filters) => {
  const search = filters.search.trim().toLowerCase();
  return tasks.filter((task) => {
    if (filters.status !== "All" && task.status !== filters.status) return false;
    if (filters.source !== "All" && task.source !== filters.source) return false;
    if (filters.priority !== "All" && task.priority !== filters.priority) return false;
    if (filters.today === "Working" && !task.workingToday) return false;
    if (filters.today === "Not Working" && task.workingToday) return false;
    if (!search) return true;
    return [task.title, task.description, task.notes, task.id, task.source, task.priority, task.status]
      .some((value) => String(value || "").toLowerCase().includes(search));
  });
};

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

const Dashboard = ({ tasks, questRun, focusSessions, activeSession, onStartFocus, onPauseFocus, onResumeFocus, onStopFocus, onStatusChange, onEdit, onToggleToday, onUpdateNotes, dashboardStats, dashboardSchedule, dashboardInsight, dashboardStatus }) => {
  const [activeTaskFilter, setActiveTaskFilter] = useState("All");
  const completedCount = dashboardStats?.tasks_completed_today ?? completedTodayTasks(tasks).length;
  const todayTasks = tasks.filter((task) => task.workingToday);
  const filteredTasks = useMemo(() => filterDashboardTasks(tasks, activeTaskFilter), [tasks, activeTaskFilter]);
  const totalXp = dashboardStats?.total_xp ?? tasks.filter((task) => task.status === "Done").reduce((sum, task) => sum + task.xp, 2450);
  const focusedToday = dashboardStats?.focus_minutes ?? dashboardStats?.available_focus_minutes ?? focusMinutesForSessions(sessionsForDay(focusSessions));
  const meetingMinutes = dashboardStats?.meeting_minutes;
  const nextQuest = getNextQuest(questRun);
  const nextQuestTask = getQuestTask(tasks, nextQuest);
  const orderedQuestTasks = getQuestOrderedTasks(tasks, questRun);
  const completedToday = completedTodayTasks(tasks);
  const runMissionTasks = isCurrentQuestRun(questRun) ? [
    nextQuestTask,
    ...(questRun.quests || []).filter((quest) => quest.id !== nextQuest?.id).map((quest) => getQuestTask(tasks, quest)),
  ].filter(Boolean) : [];
  const missionSourceTasks = runMissionTasks.length ? runMissionTasks : orderedQuestTasks.length ? orderedQuestTasks : [...tasks].sort(compareQuestTasks);
  const topMissions = uniqueTasksById([...missionSourceTasks.slice(0, 3), ...completedToday]);

  return (
    <main className="dashboard-page" data-testid="dashboard-page">
      <section className="stats-grid" aria-label="Daily productivity metrics">
        <StatCard label="Total XP" value={`${totalXp.toLocaleString()} XP`} detail="Includes completed work" icon={Trophy} tone="violet" trend testId="stat-total-xp" />
        <StatCard label="Tasks Completed" value={`${completedCount} today`} detail="Completion date is captured" icon={CheckCircle} tone="blue" progress={Math.min(100, (completedCount / Math.max(1, todayTasks.length)) * 100)} testId="stat-tasks-completed" />
        <StatCard label="Working Today" value={`${todayTasks.length} tasks`} detail="Feeds the Quests page" icon={Flag} tone="gold" testId="stat-working-today" />
        <StatCard label="Focus Time" value={formatMinutes(focusedToday)} detail={dashboardStatus === "live" ? "From Phase 8 capacity API" : "Captured from sessions"} icon={Clock} tone="green" trend testId="stat-focus-time" />
        <StatCard label="Meetings" value={meetingMinutes ? formatMinutes(meetingMinutes) : "3h 10m"} detail={dashboardStatus === "live" ? "From Phase 8 calendar data" : "Tracked in overview"} icon={CalendarBlank} tone="orange" trend down testId="stat-meetings" />
      </section>
      <div className="content-grid">
        <section className="surface missions-panel" data-testid="missions-panel"><div className="section-heading"><h2><Flag size={26} weight="duotone" aria-hidden="true" /> Today&apos;s Missions</h2><NavLink to="/quests" data-testid="view-all-missions-link">{questRun?.status === "needs_update" ? "Update quests" : "View quests"}</NavLink></div>{questRun?.status === "needs_update" && <p className="quest-board-summary quest-board-warning" data-testid="dashboard-quests-update-warning">Working Today changed. Update the run before trusting the order.</p>}<div className="mission-list">{topMissions.map((task, index) => <MissionCard key={task.id} task={task} index={index} questMeta={isUsableQuestRun(tasks, questRun) ? { action: questActionLabel(task), rationale: questRationale(task, index) } : null} />)}</div></section>
        <SchedulePanel events={dashboardSchedule} />
        <section className="surface my-tasks-panel" data-testid="my-tasks-panel"><div className="section-heading task-panel-heading"><h2><ListBullets size={26} weight="duotone" aria-hidden="true" /> My Tasks</h2><NavLink className="add-task-link" to="/tasks" data-testid="dashboard-add-task-link"><Plus size={19} weight="bold" aria-hidden="true" /> Add Task</NavLink></div><div className="tab-row" role="tablist" aria-label="Task filters">{dashboardTaskFilters.map((tab) => <button key={tab} type="button" className={activeTaskFilter === tab ? "tab active" : "tab"} role="tab" aria-selected={activeTaskFilter === tab} onClick={() => setActiveTaskFilter(tab)} data-testid={`task-filter-${slug(tab)}`}>{tab}</button>)}</div><TaskTable tasks={filteredTasks} onStatusChange={onStatusChange} onEdit={onEdit} onToggleToday={onToggleToday} onUpdateNotes={onUpdateNotes} editable={false} /></section>
        <aside className="right-stack" data-testid="right-stack"><FocusWidget compact tasks={tasks} focusSessions={focusSessions} activeSession={activeSession} onStartFocus={onStartFocus} onPauseFocus={onPauseFocus} onResumeFocus={onResumeFocus} onStopFocus={onStopFocus} /><section className="surface insight-card" data-testid="ai-insight-card"><div className="quote-mark" aria-hidden="true">&quot;</div><h2><Sparkle size={25} weight="duotone" aria-hidden="true" /> AI Insight</h2><p data-testid="ai-insight-text">{dashboardInsight?.text || topMissions[0]?.aiInsight || "Select work for today to generate focused insights."}</p><div className="insight-grid"><span data-testid="ai-capacity-value">{formatMinutes(dashboardInsight?.capacity_minutes ?? todayTasks.reduce((sum, task) => sum + task.time, 0))} {dashboardInsight ? "capacity" : "planned"}</span><span data-testid="ai-impact-value">{dashboardInsight?.impact_score ? `${dashboardInsight.impact_score}/10 impact` : `${Math.round((topMissions[0]?.priorityScore || 0) * 100)} priority score`}</span></div></section><section className="surface quote-card" data-testid="quote-card"><div className="quote-mark" aria-hidden="true">&quot;</div><p data-testid="quote-text">Discipline is the bridge between goals and accomplishment.</p><span data-testid="quote-author">- Jim Rohn</span></section></aside>
      </div>
      <p className="footer-note" data-testid="dashboard-footer-note">You&apos;re doing great. Keep the momentum going.</p>
    </main>
  );
};

const TasksPage = ({ tasks, onAddTask, onStatusChange, onEdit, onToggleToday, onUpdateNotes }) => {
  const [editingTask, setEditingTask] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [taskFilters, setTaskFilters] = useState(emptyTaskFilters);
  const filteredTasks = useMemo(() => filterUnifiedTasks(tasks, taskFilters), [tasks, taskFilters]);
  const activeFilterCount = Object.entries(taskFilters).filter(([key, value]) => key === "search" ? Boolean(value.trim()) : value !== "All").length;
  const updateFilter = (field, value) => setTaskFilters((current) => ({ ...current, [field]: value }));
  const resetFilters = () => setTaskFilters(emptyTaskFilters);

  return (
    <main className="page-stack" data-testid="tasks-page">
      <section className="surface form-card" data-testid="add-task-card">
        <div className="section-heading"><h2><Plus size={26} weight="duotone" aria-hidden="true" /> Add Task With Full Details</h2><span data-testid="task-count-label">{tasks.length} tasks loaded</span></div>
        <TaskEditor mode="create" onSubmit={onAddTask} />
      </section>
      {editingTask && (
        <section className="surface form-card" data-testid="edit-task-card">
          <div className="section-heading"><h2><FileText size={26} weight="duotone" aria-hidden="true" /> Edit Task</h2><span>{editingTask.id}</span></div>
          <TaskEditor mode="edit" task={editingTask} onSubmit={async (form) => { await onEdit(editingTask.id, form); setEditingTask(null); }} onCancel={() => setEditingTask(null)} />
        </section>
      )}
      <section className="surface" data-testid="unified-task-list-card">
        <div className="section-heading">
          <h2><Database size={26} weight="duotone" aria-hidden="true" /> Unified Task List</h2>
          <button
            className={`ghost-button ${filtersOpen ? "active-filter-button" : ""}`}
            type="button"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((value) => !value)}
            data-testid="task-filter-button"
          >
            <FunnelSimple size={18} weight="duotone" aria-hidden="true" /> Filter{activeFilterCount ? ` (${activeFilterCount})` : ""}
          </button>
        </div>
        {filtersOpen && (
          <div className="task-filter-panel" data-testid="task-filter-panel">
            <label>
              Search
              <input value={taskFilters.search} onChange={(event) => updateFilter("search", event.target.value)} placeholder="Title, notes, source..." data-testid="task-filter-search" />
            </label>
            <label>
              Status
              <select value={taskFilters.status} onChange={(event) => updateFilter("status", event.target.value)} data-testid="task-filter-status">
                <option>All</option>
                {tableStatuses.map((status) => <option key={status}>{status}</option>)}
              </select>
            </label>
            <label>
              Source
              <select value={taskFilters.source} onChange={(event) => updateFilter("source", event.target.value)} data-testid="task-filter-source">
                <option>All</option>
                {sources.map((source) => <option key={source}>{source}</option>)}
              </select>
            </label>
            <label>
              Priority
              <select value={taskFilters.priority} onChange={(event) => updateFilter("priority", event.target.value)} data-testid="task-filter-priority">
                <option>All</option>
                {priorities.map((priority) => <option key={priority}>{priority}</option>)}
              </select>
            </label>
            <label>
              Today
              <select value={taskFilters.today} onChange={(event) => updateFilter("today", event.target.value)} data-testid="task-filter-today">
                <option>All</option>
                <option>Working</option>
                <option>Not Working</option>
              </select>
            </label>
            <div className="task-filter-actions">
              <span data-testid="task-filter-result-count">{filteredTasks.length} of {tasks.length} tasks</span>
              <button className="ghost-button" type="button" onClick={resetFilters} disabled={!activeFilterCount} data-testid="task-filter-reset-button">Reset</button>
            </div>
          </div>
        )}
        <TaskTable tasks={filteredTasks} onStatusChange={onStatusChange} onEdit={setEditingTask} onToggleToday={onToggleToday} onUpdateNotes={onUpdateNotes} />
        {!filteredTasks.length && <p className="empty-state" data-testid="task-filter-empty-state">No tasks match the selected filters.</p>}
      </section>
    </main>
  );
};

const CalendarPage = ({ overview }) => <main className="page-stack" data-testid="calendar-page"><SchedulePanel /><section className="surface weekly-panel" data-testid="weekly-overview-card"><div className="section-heading"><h2><SquaresFour size={26} weight="duotone" aria-hidden="true" /> Weekly Overview</h2><NavLink to="/overview">Open overview</NavLink></div><div className="weekly-grid"><StatCard label="Completed" value="24 tasks" detail="6 more than last week" icon={CheckSquare} tone="green" trend testId="weekly-completed-stat" /><StatCard label="XP Earned" value="740 XP" detail="Level 8 is within reach" icon={Trophy} tone="violet" testId="weekly-xp-stat" /><StatCard label="Meeting Time" value={formatMinutes(overview.meetingMinutes)} detail="Tracked from calendar" icon={Clock} tone="blue" trend testId="weekly-time-stat" /></div></section></main>;

const FocusPage = ({ tasks, questRun, focusSessions, activeSession, lastSavedFocus, completionUndo, onStartFocus, onPauseFocus, onResumeFocus, onStopFocus, onCompleteQuest, onUndoQuestCompletion }) => {
  const todaySessions = sessionsForDay(focusSessions);
  const weekStart = startOfWeekKey();
  const weekSessions = focusSessions.filter((session) => {
    const day = session.work_date || new Date(session.started_at).toLocaleDateString("en-CA");
    return day >= weekStart && day <= addDaysKey(weekStart, 6);
  });
  const focusedToday = focusMinutesForSessions(todaySessions);
  const focusedWeek = focusMinutesForSessions(weekSessions);
  const topTask = topFocusedTask(todaySessions);
  const taskBreakdown = Object.values(todaySessions.reduce((acc, session) => {
    const key = session.task_id || "unassigned";
    acc[key] = acc[key] || { title: session.task_title || "Unassigned focus", minutes: 0, count: 0 };
    acc[key].minutes += sessionMinutes(session);
    acc[key].count += 1;
    return acc;
  }, {})).sort((a, b) => b.minutes - a.minutes);
  const activeQuest = getQuestById(questRun, activeSession?.quest_id) || getQuestById(questRun, lastSavedFocus?.quest_id) || getQuestById(questRun, questRun?.activeQuestId);
  const activeQuestTask = getQuestTask(tasks, activeQuest);
  const questContext = activeQuest && activeQuestTask ? { quest: activeQuest, task: activeQuestTask } : null;
  const savedQuest = getQuestById(questRun, lastSavedFocus?.quest_id);
  const savedQuestTask = getQuestTask(tasks, savedQuest);

  return (
    <main className="focus-page" data-testid="focus-page">
      <FocusWidget tasks={tasks} focusSessions={focusSessions} activeSession={activeSession} questContext={questContext} onStartFocus={onStartFocus} onPauseFocus={onPauseFocus} onResumeFocus={onResumeFocus} onStopFocus={onStopFocus} onCompleteQuest={onCompleteQuest} />
      <section className="surface focus-log-panel" data-testid="focus-guidance-card">
        <div className="section-heading focus-log-heading"><h2><Lightning size={26} weight="duotone" aria-hidden="true" /> Today&apos;s Focus</h2><span>{todayKey()}</span></div>
        <CompletionUndoNotice undo={completionUndo} onUndo={onUndoQuestCompletion} />
        {savedQuest && savedQuestTask && !activeSession && (
          <div className="focus-quest-saved" data-testid="focus-quest-saved">
            <span className="quest-eyebrow">Session saved</span>
            <div>
              <strong>{savedQuestTask.title}</strong>
              <p>{formatMinutes(savedQuest.focusMinutes)} logged toward a {formatMinutes(savedQuest.focusTargetMinutes)} target.</p>
            </div>
            <div className="focus-quest-saved-actions">
              <button className="primary-action" onClick={() => onStartFocus(savedQuestTask, savedQuest.id)} data-testid="focus-continue-quest-button"><Play size={19} weight="fill" aria-hidden="true" /> Continue Focus</button>
              <button className="ghost-button success-action" onClick={() => onCompleteQuest(savedQuest.id)} data-testid="focus-save-complete-quest-button"><CheckCircle size={19} weight="duotone" aria-hidden="true" /> Complete Quest</button>
              <NavLink className="ghost-button" to="/quests" data-testid="focus-return-quest-button">Back to Quest Run</NavLink>
            </div>
          </div>
        )}
        <div className="focus-calm-summary" data-testid="focus-calm-summary">
          <span><strong>{formatMinutes(focusedToday)}</strong>today</span>
          <span><strong>{todaySessions.length}</strong>session{todaySessions.length === 1 ? "" : "s"}</span>
          <span><strong>{formatMinutes(focusedWeek)}</strong>this week</span>
        </div>
        <p className="focus-log-copy" data-testid="focus-log-copy">{topTask ? `Most of your deep work is going into ${topTask.title}.` : "No focus evidence captured yet today."}</p>
        {taskBreakdown.length > 0 && (
          <div className="focus-breakdown" data-testid="focus-task-breakdown">
            {taskBreakdown.slice(0, 3).map((item) => <article className="focus-breakdown-item" key={item.title}><strong>{item.title}</strong><span>{formatMinutes(item.minutes)}</span></article>)}
          </div>
        )}
        <div className="focus-session-list compact-session-list" data-testid="focus-session-list">
          <h3>Recent sessions</h3>
          {todaySessions.slice(0, 4).map((session) => <article className="focus-session-row" key={session.focus_session_id}><div><strong>{session.task_title}</strong><span>{formatDateTime(session.started_at)} - {session.outcome_type}</span></div><em>{formatMinutes(sessionMinutes(session))}</em>{session.outcome_note && <p>{session.outcome_note}</p>}</article>)}
          {!todaySessions.length && <p className="empty-state">No focus sessions captured today.</p>}
        </div>
      </section>
    </main>
  );
};

const QuestsPage = ({ tasks, questRun, activeSession, completionUndo, onGenerateQuests, onClearQuests, onStartQuestFocus, onCompleteQuest, onUndoQuestCompletion, onSkipQuest, onActivateQuest }) => {
  const navigate = useNavigate();
  const [skipReason, setSkipReason] = useState(skipReasons[0]);
  const todayTasks = getQuestOrderedTasks(tasks, questRun);
  const hasCurrentRun = isCurrentQuestRun(questRun);
  const isGenerated = isUsableQuestRun(tasks, questRun);
  const isOutOfSync = hasCurrentRun && questRun.status === "needs_update";
  const generateLabel = isOutOfSync ? "Update Quests" : isGenerated ? "Regenerate Quests" : "Generate Quests";
  const nextQuest = getNextQuest(questRun);
  const nextQuestTask = getQuestTask(tasks, nextQuest);
  const activeSessionMatchesNextQuest = Boolean(activeSession && nextQuest && activeSession.quest_id === nextQuest.id);
  const activeSessionConflicts = Boolean(activeSession && nextQuest && activeSession.quest_id !== nextQuest.id);
  const summary = questProgressSummary(questRun);
  const questRows = (questRun?.quests || []).map((quest) => ({ quest, task: getQuestTask(tasks, quest) })).filter((item) => item.task);
  const startFocus = () => {
    if (!nextQuestTask) return;
    if (activeSessionMatchesNextQuest || activeSessionConflicts) {
      navigate("/focus");
      return;
    }
    onStartQuestFocus(nextQuestTask, nextQuest.id);
    navigate("/focus");
  };
  return (
    <main className="page-stack" data-testid="quests-page">
      <section className="surface quest-run-panel" data-testid="quest-run-panel">
        <div className="section-heading quest-board-heading">
          <div>
            <h2><Flag size={26} weight="duotone" aria-hidden="true" /> Daily Quest Run</h2>
            <p className={`quest-board-summary ${isOutOfSync ? "quest-board-warning" : ""}`} data-testid="quest-board-summary" aria-live="polite">{questGeneratedLabel(tasks, questRun, todayTasks.length)}</p>
          </div>
          <div className="quest-board-actions">
            {hasCurrentRun && <button className="ghost-button" onClick={onClearQuests} data-testid="clear-quests-button">Reset</button>}
            <button className="primary-action" onClick={onGenerateQuests} disabled={!todayTasks.length} data-testid="generate-quests-button"><Sparkle size={19} weight="duotone" aria-hidden="true" /> {generateLabel}</button>
          </div>
        </div>
        <CompletionUndoNotice undo={completionUndo} onUndo={onUndoQuestCompletion} />
        {isGenerated && (
          <div className="quest-layout">
            <article className="next-quest-card" data-testid="next-quest-card">
              <div className="next-quest-copy">
                <span className="quest-eyebrow" data-testid="next-quest-rank">Next quest</span>
                <h3 data-testid="next-quest-title">{nextQuestTask?.title || "Daily run complete"}</h3>
                <p data-testid="next-quest-reason">{nextQuest?.reason || "All generated quests are either completed or skipped."}</p>
                {nextQuestTask && (
                  <div className="quest-facts" aria-label="Next quest details">
                    <span data-testid="next-quest-effort"><Clock size={16} weight="duotone" aria-hidden="true" /> {formatMinutes(nextQuestTask.time)} effort</span>
                    <span data-testid="next-quest-focus-progress"><Timer size={16} weight="duotone" aria-hidden="true" /> {formatMinutes(nextQuest.focusMinutes)} / {formatMinutes(nextQuest.focusTargetMinutes)} focus</span>
                    <span data-testid="next-quest-xp"><Trophy size={16} weight="duotone" aria-hidden="true" /> {nextQuest.rewardXp} XP</span>
                  </div>
                )}
              </div>
              {nextQuestTask ? (
                <div className="next-quest-actions" data-testid="next-quest-actions">
                  <button className="primary-action" onClick={startFocus} data-testid="quest-start-focus-button"><Play size={19} weight="fill" aria-hidden="true" /> {activeSessionMatchesNextQuest ? "Resume Focus" : activeSessionConflicts ? "Open Focus" : "Start Focus"}</button>
                  {activeSessionConflicts && <p className="quest-focus-warning" data-testid="quest-focus-warning">A focus session is already running. Open Focus Mode to wrap it before starting this quest.</p>}
                  <button className="ghost-button success-action" onClick={() => onCompleteQuest(nextQuest.id)} data-testid="quest-complete-button"><CheckCircle size={19} weight="duotone" aria-hidden="true" /> Complete</button>
                  <div className="skip-control">
                    <label htmlFor="quest-skip-reason">Skip reason</label>
                    <select id="quest-skip-reason" value={skipReason} onChange={(event) => setSkipReason(event.target.value)} data-testid="quest-skip-reason-select">
                      {skipReasons.map((reason) => <option key={reason} value={reason}>{reason}</option>)}
                    </select>
                    <button className="ghost-button" onClick={() => onSkipQuest(nextQuest.id, skipReason)} data-testid="quest-skip-button">Skip</button>
                  </div>
                </div>
              ) : (
                <p className="daily-summary" data-testid="quest-complete-summary">Completed {summary.completed} of {summary.total}, skipped {summary.skipped}, earned {summary.earnedXp} XP, and captured {formatMinutes(summary.focusMinutes)} of focus.</p>
              )}
            </article>
            <aside className="quest-summary" data-testid="quest-summary">
              <span><strong>{summary.completed}/{summary.total}</strong>complete</span>
              <span><strong>{formatMinutes(summary.focusMinutes)}</strong>focus</span>
              <span><strong>{summary.earnedXp}/{summary.availableXp}</strong>XP</span>
              <span><strong>{summary.skipped}</strong>skipped</span>
            </aside>
          </div>
        )}
        {!isGenerated && <div className="mission-list">{todayTasks.length ? todayTasks.map((task, index) => <MissionCard key={task.id} task={task} index={index} questMeta={null} />) : <p className="empty-state">No tasks are marked as Working Today yet. Open My Tasks and use the Today column to add work here.</p>}</div>}
      </section>
      {isGenerated && (
        <section className="surface" data-testid="quest-path-card">
          <div className="section-heading"><h2><ListChecks size={26} weight="duotone" aria-hidden="true" /> Quest Path</h2><span>{questRows.length} quests</span></div>
          <div className="quest-path-list">
            {questRows.map(({ quest, task }) => (
              <article className={`quest-path-row quest-state-${quest.state}`} key={quest.id} data-testid={`quest-path-row-${slug(task.id)}`}>
                <span className="quest-path-rank">#{quest.rank}</span>
                <div className="quest-path-copy">
                  <strong>{task.title}</strong>
                  <span>{quest.reasonLabel} - {task.priority} - {formatMinutes(task.time)} - {quest.rewardXp} XP</span>
                  <div className="progress-track quest-progress" aria-label={`${task.title} focus progress`}>
                    <span className="progress-fill" style={{ width: `${Math.min(100, (quest.focusMinutes / Math.max(1, quest.focusTargetMinutes)) * 100)}%` }} />
                  </div>
                  {quest.state === "skipped" && <p>Skipped: {quest.skipReason}</p>}
                </div>
                <div className="quest-path-state">
                  <Pill tone={slug(quest.state)} testId={`quest-state-${slug(task.id)}`}>{quest.state}</Pill>
                  {quest.state === "queued" && <button className="ghost-button" onClick={() => onActivateQuest(quest.id)} data-testid={`quest-activate-${slug(task.id)}`}>Choose</button>}
                  {quest.state === "skipped" && <button className="ghost-button" onClick={() => onActivateQuest(quest.id)} data-testid={`quest-resume-${slug(task.id)}`}>Resume</button>}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
      <section className="surface" data-testid="daily-work-source-card">
        <div className="section-heading"><h2><Database size={26} weight="duotone" aria-hidden="true" /> Daily Work Source</h2><span>{todayKey()}</span></div>
        <div className="source-truth-grid">
          {todayTasks.map((task, index) => (
            <article className="source-row" key={task.id}>
              <strong>{index + 1}. {task.title}</strong>
              <span>{task.id} - {task.priority} - {task.status} - {task.time} mins planned - {task.xp} XP</span>
              <p>{isGenerated ? questRationale(task, index) : task.notes || task.aiInsight}</p>
            </article>
          ))}
          {!todayTasks.length && <p className="empty-state">Working Today selection is the source for generated quests.</p>}
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

const toList = (value) => Array.isArray(value) ? value : String(value || "").split(/\n+/).map((item) => item.trim()).filter(Boolean);

const OverviewPage = ({ tasks, overview, focusSessions, onOverviewChange }) => {
  const [selectedDate, setSelectedDate] = useState(todayKey());
  const [selectedWeek, setSelectedWeek] = useState(startOfWeekKey());
  const [dailyData, setDailyData] = useState(null);
  const [weeklyData, setWeeklyData] = useState(null);
  const [overviewStatus, setOverviewStatus] = useState("loading");
  const [generating, setGenerating] = useState(null);

  const fallbackCompletedDay = tasks.filter((task) => task.status === "Done" && isSameDay(task.completedAt, selectedDate));
  const fallbackWeekEnd = addDaysKey(selectedWeek, 6);
  const fallbackCompletedWeek = tasks.filter((task) => task.status === "Done" && isWithinWeek(task.completedAt, selectedWeek));
  const fallbackDailyFocus = sessionsForDay(focusSessions, selectedDate);
  const fallbackWeeklyFocus = focusSessions.filter((session) => {
    const day = session.work_date || new Date(session.started_at).toLocaleDateString("en-CA");
    return day >= selectedWeek && day <= fallbackWeekEnd;
  });
  const fallbackDailyFocusMinutes = focusMinutesForSessions(fallbackDailyFocus);
  const fallbackWeeklyFocusMinutes = focusMinutesForSessions(fallbackWeeklyFocus);
  const topFocus = topFocusedTask(fallbackDailyFocus);
  const fallbackDailyXp = fallbackCompletedDay.reduce((sum, task) => sum + task.xp, 0);
  const fallbackWeeklyXp = fallbackCompletedWeek.reduce((sum, task) => sum + task.xp, 0);

  useEffect(() => {
    let cancelled = false;
    setOverviewStatus("loading");
    overviewApi.daily({ date: selectedDate })
      .then((data) => {
        if (cancelled) return;
        setDailyData(data);
        setOverviewStatus("live");
        onOverviewChange((current) => ({
          ...current,
          meetingMinutes: data.meeting_minutes ?? current.meetingMinutes,
          focusMinutes: data.focus_minutes ?? current.focusMinutes,
          newLearnings: toList(data.new_learnings).join("\n") || current.newLearnings,
          wentWell: toList(data.went_well).join("\n") || current.wentWell,
          wentWrong: toList(data.went_wrong).join("\n") || current.wentWrong,
        }));
      })
      .catch(() => {
        if (cancelled) return;
        setDailyData(null);
        setOverviewStatus("fallback");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDate, onOverviewChange]);

  useEffect(() => {
    let cancelled = false;
    overviewApi.weekly({ week_start: selectedWeek })
      .then((data) => {
        if (!cancelled) setWeeklyData(data);
      })
      .catch(() => {
        if (!cancelled) setWeeklyData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedWeek]);

  const generateDaily = async () => {
    setGenerating("daily");
    try {
      const data = await overviewApi.generateDaily({ date: selectedDate, include_task_notes: true, include_meetings: true, force: true });
      setDailyData(data);
      setOverviewStatus("live");
    } catch {
      setOverviewStatus("fallback");
    } finally {
      setGenerating(null);
    }
  };

  const generateWeekly = async () => {
    setGenerating("weekly");
    try {
      const data = await overviewApi.generateWeekly({ week_start: selectedWeek, include_daily_overviews: true, include_task_notes: true, force: true });
      setWeeklyData(data);
    } finally {
      setGenerating(null);
    }
  };

  const shiftDailyDate = (days) => setSelectedDate((current) => addDaysKey(current, days));
  const shiftWeeklyDate = (days) => setSelectedWeek((current) => addDaysKey(current, days * 7));
  const update = (field, value) => onOverviewChange({ ...overview, [field]: value });
  const dailyTasks = dailyData?.accomplished_tasks || fallbackCompletedDay;
  const dailyFocus = dailyData?.focus_sessions || fallbackDailyFocus;
  const dailyLearnings = toList(dailyData?.new_learnings ?? overview.newLearnings);
  const dailyWentWell = toList(dailyData?.went_well ?? overview.wentWell);
  const dailyWentWrong = toList(dailyData?.went_wrong ?? overview.wentWrong);
  const dailyThemes = toList(dailyData?.themes);
  const dailyTaskCount = dailyData?.tasks_completed ?? fallbackCompletedDay.length;
  const dailyXp = dailyData?.xp_earned ?? fallbackDailyXp;
  const dailyMeetingMinutes = dailyData?.meeting_minutes ?? overview.meetingMinutes;
  const dailyFocusMinutes = dailyData?.focus_minutes ?? fallbackDailyFocusMinutes;
  const weeklyThemes = toList(weeklyData?.themes).length ? toList(weeklyData?.themes) : [...new Set(fallbackCompletedWeek.flatMap((task) => task.labels || []))].slice(0, 5);
  const topAccomplishments = toList(weeklyData?.top_accomplishments);

  return (
    <main className="page-stack" data-testid="overview-page">
      <section className="surface" data-testid="daily-overview-card">
        <div className="section-heading">
          <h2><CalendarBlank size={26} weight="duotone" aria-hidden="true" /> Daily Overview</h2>
          <div className="overview-controls">
            <button className="icon-button overview-step-button" type="button" onClick={() => shiftDailyDate(-1)} aria-label="Previous day" data-testid="daily-overview-prev-button"><CaretLeft size={20} weight="bold" /></button>
            <input type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} data-testid="daily-overview-date-input" aria-label="Daily overview date" />
            <button className="icon-button overview-step-button" type="button" onClick={() => shiftDailyDate(1)} aria-label="Next day" data-testid="daily-overview-next-button"><CaretRight size={20} weight="bold" /></button>
            <button className="primary-action" onClick={generateDaily} disabled={generating === "daily"} data-testid="generate-daily-overview-button"><Sparkle size={19} weight="duotone" aria-hidden="true" /> {generating === "daily" ? "Generating" : "Generate"}</button>
          </div>
        </div>
        <div className="overview-stats">
          <StatCard label="Tasks Accomplished" value={dailyTaskCount} detail={`${dailyXp} XP earned`} icon={CheckCircle} tone="green" testId="daily-completed-stat" />
          <StatCard label="Meetings" value={formatMinutes(dailyMeetingMinutes)} detail={dailyData ? `${dailyData.meeting_summary?.meeting_count || 0} scheduled` : "Editable daily tracker"} icon={UsersThree} tone="orange" testId="daily-meetings-stat" />
          <StatCard label="Focus Time" value={formatMinutes(dailyFocusMinutes)} detail={topFocus ? `Top: ${topFocus.title}` : `${dailyFocus.length} session(s)`} icon={Timer} tone="blue" testId="daily-focus-stat" />
        </div>
        <div className="overview-editor">
          <label>Meeting minutes<input type="number" min="0" value={dailyMeetingMinutes} onChange={(event) => update("meetingMinutes", parseNumber(event.target.value, 0))} /></label>
          <label>Focus minutes<input type="number" min="0" value={dailyFocusMinutes} readOnly /></label>
          <label>New learnings<textarea value={dailyLearnings.join("\n")} onChange={(event) => update("newLearnings", event.target.value)} /></label>
          <label>Went well<textarea value={dailyWentWell.join("\n")} onChange={(event) => update("wentWell", event.target.value)} /></label>
          <label>Went wrong<textarea value={dailyWentWrong.join("\n")} onChange={(event) => update("wentWrong", event.target.value)} /></label>
        </div>
        {!!dailyThemes.length && <div className="theme-list" data-testid="daily-theme-list">{dailyThemes.map((theme) => <Pill key={theme} tone="task">{theme}</Pill>)}</div>}
        <div className="accomplished-list focus-evidence-list" data-testid="daily-focus-session-list">
          {dailyFocus.map((session) => <article key={session.focus_session_id}><strong>{session.task_title}</strong><span>{formatDateTime(session.started_at)} - {formatMinutes(session.actual_minutes || sessionMinutes(session))} - {session.status || session.outcome_type}</span><p>{session.notes || session.outcome_note || "Captured focus session for AI summary context."}</p></article>)}
          {!dailyFocus.length && <article><strong>No focus captured yet</strong><span>Use Focus Mode to create session-backed deep-work evidence.</span></article>}
        </div>
        <div className="accomplished-list">
          {dailyTasks.map((task) => <article key={task.task_id || task.id}><strong>{task.title}</strong><span>{formatDateTime(task.completed_at || task.completedAt)} - {task.actual_minutes || task.actualMinutes || task.time} mins - {task.xp_value || task.xp} XP</span><p>{task.notes}</p></article>)}
          {!dailyTasks.length && <article><strong>No completed tasks</strong><span>{selectedDate}</span><p>Working tasks and focus sessions will still inform the generated overview.</p></article>}
        </div>
        <p className="insight-copy" data-testid="daily-overview-summary">Summary: {dailyData?.summary || (dailyTasks.length || dailyFocus.length ? `Completed ${dailyTaskCount} task(s), focused ${formatMinutes(dailyFocusMinutes)}, and earned ${dailyXp} XP.` : "No completion or focus evidence for this date yet.")}</p>
        <span className="overview-status" data-testid="overview-api-status">{overviewStatus === "live" ? "AI overview from backend" : overviewStatus === "loading" ? "Loading overview" : "Local fallback overview"}</span>
      </section>
      <section className="surface" data-testid="weekly-overview-card">
        <div className="section-heading">
          <h2><SquaresFour size={26} weight="duotone" aria-hidden="true" /> Weekly Overview</h2>
          <div className="overview-controls">
            <button className="icon-button overview-step-button" type="button" onClick={() => shiftWeeklyDate(-1)} aria-label="Previous week" data-testid="weekly-overview-prev-button"><CaretLeft size={20} weight="bold" /></button>
            <input type="date" value={selectedWeek} onChange={(event) => setSelectedWeek(startOfWeekKey(new Date(`${event.target.value}T00:00:00`)))} data-testid="weekly-overview-week-input" aria-label="Weekly overview week" />
            <button className="icon-button overview-step-button" type="button" onClick={() => shiftWeeklyDate(1)} aria-label="Next week" data-testid="weekly-overview-next-button"><CaretRight size={20} weight="bold" /></button>
            <button className="primary-action" onClick={generateWeekly} disabled={generating === "weekly"} data-testid="generate-weekly-overview-button"><Sparkle size={19} weight="duotone" aria-hidden="true" /> {generating === "weekly" ? "Generating" : "Generate"}</button>
          </div>
        </div>
        <div className="weekly-grid">
          <StatCard label="Completed" value={`${weeklyData?.tasks_completed ?? fallbackCompletedWeek.length} tasks`} detail={`${weeklyData?.xp_earned ?? fallbackWeeklyXp} XP earned`} icon={CheckSquare} tone="green" testId="overview-weekly-completed-stat" />
          <StatCard label="Meeting Time" value={formatMinutes(weeklyData?.meeting_minutes ?? dailyMeetingMinutes * 5)} detail={`${selectedWeek} to ${weeklyData?.week_end || fallbackWeekEnd}`} icon={CalendarBlank} tone="orange" testId="overview-weekly-meetings-stat" />
          <StatCard label="Focus Time" value={formatMinutes(weeklyData?.focus_minutes ?? fallbackWeeklyFocusMinutes)} detail={`${weeklyData?.daily_overviews?.length || fallbackWeeklyFocus.length} evidence row(s)`} icon={Clock} tone="blue" testId="overview-weekly-focus-stat" />
        </div>
        {!!weeklyThemes.length && <div className="theme-list">{weeklyThemes.map((theme) => <Pill key={theme} tone="task">{theme}</Pill>)}</div>}
        {!!topAccomplishments.length && <div className="accomplished-list" data-testid="weekly-top-accomplishments">{topAccomplishments.map((item) => <article key={item}><strong>{item}</strong><span>Top accomplishment</span></article>)}</div>}
        <p className="insight-copy" data-testid="weekly-overview-summary">Weekly summary: {weeklyData?.summary || (fallbackCompletedWeek.length ? `The week is trending around ${fallbackCompletedWeek.slice(0, 3).map((task) => task.title).join(", ")}.` : "Complete tasks to build the weekly summary.")}</p>
      </section>
    </main>
  );
};

const SyncPage = () => <main className="page-stack" data-testid="sync-page"><section className="surface sync-card" data-testid="sync-management-card"><div className="section-heading"><h2><CloudArrowDown size={26} weight="duotone" aria-hidden="true" /> Sync Center</h2><button className="primary-action" data-testid="run-sync-button"><CloudArrowDown size={19} weight="duotone" aria-hidden="true" /> Sync Now</button></div><div className="sync-grid">{["Jira", "Outlook Calendar", "Microsoft To Do"].map((source) => <article className="sync-source" key={source} data-testid={`sync-source-${slug(source)}`}><CheckCircle size={26} weight="duotone" aria-hidden="true" /><strong data-testid={`sync-source-title-${slug(source)}`}>{source}</strong><span data-testid={`sync-source-status-${slug(source)}`}>Ready to sync</span></article>)}</div></section></main>;

const SettingsPage = () => <main className="page-stack" data-testid="settings-page"><section className="surface settings-card" data-testid="settings-card"><div className="section-heading"><h2><GearSix size={26} weight="duotone" aria-hidden="true" /> Productivity Settings</h2></div><label className="settings-row" data-testid="working-hours-setting-label">Working hours<input value="09:00 - 17:00" readOnly data-testid="working-hours-setting-input" /></label><label className="settings-row" data-testid="xp-multiplier-setting-label">Focus XP multiplier<input value="1.5x" readOnly data-testid="xp-multiplier-setting-input" /></label></section></main>;

const AppShell = ({ currentUser, isLoggingOut, onLogout }) => {
  const [tasks, setTasks] = useState([]);
  const [taskLoadError, setTaskLoadError] = useState("");
  const [overview, setOverview] = useState(defaultOverview);
  const [dashboardStats, setDashboardStats] = useState(null);
  const [dashboardSchedule, setDashboardSchedule] = useState(schedule);
  const [dashboardInsight, setDashboardInsight] = useState(null);
  const [dashboardStatus, setDashboardStatus] = useState("fallback");
  const [focusSessions, setFocusSessions] = useState(() => readStoredJson(FOCUS_SESSIONS_STORAGE_KEY, []));
  const [activeSession, setActiveSession] = useState(() => readStoredJson(ACTIVE_FOCUS_STORAGE_KEY, null));
  const [questRun, setQuestRun] = useState(() => readQuestRun(readStoredTasks(), readStoredJson(FOCUS_SESSIONS_STORAGE_KEY, [])));
  const [lastSavedFocus, setLastSavedFocus] = useState(null);
  const [completionUndo, setCompletionUndo] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    let isActive = true;
    tasksApi.list()
      .then((loadedTasks) => {
        if (!isActive) return;
        const taskItems = Array.isArray(loadedTasks) ? loadedTasks : loadedTasks?.items || [];
        setTasks(taskItems.map(normalizeTask));
        setTaskLoadError("");
      })
      .catch((error) => {
        if (!isActive) return;
        setTaskLoadError(error?.message || "Unable to load saved tasks.");
      });

    return () => {
      isActive = false;
    };
  }, []);

  const handleComplete = async (id) => {
    const task = tasks.find((item) => item.id === id);
    if (!task) return;
    try {
      const updatedTask = await tasksApi.complete(id, { row_version: task.row_version, completedAt: task.completedAt || nowIso() });
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTask(updatedTask) : item)));
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to complete task.");
    }
  };
  const handleStatusChange = async (id, nextStatus) => {
    const task = tasks.find((item) => item.id === id);
    if (!task || !nextStatus || task.status === nextStatus) return;
    try {
      const updatedTask = await tasksApi.updateStatus(id, { status: nextStatus, row_version: task.row_version });
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTask(updatedTask) : item)));
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to update task status.");
    }
  };
  const handleToggleToday = async (id) => {
    const task = tasks.find((item) => item.id === id);
    if (!task) return;
    try {
      const updatedTask = await tasksApi.updateToday(id, { workingToday: !task.workingToday });
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTask(updatedTask) : item)));
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to update working-today state.");
    }
  };
  const handleUpdateNotes = async (id, notes, persist = true) => {
    const task = tasks.find((item) => item.id === id);
    setTasks((items) => items.map((item) => (item.id === id ? normalizeTask({ ...item, notes, aiInsight: "" }) : item)));
    if (!persist || !task) return;
    try {
      const updatedTask = await tasksApi.updateNotes(id, { notes, row_version: task.row_version });
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTask(updatedTask) : item)));
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to update notes.");
      throw error;
    }
  };
  const handleEditTask = async (id, form) => {
    const task = tasks.find((item) => item.id === id);
    if (!task || !form) return;
    const updatedTask = await tasksApi.update(id, { ...form, row_version: task.row_version, runAiEnrichment: form.runAiEnrichment });
    setTasks((items) => items.map((item) => (item.id === id ? normalizeTask(updatedTask) : item)));
  };
  const handleRefreshInsights = () => setTasks((items) => items.map((task) => normalizeTask({ ...task, aiInsight: "" })));
  const handleAddTask = async (form) => {
    const createdTask = await tasksApi.create(form);
    setTasks((items) => [normalizeTask(createdTask), ...items]);
  };

  const updateQuestRun = (updater) => setQuestRun((run) => {
    const nextRun = typeof updater === "function" ? updater(run) : updater;
    saveQuestRun(nextRun);
    return nextRun;
  });

  const handleGenerateQuests = () => updateQuestRun(generateQuestRun(tasks, focusSessions));
  const handleClearQuests = () => {
    clearQuestRun();
    setQuestRun(null);
  };
  const handleStartFocus = (task, questId) => {
    const startedAt = nowIso();
    const linkedQuest = questId ? getQuestById(questRun, questId) : getOpenQuestForTask(questRun, task.id);
    if (linkedQuest) {
      updateQuestRun((run) => applyActiveQuest({
        ...run,
        activeQuestId: linkedQuest.id,
        quests: (run?.quests || []).map((quest) => quest.id === linkedQuest.id ? { ...quest, state: "active", startedAt: quest.startedAt || startedAt } : quest),
      }));
    }
    setLastSavedFocus(null);
    setActiveSession({
      focus_session_id: createFocusId(),
      task_id: task.id,
      task_title: task.title,
      task_source: task.source,
      quest_id: linkedQuest?.id || null,
      work_date: todayKey(),
      started_at: startedAt,
      lastStartedAt: startedAt,
      accumulatedSeconds: 0,
      isRunning: true,
      created_at: startedAt,
    });
  };
  const handleStartQuestFocus = (task, questId) => {
    updateQuestRun((run) => applyActiveQuest({
      ...run,
      activeQuestId: questId,
      quests: (run?.quests || []).map((quest) => quest.id === questId ? { ...quest, state: "active", startedAt: quest.startedAt || nowIso() } : quest),
    }));
    handleStartFocus(task, questId);
  };
  const handleCompleteQuest = (questId) => {
    const quest = questRun?.quests?.find((item) => item.id === questId);
    const task = tasks.find((item) => item.id === quest?.taskId);
    if (!quest || !task) return;
    const completedAt = nowIso();
    setCompletionUndo({
      questId,
      taskId: task.id,
      taskTitle: task.title,
      previousTaskStatus: task.status,
      previousCompletedAt: task.completedAt,
      previousQuestState: quest.state,
      previousQuestCompletedAt: quest.completedAt,
      previousActiveQuestId: questRun?.activeQuestId,
    });
    setTasks((items) => items.map((item) => (item.id === task.id ? normalizeTask({ ...item, status: "Done", completedAt: item.completedAt || completedAt }) : item)));
    updateQuestRun((run) => applyActiveQuest({
      ...run,
      quests: (run?.quests || []).map((item) => item.id === questId ? { ...item, state: "completed", completedAt } : item),
    }));
  };
  const handleUndoQuestCompletion = () => {
    if (!completionUndo) return;
    setTasks((items) => items.map((task) => (task.id === completionUndo.taskId ? normalizeTask({ ...task, status: completionUndo.previousTaskStatus, completedAt: completionUndo.previousCompletedAt }) : task)));
    updateQuestRun((run) => applyActiveQuest({
      ...run,
      activeQuestId: completionUndo.previousActiveQuestId || completionUndo.questId,
      quests: (run?.quests || []).map((quest) => quest.id === completionUndo.questId ? { ...quest, state: completionUndo.previousQuestState, completedAt: completionUndo.previousQuestCompletedAt } : quest),
    }));
    setCompletionUndo(null);
  };
  const handleSkipQuest = (questId, skipReason) => updateQuestRun((run) => applyActiveQuest({
    ...run,
    quests: (run?.quests || []).map((quest) => quest.id === questId ? { ...quest, state: "skipped", skippedAt: nowIso(), skipReason } : quest),
  }));
  const handleActivateQuest = (questId) => updateQuestRun((run) => applyActiveQuest({
    ...run,
    activeQuestId: questId,
    quests: (run?.quests || []).map((quest) => {
      if (quest.id === questId) return { ...quest, state: "active", startedAt: quest.startedAt || nowIso(), skippedAt: null, skipReason: "" };
      if (quest.state === "active") return { ...quest, state: "queued" };
      return quest;
    }),
  }));
  const handlePauseFocus = () => setActiveSession((session) => {
    if (!session || !session.isRunning) return session;
    return { ...session, accumulatedSeconds: activeFocusSeconds(session), isRunning: false, lastStartedAt: null };
  });
  const handleResumeFocus = () => setActiveSession((session) => {
    if (!session || session.isRunning) return session;
    return { ...session, isRunning: true, lastStartedAt: nowIso() };
  });
  const handleStopFocus = ({ outcomeType, outcomeNote }) => setActiveSession((session) => {
    if (!session) return null;
    const endedAt = nowIso();
    const durationSeconds = activeFocusSeconds(session);
    const savedSession = {
      focus_session_id: session.focus_session_id,
      task_id: session.task_id,
      task_title: session.task_title,
      task_source: session.task_source,
      quest_id: session.quest_id || null,
      work_date: session.work_date || todayKey(),
      started_at: session.started_at,
      ended_at: endedAt,
      duration_seconds: durationSeconds,
      duration_minutes: Math.max(1, Math.ceil(durationSeconds / 60)),
      outcome_type: outcomeType || "Progress made",
      outcome_note: outcomeNote?.trim() || "",
      created_at: session.created_at || endedAt,
    };
    setFocusSessions((items) => [savedSession, ...items]);
    setLastSavedFocus(savedSession);
    return null;
  });

  useEffect(() => {
    writeStoredJson(FOCUS_SESSIONS_STORAGE_KEY, focusSessions);
  }, [focusSessions]);

  useEffect(() => {
    if (activeSession) writeStoredJson(ACTIVE_FOCUS_STORAGE_KEY, activeSession);
    else removeStoredJson(ACTIVE_FOCUS_STORAGE_KEY);
  }, [activeSession]);

  useEffect(() => {
    setQuestRun((run) => {
      const derived = deriveQuestProgress(run, tasks, focusSessions);
      return JSON.stringify(derived) === JSON.stringify(run) ? run : derived;
    });
  }, [tasks, focusSessions]);

  useEffect(() => {
    saveQuestRun(questRun);
  }, [questRun]);

  useEffect(() => {
    writeStoredJson(TASKS_STORAGE_KEY, tasks);
  }, [tasks]);

  useEffect(() => {
    let cancelled = false;
    dashboardApi.today({ date: todayKey() })
      .then((data) => {
        if (cancelled) return;
        setDashboardStats(data.stats || null);
        setDashboardSchedule(normalizeApiSchedule(data.schedule || []));
        setDashboardInsight(data.ai_insight || null);
        setDashboardStatus("live");
        if (data.stats) {
          setOverview((current) => ({
            ...current,
            meetingMinutes: data.stats.meeting_minutes ?? current.meetingMinutes,
            focusMinutes: data.stats.focus_minutes ?? data.stats.available_focus_minutes ?? current.focusMinutes,
          }));
        }
      })
      .catch(() => {
        if (cancelled) return;
        setDashboardStatus("fallback");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app-shell" data-testid="app-shell">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <button className={`sidebar-scrim ${sidebarOpen ? "sidebar-scrim-active" : ""}`} aria-label="Close navigation" onClick={() => setSidebarOpen(false)} data-testid="sidebar-scrim-button" aria-hidden={!sidebarOpen} tabIndex={sidebarOpen ? 0 : -1} />
      <div className="workspace" data-testid="workspace">
        <Topbar currentUser={currentUser} isLoggingOut={isLoggingOut} onLogout={onLogout} onMenuClick={() => setSidebarOpen(true)} />
        {taskLoadError && <p className="form-error" role="alert">{taskLoadError}</p>}
        <Routes>
          <Route path="/tasks" element={<TasksPage tasks={tasks} onAddTask={handleAddTask} onStatusChange={handleStatusChange} onEdit={handleEditTask} onToggleToday={handleToggleToday} onUpdateNotes={handleUpdateNotes} />} />
          <Route path="/" element={<Dashboard tasks={tasks} questRun={questRun} focusSessions={focusSessions} activeSession={activeSession} onStartFocus={handleStartFocus} onPauseFocus={handlePauseFocus} onResumeFocus={handleResumeFocus} onStopFocus={handleStopFocus} onStatusChange={handleStatusChange} onEdit={handleEditTask} onToggleToday={handleToggleToday} onUpdateNotes={handleUpdateNotes} dashboardStats={dashboardStats} dashboardSchedule={dashboardSchedule} dashboardInsight={dashboardInsight} dashboardStatus={dashboardStatus} />} />
          <Route path="/calendar" element={<CalendarPage overview={overview} />} />
          <Route path="/focus" element={<FocusPage tasks={tasks} questRun={questRun} focusSessions={focusSessions} activeSession={activeSession} lastSavedFocus={lastSavedFocus} completionUndo={completionUndo} onStartFocus={handleStartFocus} onPauseFocus={handlePauseFocus} onResumeFocus={handleResumeFocus} onStopFocus={handleStopFocus} onCompleteQuest={handleCompleteQuest} onUndoQuestCompletion={handleUndoQuestCompletion} />} />
          <Route path="/quests" element={<QuestsPage tasks={tasks} questRun={questRun} activeSession={activeSession} completionUndo={completionUndo} onGenerateQuests={handleGenerateQuests} onClearQuests={handleClearQuests} onStartQuestFocus={handleStartQuestFocus} onCompleteQuest={handleCompleteQuest} onUndoQuestCompletion={handleUndoQuestCompletion} onSkipQuest={handleSkipQuest} onActivateQuest={handleActivateQuest} />} />
          <Route path="/insights" element={<InsightsPage tasks={tasks} onRefreshInsights={handleRefreshInsights} />} />
          <Route path="/overview" element={<OverviewPage tasks={tasks} overview={overview} focusSessions={focusSessions} onOverviewChange={setOverview} />} />
          <Route path="/sync" element={<SyncPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
};

const AuthenticatedApp = () => {
  const [currentUser, setCurrentUser] = useState(() => readCurrentUser());
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleAuthenticated = (profile) => {
    window.localStorage.setItem(CURRENT_USER_STORAGE_KEY, JSON.stringify(profile));
    setCurrentUser(profile);
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await authApi.logout();
    } catch {
      // Local auth has no server-side session; always clear local state.
    } finally {
      window.localStorage.removeItem(CURRENT_USER_STORAGE_KEY);
      setCurrentUser(null);
      setIsLoggingOut(false);
    }
  };

  if (!currentUser?.user_id) {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  return <AppShell currentUser={currentUser} isLoggingOut={isLoggingOut} onLogout={handleLogout} />;
};

function App() {
  return <BrowserRouter><AuthenticatedApp /></BrowserRouter>;
}

export default App;
