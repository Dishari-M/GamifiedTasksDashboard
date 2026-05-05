import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "/api/v1";
const BACKEND_BASE_URL = process.env.REACT_APP_BACKEND_BASE_URL || "http://127.0.0.1:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const backendApi = axios.create({
  baseURL: BACKEND_BASE_URL,
  timeout: 0,
  headers: {
    "Content-Type": "application/json",
  },
});

const unwrap = (response) => response.data?.data ?? response.data;

export const tasksApi = {
  list: (params = {}) => api.get("/tasks", { params }).then(unwrap),
  create: (payload) => api.post("/tasks", payload).then(unwrap),
  update: (taskId, payload) => api.patch(`/tasks/${taskId}`, payload).then(unwrap),
  updateNotes: (taskId, payload) => api.put(`/tasks/${taskId}/notes`, payload).then(unwrap),
  updateToday: (taskId, payload) => api.put(`/tasks/${taskId}/today`, payload).then(unwrap),
  complete: (taskId, payload = {}) => api.post(`/tasks/${taskId}/complete`, payload).then(unwrap),
  enrich: (taskId, payload = {}) => api.post(`/tasks/${taskId}/ai/enrich`, payload).then(unwrap),
};

export const questsApi = {
  today: (params = {}) => api.get("/quests/today", { params }).then(unwrap),
  generate: (payload) => api.post("/quests/generate", payload).then(unwrap),
};

export const insightsApi = {
  today: (params = {}) => api.get("/insights/today", { params }).then(unwrap),
  generateToday: (payload) => api.post("/insights/today/generate", payload).then(unwrap),
};

export const standupApi = {
  get: (params = {}) => api.get("/standup-notes", { params }).then(unwrap),
  generate: (payload) => api.post("/standup-notes/generate", payload).then(unwrap),
};

export const overviewApi = {
  daily: (params = {}) => api.get("/overviews/daily", { params }).then(unwrap),
  generateDaily: (payload) => api.post("/overviews/daily/generate", payload).then(unwrap),
  weekly: (params = {}) => api.get("/overviews/weekly", { params }).then(unwrap),
  generateWeekly: (payload) => api.post("/overviews/weekly/generate", payload).then(unwrap),
};

export const calendarApi = {
  events: (params = {}) => api.get("/calendar/events", { params }).then(unwrap),
};

export const syncApi = {
  run: (payload) => api.post("/sync/run", payload).then(unwrap),
  runs: (params = {}) => api.get("/sync/runs", { params }).then(unwrap),
};

export const jiraApi = {
  oneLineDescription: (jiraKey) => backendApi.post("/api/jira/one-line-description", { jira_key: jiraKey }).then(unwrap),
  rca: (jiraKey, additionalContext = "") => backendApi.post("/api/jira/rca", { jira_key: jiraKey, additional_context: additionalContext }).then(unwrap),
  startRcaJob: (jiraKey, additionalContext = "") => backendApi.post("/api/jira/rca/jobs", { jira_key: jiraKey, additional_context: additionalContext }).then(unwrap),
  getRcaJob: (jobId) => backendApi.get(`/api/jira/rca/jobs/${jobId}`).then(unwrap),
  startSsoLogin: (jiraKey) => backendApi.post("/api/jira/sso-login", { jira_key: jiraKey }).then(unwrap),
};
