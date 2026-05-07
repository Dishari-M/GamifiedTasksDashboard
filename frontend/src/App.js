import { useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowClockwise,
  Bell,
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
  FolderOpen,
  FunnelSimple,
  GearSix,
  House,
  Hourglass,
  Lightning,
  ListBullets,
  ListChecks,
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
import { authApi, calendarApi, CURRENT_USER_STORAGE_KEY, dashboardApi, focusApi, insightsApi, jiraApi, overviewApi, questsApi, settingsApi, standupApi, syncApi, taskEnrichmentApi, tasksApi } from "./api/client";
import { FocusQuestBadge, FocusSavedQuestPanel } from "./features/focus/FocusMomentum";
import FocusAnalyticsPage from "./features/focusAnalytics/FocusAnalyticsPage";
import { activeFocusSeconds, ACTIVE_FOCUS_STORAGE_KEY, createFocusId, FOCUS_SESSIONS_STORAGE_KEY, focusMinutesForSessions, focusOutcomes, orderedFocusTasks, sessionsForDay, sessionMinutes, topFocusedTask } from "./features/focus/focusSessions";
import { deriveTaskXpBreakdown, levelProgressFromXp, streakHeat } from "./features/progress/progressionMath";
import { NextQuestCard, QuestPathList, QuestSummaryPanel } from "./features/quests/QuestMomentum";
import { buildProgressSnapshot, mergeMonotonicTotalXp } from "./features/progress/progressModel";
import { compareQuestTasks, getNextQuest, getOpenQuestForTask, getQuestById, getQuestOrderedTasks, getQuestTask, hasGeneratedQuestRun, isCurrentQuestRun, isUsableQuestRun, questActionLabel, questGeneratedLabel, questProgressSummary, questRationale, skipReasons } from "./features/quests/questRun";
import { earnedXpForTasks, FOCUS_XP_MULTIPLIER, focusRewardsByTaskId, formatFocusMultiplier, taskRewardDetails, taskRewardDetailsFromSessions } from "./features/rewards/xpRewards";
import { defaultOverview, emptyTaskForm, formFromTask, normalizeApiSchedule, normalizeApiTask, normalizeTask, priorities, rcaTshirtSizes, schedule, sources, statuses, TASKS_STORAGE_KEY, taskFromForm, taskTypes } from "./features/tasks/taskModel";
import { addDaysKey, formatDateTime, formatMinutes, formatTimer, isSameDay, isWithinWeek, nowIso, startOfWeekKey, todayKey } from "./utils/dateTime";
import { parseNumber } from "./utils/number";
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
const tableStatuses = ["To Do", "In Progress", "Blocked", "Done"];

const THEME_STORAGE_KEY = "devquest.theme.v1";
const PROGRESS_GUIDE_STORAGE_KEY = "devquest.progressGuide.dismissed.v2";
const XP_LEDGER_STORAGE_KEY = "devquest.progress.totalXpByUser.v1";

const readInitialTheme = () => {
  const stored = readStoredJson(THEME_STORAGE_KEY, null);
  if (stored === "light" || stored === "dark") return stored;
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: light)").matches) return "light";
  return "dark";
};

const readPersistedXpLedger = () => readStoredJson(XP_LEDGER_STORAGE_KEY, {});

const readPersistedXpForUser = (userId) => {
  if (!userId) return 0;
  const ledger = readPersistedXpLedger();
  return parseNumber(ledger?.[String(userId)], 0);
};

const persistXpForUser = (userId, totalXp) => {
  if (!userId) return;
  const ledger = readPersistedXpLedger();
  const key = String(userId);
  const nextTotal = mergeMonotonicTotalXp(totalXp, ledger?.[key]);
  writeStoredJson(XP_LEDGER_STORAGE_KEY, {
    ...ledger,
    [key]: nextTotal,
  });
};

const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

const profileFirstName = (user) => user?.first_name || user?.firstName || "User";
const profileLastName = (user) => user?.last_name || user?.lastName || "";
const profileFullName = (user) => [profileFirstName(user), profileLastName(user)].filter(Boolean).join(" ");
const profileInitials = (user) => {
  const first = profileFirstName(user).charAt(0);
  const last = profileLastName(user).charAt(0);
  return `${first}${last || ""}`.toUpperCase();
};
const greetingForDate = (date = new Date()) => {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
};

const readCurrentUser = () => {
  try {
    return JSON.parse(window.localStorage.getItem(CURRENT_USER_STORAGE_KEY) || "null");
  } catch {
    return null;
  }
};

const apiErrorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return detail?.message || detail?.error || error?.message || fallback;
};
const authErrorMessage = (error, fallback) => apiErrorMessage(error, fallback);
const readProgressGuideDismissed = () => readStoredJson(PROGRESS_GUIDE_STORAGE_KEY, false);
const settingsErrorMessage = (error, fallback) => apiErrorMessage(error, fallback);

const timeToMinutes = (value) => {
  const [hours, minutes] = String(value || "").split(":").map((part) => Number(part));
  return hours * 60 + minutes;
};

const openNativeTimePicker = (event) => {
  try {
    event.currentTarget.showPicker?.();
  } catch {
    // Some browsers only allow showPicker during direct pointer gestures.
  }
};

const settingsFormFromUser = (user) => ({
  working_hours_start: user?.working_hours_start || user?.workday_start_local || "09:00",
  working_hours_end: user?.working_hours_end || user?.workday_end_local || "17:00",
  focus_xp_multiplier: String(user?.focus_xp_multiplier ?? FOCUS_XP_MULTIPLIER),
});

const settingsFormFromApi = (settings) => ({
  working_hours_start: settings?.working_hours_start || "09:00",
  working_hours_end: settings?.working_hours_end || "17:00",
  focus_xp_multiplier: String(settings?.focus_xp_multiplier ?? FOCUS_XP_MULTIPLIER),
});

const multiplierSliderValue = (value) => {
  const multiplier = Number(value);
  if (!Number.isFinite(multiplier)) return FOCUS_XP_MULTIPLIER;
  return Math.min(3, Math.max(0.25, multiplier));
};

const focusMultiplierFromUser = (user) => {
  const multiplier = Number(user?.focus_xp_multiplier);
  return Number.isFinite(multiplier) && multiplier > 0 ? multiplier : FOCUS_XP_MULTIPLIER;
};

const mergeSettingsIntoUser = (user, settings) => ({
  ...user,
  working_hours_start: settings.working_hours_start,
  working_hours_end: settings.working_hours_end,
  workday_start_local: settings.working_hours_start,
  workday_end_local: settings.working_hours_end,
  focus_xp_multiplier: settings.focus_xp_multiplier,
});

const validateSettingsForm = (form) => {
  const errors = {};
  const timePattern = /^(?:[01]\d|2[0-3]):[0-5]\d$/;
  if (!timePattern.test(form.working_hours_start)) {
    errors.working_hours_start = "Enter a valid start time.";
  }
  if (!timePattern.test(form.working_hours_end)) {
    errors.working_hours_end = "Enter a valid end time.";
  }
  if (!errors.working_hours_start && !errors.working_hours_end && timeToMinutes(form.working_hours_end) <= timeToMinutes(form.working_hours_start)) {
    errors.working_hours_end = "End time must be after start time.";
  }
  const multiplier = Number(form.focus_xp_multiplier);
  if (!Number.isFinite(multiplier) || multiplier <= 0) {
    errors.focus_xp_multiplier = "Enter a positive multiplier.";
  }
  return errors;
};

