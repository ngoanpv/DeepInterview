/**
 * Browser-local history of interview sessions this device has started/viewed.
 * Session ids are unguessable capabilities with no server-side list endpoint,
 * so the only way back to a past interview is to remember its id locally.
 */
export type RecentSession = { id: string; label?: string; at: number };

const KEY = "deepinterview.recentSessions";
const MAX = 20;

export function getRecentSessions(): RecentSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(raw)
      ? raw.filter((s) => s && typeof s.id === "string")
      : [];
  } catch {
    return [];
  }
}

export function rememberSession(id: string, label?: string): void {
  if (typeof window === "undefined" || !id) return;
  try {
    const prev = getRecentSessions().find((s) => s.id === id);
    const rest = getRecentSessions().filter((s) => s.id !== id);
    const next = [
      { id, label: label || prev?.label, at: Date.now() },
      ...rest,
    ].slice(0, MAX);
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage disabled / full — history is best-effort
  }
}
