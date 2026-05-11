import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
const BACKEND_BASE_URL = process.env.REACT_APP_BACKEND_BASE_URL || "http://127.0.0.1:8000";
const LOCAL_CODEX_BASE_URL = process.env.REACT_APP_LOCAL_CODEX_BASE_URL || "http://127.0.0.1:8000";
export const CURRENT_USER_STORAGE_KEY = "devquest.currentUser";

const readStoredUser = () => {
  try {
    return JSON.parse(window.localStorage.getItem(CURRENT_USER_STORAGE_KEY) || "null");
  } catch {
    return null;
  }
};
const PHASE8_API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  const user = readStoredUser();
  if (user?.user_id) {
    config.headers["X-DevQuest-User-Id"] = user.user_id;
  }
  return config;
});

export const backendApi = axios.create({
  baseURL: BACKEND_BASE_URL,
  timeout: 0,
  headers: {
    "Content-Type": "application/json",
  },
});

const localCodexApi = axios.create({
  baseURL: LOCAL_CODEX_BASE_URL,
  timeout: 0,
  headers: {
    "Content-Type": "application/json",
  },
});

const attachUserHeader = (config) => {
  const user = readStoredUser();
  if (user?.user_id) {
    config.headers["X-DevQuest-User-Id"] = user.user_id;
  }
  return config;
};

backendApi.interceptors.request.use(attachUserHeader);
localCodexApi.interceptors.request.use(attachUserHeader);

