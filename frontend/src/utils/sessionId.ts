const SESSION_KEY = "session_id";

function generateSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `sess_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

export function getSessionId() {
  if (typeof sessionStorage === "undefined") return generateSessionId();
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const generated = generateSessionId();
  sessionStorage.setItem(SESSION_KEY, generated);
  return generated;
}
