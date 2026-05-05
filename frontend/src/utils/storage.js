export const readStoredJson = (key, fallback) => {
  if (typeof window === "undefined") return fallback;
  try {
    const stored = window.localStorage.getItem(key);
    return stored ? JSON.parse(stored) : fallback;
  } catch {
    return fallback;
  }
};

export const writeStoredJson = (key, value) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
};

export const removeStoredJson = (key) => {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
};