const phase8Api = axios.create({
  baseURL: PHASE8_API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

phase8Api.interceptors.request.use((config) => {
  const user = readStoredUser();
  if (user?.user_id) {
    config.headers["X-DevQuest-User-Id"] = user.user_id;
  }
  return config;
});

const unwrap = (response) => response.data?.data ?? response.data;
const inFlightGetRequests = new Map();
const ENRICHMENT_POLL_TIMEOUT_MS = 10000;

const getKey = (scope, params = {}) => {
  const entries = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .sort(([left], [right]) => left.localeCompare(right));
  const query = new URLSearchParams(entries).toString();
  return query ? `${scope}:${query}` : scope;
};

const dedupeGet = (key, requestFactory) => {
  if (inFlightGetRequests.has(key)) {
    return inFlightGetRequests.get(key);
  }
  let request;
  request = requestFactory().finally(() => {
    if (inFlightGetRequests.get(key) === request) {
      inFlightGetRequests.delete(key);
    }
  });
  inFlightGetRequests.set(key, request);
  return request;
};

const invalidateReadRequests = () => {
  inFlightGetRequests.clear();
};

const writeRequest = (requestFactory) => requestFactory().then((data) => {
  invalidateReadRequests();
  return data;
});

export const authApi = {
  register: (payload) => writeRequest(() => api.post("/auth/register", payload).then(unwrap)),
  login: (payload) => api.post("/auth/login", payload).then(unwrap),
  logout: () => writeRequest(() => api.post("/auth/logout", {}).then(unwrap)),
  getProfile: (identifier) => dedupeGet(
    getKey("users:profile", { identifier }),
    () => api.get("/users/profile", { params: { identifier } }).then(unwrap),
  ),
};

export const settingsApi = {
  get: () => dedupeGet("users:settings", () => api.get("/users/settings").then(unwrap)),
  save: (payload) => writeRequest(() => api.put("/users/settings", payload).then(unwrap)),
};

export const tasksApi = {
  list: (params = {}) => dedupeGet(
    getKey("tasks:list", params),
    () => api.get("/tasks", { params }).then(unwrap),
  ),
  create: (payload) => writeRequest(() => api.post("/tasks", payload).then(unwrap)),
  update: (taskId, payload) => writeRequest(() => api.patch(`/tasks/${taskId}`, payload).then(unwrap)),
  remove: (taskId) => writeRequest(() => api.delete(`/tasks/${taskId}`).then(unwrap)),
  updateNotes: (taskId, payload) => writeRequest(() => api.put(`/tasks/${taskId}/notes`, payload).then(unwrap)),
  updateStatus: (taskId, payload) => writeRequest(() => api.patch(`/tasks/${taskId}/status`, payload).then(unwrap)),
  updateToday: (taskId, payload) => writeRequest(() => api.put(`/tasks/${taskId}/today`, payload).then(unwrap)),
  complete: (taskId, payload = {}) => writeRequest(() => api.post(`/tasks/${taskId}/complete`, payload).then(unwrap)),
  enrich: (taskId, payload = {}) => writeRequest(() => api.post(`/tasks/${taskId}/ai/enrich`, payload).then(unwrap)),
};

export const taskEnrichmentApi = {
  start: (payload) => writeRequest(() => api.post("/task-enrichments", payload).then(unwrap)),
  list: (params = {}) => dedupeGet(
    getKey("task-enrichments:list", params),
    () => api.get("/task-enrichments", { params, timeout: ENRICHMENT_POLL_TIMEOUT_MS }).then(unwrap),
  ),
  get: (jobId) => dedupeGet(
    `task-enrichments:get:${jobId}`,
    () => api.get(`/task-enrichments/${jobId}`, { timeout: ENRICHMENT_POLL_TIMEOUT_MS }).then(unwrap),
  ),
};

export const questsApi = {
  today: (params = {}) => dedupeGet(
    getKey("quests:today", params),
    () => api.get("/quests/today", { params }).then(unwrap),
  ),
  progress: (params = {}) => dedupeGet(
    getKey("quests:progress", params),
    () => api.get("/quests/progress", { params }).then(unwrap),
  ),
  generate: (payload) => writeRequest(() => api.post("/quests/generate", payload).then(unwrap)),
  update: (questItemId, payload) => writeRequest(() => api.patch(`/quests/${questItemId}`, payload).then(unwrap)),
};

export const focusApi = {
  list: (params = {}) => dedupeGet(
    getKey("focus-sessions:list", params),
    () => api.get("/focus-sessions", { params }).then(unwrap),
  ),
  create: (payload) => writeRequest(() => api.post("/focus-sessions", payload).then(unwrap)),
};

export const insightsApi = {
  today: (params = {}) => dedupeGet(
    getKey("insights:today", params),
    () => api.get("/insights/today", { params }).then(unwrap),
  ),
  generateToday: (payload) => {
    inFlightGetRequests.delete(getKey("insights:today", { date: payload.date }));
    return writeRequest(() => api.post("/insights/today/generate", payload).then(unwrap));
  },
};

export const standupApi = {
  get: (params = {}) => dedupeGet(
    getKey("standup-notes:get", params),
    () => api.get("/standup-notes", { params }).then(unwrap),
  ),
  generate: (payload) => writeRequest(() => api.post("/standup-notes/generate", payload).then(unwrap)),
};

export const overviewApi = {
  daily: (params = {}) => dedupeGet(
    `overviews:daily:${params.date || ""}`,
    () => phase8Api.get("/overviews/daily", { params }).then(unwrap),
  ),
  saveDaily: (payload) => writeRequest(() => phase8Api.put("/overviews/daily", payload).then(unwrap)),
  generateDaily: (payload) => {
    inFlightGetRequests.delete(`overviews:daily:${payload.date || ""}`);
    return writeRequest(() => phase8Api.post("/overviews/daily/generate", payload).then(unwrap));
  },
  weekly: (params = {}) => dedupeGet(
    `overviews:weekly:${params.week_start || ""}`,
    () => phase8Api.get("/overviews/weekly", { params }).then(unwrap),
  ),
  generateWeekly: (payload) => {
    inFlightGetRequests.delete(`overviews:weekly:${payload.week_start || ""}`);
    return writeRequest(() => phase8Api.post("/overviews/weekly/generate", payload).then(unwrap));
  },
};

export const calendarApi = {
  events: (params = {}) => dedupeGet(
    getKey("calendar:events", params),
    () => api.get("/calendar/events", { params }).then(unwrap),
  ),
  fetchEvents: (payload = {}) => writeRequest(() => api.post("/calendar/events/fetch", payload).then(unwrap)),
  updateEvent: (eventId, payload) => writeRequest(() => api.patch(`/calendar/events/${eventId}`, payload).then(unwrap)),
  removeEvent: (eventId) => writeRequest(() => api.delete(`/calendar/events/${eventId}`).then(unwrap)),
  restoreEvent: (eventId) => writeRequest(() => api.post(`/calendar/events/${eventId}/restore`).then(unwrap)),
};

export const dashboardApi = {
  today: (params = {}) => dedupeGet(
    getKey("dashboard:today", params),
    () => phase8Api.get("/dashboard/today", { params }).then(unwrap),
  ),
};

export const capacityApi = {
  get: (params = {}) => dedupeGet(
    getKey("capacity", params),
    () => phase8Api.get("/capacity", { params }).then(unwrap),
  ),
};

export const syncApi = {
  run: (payload) => writeRequest(() => api.post("/sync/run", payload).then(unwrap)),
  runs: (params = {}) => dedupeGet(
    getKey("sync:runs", params),
    () => api.get("/sync/runs", { params }).then(unwrap),
  ),
};

export const jiraApi = {
  oneLineDescription: (jiraKey) => localCodexApi.post("/api/jira/one-line-description", { jira_key: jiraKey }).then(unwrap),
  taskFields: (jiraKey) => localCodexApi.post("/api/jira/task-fields", { jira_key: jiraKey }).then(unwrap),
  rca: (jiraKey, additionalContext = "", priority = "", codeBasePath = "", memoryBankPath = "", skillPath = "") => localCodexApi.post("/api/jira/rca", { jira_key: jiraKey, additional_context: additionalContext, priority, code_base_path: codeBasePath, memory_bank_path: memoryBankPath, skill_path: skillPath }).then(unwrap),
  startRcaJob: (jiraKey, additionalContext = "", priority = "", codeBasePath = "", memoryBankPath = "", skillPath = "") => localCodexApi.post("/api/jira/rca/jobs", { jira_key: jiraKey, additional_context: additionalContext, priority, code_base_path: codeBasePath, memory_bank_path: memoryBankPath, skill_path: skillPath }).then(unwrap),
  getRcaJob: (jobId) => localCodexApi.get(`/api/jira/rca/jobs/${jobId}`).then(unwrap),
  cancelRcaJob: (jobId) => localCodexApi.post(`/api/jira/rca/jobs/${jobId}/cancel`).then(unwrap),
  selectRcaWorkspace: (initialPath = "", title = "") => localCodexApi.post("/api/jira/rca/workspace/select", { initial_path: initialPath, title }).then(unwrap),
  startSsoLogin: (jiraKey) => localCodexApi.post("/api/jira/sso-login", { jira_key: jiraKey }).then(unwrap),
};
