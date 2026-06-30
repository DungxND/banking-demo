const API = ""; // same origin via nginx proxy

export function setSession(session) {
  localStorage.setItem("session", session);
}

export function getSession() {
  return localStorage.getItem("session");
}

export function clearSession() {
  localStorage.removeItem("session");
}

/**
 * Normalise the `detail` field from an API error response into a plain string.
 *
 * FastAPI can return:
 *   - a string  → used as-is
 *   - an object → JSON.stringify fallback
 *   - an array of Pydantic validation errors [{loc, msg, type}]
 *     → flatten to "field: message; field: message"
 */
function extractDetail(detail) {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const loc = Array.isArray(e.loc)
          ? e.loc.filter((p) => p !== "body").join(".")
          : "";
        return loc ? `${loc}: ${e.msg}` : e.msg;
      })
      .join("; ");
  }
  if (typeof detail === "object" && detail.msg) return detail.msg;
  return JSON.stringify(detail);
}

async function req(path, { method = "GET", body } = {}) {
  const session = getSession();

  let res;
  try {
    res = await fetch(API + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(session ? { "X-Session": session } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Network error — please check your connection");
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const msg = extractDetail(data.detail) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

export const api = {
  register: (username, password) =>
    req("/api/auth/register", { method: "POST", body: { username, password } }),

  login: (username, password) =>
    req("/api/auth/login", { method: "POST", body: { username, password } }),

  logout: () =>
    req("/api/auth/logout", { method: "POST" }),

  me: () => req("/api/account/me"),

  transfer: (to_username, amount) =>
    req("/api/transfer/transfer", {
      method: "POST",
      body: { to_username, amount: Number(amount) },
    }),

  notifications: () => req("/api/notifications/notifications"),
};
