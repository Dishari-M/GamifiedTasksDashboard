import { parseNumber } from "./number";

export const todayKey = () => new Date().toLocaleDateString("en-CA");

export const nowIso = () => new Date().toISOString();

export const isSameDay = (isoValue, day = todayKey()) => {
  if (!isoValue) return false;
  return new Date(isoValue).toLocaleDateString("en-CA") === day;
};

export const startOfWeekKey = (date = new Date()) => {
  const copy = new Date(date);
  const day = copy.getDay() || 7;
  copy.setDate(copy.getDate() - day + 1);
  return copy.toLocaleDateString("en-CA");
};

export const addDaysKey = (dateKey, days) => {
  const date = new Date(`${dateKey}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toLocaleDateString("en-CA");
};

export const isWithinWeek = (isoValue, weekStart = startOfWeekKey()) => {
  if (!isoValue) return false;
  const day = new Date(isoValue).toLocaleDateString("en-CA");
  return day >= weekStart && day <= addDaysKey(weekStart, 6);
};

export const formatMinutes = (minutes) => {
  const value = Math.max(0, parseNumber(minutes, 0));
  const hours = Math.floor(value / 60);
  const mins = value % 60;
  if (!hours) return `${mins}m`;
  if (!mins) return `${hours}h`;
  return `${hours}h ${mins}m`;
};

export const formatDateTime = (isoValue) => {
  if (!isoValue) return "Not completed";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(isoValue));
};

export const formatDate = (isoValue) => {
  if (!isoValue) return "";
  const dateValue = String(isoValue).includes("T") ? isoValue : `${isoValue}T00:00:00`;
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
};

export const formatTime = (isoValue) => {
  if (!isoValue) return "";
  return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date(isoValue));
};

export const formatTimer = (seconds) => {
  const mins = Math.floor(seconds / 60).toString().padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
};