const truncateText = (value, maxLength = 46) => {
  const text = String(value || "");
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}...` : text;
};

const scheduleHeadingForDate = (dateKey) => {
  const selected = dateKey || todayKey();
  if (selected === todayKey()) return "Today's Schedule";
  if (selected === addDaysKey(todayKey(), 1)) return "Tomorrow's Schedule";
  return `${new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${selected}T00:00:00`))} Schedule`;
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

const Sidebar = ({ open, onClose, levelProgress, streakDays }) => {
  const streakState = streakHeat(streakDays);
  return (
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

    <div className={`sidebar-card streak-card streak-card-${streakState.tone}`} data-testid="sidebar-streak-card">
      <div className="mini-title"><Fire size={20} weight="fill" aria-hidden="true" /> Streak</div>
      <strong data-testid="streak-days-value">{streakDays} day{streakDays === 1 ? "" : "s"}</strong>
      <span className="streak-heat-label" data-testid="streak-heat-label">{streakState.label}</span>
      <p>{streakState.description}</p>
    </div>

    <div className="sidebar-card level-card" data-testid="sidebar-level-card">
      <div className="level-row">
        <ShieldStar size={34} weight="duotone" aria-hidden="true" />
        <div>
          <strong data-testid="level-value">Level {levelProgress.level}</strong>
          <span data-testid="level-progress-label">{levelProgress.currentLevelXp} / {levelProgress.xpForNextLevel} XP to Level {levelProgress.level + 1}</span>
        </div>
      </div>
      <div className="progress-track" data-testid="level-progress-track" aria-label="Level progress">
        <span className="progress-fill level-fill" style={{ width: `${levelProgress.progressPercent}%` }} data-testid="level-progress-fill" />
      </div>
      <p className="level-total-xp" data-testid="level-total-xp">{levelProgress.totalXp.toLocaleString()} total XP</p>
    </div>
  </aside>
);
};

const Topbar = ({ currentUser, isLoggingOut, onLogout, onMenuClick, theme, onThemeToggle }) => {
  const location = useLocation();
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [currentDate, setCurrentDate] = useState(() => new Date());
  useEffect(() => {
    const intervalId = window.setInterval(() => setCurrentDate(new Date()), 60000);
    return () => window.clearInterval(intervalId);
  }, []);
  const localGreeting = greetingForDate(currentDate);
  const title = location.pathname === "/" ? `${localGreeting}, ${profileFirstName(currentUser)}` : location.pathname === "/focus/analytics" ? "Focus Analytics" : navItems.find((item) => item.path === location.pathname)?.label || "DevQuest";
  const subtitle = location.pathname === "/focus/analytics" ? "Review focus trends, XP, streaks, and consistency." : location.pathname === "/focus" ? "Track deep work against a task." : "Plan the work, capture the learning, and keep momentum visible.";
  const isLight = theme === "light";

  return (
    <header className="topbar" data-testid="topbar">
      <button className="icon-button mobile-menu" onClick={onMenuClick} aria-label="Open navigation" data-testid="mobile-menu-button"><SidebarSimple size={24} weight="duotone" /></button>
      <div className="topbar-title">
        <h1 data-testid="page-title">{title}</h1>
        <p data-testid="page-subtitle">{subtitle}</p>
      </div>
      <button className="theme-toggle" type="button" onClick={onThemeToggle} aria-label={`Switch to ${isLight ? "dark" : "light"} theme`} aria-pressed={isLight} data-testid="theme-toggle-button">
        <span className="toggle-knob" aria-hidden="true" />
        <Moon className="theme-toggle-icon theme-toggle-icon-moon" size={18} weight={isLight ? "duotone" : "fill"} aria-hidden="true" />
        <SunDim className="theme-toggle-icon theme-toggle-icon-sun" size={18} weight={isLight ? "fill" : "duotone"} aria-hidden="true" />
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

const StatCard = ({ label, value, detail, detailInsight, icon, tone, trend, down, progress, testId }) => {
  const insightDirection = detailInsight?.direction;
  const direction = insightDirection || (down ? "down" : "up");
  const showTrend = trend || insightDirection === "up" || insightDirection === "down";
  const detailText = detailInsight?.label || detail;
  return (
    <section className="stat-card surface" data-testid={testId}>
      <div className="stat-head"><span>{label}</span><IconBadge icon={icon} tone={tone} testId={`${testId}-icon`} /></div>
      <div className="stat-value" data-testid={`${testId}-value`}>{value}</div>
      {typeof progress === "number" && <div className="progress-track" data-testid={`${testId}-progress-track`} aria-label={`${label} progress`}><span className="progress-fill" style={{ width: `${progress}%` }} data-testid={`${testId}-progress-fill`} /></div>}
      <div className={`stat-detail stat-detail-chip ${direction === "down" ? "negative" : direction === "neutral" ? "neutral" : "positive"}`} data-testid={`${testId}-detail`}>
        {showTrend && (direction === "down" ? <TrendDown size={17} weight="bold" aria-hidden="true" /> : <TrendUp size={17} weight="bold" aria-hidden="true" />)}
        {detailText}
      </div>
    </section>
  );
};

const MissionCard = ({ task, index, questMeta }) => {
  const Icon = task.icon;
  const displayExternalId = task.externalId || task.external_id || task.id;
  const missionDescription = task.description || task.aiInsight;
  const tshirtSize = task.rcaTshirtSize || task.rca_tshirt_size || task.jiraTshirtSize || "";
  return (
    <article className={`mission-card mission-${task.accent}`} data-testid={`mission-card-${slug(task.id)}`}>
      <IconBadge icon={Icon} tone={task.accent} testId={`mission-icon-${slug(task.id)}`} />
      <div className="mission-copy">
        <div className="mission-title-row">
          <h3 data-testid={`mission-title-${slug(task.id)}`}>{task.title}</h3>
          <Pill tone={task.type.toLowerCase()} testId={`mission-type-${slug(task.id)}`}>{task.type}</Pill>
          <Pill tone={slug(task.status)} testId={`mission-status-${slug(task.id)}`}>{task.status}</Pill>
        </div>
        <p className="mission-meta" data-testid={`mission-meta-${slug(task.id)}`}>{task.source} - {displayExternalId}</p>
        <p data-testid={`mission-description-${slug(task.id)}`}>{missionDescription}</p>
        {questMeta && <p className="quest-rationale" data-testid={`quest-rationale-${slug(task.id)}`}>{questMeta.rationale}</p>}
      </div>
      <div className="mission-score">
        {questMeta && <span className={`quest-action quest-action-${slug(task.status)}`} data-testid={`quest-action-${slug(task.id)}`}>{questMeta.action}</span>}
        <Pill tone={task.priority.toLowerCase()} testId={`mission-priority-${slug(task.id)}`}>{task.priority}</Pill>
        {tshirtSize && <Pill tone={`tshirt-${slug(tshirtSize)}`} testId={`mission-tshirt-${slug(task.id)}`}>{tshirtSize}</Pill>}
        <span data-testid={`mission-time-${slug(task.id)}`}><Clock size={16} weight="duotone" aria-hidden="true" /> {task.time} mins</span>
        <strong data-testid={`mission-xp-${slug(task.id)}`}>{task.xp} XP</strong>
        <span className="mission-rank" data-testid={`mission-rank-${slug(task.id)}`}>#{index + 1}</span>
      </div>
    </article>
  );
};

const SchedulePanel = ({ events = schedule, removedEvents = [], onUpdateEvent, onRemoveEvent, onRestoreEvent, selectedDate = todayKey(), onDateChange, onFetchDate, isFetchingDate = false }) => {
  const [editingEventId, setEditingEventId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [savingEventId, setSavingEventId] = useState(null);

  const startEditing = (event) => {
    setEditingEventId(event.eventId);
    setEditingTitle(event.title || "");
  };
  const cancelEditing = () => {
    setEditingEventId(null);
    setEditingTitle("");
  };
  const saveTitle = async (event) => {
    const title = editingTitle.trim();
    if (!title || !event.eventId) return;
    setSavingEventId(event.eventId);
    try {
      await onUpdateEvent?.(event.eventId, title);
      cancelEditing();
    } finally {
      setSavingEventId(null);
    }
  };

  return (
    <section className="surface schedule-panel" data-testid="schedule-panel">
      <div className="section-heading schedule-heading">
        <h2><CalendarBlank size={26} weight="duotone" aria-hidden="true" /> {scheduleHeadingForDate(selectedDate)}</h2>
        {onFetchDate && (
          <div className="schedule-date-controls">
            <input type="date" value={selectedDate} onChange={(event) => onDateChange?.(event.target.value)} aria-label="Calendar date" data-testid="schedule-date-input" />
            <button className="ghost-button" type="button" onClick={onFetchDate} disabled={isFetchingDate} data-testid="fetch-schedule-date-button">
              {isFetchingDate ? <ArrowClockwise className="sync-spin" size={17} weight="bold" aria-hidden="true" /> : <CloudArrowDown size={17} weight="duotone" aria-hidden="true" />}
              {isFetchingDate ? "Fetching..." : "Fetch Calendar"}
            </button>
          </div>
        )}
      </div>
      <div className="timeline" data-testid="schedule-timeline">
        {events.map((event) => {
          const isEditing = editingEventId && String(editingEventId) === String(event.eventId);
          const isSaving = savingEventId && String(savingEventId) === String(event.eventId);
          return (
            <div className="timeline-row" key={event.id || `${event.time}-${event.title}`} data-testid={`schedule-row-${slug(event.time)}`}>
              <time data-testid={`schedule-time-${slug(event.time)}`}>{event.time}</time>
              <span className={`timeline-dot timeline-${event.color}`} data-testid={`schedule-dot-${slug(event.time)}`} />
              <article className={`event-card event-${event.color}`} data-testid={`schedule-event-${slug(event.title)}`}>
                {isEditing ? (
                  <input
                    className="event-title-input"
                    value={editingTitle}
                    onChange={(inputEvent) => setEditingTitle(inputEvent.target.value)}
                    onKeyDown={(keyEvent) => {
                      if (keyEvent.key === "Enter") saveTitle(event);
                      if (keyEvent.key === "Escape") cancelEditing();
                    }}
                    aria-label={`Edit ${event.title} title`}
                    data-testid={`schedule-title-input-${slug(event.title)}`}
                    autoFocus
                  />
                ) : (
                  <strong data-testid={`schedule-title-${slug(event.title)}`}>{event.title}</strong>
                )}
                <span data-testid={`schedule-duration-${slug(event.title)}`}>{event.duration}</span>
                {event.focus && <Lightning size={22} weight="fill" aria-hidden="true" />}
                {onUpdateEvent && event.eventId && !isEditing && (
                  <button className="event-icon-button event-edit-button" type="button" onClick={() => startEditing(event)} aria-label={`Edit ${event.title} title`} data-testid={`edit-schedule-event-${slug(event.title)}`}>
                    <PencilSimple size={16} weight="bold" aria-hidden="true" />
                  </button>
                )}
                {isEditing && (
                  <>
                    <button className="event-icon-button event-save-button" type="button" onClick={() => saveTitle(event)} disabled={isSaving || !editingTitle.trim()} aria-label={`Save ${event.title} title`} data-testid={`save-schedule-event-${slug(event.title)}`}>
                      <CheckCircle size={16} weight="bold" aria-hidden="true" />
                    </button>
                    <button className="event-icon-button event-cancel-button" type="button" onClick={cancelEditing} disabled={isSaving} aria-label={`Cancel editing ${event.title}`} data-testid={`cancel-schedule-event-${slug(event.title)}`}>
                      <X size={16} weight="bold" aria-hidden="true" />
                    </button>
                  </>
                )}
                {onRemoveEvent && event.eventId && !isEditing && (
                  <button className="event-icon-button event-remove-button" type="button" onClick={() => onRemoveEvent(event.eventId)} aria-label={`Remove ${event.title} from today's schedule`} data-testid={`remove-schedule-event-${slug(event.title)}`}>
                    <X size={16} weight="bold" aria-hidden="true" />
                  </button>
                )}
              </article>
            </div>
          );
        })}
        {!events.length && <p className="empty-state">No events in today&apos;s schedule.</p>}
      </div>
      {!!removedEvents.length && (
        <div className="removed-events-panel" data-testid="removed-calendar-events">
          <h3>Removed events</h3>
          {removedEvents.map((event) => (
            <article className="removed-event-row" key={event.id || event.eventId || event.title}>
              <span>{event.time}</span>
              <strong>{event.title}</strong>
              <button className="ghost-button" type="button" onClick={() => onRestoreEvent?.(event.eventId)} data-testid={`restore-schedule-event-${slug(event.title)}`}>
                <ArrowClockwise size={16} weight="bold" aria-hidden="true" /> Restore
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

const FocusWidget = ({ tasks = [], focusSessions = [], activeSession, questContext, onStartFocus, onPauseFocus, onResumeFocus, onStopFocus, compact = false }) => {
  const taskOptions = useMemo(() => orderedFocusTasks(tasks), [tasks]);
  const [selectedTaskId, setSelectedTaskId] = useState(() => activeSession?.task_id || taskOptions[0]?.id || "");
  const [outcomeType, setOutcomeType] = useState("Progress made");
  const [outcomeNote, setOutcomeNote] = useState("");
  const [, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!selectedTaskId && taskOptions[0]?.id) setSelectedTaskId(taskOptions[0].id);
    if (!activeSession && selectedTaskId && !taskOptions.some((task) => task.id === selectedTaskId)) setSelectedTaskId(taskOptions[0]?.id || "");
  }, [activeSession, selectedTaskId, taskOptions]);

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
  const activeTask = activeSession ? tasks.find((task) => task.id === activeSession.task_id) || selectedTask : null;
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

  if (activeSession) {
    const activeTaskTitle = activeSession.task_title || activeTask?.title || "Current focus task";
    const activeTaskContext = activeTask?.source ? `${activeTask.source}${activeTask.priority ? ` - ${activeTask.priority}` : ""}` : "Focus session";

    return (
      <section className="surface focus-widget focus-widget-active" data-testid="focus-widget" aria-label="Active focus session">
        <div className="focus-hero-grid focus-hero-grid-active">
          <div className="timer-ring focus-session-ring" style={{ "--timer-progress": `${progress}deg` }} data-testid="focus-timer-ring" aria-label="Focus session progress">
            <div><strong data-testid="focus-timer-value">{formatTimer(elapsedSeconds)}</strong><span data-testid="focus-timer-label">{statusLabel}</span></div>
          </div>
        </div>
        <article className="focus-active-task-card" data-testid="focus-active-task">
          <span>{activeTaskContext}</span>
          <strong>{activeTaskTitle}</strong>
        </article>
        <div className="focus-actions focus-active-actions">
          {activeSession.isRunning && <button className="primary-action" onClick={onPauseFocus} data-testid="focus-pause-button"><Hourglass size={20} weight="duotone" aria-hidden="true" /> Pause</button>}
          {!activeSession.isRunning && <button className="primary-action" onClick={onResumeFocus} data-testid="focus-resume-button"><Play size={20} weight="fill" aria-hidden="true" /> Resume</button>}
          <button className="ghost-button focus-save-action" onClick={stopFocus} data-testid="focus-stop-button"><CheckCircle size={20} weight="duotone" aria-hidden="true" /> Stop &amp; save</button>
        </div>
      </section>
    );
  }

  return (
    <section className={`surface focus-widget focus-launcher-card ${compact ? "focus-compact" : ""}`} data-testid="focus-widget">
      <div className="focus-launcher-head">
        <div>
          <h2><Timer size={26} weight="duotone" aria-hidden="true" /> Start a focus session</h2>
          <p>Choose a task and begin deep work.</p>
        </div>
      </div>
      <div className="focus-launcher-layout" data-testid="focus-session-layout">
        <div className="focus-hero-grid focus-launcher-hero">
          <div className="timer-ring focus-session-ring" style={{ "--timer-progress": `${progress}deg` }} data-testid="focus-timer-ring" aria-label="Focus session progress">
            <div><strong data-testid="focus-timer-value">{formatTimer(elapsedSeconds)}</strong><span data-testid="focus-timer-label">{statusLabel}</span></div>
          </div>
        </div>
        <div className="focus-launcher-panel">
          <label className="focus-task-picker">
            Focus task
            <select value={selectedTaskId} onChange={(event) => setSelectedTaskId(event.target.value)} disabled={Boolean(activeSession) || !hasTasks} data-testid="focus-task-select">
              {taskOptions.map((task) => <option key={task.id} value={task.id}>{task.workingToday ? "Today - " : ""}{truncateText(task.title, 24)}</option>)}
              {!taskOptions.length && <option value="">No open tasks</option>}
            </select>
          </label>
          {!compact && selectedTask && (
            <article className="focus-selected-task focus-launcher-selected" data-testid="focus-selected-task">
              <div className="focus-selected-copy">
                <span>{selectedTask.source}</span>
                <strong>{selectedTask.title}</strong>
                {selectedTask.description ? <p>{selectedTask.description}</p> : <p>{selectedTask.priority} priority work ready for a focused block.</p>}
              </div>
              <div className="focus-selected-meta" aria-label="Selected task details">
                <Pill tone={selectedTask.priority.toLowerCase()}>{selectedTask.priority}</Pill>
                <span>{plannedMinutes}</span>
                <span>{formatMinutes(selectedTaskFocusedToday)} today</span>
                <FocusQuestBadge quest={selectedQuest ? { ...selectedQuest, focusMinutes: selectedQuestFocusMinutes, focusTargetMinutes: selectedQuestTargetMinutes } : null} />
              </div>
            </article>
          )}
          {!compact && !selectedTask && (
            <div className="focus-empty-state" data-testid="focus-empty-state">
              <strong>No tasks ready for focus.</strong>
              <p>Create a task or open My Tasks to make Focus Mode actionable.</p>
              <div className="focus-empty-actions">
                <NavLink className="ghost-button" to="/tasks" data-testid="focus-create-task-link">Create task</NavLink>
                <NavLink className="ghost-button" to="/tasks" data-testid="focus-view-tasks-link">View My Tasks</NavLink>
              </div>
            </div>
          )}
          <div className="focus-actions focus-launcher-actions">
            {!activeSession && <button className="primary-action focus-start-primary" onClick={startFocus} disabled={!selectedTask} data-testid="focus-start-pause-button"><Play size={20} weight="fill" aria-hidden="true" /> Start focus session</button>}
            {activeSession?.isRunning && <button className="primary-action" onClick={onPauseFocus} data-testid="focus-pause-button"><Hourglass size={20} weight="duotone" aria-hidden="true" /> Pause</button>}
            {activeSession && !activeSession.isRunning && <button className="primary-action" onClick={onResumeFocus} data-testid="focus-resume-button"><Play size={20} weight="fill" aria-hidden="true" /> Resume</button>}
            {activeSession && <button className="ghost-button focus-save-action" onClick={stopFocus} data-testid="focus-stop-button"><CheckCircle size={20} weight="duotone" aria-hidden="true" /> Stop &amp; save</button>}
          </div>
        </div>
      </div>
      {!compact && activeSession && (
        <div className="focus-outcome-panel" data-testid="focus-outcome-panel">
          <span>Wrap up session</span>
          <div className="focus-chip-row">
            {focusOutcomes.map((outcome) => <button key={outcome} className={`focus-chip ${outcomeType === outcome ? "active" : ""}`} onClick={() => setOutcomeType(outcome)} type="button">{outcome}</button>)}
          </div>
          <textarea value={outcomeNote} onChange={(event) => setOutcomeNote(event.target.value)} placeholder="What changed during this session?" data-testid="focus-outcome-note" />
        </div>
      )}
    </section>
  );
};

const TaskTable = ({ tasks, onStatusChange, onEdit, onToggleToday, onUpdateNotes, onOpenEnrichmentDetails, editable = true }) => {
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
            const isEnrichmentJob = Boolean(task.isEnrichmentJob);
            const enrichmentJobId = task.enrichmentJobId || task.sourceEnrichmentJobId;
            const enrichmentStatus = String(task.enrichmentStatus || "").toUpperCase();
            const isTaskEnrichmentActive = activeEnrichmentStatuses.has(enrichmentStatus);
            const canOpenEnrichmentDetails = Boolean(enrichmentJobId && onOpenEnrichmentDetails);
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
                    disabled={task.status === "Done" || isEnrichmentJob}
                    data-testid={`task-today-button-${slug(task.id)}`}
                  >
                    {isEnrichmentJob ? "Pending" : task.status === "Done" ? "Done" : task.workingToday ? "Working" : "Add"}
                  </button>
                </td>
                <td data-testid={`task-source-${slug(task.id)}`}>{task.source}</td>
                <td><Pill tone={task.priority.toLowerCase()} testId={`task-priority-${slug(task.id)}`}>{task.priority}</Pill></td>
                <td className="ai-cell" data-testid={`task-ai-${slug(task.id)}`}>
                  {isEnrichmentJob ? (
                    <>
                      <span className="ai-score enrichment-spinner"><Hourglass size={16} weight="duotone" aria-hidden="true" /></span>
                      <span>{task.enrichmentStatusLabel || "AI enrichment in progress"}</span>
                      {canOpenEnrichmentDetails && (
                        <button
                          className="row-icon-action enrichment-ai-action"
                          aria-label={`Open enrichment details for ${task.title}`}
                          title="Enrichment details"
                          onClick={() => onOpenEnrichmentDetails?.(enrichmentJobId)}
                          data-testid={`task-enrichment-details-button-${slug(task.id)}`}
                        >
                          <Sparkle size={17} weight="duotone" />
                        </button>
                      )}
                    </>
                  ) : (
                    <>
                      {isTaskEnrichmentActive ? (
                        <>
                          <span className="ai-score enrichment-spinner"><Hourglass size={16} weight="duotone" aria-hidden="true" /></span>
                          <span>{task.enrichmentStatusLabel || "AI enrichment in progress"}</span>
                        </>
                      ) : (
                        <>
                          <span className="ai-score">{Math.round((task.priorityScore || 0) * 100)}%</span>
                          <span>{task.difficulty} - impact {task.impact}/10</span>
                        </>
                      )}
                      {canOpenEnrichmentDetails && (
                        <button
                          className="row-icon-action enrichment-ai-action"
                          aria-label={`Open enrichment details for ${task.title}`}
                          title="Enrichment details"
                          onClick={() => onOpenEnrichmentDetails?.(enrichmentJobId)}
                          data-testid={`task-enrichment-details-button-${slug(task.id)}`}
                        >
                          <Sparkle size={17} weight="duotone" />
                        </button>
                      )}
                    </>
                  )}
                </td>
                <td data-testid={`task-time-${slug(task.id)}`}>{task.time} mins</td>
                <td data-testid={`task-xp-${slug(task.id)}`}>{task.xp} XP</td>
                <td data-testid={`task-completed-${slug(task.id)}`}>{isEnrichmentJob ? task.enrichmentStatusLabel : formatDateTime(task.completedAt)}</td>
                <td>
                  <select
                    className={`status-select status-select-${slug(task.status)}`}
                    value={task.status}
                    onChange={(event) => onStatusChange(task.id, event.target.value)}
                    data-testid={`task-status-${slug(task.id)}`}
                    aria-label={`Status for ${task.title}`}
                    disabled={isEnrichmentJob}
                  >
                    {tableStatuses.map((status) => <option key={status} value={status}>{status}</option>)}
                  </select>
                </td>
                <td className="notes-cell">
                  <textarea
                    className={`inline-notes ${editable ? "" : "inline-notes-readonly"}`}
                    value={noteDrafts[task.id] ?? task.notes ?? ""}
                    onChange={(event) => updateNoteDraft(task, event.target.value)}
                    readOnly={!editable || isEnrichmentJob}
                    aria-label={`Notes for ${task.title}`}
                    data-testid={`task-notes-${slug(task.id)}`}
                  />
                </td>
                {editable && (
                  <td className="action-menu-cell">
                    {isEnrichmentJob ? (
                      <span className="row-action-placeholder" aria-hidden="true">-</span>
                    ) : hasUnsavedNote ? (
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
const TaskEditor = ({ mode = "create", task, onSubmit, onCancel, onSelectCodeBase }) => {
  const [form, setForm] = useState(task ? formFromTask(task) : emptyTaskForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSelectingCodeBase, setIsSelectingCodeBase] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const submitInFlightRef = useRef(false);
  const isJiraEnrichment = form.source === "Jira" && form.runAiEnrichment;
  const isCodeBaseEnabled = form.source === "Jira";
  const xpPreview = useMemo(() => deriveTaskXpBreakdown({
    title: form.title,
    type: form.type,
    priority: form.priority,
    estimatedMinutes: form.estimatedMinutes,
    rcaTshirtSize: form.rcaTshirtSize,
    notes: form.notes,
  }), [form]);

  useEffect(() => {
    setForm(task ? formFromTask(task) : emptyTaskForm);
    setIsSubmitting(false);
    setIsSelectingCodeBase(false);
    setSubmitError("");
    setFieldErrors({});
    submitInFlightRef.current = false;
  }, [task]);

  const update = (field, value) => {
    setForm((current) => ({
      ...current,
      [field]: value,
      ...(field === "source" && value !== "Jira" ? { codeBaseLocation: "" } : {}),
    }));
    setFieldErrors((current) => ({ ...current, [field]: "" }));
    setSubmitError("");
  };

  const validate = () => {
    const errors = {};
    if (!form.title.trim()) errors.title = "Title is required.";
    if (!form.type) errors.type = "Type is required.";
    if (!form.source) errors.source = "Source is required.";
    if (!form.priority) errors.priority = "Priority is required.";
    if (!form.status) errors.status = "Status is required.";
    if (isJiraEnrichment && !form.externalId.trim()) errors.externalId = "External ID is required for Jira AI enrichment.";
    if (isJiraEnrichment && !form.codeBaseLocation.trim()) errors.codeBaseLocation = "Code Base Location is required for Jira AI enrichment.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const selectCodeBase = async () => {
    if (!onSelectCodeBase || !isCodeBaseEnabled) return;
    setIsSelectingCodeBase(true);
    setSubmitError("");
    try {
      const path = await onSelectCodeBase(form.codeBaseLocation);
      if (path) update("codeBaseLocation", path);
    } catch (error) {
      setSubmitError(apiErrorMessage(error, "Unable to select code base folder."));
    } finally {
      setIsSelectingCodeBase(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    if (submitInFlightRef.current) return;
    if (!validate()) return;
    submitInFlightRef.current = true;
    setIsSubmitting(true);
    setSubmitError("");
    try {
      await onSubmit(form);
      if (mode === "create") {
        setForm(emptyTaskForm);
        setFieldErrors({});
      }
    } catch (error) {
      setSubmitError(apiErrorMessage(error, "Unable to save task."));
    } finally {
      submitInFlightRef.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <form className="task-editor-form" onSubmit={submit} noValidate data-testid={`${mode}-task-form`}>
      <label>
        Title
        <input value={form.title} onChange={(event) => update("title", event.target.value)} placeholder="Investigate CI failure" aria-invalid={Boolean(fieldErrors.title)} aria-describedby={fieldErrors.title ? `${mode}-task-title-error` : undefined} data-testid={`${mode}-task-title-input`} />
        {fieldErrors.title && <span className="field-error" id={`${mode}-task-title-error`}>{fieldErrors.title}</span>}
      </label>
      <label>Description<textarea value={form.description} onChange={(event) => update("description", event.target.value)} placeholder="What needs to happen?" data-testid={`${mode}-task-description-input`} /></label>
      <label>
        Type
        <select value={form.type} onChange={(event) => update("type", event.target.value)} aria-invalid={Boolean(fieldErrors.type)} aria-describedby={fieldErrors.type ? `${mode}-task-type-error` : undefined}>{taskTypes.map((item) => <option key={item}>{item}</option>)}</select>
        {fieldErrors.type && <span className="field-error" id={`${mode}-task-type-error`}>{fieldErrors.type}</span>}
      </label>
      <label>
        Source
        <select value={form.source} onChange={(event) => update("source", event.target.value)} aria-invalid={Boolean(fieldErrors.source)} aria-describedby={fieldErrors.source ? `${mode}-task-source-error` : undefined}>{sources.map((item) => <option key={item}>{item}</option>)}</select>
        {fieldErrors.source && <span className="field-error" id={`${mode}-task-source-error`}>{fieldErrors.source}</span>}
      </label>
      <label>
        External ID
        <input value={form.externalId} onChange={(event) => update("externalId", event.target.value)} placeholder="PAY-2301" aria-invalid={Boolean(fieldErrors.externalId)} aria-describedby={fieldErrors.externalId ? `${mode}-task-external-id-error` : undefined} />
        {fieldErrors.externalId && <span className="field-error" id={`${mode}-task-external-id-error`}>{fieldErrors.externalId}</span>}
      </label>
      <label className="codebase-location-field">
        Code Base Location
        <span className="codebase-location-picker">
          <input value={form.codeBaseLocation} onChange={(event) => update("codeBaseLocation", event.target.value)} placeholder="Select codebase folder" disabled={!isCodeBaseEnabled} aria-invalid={Boolean(fieldErrors.codeBaseLocation)} aria-describedby={fieldErrors.codeBaseLocation ? `${mode}-task-codebase-error` : undefined} data-testid={`${mode}-task-codebase-input`} />
          <button className="ghost-button" type="button" onClick={selectCodeBase} disabled={!isCodeBaseEnabled || isSelectingCodeBase} data-testid={`${mode}-select-codebase-button`}>
            <FolderOpen size={17} weight="duotone" aria-hidden="true" /> {isSelectingCodeBase ? "Selecting" : "Browse"}
          </button>
        </span>
        {fieldErrors.codeBaseLocation && <span className="field-error" id={`${mode}-task-codebase-error`}>{fieldErrors.codeBaseLocation}</span>}
      </label>
      <label>
        Priority
        <select value={form.priority} onChange={(event) => update("priority", event.target.value)} aria-invalid={Boolean(fieldErrors.priority)} aria-describedby={fieldErrors.priority ? `${mode}-task-priority-error` : undefined}>{priorities.map((item) => <option key={item}>{item}</option>)}</select>
        {fieldErrors.priority && <span className="field-error" id={`${mode}-task-priority-error`}>{fieldErrors.priority}</span>}
      </label>
      <label>
        Status
        <select value={form.status} onChange={(event) => update("status", event.target.value)} aria-invalid={Boolean(fieldErrors.status)} aria-describedby={fieldErrors.status ? `${mode}-task-status-error` : undefined}>{statuses.map((item) => <option key={item}>{item}</option>)}</select>
        {fieldErrors.status && <span className="field-error" id={`${mode}-task-status-error`}>{fieldErrors.status}</span>}
      </label>
      <label>Due date<input type="date" value={form.dueDate} onChange={(event) => update("dueDate", event.target.value)} /></label>
      <label>Start date<input type="date" value={form.startDate} onChange={(event) => update("startDate", event.target.value)} /></label>
      <label>RCA T-shirt size<select value={form.rcaTshirtSize} onChange={(event) => update("rcaTshirtSize", event.target.value)} data-testid={`${mode}-task-rca-size-select`}>{rcaTshirtSizes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label>Labels<input value={form.labels} onChange={(event) => update("labels", event.target.value)} placeholder="api, backend" /></label>
      <label className="wide-field">Notes<textarea value={form.notes} onChange={(event) => update("notes", event.target.value)} placeholder="Learnings, what went right, what went wrong, blockers..." data-testid={`${mode}-task-notes-input`} /></label>
      <label className="checkbox-field"><input type="checkbox" checked={form.workingToday} onChange={(event) => update("workingToday", event.target.checked)} /> Working on this today</label>
      <label className="checkbox-field"><input type="checkbox" checked={form.runAiEnrichment} onChange={(event) => update("runAiEnrichment", event.target.checked)} /> Run AI enrichment</label>
      {submitError && <p className="form-error" role="alert">{submitError}</p>}
      <div className="editor-actions">
        <div className="task-xp-preview" data-testid={`${mode}-task-xp-preview`}>
          <strong>{xpPreview.xp} XP projected</strong>
          <span>{formatMinutes(xpPreview.estimatedMinutes)} effort | {xpPreview.difficulty} difficulty | focus bonus after {formatMinutes(xpPreview.focusUnlockMinutes)}</span>
        </div>
        {onCancel && <button type="button" className="ghost-button" onClick={onCancel} disabled={isSubmitting} data-testid={`${mode}-task-cancel-button`}>Cancel</button>}
        <button className="primary-action" type="submit" disabled={isSubmitting} data-testid={`${mode}-task-submit-button`}>
          {mode === "create" && <Plus size={19} weight="bold" aria-hidden="true" />}
          {isSubmitting ? "Saving..." : mode === "edit" ? "Save Task" : "Add Task"}
        </button>
      </div>
    </form>
  );
};

const completedTodayTasks = (tasks) => tasks.filter((task) => task.status === "Done" && isSameDay(task.completedAt));

const uniqueTasksById = (tasks) => [...new Map(tasks.filter(Boolean).map((task) => [task.id, task])).values()];

const dashboardTaskFilters = ["All", "Working Today", "Done"];

const normalizeTaskPayload = (task) => (
  task && (
    Object.prototype.hasOwnProperty.call(task, "task_id")
    || Object.prototype.hasOwnProperty.call(task, "working_today")
    || Object.prototype.hasOwnProperty.call(task, "external_source")
    || Object.prototype.hasOwnProperty.call(task, "estimated_minutes")
  )
    ? normalizeApiTask(task)
    : normalizeTask(task)
);

const taskBackendKey = (task) => String(task?.taskId || task?.id || "").trim();
const taskMatchesBackendKey = (task, backendKey) => String(taskBackendKey(task)) === String(backendKey || "").trim();

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

const normalizeStandupNote = (note, fallback) => {
  if (!note) return fallback;
  const sentences = Array.isArray(note.sentences) ? note.sentences : [];
  const fullNote = note.full_note || note.fullNote || sentences.join(" ") || fallback.fullNote;
  return {
    accomplished: note.accomplished || fallback.accomplished,
    inProgress: note.in_progress || note.inProgress || fallback.inProgress,
    blockers: note.blockers || fallback.blockers,
    nextSteps: note.next_steps || note.nextSteps || fallback.nextSteps,
    fullNote,
    mode: note.mode,
    modelId: note.model_id || note.modelId,
    generatedAt: note.generated_at || note.generatedAt,
  };
};

const PageLoader = ({ title = "Loading", detail = "Getting the latest data ready.", steps = ["Tasks", "Capacity", "AI"] }) => (
  <main className="page-stack page-loading-shell" data-testid="page-loader" aria-live="polite" aria-busy="true">
    <section className="surface page-loader-card" role="status">
      <div className="page-loader-visual" aria-hidden="true">
        <span className="page-loader-orbit" />
        <span className="page-loader-core">
          <Hourglass size={34} weight="duotone" />
        </span>
      </div>
      <strong>{title}</strong>
      <p>{detail}</p>
      <div className="page-loader-steps" aria-hidden="true">
        {steps.map((step) => <span key={step}>{step}</span>)}
      </div>
    </section>
  </main>
);

const FloatingNotice = ({ notice, onDismiss }) => {
  if (!notice) return null;
  return (
    <div className={`floating-notice floating-notice-${notice.tone || "success"}`} role="status" aria-live="polite" data-testid="floating-notice">
      <div className="floating-notice-copy">
        <strong>{notice.title}</strong>
        {notice.message && <span>{notice.message}</span>}
        {notice.detail && <span>{notice.detail}</span>}
      </div>
      <button className="floating-notice-close" type="button" onClick={onDismiss} aria-label="Dismiss notification" data-testid="floating-notice-close">
        <X size={16} weight="bold" aria-hidden="true" />
      </button>
    </div>
  );
};

const activeEnrichmentStatuses = new Set(["QUEUED", "RUNNING"]);
const terminalEnrichmentStatuses = new Set(["SUCCEEDED", "FAILED", "AUTH_REQUIRED", "CANCELLED"]);

const enrichmentJobId = (job) => job?.enrichment_job_id || job?.enrichmentJobId || job?.id;
const enrichmentJobTaskId = (job) => {
  const request = job?.request || {};
  return job?.task_id || job?.taskId || request.existingTaskId || request.existing_task_id || request.taskId || request.task_id || null;
};
const enrichmentStatusLabel = (status) => {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "QUEUED") return "Queued";
  if (normalized === "RUNNING") return "AI enrichment in progress";
  if (normalized === "SUCCEEDED") return "Completed";
  if (normalized === "AUTH_REQUIRED") return "Jira sign-in required";
  if (normalized === "CANCELLED") return "Cancelled";
  if (normalized === "FAILED") return "Failed";
  return "AI enrichment";
};

const jobToTask = (job) => {
  const fields = job?.jira_fields || job?.jiraFields || {};
  const request = job?.request || {};
  const result = job?.rca_result || job?.rcaResult || {};
  const status = String(job?.status || "QUEUED").toUpperCase();
  return normalizeTask({
    id: `enrichment-${enrichmentJobId(job)}`,
    title: fields.title || request.title || job?.external_id || job?.externalId || "Jira enrichment",
    description: status === "FAILED" || status === "AUTH_REQUIRED"
      ? job?.error_message || job?.errorMessage || enrichmentStatusLabel(status)
      : fields.description || "The task will appear after AI enrichment finishes.",
    source: "Jira",
    externalId: job?.external_id || job?.externalId || request.externalId || "",
    type: fields.type || request.type || "Task",
    priority: fields.priority || request.priority || "Medium",
    status: status === "SUCCEEDED" ? "Done" : status === "FAILED" || status === "AUTH_REQUIRED" ? "Blocked" : "In Progress",
    time: request.estimatedMinutes || 60,
    xp: result.xp_value || 0,
    workingToday: Boolean(request.workingToday ?? true),
    notes: "",
    isEnrichmentJob: true,
    enrichmentJobId: enrichmentJobId(job),
    enrichmentStatus: status,
    enrichmentStatusLabel: enrichmentStatusLabel(status),
    accent: status === "FAILED" || status === "AUTH_REQUIRED" ? "red" : "cyan",
  });
};

const EnrichmentDetailsModal = ({ job, onClose, onRefresh }) => {
  if (!job) return null;
  const fields = job.jira_fields || job.jiraFields || {};
  const result = job.rca_result || job.rcaResult || {};
  const logs = Array.isArray(job.logs) ? job.logs : [];
  const affectedFiles = result.affected_files || result.affectedFiles || result.rca_affected_files || result.rcaAffectedFiles || [];
  const codeSuggestion = result.code_suggestion || result.codeSuggestion || result.code_fix_suggestion || result.codeFixSuggestion || result.rca_code_suggestion || result.rcaCodeSuggestion || "";
  const tshirt = result.tshirt_sizing || result.tshirtSizing || result.jira_tshirt_sizing || result.jiraTshirtSizing || {};
  const tshirtSize = result.tshirt_size || result.tshirtSize || result.rca_tshirt_size || result.rcaTshirtSize || tshirt.size || "";
  const tshirtJustification = result.tshirt_justification || result.tshirtJustification || result.rca_tshirt_justification || result.rcaTshirtJustification || tshirt.reason || tshirt.justification || "";
  const error = job.error_message || job.errorMessage || "";
  return (
    <div className="enrichment-modal-backdrop" role="presentation">
      <section className="surface enrichment-modal" role="dialog" aria-modal="true" aria-labelledby="enrichment-modal-title" data-testid="enrichment-details-modal">
        <div className="section-heading enrichment-modal-heading">
          <div>
            <h2 id="enrichment-modal-title"><Sparkle size={26} weight="duotone" aria-hidden="true" /> Enrichment Details</h2>
            <p>{job.external_id || job.externalId} - {enrichmentStatusLabel(job.status)}</p>
          </div>
          <div className="editor-actions">
            <button className="ghost-button" type="button" onClick={onRefresh} data-testid="refresh-enrichment-details-button"><ArrowClockwise size={18} weight="duotone" aria-hidden="true" /> Refresh</button>
            <button className="row-icon-action" type="button" onClick={onClose} aria-label="Close enrichment details" data-testid="close-enrichment-details-button"><X size={18} weight="bold" /></button>
          </div>
        </div>
        <div className="enrichment-detail-stack">
          <section className="enrichment-console-block">
            <strong>Console</strong>
            <pre className="codex-console enrichment-console" data-testid="enrichment-console-output">{logs.map((log) => log.message || log).join("\n") || "Waiting for enrichment output..."}</pre>
          </section>
          <section className="enrichment-summary-block">
            <strong>Enrichment</strong>
            <dl className="enrichment-details-list">
              <dt>Title</dt><dd>{fields.title || "-"}</dd>
              <dt>Description</dt><dd>{fields.description || "-"}</dd>
              <dt>Root cause</dt><dd>{result.rca_reason || result.rcaReason || "-"}</dd>
              <dt>Affected files</dt><dd>{affectedFiles.length ? affectedFiles.map((item) => item.path || item).join(", ") : "-"}</dd>
              <dt>Code suggestion</dt><dd>{codeSuggestion || "-"}</dd>
              <dt>T-shirt size</dt><dd>{tshirtSize || "-"}</dd>
              <dt>Justification</dt><dd>{tshirtJustification || "-"}</dd>
              {error && <><dt>Error</dt><dd className="enrichment-error-text">{error}</dd></>}
            </dl>
          </section>
        </div>
      </section>
    </div>
  );
};

const LevelUpBanner = ({ levelUp }) => {
  if (!levelUp) return null;
  return (
    <div className="level-up-banner" role="status" aria-live="assertive" data-testid="level-up-banner">
      <span className="level-up-kicker">Level up</span>
      <strong>Level {levelUp.level} unlocked</strong>
      <p>{levelUp.message}</p>
    </div>
  );
};

const ProgressGuideCard = ({ page = "dashboard", onDismiss }) => {
  const guideCopy = page === "quests"
    ? {
        title: "Quest flow in one glance",
        caption: "Generate once for today's Working tasks, then clear quests one by one.",
        highlights: [
          {
            title: "Daily run order",
            body: "Generated quests become your sequence for today, so you can move from one clear target to the next.",
          },
          {
            title: "Focus unlocks bonus XP",
            body: "A short timer is not enough. You need meaningful focus on the task before the multiplier kicks in.",
          },
          {
            title: "Regenerate only when scope changes",
            body: "If you add or remove Working Today tasks, regenerate. Otherwise keep progressing through the current run.",
          },
        ],
      }
    : page === "focus"
      ? {
          title: "Focus mode pays off with intent",
          caption: "The timer starts instantly, but the XP bonus only unlocks after meaningful focus.",
          highlights: [
            {
              title: "Each task has a threshold",
              body: "The unlock point is based on task estimate, so longer work needs more focus before bonus XP starts.",
            },
            {
              title: "Deeper work earns more",
              body: "Once unlocked, the multiplier climbs as you cover more of the task, up to your profile cap.",
            },
            {
              title: "Save before switching context",
              body: "Saving syncs the minutes, quest progress, and earned reward back into the rest of the app.",
            },
          ],
        }
      : {
          title: "How DevQuest progression works",
          caption: "A quick primer for new users.",
          highlights: [
            {
              title: "XP reflects real task weight",
              body: "Estimate, priority, impact, type, and complexity all shape the XP value instead of using a flat reward.",
            },
            {
              title: "Levels are paced like a game",
              body: "Early levels move quickly, then the curve slows down so later progress feels more meaningful.",
            },
            {
              title: "Streaks are quest-based",
              body: "A streak only grows on days where you complete at least one quest from your generated run.",
            },
          ],
        };

  return (
    <section className={`surface progress-guide progress-guide-${page}`} data-testid={`progress-guide-${page}`}>
      <div className="section-heading progress-guide-heading">
        <div>
          <h2><Sparkle size={24} weight="duotone" aria-hidden="true" /> {guideCopy.title}</h2>
          <p>{guideCopy.caption}</p>
        </div>
        <button type="button" className="ghost-button progress-guide-dismiss" onClick={onDismiss} data-testid={`progress-guide-dismiss-${page}`}>
          <X size={16} weight="bold" aria-hidden="true" /> Got it
        </button>
      </div>
      <div className="progress-guide-grid">
        {guideCopy.highlights.map((highlight) => (
          <article key={highlight.title} className="progress-guide-item">
            <strong>{highlight.title}</strong>
            <p>{highlight.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
};

const Dashboard = ({ tasks, questRun, focusSessions, activeSession, focusMultiplier, onStartFocus, onPauseFocus, onResumeFocus, onStopFocus, onStatusChange, onEdit, onToggleToday, onUpdateNotes, dashboardStats, dashboardStatInsights, dashboardSchedule, dashboardInsight, dashboardStatus, isLoading, showProgressGuide, onDismissProgressGuide }) => {
  const [activeTaskFilter, setActiveTaskFilter] = useState("All");
  const completedCount = dashboardStats?.tasks_completed_today ?? completedTodayTasks(tasks).length;
  const todayTasks = tasks.filter((task) => task.workingToday);
  const filteredTasks = useMemo(() => filterDashboardTasks(tasks, activeTaskFilter), [tasks, activeTaskFilter]);
  const totalXp = dashboardStats?.total_xp ?? earnedXpForTasks(tasks.filter((task) => task.status === "Done"), focusSessions, null, focusMultiplier);
  const focusedToday = dashboardStats?.focus_minutes ?? dashboardStats?.available_focus_minutes ?? focusMinutesForSessions(sessionsForDay(focusSessions));
  const meetingMinutes = dashboardStats?.meeting_minutes;
  const nextQuest = getNextQuest(questRun);
  const nextQuestTask = getQuestTask(tasks, nextQuest);
  const orderedQuestTasks = getQuestOrderedTasks(tasks, questRun);
  const runMissionTasks = isCurrentQuestRun(questRun) ? [
    nextQuestTask,
    ...(questRun.quests || []).filter((quest) => quest.id !== nextQuest?.id).map((quest) => getQuestTask(tasks, quest)),
  ].filter((task) => task && task.status !== "Done") : [];
  const orderedOpenQuestTasks = orderedQuestTasks.filter((task) => task.status !== "Done");
  const rankedOpenTasks = [...tasks].filter((task) => task.status !== "Done").sort(compareQuestTasks);
  const missionSourceTasks = runMissionTasks.length ? runMissionTasks : orderedOpenQuestTasks.length ? orderedOpenQuestTasks : rankedOpenTasks;
  const topMissions = uniqueTasksById(missionSourceTasks.slice(0, 3));

  if (isLoading) {
    return <PageLoader title="Loading dashboard" detail="Fetching tasks, capacity, calendar, and AI insight data." steps={["Tasks", "Calendar", "AI"]} />;
  }

  return (
    <main className="dashboard-page" data-testid="dashboard-page">
      {showProgressGuide && <ProgressGuideCard page="dashboard" onDismiss={onDismissProgressGuide} />}
      <section className="stats-grid" aria-label="Daily productivity metrics">
        <StatCard label="Total XP" value={`${totalXp.toLocaleString()} XP`} detail="Includes completed work" detailInsight={dashboardStatInsights?.total_xp} icon={Trophy} tone="violet" trend testId="stat-total-xp" />
        <StatCard label="Tasks Completed" value={`${completedCount} today`} detail="Completion date is captured" detailInsight={dashboardStatInsights?.tasks_completed} icon={CheckCircle} tone="blue" progress={Math.min(100, (completedCount / Math.max(1, todayTasks.length)) * 100)} testId="stat-tasks-completed" />
        <StatCard label="Working Today" value={`${todayTasks.length} tasks`} detail="Feeds the Quests page" detailInsight={dashboardStatInsights?.working_today} icon={Flag} tone="gold" testId="stat-working-today" />
        <StatCard label="Focus Time" value={formatMinutes(focusedToday)} detail={dashboardStatus === "live" ? "From Phase 8 capacity API" : "Captured from sessions"} detailInsight={dashboardStatInsights?.focus_minutes} icon={Clock} tone="green" trend testId="stat-focus-time" />
        <StatCard label="Meetings" value={meetingMinutes ? formatMinutes(meetingMinutes) : "3h 10m"} detail={dashboardStatus === "live" ? "From Phase 8 calendar data" : "Tracked in overview"} detailInsight={dashboardStatInsights?.meeting_minutes} icon={CalendarBlank} tone="orange" trend down testId="stat-meetings" />
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

const TasksPage = ({ tasks, enrichmentJobs = [], selectedEnrichmentJob, onAddTask, onSelectCodeBase, onOpenEnrichmentDetails, onCloseEnrichmentDetails, onRefreshEnrichmentDetails, isLoading, onStatusChange, onEdit, onToggleToday, onUpdateNotes }) => {
  const [editingTask, setEditingTask] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [taskFilters, setTaskFilters] = useState(emptyTaskFilters);
  const activeExistingEnrichmentJobs = useMemo(
    () => enrichmentJobs.filter((job) => activeEnrichmentStatuses.has(String(job.status || "").toUpperCase()) && enrichmentJobTaskId(job)),
    [enrichmentJobs],
  );
  const activeEnrichmentByTaskId = useMemo(() => {
    const map = new Map();
    activeExistingEnrichmentJobs.forEach((job) => map.set(String(enrichmentJobTaskId(job)), job));
    return map;
  }, [activeExistingEnrichmentJobs]);
  const activeEnrichmentByExternalId = useMemo(() => {
    const map = new Map();
    activeExistingEnrichmentJobs.forEach((job) => {
      const externalId = String(job.external_id || job.externalId || "").trim().toUpperCase();
      if (externalId) map.set(externalId, job);
    });
    return map;
  }, [activeExistingEnrichmentJobs]);
  const enrichmentTaskRows = useMemo(
    () => enrichmentJobs
      .filter((job) => activeEnrichmentStatuses.has(String(job.status || "").toUpperCase()) && !enrichmentJobTaskId(job))
      .map(jobToTask),
    [enrichmentJobs],
  );
  const tasksWithActiveEnrichment = useMemo(() => tasks.map((task) => {
    const job = activeEnrichmentByTaskId.get(String(task.taskId || task.id))
      || activeEnrichmentByExternalId.get(String(task.externalId || "").trim().toUpperCase());
    if (!job) return task;
    const status = String(job.status || "").toUpperCase();
    return {
      ...task,
      enrichmentJobId: enrichmentJobId(job),
      enrichmentStatus: status,
      enrichmentStatusLabel: enrichmentStatusLabel(status),
    };
  }), [tasks, activeEnrichmentByTaskId, activeEnrichmentByExternalId]);
  const unifiedTasks = useMemo(() => [...enrichmentTaskRows, ...tasksWithActiveEnrichment], [enrichmentTaskRows, tasksWithActiveEnrichment]);
  const filteredTasks = useMemo(() => filterUnifiedTasks(unifiedTasks, taskFilters), [unifiedTasks, taskFilters]);
  const activeFilterCount = Object.entries(taskFilters).filter(([key, value]) => key === "search" ? Boolean(value.trim()) : value !== "All").length;
  const updateFilter = (field, value) => setTaskFilters((current) => ({ ...current, [field]: value }));
  const resetFilters = () => setTaskFilters(emptyTaskFilters);

  if (isLoading) {
    return <PageLoader title="Loading tasks" detail="Reading your saved work items from the backend." steps={["Work items", "Dates", "Stats"]} />;
  }

  return (
    <main className="page-stack" data-testid="tasks-page">
      <section className="surface form-card" data-testid="add-task-card">
        <div className="section-heading"><h2><Plus size={26} weight="duotone" aria-hidden="true" /> Add Task With Full Details</h2><span data-testid="task-count-label">{tasks.length} tasks loaded</span></div>
        <TaskEditor mode="create" onSubmit={onAddTask} onSelectCodeBase={onSelectCodeBase} />
      </section>
      {editingTask && (
        <section className="surface form-card" data-testid="edit-task-card">
          <div className="section-heading"><h2><FileText size={26} weight="duotone" aria-hidden="true" /> Edit Task</h2><span>{editingTask.id}</span></div>
          <TaskEditor mode="edit" task={editingTask} onSubmit={async (form) => { await onEdit(editingTask.id, form); setEditingTask(null); }} onCancel={() => setEditingTask(null)} onSelectCodeBase={onSelectCodeBase} />
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
              <span data-testid="task-filter-result-count">{filteredTasks.length} of {unifiedTasks.length} tasks</span>
              <button className="ghost-button" type="button" onClick={resetFilters} disabled={!activeFilterCount} data-testid="task-filter-reset-button">Reset</button>
            </div>
          </div>
        )}
        <TaskTable tasks={filteredTasks} onStatusChange={onStatusChange} onEdit={setEditingTask} onToggleToday={onToggleToday} onUpdateNotes={onUpdateNotes} onOpenEnrichmentDetails={onOpenEnrichmentDetails} />
        {!filteredTasks.length && <p className="empty-state" data-testid="task-filter-empty-state">No tasks match the selected filters.</p>}
      </section>
      <EnrichmentDetailsModal job={selectedEnrichmentJob} onClose={onCloseEnrichmentDetails} onRefresh={onRefreshEnrichmentDetails} />
    </main>
  );
};

const CalendarPage = ({ overview = defaultOverview, events = schedule, removedEvents = [], onUpdateEvent, onRemoveEvent, onRestoreEvent }) => (
  <main className="page-stack calendar-page" data-testid="calendar-page">
    <section className="surface weekly-panel" data-testid="weekly-overview-card">
      <div className="section-heading">
        <h2><SquaresFour size={26} weight="duotone" aria-hidden="true" /> Weekly Overview</h2>
        <NavLink to="/overview">Open overview</NavLink>
      </div>
      <div className="weekly-grid calendar-weekly-grid">
        <StatCard label="Completed" value="24 tasks" detail="6 more than last week" icon={CheckSquare} tone="green" trend testId="weekly-completed-stat" />
        <StatCard label="XP Earned" value="740 XP" detail="Level 8 is within reach" icon={Trophy} tone="violet" testId="weekly-xp-stat" />
        <StatCard label="Meeting Time" value={formatMinutes(overview.meetingMinutes)} detail="Tracked from calendar" icon={Clock} tone="blue" trend testId="weekly-time-stat" />
      </div>
    </section>
    <SchedulePanel events={events} removedEvents={removedEvents} onUpdateEvent={onUpdateEvent} onRemoveEvent={onRemoveEvent} onRestoreEvent={onRestoreEvent} />
  </main>
);

const FocusPage = ({ tasks, questRun, focusSessions, activeSession, lastSavedFocus, savingFocusState, focusMultiplier, onStartFocus, onPauseFocus, onResumeFocus, onStopFocus, streakDays = 0 }) => {
  const todaySessions = sessionsForDay(focusSessions);
  const weekStart = startOfWeekKey();
  const weekSessions = focusSessions.filter((session) => {
    const day = session.work_date || new Date(session.started_at).toLocaleDateString("en-CA");
    return day >= weekStart && day <= addDaysKey(weekStart, 6);
  });
  const focusedToday = focusMinutesForSessions(todaySessions);
  const focusedWeek = focusMinutesForSessions(weekSessions);
  const topTask = topFocusedTask(todaySessions);
  const activeQuest = getQuestById(questRun, activeSession?.quest_id) || getQuestById(questRun, questRun?.activeQuestId);
  const activeQuestTask = getQuestTask(tasks, activeQuest);
  const questContext = activeQuest && activeQuestTask ? { quest: activeQuest, task: activeQuestTask } : null;
  const savedQuest = getQuestById(questRun, lastSavedFocus?.quest_id);
  const savedQuestTask = getQuestTask(tasks, savedQuest);
  const nextQuest = getNextQuest(questRun);
  const recentSessions = todaySessions.slice(0, 2);
  const hasMoreSessionHistory = todaySessions.length > recentSessions.length;
  const deepWorkTasks = todaySessions.reduce((acc, session) => {
    const key = session.task_id || "unassigned";
    acc[key] = acc[key] || { title: session.task_title || "Unassigned focus", minutes: 0, count: 0 };
    acc[key].minutes += sessionMinutes(session);
    acc[key].count += 1;
    return acc;
  }, {});
  const deepWorkLeaders = Object.values(deepWorkTasks).sort((a, b) => b.minutes - a.minutes).slice(0, 3);
  const bestSession = [...todaySessions].sort((a, b) => sessionMinutes(b) - sessionMinutes(a))[0];
  const rhythmInsight = topTask
    ? `${topTask.title} is leading your focus today with ${formatMinutes(topTask.minutes)} logged.`
    : "Complete your first session to see history and rhythm insights.";

  return (
    <main className={`focus-page ${activeSession ? "focus-page-active" : ""}`} data-testid="focus-page">
      <FocusWidget tasks={tasks} focusSessions={focusSessions} activeSession={activeSession} questContext={questContext} onStartFocus={onStartFocus} onPauseFocus={onPauseFocus} onResumeFocus={onResumeFocus} onStopFocus={onStopFocus} />
      {!activeSession && (
        <section className="focus-secondary-grid" data-testid="focus-support-grid">
          <article className="surface focus-secondary-card focus-today-card" data-testid="focus-today-card">
            <div className="section-heading focus-secondary-heading">
              <div>
                <h2><Lightning size={22} weight="duotone" aria-hidden="true" /> Today</h2>
                <p>Lightweight progress for the current rhythm.</p>
              </div>
              <div className="focus-log-actions">
                <span>{todayKey()}</span>
                <NavLink className="ghost-button" to="/focus/analytics" data-testid="view-focus-analytics-button"><TrendUp size={18} weight="duotone" aria-hidden="true" /> View analytics</NavLink>
              </div>
            </div>
            {!activeSession && <FocusSavedQuestPanel savedQuest={savedQuest} savedQuestTask={savedQuestTask} onStartFocus={onStartFocus} focusMultiplier={focusMultiplier} />}
            {savingFocusState && (
              <div className="focus-saving-panel" data-testid="focus-saving-panel" role="status" aria-live="polite">
                <Hourglass size={20} weight="duotone" aria-hidden="true" />
                <div>
                  <strong>Saving focus session...</strong>
                  <p>{savingFocusState.task_title} locked at {formatMinutes(Math.max(1, Math.ceil((savingFocusState.duration_seconds || 0) / 60)))}. The timer has stopped.</p>
                </div>
              </div>
            )}
            <div className="focus-calm-summary" data-testid="focus-calm-summary">
              <span><strong>{formatMinutes(focusedToday)}</strong>focus today</span>
              <span><strong>{todaySessions.length}</strong>sessions today</span>
              <span><strong>{formatMinutes(focusedWeek)}</strong>this week</span>
              <span><strong>{streakDays}</strong>day streak</span>
            </div>
          </article>
          <article className="surface focus-secondary-card focus-history-card" data-testid="focus-rhythm-card">
            <div className="section-heading focus-secondary-heading">
              <div>
                <h2><Clock size={22} weight="duotone" aria-hidden="true" /> Focus history & rhythm</h2>
                <p>{recentSessions.length ? "Recent evidence plus a quick rhythm read." : "A single place for your first focus insights."}</p>
              </div>
              <div className="focus-log-actions">
                {(recentSessions.length || hasMoreSessionHistory) ? <NavLink className="ghost-button" to="/focus/analytics" data-testid="focus-history-view-all-link">View all</NavLink> : null}
              </div>
            </div>
            {recentSessions.length ? (
              <div className="focus-history-layout">
                <div className="focus-rhythm-callout">
                  <strong>Rhythm insight</strong>
                  <p>{rhythmInsight}</p>
                  {bestSession ? <span>Best session today: {formatMinutes(sessionMinutes(bestSession))} on {bestSession.task_title || "focus work"}.</span> : null}
                  {deepWorkLeaders[1] ? <span>Next strongest thread: {deepWorkLeaders[1].title} with {formatMinutes(deepWorkLeaders[1].minutes)}.</span> : null}
                </div>
                <div className="focus-history-list">
                  {recentSessions.map((session) => (
                    <article key={session.focus_session_id} className="focus-history-item">
                      <div>
                        <strong>{session.task_title || "Focus session"}</strong>
                        <p>{formatDateTime(session.started_at)} | {session.outcome_type || session.status || "Saved"}</p>
                      </div>
                      <div className="focus-support-meta">
                        <span>{formatMinutes(sessionMinutes(session))}</span>
                        {session.xp_awarded ? <span>{session.xp_awarded} XP</span> : null}
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ) : (
              <div className="focus-history-empty" data-testid="focus-history-empty">
                <strong>Complete your first session to see history and rhythm insights.</strong>
                <p>This card will start showing recent sessions, strongest focus thread, and simple trend signals as soon as you save one session.</p>
              </div>
            )}
          </article>
        </section>
      )}
    </main>
  );
};

const QuestsPage = ({ tasks, questRun, activeSession, isLoading, isGenerating, completingQuestId, focusMultiplier, onGenerateQuests, onClearQuests, onStartQuestFocus, onCompleteQuest, onSkipQuest, onActivateQuest, showProgressGuide, onDismissProgressGuide }) => {
  const navigate = useNavigate();
  const [skipReason, setSkipReason] = useState(skipReasons[0]);
  if (isLoading) {
    return <PageLoader title="Loading quests" detail="Reading Working Today tasks and your current quest run from the backend." steps={["Tasks", "Quest run", "Focus"]} />;
  }
  const todayTasks = getQuestOrderedTasks(tasks, questRun);
  const hasCurrentRun = isCurrentQuestRun(questRun);
  const hasGeneratedRun = hasGeneratedQuestRun(questRun);
  const isGenerated = hasGeneratedRun;
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
      {showProgressGuide && <ProgressGuideCard page="quests" onDismiss={onDismissProgressGuide} />}
      <section className="surface quest-run-panel" data-testid="quest-run-panel">
        <div className="section-heading quest-board-heading">
          <div>
            <h2><Flag size={26} weight="duotone" aria-hidden="true" /> Daily Quest Run</h2>
            <p className={`quest-board-summary ${isOutOfSync ? "quest-board-warning" : ""}`} data-testid="quest-board-summary" aria-live="polite">{questGeneratedLabel(tasks, questRun, todayTasks.length)}</p>
          </div>
          <div className="quest-board-actions">
            {hasCurrentRun && <button className="ghost-button" onClick={onClearQuests} disabled={isGenerating} data-testid="clear-quests-button">Reset</button>}
            <button className={`primary-action ${isGenerating ? "quest-generate-busy" : ""}`} onClick={onGenerateQuests} disabled={!todayTasks.length || isGenerating} data-testid="generate-quests-button">
              {isGenerating ? <span className="quest-button-loader" aria-hidden="true" /> : <Sparkle size={19} weight="duotone" aria-hidden="true" />}
              {isGenerating ? "Generating..." : generateLabel}
            </button>
          </div>
        </div>
        {isGenerating && <p className="quest-inline-status" data-testid="quest-generation-status" role="status" aria-live="polite">Generating your next quest run from the latest Working Today tasks...</p>}
        {isGenerated && nextQuestTask && (
          <div className="quest-layout">
            <NextQuestCard
              nextQuest={nextQuest}
              nextQuestTask={nextQuestTask}
              summary={summary}
              isCompleting={Boolean(nextQuest && completingQuestId && String(completingQuestId) === String(nextQuest.id))}
              activeSessionMatchesNextQuest={activeSessionMatchesNextQuest}
              activeSessionConflicts={activeSessionConflicts}
              skipReason={skipReason}
              skipReasons={skipReasons}
              onStartFocus={startFocus}
              onCompleteQuest={onCompleteQuest}
              onSkipQuest={onSkipQuest}
              onSkipReasonChange={setSkipReason}
              focusMultiplier={focusMultiplier}
            />
            <QuestSummaryPanel summary={summary} />
          </div>
        )}
        {isGenerated && !nextQuestTask && <div className="mission-list"><p className="empty-state">The quest run was generated, but the linked task details have not loaded cleanly yet. Refresh the page or update quests to resync the route.</p></div>}
        {!isGenerated && <div className="mission-list">{todayTasks.length ? todayTasks.map((task, index) => <MissionCard key={task.id} task={task} index={index} questMeta={null} />) : <p className="empty-state">No tasks are marked as Working Today yet. Open My Tasks and use the Today column to add work here.</p>}</div>}
      </section>
      {isGenerated && questRows.length > 0 && (
        <section className="surface" data-testid="quest-path-card">
          <div className="section-heading"><h2><ListChecks size={26} weight="duotone" aria-hidden="true" /> Quest Path</h2><span>{questRows.length} quests</span></div>
          <QuestPathList questRows={questRows} onActivateQuest={onActivateQuest} />
        </section>
      )}
    </main>
  );
};

const InsightsPage = ({ tasks, focusSessions, focusMultiplier, onRefreshInsights }) => {
  const fallbackStandupNote = useMemo(() => generateStandupNote(tasks), [tasks]);
  const [standupNote, setStandupNote] = useState(() => fallbackStandupNote);
  const [standupStatus, setStandupStatus] = useState("loading");
  const [isGeneratingStandup, setIsGeneratingStandup] = useState(false);
  const [todayInsight, setTodayInsight] = useState(null);
  const [insightStatus, setInsightStatus] = useState("loading");
  const [insightError, setInsightError] = useState("");
  const [isGeneratingInsight, setIsGeneratingInsight] = useState(false);
  const todayTasks = tasks.filter((task) => task.workingToday);
  const completed = completedTodayTasks(tasks);
  const completedXp = earnedXpForTasks(completed, focusSessions, null, focusMultiplier);
  const topPriority = [...todayTasks].sort((a, b) => (b.priorityScore || 0) - (a.priorityScore || 0))[0];
  const backendTaskInsights = todayInsight?.task_insights || [];
  const displayedInsights = backendTaskInsights.length ? backendTaskInsights : todayTasks.map((task) => ({
    task_id: task.taskId || task.id,
    title: task.title,
    priority_score: task.priorityScore || 0,
    xp_value: task.xp,
    effort_minutes: task.time,
    insight: task.aiInsight,
  }));
  const risks = todayInsight?.risks || [];
  const recommendations = todayInsight?.recommendations || [];
  const isInsightLoading = insightStatus === "loading";
  const isStandupLoading = standupStatus === "loading";
  const showInsightLoader = isGeneratingInsight;

  useEffect(() => {
    let cancelled = false;
    setInsightStatus("loading");
    insightsApi.today({ date: todayKey() })
      .then((data) => {
        if (cancelled) return;
        setTodayInsight(data);
        setInsightStatus("live");
        setInsightError("");
      })
      .catch((error) => {
        if (cancelled) return;
        setTodayInsight(null);
        setInsightStatus("fallback");
        setInsightError(error?.response?.data?.detail?.message || error?.message || "AI insights are using local fallback data.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStandupStatus("loading");
    standupApi.get({ date: todayKey() })
      .then((data) => {
        if (cancelled) return;
        setStandupNote(normalizeStandupNote(data, fallbackStandupNote));
        setStandupStatus("live");
      })
      .catch(() => {
        if (cancelled) return;
        setStandupNote(fallbackStandupNote);
        setStandupStatus("fallback");
      });
    return () => {
      cancelled = true;
    };
  }, [fallbackStandupNote]);

  const refresh = () => {
    onRefreshInsights();
    setStandupNote(fallbackStandupNote);
    setStandupStatus("fallback");
  };

  const generateStandup = async () => {
    setIsGeneratingStandup(true);
    try {
      const data = await standupApi.generate({ date: todayKey(), force: true });
      setStandupNote(normalizeStandupNote(data, fallbackStandupNote));
      setStandupStatus("live");
    } catch {
      setStandupNote(fallbackStandupNote);
      setStandupStatus("fallback");
    } finally {
      setIsGeneratingStandup(false);
    }
  };

  const generateInsight = async () => {
    setIsGeneratingInsight(true);
    setInsightError("");
    try {
      const data = await insightsApi.generateToday({
        date: todayKey(),
        include_tasks: true,
        include_calendar: true,
        include_notes: true,
        force: true,
      });
      setTodayInsight(data);
      setInsightStatus("live");
    } catch (error) {
      setInsightStatus("fallback");
      setInsightError(error?.response?.data?.detail?.message || error?.message || "Unable to generate AI insight.");
    } finally {
      setIsGeneratingInsight(false);
    }
  };

  if (isInsightLoading || isStandupLoading) {
    return <PageLoader title="Loading AI insights" detail="Fetching insight, standup, and task context." steps={["Tasks", "Standup", "AI"]} />;
  }

  return (
    <main className="page-stack" data-testid="insights-page">
      <section className="surface insight-detail-card" data-testid="capacity-analysis-card">
        <div className="section-heading">
          <h2><Sparkle size={26} weight="duotone" aria-hidden="true" /> AI Task Insights</h2>
          <div className="editor-actions">
            <button className="ghost-button" onClick={refresh} data-testid="refresh-insights-button"><ArrowClockwise size={18} weight="duotone" aria-hidden="true" /> Refresh</button>
            <button className={`primary-action ${isGeneratingInsight ? "ai-generate-busy" : ""}`} onClick={generateInsight} disabled={isGeneratingInsight} data-testid="generate-ai-insight-button">
              {isGeneratingInsight ? <span className="quest-button-loader" aria-hidden="true" /> : <Sparkle size={19} weight="duotone" aria-hidden="true" />}
              {isGeneratingInsight ? "Generating..." : "AI"}
            </button>
          </div>
        </div>
        {showInsightLoader && (
          <div className="ai-inline-loader" role="status" aria-live="polite" data-testid="ai-insights-inline-loader">
            <div className="page-loader-visual ai-inline-loader-visual" aria-hidden="true">
              <span className="page-loader-orbit" />
              <span className="page-loader-core">
                <Hourglass size={24} weight="duotone" />
              </span>
            </div>
            <div>
              <strong>{isGeneratingInsight ? "Generating AI insight" : "Loading AI insights"}</strong>
              <p>{isGeneratingInsight ? "OCI GenAI is reviewing tasks, calendar, capacity, due dates, and notes." : "Fetching latest insight, standup, and task context."}</p>
            </div>
          </div>
        )}
        <div className="capacity-grid">
          <StatCard label="Top Priority" value={topPriority?.priority || "None"} detail={topPriority?.title || "Mark a task for today"} icon={Flag} tone="red" testId="capacity-top-priority-stat" />
          <StatCard label="Focus Capacity" value={formatMinutes(todayInsight?.capacity?.available_focus_minutes ?? todayTasks.reduce((sum, task) => sum + task.time, 0))} detail={insightStatus === "live" ? "From insights API" : "Working-today effort"} detailInsight={todayInsight?.stat_insights?.focus_minutes} icon={Clock} tone="blue" testId="capacity-working-hours-stat" />
          <StatCard label="Today XP" value={`${completedXp} XP`} detail={`Includes ${formatFocusMultiplier()} focus rewards`} detailInsight={todayInsight?.stat_insights?.total_xp} icon={Trophy} tone="green" testId="capacity-xp-stat" />
        </div>
        {!showInsightLoader && (
          <>
            <article className="ai-daily-summary" data-testid="daily-ai-insight">
              <span className="ai-section-kicker">Daily Insight</span>
              <p>{todayInsight?.daily_insight || "Generate AI insight to see risks and recommendations for today's work."}</p>
              {insightError && <p className="form-error" role="alert">{insightError}</p>}
            </article>
            {(risks.length > 0 || recommendations.length > 0) && (
              <div className="ai-guidance-grid" data-testid="ai-risk-recommendation-grid">
                <article className="ai-guidance-panel ai-risk-panel">
                  <strong>Risks</strong>
                  <ul>
                    {(risks.length ? risks : ["No risks returned."]).map((item, index) => <li key={`risk-${index}`}>{item}</li>)}
                  </ul>
                </article>
                <article className="ai-guidance-panel ai-recommendation-panel">
                  <strong>Recommendations</strong>
                  <ul>
                    {(recommendations.length ? recommendations : ["No recommendations returned."]).map((item, index) => <li key={`recommendation-${index}`}>{item}</li>)}
                  </ul>
                </article>
              </div>
            )}
            <div className="ai-task-list">
              {displayedInsights.map((task, index) => (
                <article className="ai-task-row" key={task.task_id}>
                  <span className="ai-task-rank">#{index + 1}</span>
                  <div className="ai-task-copy">
                    <strong>{task.title}</strong>
                    <p>{task.insight || "AI did not return a task-specific insight for this item."}</p>
                  </div>
                  <div className="ai-task-metrics" aria-label={`${task.title} AI metrics`}>
                    <span>{Math.round((task.priority_score || 0) * 100)} priority</span>
                    <span>{task.xp_value} XP</span>
                    <span>{task.effort_minutes} min</span>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </section>
      <section className="surface standup-card" data-testid="standup-generator-card">
        <div className="section-heading"><h2><FileText size={26} weight="duotone" aria-hidden="true" /> Standup Note Generator</h2><button className="primary-action" onClick={generateStandup} disabled={isGeneratingStandup} data-testid="generate-standup-button"><Sparkle size={19} weight="duotone" aria-hidden="true" /> {isGeneratingStandup ? "Generating" : "Generate"}</button></div>
        <pre className="standup-note" data-testid="standup-summary-text">{standupNote.fullNote}</pre>
        <span className="overview-status" data-testid="standup-api-status">{standupStatus === "live" ? "Standup note from backend" : standupStatus === "loading" ? "Loading standup note" : "Local fallback standup note"}</span>
        <div className="standup-snapshot-grid">
          <span><strong>Accomplished</strong>{standupNote.accomplished}</span>
          <span><strong>In Progress</strong>{standupNote.inProgress}</span>
          <span><strong>Blockers</strong>{standupNote.blockers}</span>
        </div>
      </section>
    </main>
  );
};

const toList = (value) => Array.isArray(value) ? value : String(value || "").split(/\n+/).map((item) => item.trim()).filter(Boolean);
const listToDraftText = (value) => toList(value).join("\n");
const reflectionDraftFrom = (source = {}, fallback = {}) => ({
  newLearnings: listToDraftText(source.new_learnings ?? fallback.newLearnings),
  wentWell: listToDraftText(source.went_well ?? fallback.wentWell),
  wentWrong: listToDraftText(source.went_wrong ?? fallback.wentWrong),
});

const OverviewPage = ({ tasks, overview, focusSessions, focusMultiplier, onOverviewChange }) => {
  const [selectedDate, setSelectedDate] = useState(todayKey());
  const [selectedWeek, setSelectedWeek] = useState(startOfWeekKey());
  const [dailyData, setDailyData] = useState(null);
  const [weeklyData, setWeeklyData] = useState(null);
  const [dailyReflectionDraft, setDailyReflectionDraft] = useState(() => reflectionDraftFrom({}, overview));
  const [overviewStatus, setOverviewStatus] = useState("loading");
  const [weeklyStatus, setWeeklyStatus] = useState("loading");
  const [generating, setGenerating] = useState(null);
  const dailyRequestIdRef = useRef(0);
  const weeklyRequestIdRef = useRef(0);

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
  const focusRewardsByTask = focusRewardsByTaskId(focusSessions);
  const fallbackDailyXp = earnedXpForTasks(fallbackCompletedDay, focusSessions, selectedDate, focusMultiplier);
  const fallbackWeeklyXp = earnedXpForTasks(fallbackCompletedWeek, focusSessions, null, focusMultiplier);

  useEffect(() => {
    let cancelled = false;
    const requestId = dailyRequestIdRef.current + 1;
    dailyRequestIdRef.current = requestId;
    setOverviewStatus("loading");
    overviewApi.daily({ date: selectedDate })
      .then((data) => {
        if (cancelled || requestId !== dailyRequestIdRef.current) return;
        setDailyData(data);
        setDailyReflectionDraft(reflectionDraftFrom(data, overview));
        setOverviewStatus("live");
        onOverviewChange((current) => ({
          ...current,
          meetingMinutes: data.meeting_minutes ?? current.meetingMinutes,
          focusMinutes: data.focus_minutes ?? current.focusMinutes,
          newLearnings: listToDraftText(data.new_learnings) || current.newLearnings,
          wentWell: listToDraftText(data.went_well) || current.wentWell,
          wentWrong: listToDraftText(data.went_wrong) || current.wentWrong,
        }));
      })
      .catch(() => {
        if (cancelled || requestId !== dailyRequestIdRef.current) return;
        setDailyData(null);
        setDailyReflectionDraft(reflectionDraftFrom({}, overview));
        setOverviewStatus("fallback");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDate, onOverviewChange]);

  useEffect(() => {
    let cancelled = false;
    const requestId = weeklyRequestIdRef.current + 1;
    weeklyRequestIdRef.current = requestId;
    setWeeklyStatus("loading");
    overviewApi.weekly({ week_start: selectedWeek })
      .then((data) => {
        if (!cancelled && requestId === weeklyRequestIdRef.current) {
          setWeeklyData(data);
          setWeeklyStatus("live");
        }
      })
      .catch(() => {
        if (!cancelled && requestId === weeklyRequestIdRef.current) {
          setWeeklyData(null);
          setWeeklyStatus("fallback");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedWeek]);

  const generateDaily = async () => {
    const requestId = dailyRequestIdRef.current + 1;
    dailyRequestIdRef.current = requestId;
    setGenerating("daily");
    try {
      const data = await overviewApi.generateDaily({ date: selectedDate, include_daily_overviews: true, include_task_notes: true, include_meetings: true, force: true });
      if (requestId !== dailyRequestIdRef.current) return;
      setDailyData(data);
      setDailyReflectionDraft(reflectionDraftFrom(data, overview));
      setOverviewStatus("live");
    } catch {
      if (requestId === dailyRequestIdRef.current) setOverviewStatus("fallback");
    } finally {
      if (requestId === dailyRequestIdRef.current) setGenerating(null);
    }
  };

  const updateReflectionDraft = (field, value) => {
    setDailyReflectionDraft((current) => ({ ...current, [field]: value }));
    onOverviewChange((current) => ({ ...current, [field]: value }));
  };

  const updateDailyMetric = (field, value) => {
    onOverviewChange((current) => ({ ...current, [field]: value }));
    if (field === "meetingMinutes") {
      setDailyData((current) => current ? {
        ...current,
        meeting_minutes: value,
        meeting_summary: {
          ...(current.meeting_summary || {}),
          meeting_minutes: value,
        },
      } : current);
    }
  };

  const generateWeekly = async () => {
    const requestId = weeklyRequestIdRef.current + 1;
    weeklyRequestIdRef.current = requestId;
    setGenerating("weekly");
    try {
      const data = await overviewApi.generateWeekly({ week_start: selectedWeek, include_daily_overviews: true, include_task_notes: true, force: true });
      if (requestId !== weeklyRequestIdRef.current) return;
      setWeeklyData(data);
    } finally {
      if (requestId === weeklyRequestIdRef.current) setGenerating(null);
    }
  };

  const shiftDailyDate = (days) => setSelectedDate((current) => addDaysKey(current, days));
  const shiftWeeklyDate = (days) => setSelectedWeek((current) => addDaysKey(current, days * 7));
  const dailyTasks = dailyData?.accomplished_tasks || fallbackCompletedDay;
  const dailyFocus = dailyData?.focus_sessions || fallbackDailyFocus;
  const dailyThemes = toList(dailyData?.themes);
  const dailyTaskCount = dailyData?.tasks_completed ?? fallbackCompletedDay.length;
  const dailyXp = dailyData?.xp_earned ?? fallbackDailyXp;
  const dailyMeetingMinutes = dailyData?.meeting_minutes ?? overview.meetingMinutes;
  const dailyFocusMinutes = dailyData?.focus_minutes ?? fallbackDailyFocusMinutes;
  const weeklyThemes = toList(weeklyData?.themes).length ? toList(weeklyData?.themes) : [...new Set(fallbackCompletedWeek.flatMap((task) => task.labels || []))].slice(0, 5);
  const topAccomplishments = toList(weeklyData?.top_accomplishments);

  if ((overviewStatus === "loading" || weeklyStatus === "loading") && !dailyData && !weeklyData) {
    return <PageLoader title="Loading overview" detail="Fetching daily and weekly overview data." steps={["Daily", "Weekly", "Summary"]} />;
  }

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
          <StatCard label="Tasks Accomplished" value={dailyTaskCount} detail={`${dailyXp} XP earned, focus rewards included`} icon={CheckCircle} tone="green" testId="daily-completed-stat" />
          <StatCard label="Meetings" value={formatMinutes(dailyMeetingMinutes)} detail={dailyData ? `${dailyData.meeting_summary?.meeting_count || 0} scheduled` : "Editable daily tracker"} icon={UsersThree} tone="orange" testId="daily-meetings-stat" />
          <StatCard label="Focus Time" value={formatMinutes(dailyFocusMinutes)} detail={topFocus ? `Top: ${topFocus.title}` : `${dailyFocus.length} session(s)`} icon={Timer} tone="blue" testId="daily-focus-stat" />
        </div>
        <div className="overview-editor">
          <label>Meeting minutes<input type="number" min="0" value={dailyMeetingMinutes} onChange={(event) => updateDailyMetric("meetingMinutes", parseNumber(event.target.value, 0))} /></label>
          <label>Focus minutes<input type="number" min="0" value={dailyFocusMinutes} readOnly /></label>
          <label className="reflection-field">New learnings<textarea rows={5} value={dailyReflectionDraft.newLearnings} onChange={(event) => updateReflectionDraft("newLearnings", event.target.value)} placeholder="One learning per line..." data-testid="daily-new-learnings-input" /></label>
          <label className="reflection-field">Went well<textarea rows={5} value={dailyReflectionDraft.wentWell} onChange={(event) => updateReflectionDraft("wentWell", event.target.value)} placeholder="Capture wins, useful patterns, or smooth handoffs..." data-testid="daily-went-well-input" /></label>
          <label className="reflection-field">Went wrong<textarea rows={5} value={dailyReflectionDraft.wentWrong} onChange={(event) => updateReflectionDraft("wentWrong", event.target.value)} placeholder="Capture blockers, friction, delays, or risks..." data-testid="daily-went-wrong-input" /></label>
        </div>
        {!!dailyThemes.length && <div className="theme-list" data-testid="daily-theme-list">{dailyThemes.map((theme) => <Pill key={theme} tone="task">{theme}</Pill>)}</div>}
        <div className="accomplished-list focus-evidence-list" data-testid="daily-focus-session-list">
          {dailyFocus.map((session) => <article key={session.focus_session_id}><strong>{session.task_title}</strong><span>{formatDateTime(session.started_at)} - {formatMinutes(session.actual_minutes || sessionMinutes(session))} - {session.status || session.outcome_type}</span><p>{session.notes || session.outcome_note || "Captured focus session for AI summary context."}</p></article>)}
          {!dailyFocus.length && <article><strong>No focus captured yet</strong><span>Use Focus Mode to create session-backed deep-work evidence.</span></article>}
        </div>
        <div className="accomplished-list">
          {dailyTasks.map((task) => {
            const focusReward = task.id ? focusRewardsByTask[task.id] : null;
            const reward = task.id ? taskRewardDetails(task, focusReward?.focusMinutes || 0, focusReward?.rewardMultiplier, focusMultiplier) : null;
            const earnedXp = reward?.rewardXp ?? task.xp_value ?? task.xp;
            return <article key={task.task_id || task.id}><strong>{task.title}</strong><span>{formatDateTime(task.completed_at || task.completedAt)} - {task.actual_minutes || task.actualMinutes || task.time} mins - {earnedXp} XP{reward?.hasFocusReward ? ` (${formatFocusMultiplier(reward.rewardMultiplier)} focus)` : ""}</span><p>{task.notes}</p></article>;
          })}
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

const syncSources = ["Jira", "Outlook Calendar"];

const sourceState = (syncRun, source, syncingSource) => {
  const current = (syncRun?.sources || []).find((item) => item.source === source);
  if (syncingSource === "ALL") return { source, status: "RUNNING", message: "Syncing..." };
  if (syncingSource === source) return { source, status: "RUNNING", message: "Syncing..." };
  if (current) return current;
  return { source, status: "IDLE", message: "Ready to sync." };
};

const SyncStatusIcon = ({ status }) => {
  if (status === "RUNNING") return <ArrowClockwise className="sync-spin" size={26} weight="bold" aria-hidden="true" />;
  if (status === "FAILED") return <X size={26} weight="bold" aria-hidden="true" />;
  return <CheckCircle size={26} weight="duotone" aria-hidden="true" />;
};

const SyncPage = ({ syncRun, syncingSource, onRunSync }) => (
  <main className="page-stack" data-testid="sync-page">
    <section className="surface sync-card" data-testid="sync-management-card">
      <div className="section-heading sync-heading">
        <h2><CloudArrowDown size={26} weight="duotone" aria-hidden="true" /> Sync Center</h2>
        <div className="sync-action-stack">
          <button className="primary-action" onClick={() => onRunSync()} disabled={Boolean(syncingSource)} data-testid="run-sync-button">
            {syncingSource === "ALL" ? <ArrowClockwise className="sync-spin" size={19} weight="bold" aria-hidden="true" /> : <CloudArrowDown size={19} weight="duotone" aria-hidden="true" />}
            {syncingSource === "ALL" ? "Syncing Up..." : "Sync Up"}
          </button>
          <span data-testid="last-sync-time">{syncRun?.last_sync_at ? `Last synced ${formatDateTime(syncRun.last_sync_at)}` : "Not synced yet"}</span>
        </div>
      </div>
      <div className="sync-grid">
        {syncSources.map((source) => {
          const state = sourceState(syncRun, source, syncingSource);
          return (
            <article className={`sync-source sync-source-${slug(state.status)}`} key={source} data-testid={`sync-source-${slug(source)}`}>
              <SyncStatusIcon status={state.status} />
              <strong data-testid={`sync-source-title-${slug(source)}`}>{source}</strong>
              <span data-testid={`sync-source-status-${slug(source)}`}>{state.message}</span>
              {state.error && <p className="sync-error" data-testid={`sync-source-error-${slug(source)}`}>{state.error}</p>}
              <button className="ghost-button sync-source-action" onClick={() => onRunSync(source)} disabled={Boolean(syncingSource)} data-testid={`run-${slug(source)}-sync-button`}>
                {syncingSource === source ? <ArrowClockwise className="sync-spin" size={17} weight="bold" aria-hidden="true" /> : source === "Jira" ? <Database size={17} weight="duotone" aria-hidden="true" /> : <CalendarBlank size={17} weight="duotone" aria-hidden="true" />}
                Sync Up
              </button>
            </article>
          );
        })}
      </div>
    </section>
  </main>
);

const SettingsPage = ({ currentUser, onUserUpdate }) => {
  const initialSettings = settingsFormFromUser(currentUser);
  const [form, setForm] = useState(initialSettings);
  const [savedSettings, setSavedSettings] = useState(initialSettings);
  const [fieldErrors, setFieldErrors] = useState({});
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setLoadError("");
    settingsApi.get()
      .then((settings) => {
        if (cancelled) return;
        const nextSettings = settingsFormFromApi(settings);
        setForm(nextSettings);
        setSavedSettings(nextSettings);
        onUserUpdate?.((user) => mergeSettingsIntoUser(user, settings));
      })
      .catch((error) => {
        if (cancelled) return;
        setLoadError(settingsErrorMessage(error, "Unable to load settings."));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser?.user_id]);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: "" }));
    setSaveError("");
    setSuccessMessage("");
  };

  const isDirty = JSON.stringify(form) !== JSON.stringify(savedSettings);
  const controlsDisabled = isLoading || isSaving;

  const cancelChanges = () => {
    setForm(savedSettings);
    setFieldErrors({});
    setSaveError("");
    setSuccessMessage("");
  };

  const saveSettings = async (event) => {
    event.preventDefault();
    const errors = validateSettingsForm(form);
    setFieldErrors(errors);
    setSaveError("");
    setSuccessMessage("");
    if (Object.keys(errors).length) return;

    setIsSaving(true);
    try {
      const updatedSettings = await settingsApi.save({
        working_hours_start: form.working_hours_start,
        working_hours_end: form.working_hours_end,
        focus_xp_multiplier: Number(form.focus_xp_multiplier),
      });
      const nextSettings = settingsFormFromApi(updatedSettings);
      setForm(nextSettings);
      setSavedSettings(nextSettings);
      onUserUpdate?.((user) => mergeSettingsIntoUser(user, updatedSettings));
      setSuccessMessage("Settings saved.");
    } catch (error) {
      setSaveError(settingsErrorMessage(error, "Unable to save settings."));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className="page-stack" data-testid="settings-page">
      <section className="surface settings-card" data-testid="settings-card">
        <form onSubmit={saveSettings}>
          <div className="section-heading">
            <h2><GearSix size={26} weight="duotone" aria-hidden="true" /> Productivity Settings</h2>
            <div className="settings-actions">
              <button className="ghost-button" type="button" onClick={cancelChanges} disabled={controlsDisabled || !isDirty} data-testid="settings-cancel-button"><X size={18} weight="bold" aria-hidden="true" /> Cancel</button>
              <button className="primary-action" type="submit" disabled={controlsDisabled || !isDirty} data-testid="settings-save-button"><FloppyDisk size={19} weight="duotone" aria-hidden="true" /> {isSaving ? "Saving" : "Save"}</button>
            </div>
          </div>
          {loadError && <p className="form-error" role="alert" data-testid="settings-load-error">{loadError}</p>}
          <div className="settings-time-grid" data-testid="working-hours-setting-label">
            <label className="settings-row">Working hours start
              <input type="time" value={form.working_hours_start} onClick={openNativeTimePicker} onChange={(event) => updateField("working_hours_start", event.target.value)} disabled={controlsDisabled} aria-invalid={Boolean(fieldErrors.working_hours_start)} aria-describedby={fieldErrors.working_hours_start ? "working-hours-start-error" : undefined} data-testid="working-hours-start-input" />
              {fieldErrors.working_hours_start && <span className="field-error" id="working-hours-start-error">{fieldErrors.working_hours_start}</span>}
            </label>
            <label className="settings-row">Working hours end
              <input type="time" value={form.working_hours_end} onClick={openNativeTimePicker} onChange={(event) => updateField("working_hours_end", event.target.value)} disabled={controlsDisabled} aria-invalid={Boolean(fieldErrors.working_hours_end)} aria-describedby={fieldErrors.working_hours_end ? "working-hours-end-error" : undefined} data-testid="working-hours-end-input" />
              {fieldErrors.working_hours_end && <span className="field-error" id="working-hours-end-error">{fieldErrors.working_hours_end}</span>}
            </label>
          </div>
          <label className="settings-row settings-slider-row" data-testid="xp-multiplier-setting-label">
            <span className="settings-slider-header">Focus XP multiplier</span>
            <span className="settings-slider-control">
              <span className="settings-slider-value">
                <input id="xp-multiplier-setting-input" type="number" min="0.25" max="3" step="0.01" value={form.focus_xp_multiplier} onChange={(event) => updateField("focus_xp_multiplier", event.target.value)} disabled={controlsDisabled} aria-invalid={Boolean(fieldErrors.focus_xp_multiplier)} aria-describedby={fieldErrors.focus_xp_multiplier ? "xp-multiplier-error" : undefined} data-testid="xp-multiplier-setting-input" />
                <span aria-hidden="true">x</span>
              </span>
              <input id="xp-multiplier-setting-slider" type="range" min="0.25" max="3" step="0.01" value={multiplierSliderValue(form.focus_xp_multiplier)} onChange={(event) => updateField("focus_xp_multiplier", event.target.value)} disabled={controlsDisabled} aria-invalid={Boolean(fieldErrors.focus_xp_multiplier)} aria-describedby={fieldErrors.focus_xp_multiplier ? "xp-multiplier-error" : undefined} data-testid="xp-multiplier-setting-slider" />
            </span>
            {fieldErrors.focus_xp_multiplier && <span className="field-error" id="xp-multiplier-error">{fieldErrors.focus_xp_multiplier}</span>}
          </label>
          {saveError && <p className="form-error" role="alert" data-testid="settings-save-error">{saveError}</p>}
          {successMessage && <p className="settings-success" role="status" data-testid="settings-success"><CheckCircle size={18} weight="duotone" aria-hidden="true" /> {successMessage}</p>}
        </form>
      </section>
    </main>
  );
};

const AppShell = ({ currentUser, isLoggingOut, onLogout, onUserUpdate }) => {
  const location = useLocation();
  const [tasks, setTasks] = useState([]);
  const [taskStatus, setTaskStatus] = useState("loading");
  const [taskLoadError, setTaskLoadError] = useState("");
  const [overview, setOverview] = useState(defaultOverview);
  const [dashboardStats, setDashboardStats] = useState(null);
  const [dashboardStatInsights, setDashboardStatInsights] = useState(null);
  const [dashboardSchedule, setDashboardSchedule] = useState(schedule);
  const [calendarSchedule, setCalendarSchedule] = useState(schedule);
  const [removedCalendarEvents, setRemovedCalendarEvents] = useState([]);
  const [calendarDate, setCalendarDate] = useState(todayKey());
  const [isFetchingCalendarDate, setIsFetchingCalendarDate] = useState(false);
  const [dashboardInsight, setDashboardInsight] = useState(null);
  const [dashboardStatus, setDashboardStatus] = useState("loading");
  const [questProgress, setQuestProgress] = useState(null);
  const [focusSessions, setFocusSessions] = useState(() => readStoredJson(FOCUS_SESSIONS_STORAGE_KEY, []));
  const [activeSession, setActiveSession] = useState(() => readStoredJson(ACTIVE_FOCUS_STORAGE_KEY, null));
  const [questRun, setQuestRun] = useState(null);
  const [lastSavedFocus, setLastSavedFocus] = useState(null);
  const [savingFocusState, setSavingFocusState] = useState(null);
  const [syncRun, setSyncRun] = useState(null);
  const [syncingSource, setSyncingSource] = useState("");
  const [enrichmentJobs, setEnrichmentJobs] = useState([]);
  const [selectedEnrichmentJob, setSelectedEnrichmentJob] = useState(null);
  const [isGeneratingQuests, setIsGeneratingQuests] = useState(false);
  const [completingQuestId, setCompletingQuestId] = useState(null);
  const [floatingNotice, setFloatingNotice] = useState(null);
  const submittedEnrichmentJobIdsRef = useRef(new Set());
  const notifiedEnrichmentJobIdsRef = useRef(new Set());
  const enrichmentListRequestInFlightRef = useRef(false);
  const enrichmentListFailureCountRef = useRef(0);
  const selectedEnrichmentJobIdRef = useRef(null);
  const selectedEnrichmentRequestInFlightRef = useRef(false);
  const selectedEnrichmentFailureCountRef = useRef(0);
  const [levelUpNotice, setLevelUpNotice] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setTheme] = useState(readInitialTheme);
  const [isProgressGuideDismissed, setIsProgressGuideDismissed] = useState(readProgressGuideDismissed);
  const [persistedXpFloor, setPersistedXpFloor] = useState(() => readPersistedXpForUser(currentUser?.user_id));
  const focusXpMultiplier = focusMultiplierFromUser(currentUser);
  const previousLevelRef = useRef(null);
  const hasInitializedLevelRef = useRef(false);
  const rawProgressSnapshot = useMemo(
    () => buildProgressSnapshot({ tasks, focusSessions, focusMultiplier: focusXpMultiplier, questProgress, questRun }),
    [tasks, focusSessions, focusXpMultiplier, questProgress, questRun],
  );
  const progressSnapshot = useMemo(
    () => ({
      ...rawProgressSnapshot,
      totalXp: mergeMonotonicTotalXp(rawProgressSnapshot.totalXp, persistedXpFloor),
    }),
    [rawProgressSnapshot, persistedXpFloor],
  );
  const levelProgress = levelProgressFromXp(progressSnapshot.totalXp);
  const isDistractionFreeFocus = location.pathname === "/focus" && Boolean(activeSession);
  const hasActiveEnrichmentJobs = useMemo(
    () => enrichmentJobs.some((job) => activeEnrichmentStatuses.has(String(job.status || "").toUpperCase())),
    [enrichmentJobs],
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    writeStoredJson(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    writeStoredJson(PROGRESS_GUIDE_STORAGE_KEY, isProgressGuideDismissed);
  }, [isProgressGuideDismissed]);

  useEffect(() => {
    setPersistedXpFloor(readPersistedXpForUser(currentUser?.user_id));
  }, [currentUser?.user_id]);

  useEffect(() => {
    if (!currentUser?.user_id) return;
    const nextFloor = mergeMonotonicTotalXp(rawProgressSnapshot.totalXp, persistedXpFloor);
    if (nextFloor <= persistedXpFloor) return;
    setPersistedXpFloor(nextFloor);
    persistXpForUser(currentUser.user_id, nextFloor);
  }, [currentUser?.user_id, persistedXpFloor, rawProgressSnapshot.totalXp]);

  useEffect(() => {
    if (!floatingNotice) return undefined;
    const timeoutId = window.setTimeout(() => setFloatingNotice(null), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [floatingNotice]);

  const showFloatingNotice = (notice) => {
    setFloatingNotice({
      id: `${Date.now()}-${Math.random()}`,
      ...notice,
    });
  };

  useEffect(() => {
    if (!levelUpNotice) return undefined;
    const timeoutId = window.setTimeout(() => setLevelUpNotice(null), 5200);
    return () => window.clearTimeout(timeoutId);
  }, [levelUpNotice]);

  useEffect(() => {
    if (taskStatus === "loading") return;
    if (!hasInitializedLevelRef.current) {
      previousLevelRef.current = levelProgress.level;
      hasInitializedLevelRef.current = true;
      return;
    }
    if (previousLevelRef.current === null) {
      previousLevelRef.current = levelProgress.level;
      return;
    }
    if (levelProgress.level > previousLevelRef.current) {
      setLevelUpNotice({
        level: levelProgress.level,
        message: `${levelProgress.totalXp.toLocaleString()} total XP and climbing. Your next unlock is now ${levelProgress.xpForNextLevel} XP away.`,
      });
    }
    previousLevelRef.current = levelProgress.level;
  }, [levelProgress, taskStatus]);

  const dismissProgressGuide = () => setIsProgressGuideDismissed(true);

  const loadTasks = async () => {
    const loadedTasks = await tasksApi.list();
    const taskItems = Array.isArray(loadedTasks) ? loadedTasks : loadedTasks?.items || [];
    setTasks(taskItems.map(normalizeTaskPayload));
  };

  const loadEnrichmentJobs = async ({ notify = false } = {}) => {
    if (enrichmentListRequestInFlightRef.current) return enrichmentJobs;
    enrichmentListRequestInFlightRef.current = true;
    try {
      const loadedJobs = await taskEnrichmentApi.list({ limit: 20 });
      const jobItems = Array.isArray(loadedJobs) ? loadedJobs : loadedJobs?.items || [];
      enrichmentListFailureCountRef.current = 0;
      setEnrichmentJobs(jobItems);
      if (notify) {
        jobItems.forEach((job) => {
          const id = enrichmentJobId(job);
          const status = String(job.status || "").toUpperCase();
          if (!submittedEnrichmentJobIdsRef.current.has(id) || !terminalEnrichmentStatuses.has(status) || notifiedEnrichmentJobIdsRef.current.has(id)) return;
          notifiedEnrichmentJobIdsRef.current.add(id);
          submittedEnrichmentJobIdsRef.current.delete(id);
          if (status === "SUCCEEDED") {
            showFloatingNotice({ title: "The task is added successfully", tone: "success" });
            void loadTasks();
          } else {
            showFloatingNotice({
              title: "AI enrichment failed",
              message: job.error_message || job.errorMessage || enrichmentStatusLabel(status),
              tone: "error",
            });
          }
        });
      }
      return jobItems;
    } catch (error) {
      enrichmentListFailureCountRef.current += 1;
      if (enrichmentListFailureCountRef.current >= 2) {
        const message = apiErrorMessage(error, "Backend connection was lost while AI enrichment was running. Restart the backend and start AI enrichment again.");
        setEnrichmentJobs((jobs) => jobs.map((job) => {
          const status = String(job.status || "").toUpperCase();
          if (!activeEnrichmentStatuses.has(status)) return job;
          return {
            ...job,
            status: "FAILED",
            error_message: message,
            errorMessage: message,
          };
        }));
        if (notify) {
          showFloatingNotice({
            title: "AI enrichment polling stopped",
            message,
            tone: "error",
          });
        }
      }
      throw error;
    } finally {
      enrichmentListRequestInFlightRef.current = false;
    }
  };

  const loadQuestRun = async (date = todayKey()) => {
    const loadedRun = await questsApi.today({ date });
    setQuestRun(loadedRun || null);
    return loadedRun || null;
  };

  const loadQuestProgress = async (date = todayKey()) => {
    const progress = await questsApi.progress({ date });
    setQuestProgress(progress || null);
    return progress || null;
  };

  const loadFocusSessions = async () => {
    const loadedSessions = await focusApi.list();
    setFocusSessions(Array.isArray(loadedSessions) ? loadedSessions : []);
  };

  useEffect(() => {
    let isActive = true;
    setTaskStatus("loading");
    Promise.all([loadTasks(), loadQuestRun(), loadQuestProgress(), loadFocusSessions()])
      .then(() => {
        if (!isActive) return;
        setTaskLoadError("");
        setTaskStatus("live");
      })
      .catch((error) => {
        if (!isActive) return;
        setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to load saved data.");
        setTaskStatus("fallback");
      });

    return () => {
      isActive = false;
    };
  }, [currentUser?.user_id]);

  useEffect(() => {
    let isActive = true;
    loadEnrichmentJobs()
      .then((jobs) => {
        if (!isActive) return;
        jobs.forEach((job) => {
          const status = String(job.status || "").toUpperCase();
          if (terminalEnrichmentStatuses.has(status)) notifiedEnrichmentJobIdsRef.current.add(enrichmentJobId(job));
        });
      })
      .catch(() => {});
    return () => {
      isActive = false;
    };
  }, [currentUser?.user_id]);

  useEffect(() => {
    if (!hasActiveEnrichmentJobs) return undefined;
    const intervalId = window.setInterval(() => {
      void loadEnrichmentJobs({ notify: true }).catch(() => {});
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [hasActiveEnrichmentJobs, currentUser?.user_id]);

  useEffect(() => {
    if (!selectedEnrichmentJob) return undefined;
    const id = enrichmentJobId(selectedEnrichmentJob);
    const status = String(selectedEnrichmentJob.status || "").toUpperCase();
    if (!activeEnrichmentStatuses.has(status)) return undefined;
    selectedEnrichmentJobIdRef.current = String(id);
    let cancelled = false;
    const refreshSelectedJob = async () => {
      if (selectedEnrichmentRequestInFlightRef.current) return;
      selectedEnrichmentRequestInFlightRef.current = true;
      try {
        const job = await taskEnrichmentApi.get(id);
        if (!cancelled && String(selectedEnrichmentJobIdRef.current) === String(id)) {
          selectedEnrichmentFailureCountRef.current = 0;
          setSelectedEnrichmentJob(job);
        }
      } catch (error) {
        selectedEnrichmentFailureCountRef.current += 1;
        if (!cancelled && selectedEnrichmentFailureCountRef.current >= 2 && String(selectedEnrichmentJobIdRef.current) === String(id)) {
          const message = apiErrorMessage(error, "Backend connection was lost while reading enrichment logs. Polling has stopped.");
          setSelectedEnrichmentJob((job) => job ? {
            ...job,
            status: "FAILED",
            error_message: job.error_message || job.errorMessage || message,
            errorMessage: job.errorMessage || job.error_message || message,
          } : job);
        }
      } finally {
        selectedEnrichmentRequestInFlightRef.current = false;
      }
    };
    const intervalId = window.setInterval(refreshSelectedJob, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [selectedEnrichmentJob?.enrichment_job_id, selectedEnrichmentJob?.id, selectedEnrichmentJob?.status]);

  const handleComplete = async (id) => {
    const task = tasks.find((item) => item.id === id);
    if (!task) return;
    try {
      const updatedTask = await tasksApi.complete(id, { row_version: task.row_version, completedAt: task.completedAt || nowIso() });
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTaskPayload(updatedTask) : item)));
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
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTaskPayload(updatedTask) : item)));
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
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTaskPayload(updatedTask) : item)));
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
      setTasks((items) => items.map((item) => (item.id === id ? normalizeTaskPayload(updatedTask) : item)));
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to update notes.");
      throw error;
    }
  };
  const handleEditTask = async (id, form) => {
    const task = tasks.find((item) => item.id === id);
    if (!task || !form) return;
    if (form.source === "Jira" && form.runAiEnrichment) {
      const taskId = task.taskId || task.task_id || task.id;
      const job = await taskEnrichmentApi.start({
        ...form,
        source: "Jira",
        externalId: form.externalId || task.externalId || task.external_id,
        existingTaskId: taskId,
        taskId,
      });
      const jobId = enrichmentJobId(job);
      submittedEnrichmentJobIdsRef.current.add(jobId);
      setEnrichmentJobs((jobs) => [job, ...jobs.filter((item) => enrichmentJobId(item) !== jobId)]);
      setSelectedEnrichmentJob(job);
      selectedEnrichmentJobIdRef.current = String(jobId);
      showFloatingNotice({
        title: "The task will be updated after the AI enrichment",
        tone: "info",
      });
      return;
    }
    const updatedTask = await tasksApi.update(id, { ...form, row_version: task.row_version, runAiEnrichment: form.runAiEnrichment });
    setTasks((items) => items.map((item) => (item.id === id ? normalizeTaskPayload(updatedTask) : item)));
  };
  const handleRefreshInsights = () => setTasks((items) => items.map((task) => normalizeTask({ ...task, aiInsight: "" })));
  const handleSelectCodeBase = async (initialPath = "") => {
    const result = await jiraApi.selectRcaWorkspace(initialPath);
    return result?.code_base_path || result?.codeBasePath || "";
  };

  const handleOpenEnrichmentDetails = async (jobId) => {
    if (!jobId) return;
    selectedEnrichmentJobIdRef.current = String(jobId);
    try {
      const job = await taskEnrichmentApi.get(jobId);
      if (String(selectedEnrichmentJobIdRef.current) === String(jobId)) {
        selectedEnrichmentFailureCountRef.current = 0;
        setSelectedEnrichmentJob(job);
      }
    } catch (error) {
      showFloatingNotice({
        title: "Unable to open enrichment details",
        message: apiErrorMessage(error, "Please try again."),
        tone: "error",
      });
    }
  };

  const handleCloseEnrichmentDetails = () => {
    selectedEnrichmentJobIdRef.current = null;
    selectedEnrichmentFailureCountRef.current = 0;
    setSelectedEnrichmentJob(null);
  };

  const handleRefreshSelectedEnrichment = async () => {
    const id = selectedEnrichmentJobIdRef.current || enrichmentJobId(selectedEnrichmentJob);
    if (!id) return;
    if (selectedEnrichmentRequestInFlightRef.current) return;
    selectedEnrichmentRequestInFlightRef.current = true;
    try {
      const job = await taskEnrichmentApi.get(id);
      if (String(selectedEnrichmentJobIdRef.current) === String(id)) {
        selectedEnrichmentFailureCountRef.current = 0;
        setSelectedEnrichmentJob(job);
      }
    } finally {
      selectedEnrichmentRequestInFlightRef.current = false;
    }
  };

  const handleAddTask = async (form) => {
    if (form?.source === "Jira" && form?.runAiEnrichment) {
      const job = await taskEnrichmentApi.start(form);
      submittedEnrichmentJobIdsRef.current.add(enrichmentJobId(job));
      setEnrichmentJobs((jobs) => [job, ...jobs.filter((item) => enrichmentJobId(item) !== enrichmentJobId(job))]);
      showFloatingNotice({
        title: "The Task will be added after the AI enrichment",
        tone: "info",
      });
      return job;
    }
    const createdTask = await tasksApi.create(form);
    setTasks((items) => [normalizeTaskPayload(createdTask), ...items]);
    return createdTask;
  };
  const handleRunSync = (source) => {
    const selectedSources = source ? [source] : ["Jira", "Outlook Calendar"];
    const syncingKey = source || "ALL";
    setSyncingSource(syncingKey);
    showFloatingNotice({
      title: "Sync Up started in background.",
      message: "You can continue using the app.",
      tone: "info",
    });
    setSyncRun((current) => ({
      ...(current || {}),
      status: "RUNNING",
      sources: [
        { source: "Jira", status: selectedSources.includes("Jira") ? "RUNNING" : "IDLE", message: selectedSources.includes("Jira") ? "Syncing Jira issues..." : "Ready to sync." },
        { source: "Outlook Calendar", status: selectedSources.includes("Outlook Calendar") ? "RUNNING" : "IDLE", message: selectedSources.includes("Outlook Calendar") ? "Fetching today's Outlook meetings." : "Ready to sync." },
      ],
    }));

    syncApi.run(source ? { sources: selectedSources } : {})
      .then(async (result) => {
        setSyncRun(result);
        const events = result?.calendar_events || result?.calendarEvents || [];
        if (selectedSources.includes("Outlook Calendar") || events.length) {
          const normalizedEvents = normalizeApiSchedule(events);
          setCalendarSchedule(normalizedEvents);
          setDashboardSchedule(normalizedEvents);
        }
        if (selectedSources.includes("Jira")) {
          const refreshedTasks = await tasksApi.list();
          const taskItems = Array.isArray(refreshedTasks) ? refreshedTasks : refreshedTasks?.items || [];
          setTasks(taskItems.map(normalizeTask));
        }
        setTaskLoadError("");
        const failedSources = (result?.sources || []).filter((item) => item?.status === "FAILED");
        if (result?.status === "FAILED" || failedSources.length) {
          showFloatingNotice({
            title: "Sync finished with issues",
            message: failedSources[0]?.error || failedSources[0]?.message || "Please check the Sync page for details.",
            tone: "error",
          });
          return;
        }
        showFloatingNotice({
          title: "Sync Successfully",
          tone: "success",
        });
      })
      .catch((error) => {
        const detail = error.response?.data?.detail;
        setSyncRun({
          status: "FAILED",
          last_sync_at: nowIso(),
          sources: [
            { source: "Jira", status: selectedSources.includes("Jira") ? "FAILED" : "IDLE", message: selectedSources.includes("Jira") ? "Sync failed." : "Ready to sync.", error: selectedSources.includes("Jira") ? typeof detail === "string" ? detail : detail?.message || error.message : "" },
            { source: "Outlook Calendar", status: selectedSources.includes("Outlook Calendar") ? "FAILED" : "IDLE", message: selectedSources.includes("Outlook Calendar") ? "Sync failed." : "Ready to sync.", error: selectedSources.includes("Outlook Calendar") ? typeof detail === "string" ? detail : detail?.message || error.message : "" },
          ],
        });
        showFloatingNotice({
          title: "Sync finished with issues",
          message: typeof detail === "string" ? detail : detail?.message || error.message || "Please check the Sync page for details.",
          tone: "error",
        });
      })
      .finally(() => {
        setSyncingSource("");
      });
  };
  const renameScheduleEvent = (items, eventId, title) =>
    items.map((event) => (String(event.eventId) === String(eventId) ? { ...event, title } : event));

  const handleUpdateCalendarEvent = async (eventId, title) => {
    const previousSchedule = calendarSchedule;
    const previousDashboardSchedule = dashboardSchedule;
    setCalendarSchedule((items) => renameScheduleEvent(items, eventId, title));
    if (calendarDate === todayKey()) setDashboardSchedule((items) => renameScheduleEvent(items, eventId, title));
    try {
      const result = await calendarApi.updateEvent(eventId, { title });
      const updatedEvent = result?.event;
      if (updatedEvent) {
        const normalizedEvent = normalizeApiSchedule([updatedEvent])[0];
        setCalendarSchedule((items) => items.map((event) => (String(event.eventId) === String(eventId) ? normalizedEvent : event)));
        if (calendarDate === todayKey()) {
          setDashboardSchedule((items) => items.map((event) => (String(event.eventId) === String(eventId) ? normalizedEvent : event)));
        }
      }
    } catch (error) {
      setCalendarSchedule(previousSchedule);
      if (calendarDate === todayKey()) setDashboardSchedule(previousDashboardSchedule);
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to update calendar event.");
      throw error;
    }
  };

  const handleRemoveCalendarEvent = async (eventId) => {
    const previousSchedule = calendarSchedule;
    const previousDashboardSchedule = dashboardSchedule;
    const previousRemoved = removedCalendarEvents;
    const removedEvent = calendarSchedule.find((event) => String(event.eventId) === String(eventId));
    setCalendarSchedule((items) => items.filter((event) => String(event.eventId) !== String(eventId)));
    if (calendarDate === todayKey()) {
      setDashboardSchedule((items) => items.filter((event) => String(event.eventId) !== String(eventId)));
    }
    if (removedEvent) setRemovedCalendarEvents((items) => [removedEvent, ...items]);
    try {
      await calendarApi.removeEvent(eventId);
    } catch (error) {
      setCalendarSchedule(previousSchedule);
      if (calendarDate === todayKey()) setDashboardSchedule(previousDashboardSchedule);
      setRemovedCalendarEvents(previousRemoved);
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to remove calendar event.");
    }
  };
  const handleRestoreCalendarEvent = async (eventId) => {
    const previousSchedule = calendarSchedule;
    const previousDashboardSchedule = dashboardSchedule;
    const previousRemoved = removedCalendarEvents;
    const restoredEvent = removedCalendarEvents.find((event) => String(event.eventId) === String(eventId));
    if (restoredEvent) {
      setRemovedCalendarEvents((items) => items.filter((event) => String(event.eventId) !== String(eventId)));
      setCalendarSchedule((items) => [...items, restoredEvent].sort((a, b) => String(a.time).localeCompare(String(b.time))));
      if (calendarDate === todayKey()) {
        setDashboardSchedule((items) => [...items, restoredEvent].sort((a, b) => String(a.time).localeCompare(String(b.time))));
      }
    }
    try {
      await calendarApi.restoreEvent(eventId);
    } catch (error) {
      setCalendarSchedule(previousSchedule);
      if (calendarDate === todayKey()) setDashboardSchedule(previousDashboardSchedule);
      setRemovedCalendarEvents(previousRemoved);
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to restore calendar event.");
    }
  };
  const handleFetchCalendarDate = async () => {
    setIsFetchingCalendarDate(true);
    setTaskLoadError("");
    try {
      const result = await calendarApi.fetchEvents({ date: calendarDate });
      const events = Array.isArray(result) ? result : result?.items || [];
      const normalizedEvents = normalizeApiSchedule(events);
      setCalendarSchedule(normalizedEvents);
      if (calendarDate === todayKey()) setDashboardSchedule(normalizedEvents);
      setRemovedCalendarEvents([]);
    } catch (error) {
      const detail = error.response?.data?.detail;
      setTaskLoadError(typeof detail === "string" ? detail : detail?.error || detail?.message || error?.message || "Unable to fetch calendar events.");
    } finally {
      setIsFetchingCalendarDate(false);
    }
  };
  const handleCalendarDateChange = async (nextDate) => {
    setCalendarDate(nextDate);
    try {
      const data = await calendarApi.events({ date: nextDate });
      const events = Array.isArray(data) ? data : data?.items || [];
      const removedEvents = data?.removed_items || data?.removedItems || [];
      const normalizedEvents = events.length ? normalizeApiSchedule(events) : [];
      setCalendarSchedule(normalizedEvents);
      if (nextDate === todayKey()) setDashboardSchedule(normalizedEvents);
      setRemovedCalendarEvents(removedEvents.length ? normalizeApiSchedule(removedEvents) : []);
    } catch {
      setCalendarSchedule([]);
      setRemovedCalendarEvents([]);
    }
  };

  const handleGenerateQuests = async () => {
    const candidateTaskIds = tasks
      .filter((task) => task.workingToday && task.status !== "Done")
      .map((task) => Number(taskBackendKey(task)))
      .filter((taskId) => Number.isFinite(taskId));
    try {
      setIsGeneratingQuests(true);
      const nextRun = await questsApi.generate({
        quest_date: todayKey(),
        candidate_task_ids: candidateTaskIds,
        max_quests: Math.max(1, Math.min(candidateTaskIds.length || 5, 5)),
      });
      setQuestRun(nextRun);
      void loadQuestProgress();
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to generate quests.");
    } finally {
      setIsGeneratingQuests(false);
    }
  };
  const handleClearQuests = () => {
    setQuestRun(null);
  };
  const handleStartFocus = (task, questId) => {
    const startedAt = nowIso();
    const linkedQuest = questId ? getQuestById(questRun, questId) : getOpenQuestForTask(questRun, taskBackendKey(task));
    setLastSavedFocus(null);
    setSavingFocusState(null);
    const nextSession = {
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
    };
    setActiveSession(nextSession);
    if (linkedQuest?.quest_item_id || linkedQuest?.id) {
      questsApi.update(linkedQuest.quest_item_id || linkedQuest.id, { action: "activate" })
        .then((nextRun) => {
          setQuestRun(nextRun);
          setTaskLoadError("");
        })
        .catch((error) => {
          setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to activate quest.");
        });
    }
  };
  const handleStartQuestFocus = (task, questId) => {
    handleStartFocus(task, questId);
  };
  const handleCompleteQuest = async (questId) => {
    const quest = questRun?.quests?.find((item) => item.id === questId);
    const task = tasks.find((item) => taskMatchesBackendKey(item, quest?.taskId));
    if (!quest || !task) return;
    try {
      setCompletingQuestId(questId);
      const nextRun = await questsApi.update(quest.quest_item_id || questId, { action: "complete" });
      const completedAt = nextRun?.quests?.find((item) => item.id === questId || item.quest_item_id === quest.quest_item_id)?.completedAt || nowIso();
      setTasks((items) => items.map((item) => (
        taskMatchesBackendKey(item, quest?.taskId)
          ? normalizeTask({ ...item, status: "Done", completedAt, completed_at: completedAt, workingToday: false })
          : item
      )));
      setQuestRun(nextRun);
      setQuestProgress((current) => {
        const dates = new Set(current?.completedQuestDates || []);
        dates.add(nextRun?.workDate || todayKey());
        return {
          referenceDate: nextRun?.workDate || todayKey(),
          completedQuestDates: [...dates].sort(),
          completedQuestDays: dates.size,
          completedQuestCount: (current?.completedQuestCount || 0) + 1,
          currentStreak: 0,
        };
      });
      void loadTasks();
      void loadQuestProgress(nextRun?.workDate || todayKey());
      const completedQuest = nextRun?.quests?.find((item) => item.id === questId || item.quest_item_id === quest.quest_item_id);
      const nextQuestTitle = getQuestTask(tasks, getNextQuest(nextRun))?.title;
      const reward = completedQuest ? {
        baseXp: completedQuest.baseXp,
        rewardXp: completedQuest.rewardXp,
        focusBonusXp: completedQuest.focusBonusXp,
        rewardMultiplier: completedQuest.rewardMultiplier,
        hasFocusReward: completedQuest.hasFocusReward,
        focusMinutes: completedQuest.focusMinutes,
      } : taskRewardDetailsFromSessions(task, focusSessions, todayKey(), focusXpMultiplier);
      const completedCount = nextRun?.quests?.filter((item) => item.state === "completed").length || 0;
      const totalCount = nextRun?.quests?.length || 0;
      setFloatingNotice({
        title: "Quest complete",
        message: task.title,
        detail: `+${reward.rewardXp || task.xp} XP${reward.hasFocusReward ? ` | ${formatFocusMultiplier(reward.rewardMultiplier)} focus` : ""} | ${completedCount}/${totalCount} cleared${nextQuestTitle ? ` | Next: ${nextQuestTitle}` : ""}`,
        tone: "success",
      });
      setLastSavedFocus((savedFocus) => savedFocus?.quest_id === questId ? null : savedFocus);
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to complete quest.");
    } finally {
      setCompletingQuestId(null);
    }
  };
  const handleSkipQuest = async (questId, skipReason) => {
    try {
      const nextRun = await questsApi.update(questId, { action: "skip", skip_reason: skipReason });
      setQuestRun(nextRun);
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to skip quest.");
    }
  };
  const handleActivateQuest = async (questId) => {
    try {
      const nextRun = await questsApi.update(questId, { action: "activate" });
      setQuestRun(nextRun);
      setTaskLoadError("");
    } catch (error) {
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to activate quest.");
    }
  };
  const handlePauseFocus = () => setActiveSession((session) => {
    if (!session || !session.isRunning) return session;
    return { ...session, accumulatedSeconds: activeFocusSeconds(session), isRunning: false, lastStartedAt: null };
  });
  const handleResumeFocus = () => setActiveSession((session) => {
    if (!session || session.isRunning) return session;
    return { ...session, isRunning: true, lastStartedAt: nowIso() };
  });
  const handleStopFocus = async ({ outcomeType, outcomeNote }) => {
    if (!activeSession) return;
    const endedAt = nowIso();
    const durationSeconds = activeFocusSeconds(activeSession);
    const frozenSession = {
      ...activeSession,
      accumulatedSeconds: durationSeconds,
      isRunning: false,
      lastStartedAt: null,
    };
    const savedSession = {
      focus_session_id: activeSession.focus_session_id,
      task_id: activeSession.task_id,
      task_title: activeSession.task_title,
      task_source: activeSession.task_source,
      quest_id: activeSession.quest_id || null,
      work_date: activeSession.work_date || todayKey(),
      started_at: activeSession.started_at,
      ended_at: endedAt,
      duration_seconds: durationSeconds,
      duration_minutes: Math.max(1, Math.ceil(durationSeconds / 60)),
      outcome_type: outcomeType || "Progress made",
      outcome_note: outcomeNote?.trim() || "",
      created_at: activeSession.created_at || endedAt,
    };
    setActiveSession(null);
    setSavingFocusState(savedSession);
    try {
      const persistedSession = await focusApi.create(savedSession);
      setFocusSessions((items) => [persistedSession, ...items.filter((item) => item.focus_session_id !== persistedSession.focus_session_id)]);
      setLastSavedFocus(persistedSession);
      setSavingFocusState(null);
      if (savedSession.quest_id) {
        await loadQuestRun(savedSession.work_date);
      }
      setTaskLoadError("");
    } catch (error) {
      setSavingFocusState(null);
      setActiveSession(frozenSession);
      setTaskLoadError(error?.response?.data?.detail?.message || error?.message || "Unable to save focus session.");
    }
  };

  useEffect(() => {
    writeStoredJson(FOCUS_SESSIONS_STORAGE_KEY, focusSessions);
  }, [focusSessions]);

  useEffect(() => {
    if (activeSession) writeStoredJson(ACTIVE_FOCUS_STORAGE_KEY, activeSession);
    else removeStoredJson(ACTIVE_FOCUS_STORAGE_KEY);
  }, [activeSession]);

  useEffect(() => {
    writeStoredJson(TASKS_STORAGE_KEY, tasks);
  }, [tasks]);

  useEffect(() => {
    if (location.pathname !== "/") return undefined;

    let cancelled = false;
    const loadTodayCalendarSchedule = () =>
      calendarApi.events({ date: todayKey() })
        .then((data) => {
          if (cancelled) return;
          const events = Array.isArray(data) ? data : data?.items || [];
          const normalizedEvents = normalizeApiSchedule(events);
          setDashboardSchedule(normalizedEvents);
          setCalendarSchedule(normalizedEvents);
        })
        .catch(() => {});

    setDashboardStatus("loading");
    dashboardApi.today({ date: todayKey() })
      .then((data) => {
        if (cancelled) return;
        setDashboardStats(data.stats || null);
        setDashboardStatInsights(data.stat_insights || null);
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
        loadTodayCalendarSchedule();
        setDashboardStatus("fallback");
        setDashboardStatInsights(null);
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;
    syncApi.runs()
      .then((data) => {
        if (!cancelled) setSyncRun(data);
      })
      .catch(() => {});
    calendarApi.events({ date: todayKey() })
      .then((data) => {
        if (cancelled) return;
        const events = Array.isArray(data) ? data : data?.items || [];
        const removedEvents = data?.removed_items || data?.removedItems || [];
        const normalizedEvents = normalizeApiSchedule(events);
        setCalendarSchedule(normalizedEvents);
        setDashboardSchedule(normalizedEvents);
        setRemovedCalendarEvents(removedEvents.length ? normalizeApiSchedule(removedEvents) : []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className={`app-shell ${isDistractionFreeFocus ? "app-shell-focus-active" : ""}`} data-theme={theme} data-testid="app-shell">
      {!isDistractionFreeFocus && <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} levelProgress={levelProgress} streakDays={progressSnapshot.streakDays} />}
      {!isDistractionFreeFocus && <button className={`sidebar-scrim ${sidebarOpen ? "sidebar-scrim-active" : ""}`} aria-label="Close navigation" onClick={() => setSidebarOpen(false)} data-testid="sidebar-scrim-button" aria-hidden={!sidebarOpen} tabIndex={sidebarOpen ? 0 : -1} />}
      <div className={`workspace ${isDistractionFreeFocus ? "workspace-focus-active" : ""}`} data-testid="workspace">
        {!isDistractionFreeFocus && <Topbar currentUser={currentUser} isLoggingOut={isLoggingOut} onLogout={onLogout} onMenuClick={() => setSidebarOpen(true)} theme={theme} onThemeToggle={() => setTheme((current) => current === "light" ? "dark" : "light")} />}
        <LevelUpBanner levelUp={levelUpNotice} />
        <FloatingNotice notice={floatingNotice} onDismiss={() => setFloatingNotice(null)} />
         {!isDistractionFreeFocus && taskLoadError && <p className="form-error" role="alert">{taskLoadError}</p>}
        <Routes>
          <Route path="/tasks" element={<TasksPage tasks={tasks} enrichmentJobs={enrichmentJobs} selectedEnrichmentJob={selectedEnrichmentJob} isLoading={taskStatus === "loading"} onAddTask={handleAddTask} onSelectCodeBase={handleSelectCodeBase} onOpenEnrichmentDetails={handleOpenEnrichmentDetails} onCloseEnrichmentDetails={handleCloseEnrichmentDetails} onRefreshEnrichmentDetails={handleRefreshSelectedEnrichment} onStatusChange={handleStatusChange} onEdit={handleEditTask} onToggleToday={handleToggleToday} onUpdateNotes={handleUpdateNotes} />} />
          <Route path="/" element={<Dashboard tasks={tasks} questRun={questRun} focusSessions={focusSessions} activeSession={activeSession} focusMultiplier={focusXpMultiplier} onStartFocus={handleStartFocus} onPauseFocus={handlePauseFocus} onResumeFocus={handleResumeFocus} onStopFocus={handleStopFocus} onStatusChange={handleStatusChange} onEdit={handleEditTask} onToggleToday={handleToggleToday} onUpdateNotes={handleUpdateNotes} dashboardStats={dashboardStats ? { ...dashboardStats, total_xp: progressSnapshot.totalXp } : { total_xp: progressSnapshot.totalXp }} dashboardStatInsights={dashboardStatInsights} dashboardSchedule={dashboardSchedule} dashboardInsight={dashboardInsight} dashboardStatus={dashboardStatus} isLoading={taskStatus === "loading" || dashboardStatus === "loading"} showProgressGuide={!isProgressGuideDismissed} onDismissProgressGuide={dismissProgressGuide} />} />
          <Route path="/calendar" element={<CalendarPage overview={overview} events={calendarSchedule} removedEvents={removedCalendarEvents} onUpdateEvent={handleUpdateCalendarEvent} onRemoveEvent={handleRemoveCalendarEvent} onRestoreEvent={handleRestoreCalendarEvent} />} />
          <Route path="/focus" element={<FocusPage tasks={tasks} questRun={questRun} focusSessions={focusSessions} activeSession={activeSession} lastSavedFocus={lastSavedFocus} savingFocusState={savingFocusState} focusMultiplier={focusXpMultiplier} onStartFocus={handleStartFocus} onPauseFocus={handlePauseFocus} onResumeFocus={handleResumeFocus} onStopFocus={handleStopFocus} streakDays={progressSnapshot.streakDays} />} />
          <Route path="/focus/analytics" element={<FocusAnalyticsPage tasks={tasks} focusSessions={focusSessions} focusMultiplier={focusXpMultiplier} />} />
          <Route path="/quests" element={<QuestsPage tasks={tasks} questRun={questRun} activeSession={activeSession} isLoading={taskStatus === "loading"} isGenerating={isGeneratingQuests} completingQuestId={completingQuestId} focusMultiplier={focusXpMultiplier} onGenerateQuests={handleGenerateQuests} onClearQuests={handleClearQuests} onStartQuestFocus={handleStartQuestFocus} onCompleteQuest={handleCompleteQuest} onSkipQuest={handleSkipQuest} onActivateQuest={handleActivateQuest} showProgressGuide={!isProgressGuideDismissed} onDismissProgressGuide={dismissProgressGuide} />} />
          <Route path="/insights" element={<InsightsPage tasks={tasks} focusSessions={focusSessions} focusMultiplier={focusXpMultiplier} onRefreshInsights={handleRefreshInsights} />} />
          <Route path="/overview" element={<OverviewPage tasks={tasks} overview={overview} focusSessions={focusSessions} focusMultiplier={focusXpMultiplier} onOverviewChange={setOverview} />} />
          <Route path="/sync" element={<SyncPage syncRun={syncRun} syncingSource={syncingSource} onRunSync={handleRunSync} />} />
          <Route path="/settings" element={<SettingsPage currentUser={currentUser} onUserUpdate={onUserUpdate} />} />
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

  const handleUserUpdate = (updater) => {
    setCurrentUser((current) => {
      const nextUser = typeof updater === "function" ? updater(current) : { ...current, ...updater };
      window.localStorage.setItem(CURRENT_USER_STORAGE_KEY, JSON.stringify(nextUser));
      return nextUser;
    });
  };

  if (!currentUser?.user_id) {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  return <AppShell currentUser={currentUser} isLoggingOut={isLoggingOut} onLogout={handleLogout} onUserUpdate={handleUserUpdate} />;
};

function App() {
  return <BrowserRouter><AuthenticatedApp /></BrowserRouter>;
}

export default App;
